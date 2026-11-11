import hashlib
import json
from pathlib import Path

from bs4 import BeautifulSoup
import httpx
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from .config import Settings
from .catalog import Catalog
from .models import Citation, DocumentRecord
from .vector_store import VectorStore


class OllamaEmbeddings:
    def __init__(self, settings: Settings):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_embed_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings: list[list[float]] = []
        for offset in range(0, len(texts), 24):
            batch = texts[offset:offset + 24]
            try:
                response = httpx.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model, "input": batch},
                    timeout=180,
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise RuntimeError(
                    f"Ollama embedding unavailable. Start Ollama and pull {self.model}: {exc}"
                ) from exc
            embeddings.extend(response.json().get("embeddings", []))
        if len(embeddings) != len(texts):
            raise RuntimeError("Embedding model returned an unexpected number of vectors")
        return embeddings


def load_manifest(path: Path) -> list[DocumentRecord]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Document manifest must be a JSON array")
    records = [DocumentRecord.model_validate(item) for item in data]
    if len({record.id for record in records}) != len(records):
        raise ValueError("Duplicate document ID")
    return records


def _read_sections(
    path: Path,
    page_ranges: list[tuple[int, int]] | None = None,
    content_selector: str | None = None,
) -> list[tuple[str, str]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        if page_ranges:
            page_numbers = sorted({number for start, end in page_ranges for number in range(start, end + 1)})
            if page_numbers[-1] > len(reader.pages):
                raise ValueError(f"Page range exceeds the {len(reader.pages)} pages in {path.name}")
        else:
            page_numbers = range(1, len(reader.pages) + 1)
        return [
            (f"第 {page_number} 页", page.extract_text() or "")
            for page_number in page_numbers
            for page in [reader.pages[page_number - 1]]
        ]
    if suffix in {".html", ".htm"}:
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        for element in soup.select("script, style, nav, footer, header, aside"):
            element.decompose()
        content = (
            soup.select_one(content_selector) if content_selector else None
        ) or soup.select_one("article") or soup.select_one("main") or soup.body or soup
        sections: list[tuple[str, str]] = []
        current_heading = "正文"
        paragraphs: list[str] = []
        for element in content.find_all(["h1", "h2", "h3", "h4", "p", "li"], recursive=True):
            text = element.get_text(" ", strip=True)
            if not text:
                continue
            if element.name.startswith("h"):
                if paragraphs:
                    sections.append((current_heading, "\n".join(paragraphs)))
                    paragraphs = []
                current_heading = text
            elif not element.find_parent("li") or element.name == "li":
                paragraphs.append(text)
        if paragraphs:
            sections.append((current_heading, "\n".join(paragraphs)))
        return sections
    if suffix in {".md", ".txt"}:
        return [("正文", path.read_text(encoding="utf-8"))]
    raise ValueError(f"Unsupported document type: {suffix}")


class KnowledgeBase:
    MIN_SIMILARITY = 0.58
    SERVICE_PAGE_MIN_SIMILARITY = 0.54
    UNSUPPORTED_METRICS = (
        "满意度", "投诉率", "故障率", "实际成交均价", "真实道路油耗", "真实道路平均油耗", "售后体验"
    )

    def __init__(self, settings: Settings, embeddings: OllamaEmbeddings | None = None):
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        self.settings = settings
        self.embeddings = embeddings or OllamaEmbeddings(settings)
        self.store = VectorStore(settings.storage_dir / "vectors.sqlite3")
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=350, chunk_overlap=60)
        self.records = load_manifest(settings.data_dir / "documents.json")
        self.records.extend(load_manifest(settings.storage_dir / "user_documents.json"))
        self.catalog = Catalog.from_file(settings.data_dir / "catalog.json")

    def linked_vehicle_ids(self, record: DocumentRecord) -> list[str]:
        if record.applies_to_make:
            return [variant.id for variant in self.catalog.list() if variant.make == record.applies_to_make]
        return record.vehicle_ids

    def count(self) -> int:
        return self.store.count()

    def page_text(self, document_id: str, page_number: int) -> tuple[DocumentRecord, str]:
        record = next((item for item in self.records if item.id == document_id), None)
        if record is None:
            raise ValueError(f"Unknown document: {document_id}")
        if record.page_ranges and not any(start <= page_number <= end for start, end in record.page_ranges):
            raise ValueError("Page is outside the indexed document ranges")
        raw_root = (self.settings.data_dir / "raw").resolve()
        path = (raw_root / record.path).resolve()
        if not path.is_relative_to(raw_root):
            raise ValueError("Document path escapes data/raw")
        sections = _read_sections(path, [(page_number, page_number)])
        if not sections:
            raise ValueError("Document page is empty")
        return record, sections[0][1]

    def ingest(self, records: list[DocumentRecord]) -> dict[str, int]:
        counts: dict[str, int] = {}
        raw_root = (self.settings.data_dir / "raw").resolve()
        for record in records:
            path = (raw_root / record.path).resolve()
            if not path.is_relative_to(raw_root):
                raise ValueError(f"Document path escapes data/raw: {record.path}")
            if not path.is_file():
                raise FileNotFoundError(path)
            chunks: list[str] = []
            metadatas: list[dict[str, str]] = []
            ids: list[str] = []
            for location, text in _read_sections(path, record.page_ranges, record.content_selector):
                for part in self.splitter.split_text(text):
                    if len(part.strip()) < 30:
                        continue
                    digest = hashlib.sha256(
                        f"{record.id}\n{location}\n{part}".encode("utf-8")
                    ).hexdigest()[:20]
                    ids.append(f"{record.id}-{digest}")
                    chunks.append(part)
                    metadatas.append({
                        "document_id": record.id,
                        "title": record.title,
                        "source_url": str(record.source_url),
                        "source_type": record.source_type,
                        "published_on": record.published_on.isoformat() if record.published_on else "",
                        "market": record.market,
                        "vehicle_ids": json.dumps(self.linked_vehicle_ids(record), ensure_ascii=False),
                        "location": location,
                    })
            if chunks:
                vectors = self.embeddings.embed(chunks)
            else:
                vectors = []
            self.store.replace_document(record.id, ids, chunks, metadatas, vectors)
            counts[record.id] = len(chunks)
        return counts

    def search(self, question: str, vehicle_ids: list[str], limit: int = 5) -> list[Citation]:
        if any(term in question for term in self.UNSUPPORTED_METRICS):
            return []
        total = self.store.count()
        if not total:
            return []
        eligible_document_ids = [
            record.id for record in self.records
            if not vehicle_ids or set(vehicle_ids).intersection(self.linked_vehicle_ids(record))
        ]
        if vehicle_ids and not eligible_document_ids:
            return []
        query_vector = self.embeddings.embed([question])[0]
        candidates = self.store.search(query_vector, eligible_document_ids if vehicle_ids else None, limit * 10)
        remaining = [
            (excerpt, metadata, score) for excerpt, metadata, score in candidates
            if score >= (
                self.SERVICE_PAGE_MIN_SIMILARITY
                if metadata["document_id"] == "byd-after-sales-process"
                else self.MIN_SIMILARITY
            )
        ]
        results: list[tuple[str, dict[str, str], float]] = []
        location_counts: dict[tuple[str, str], int] = {}
        while remaining and len(results) < limit:
            best = max(
                remaining,
                key=lambda item: item[2] - 0.05 * location_counts.get(
                    (item[1]["document_id"], item[1]["location"]), 0
                ),
            )
            remaining.remove(best)
            results.append(best)
            location = (best[1]["document_id"], best[1]["location"])
            location_counts[location] = location_counts.get(location, 0) + 1
        citations: list[Citation] = []
        for excerpt, metadata, score in results:
            linked_vehicles = json.loads(metadata["vehicle_ids"])
            if vehicle_ids and not set(vehicle_ids).intersection(linked_vehicles):
                continue
            citations.append(Citation(
                id=f"S{len(citations) + 1}",
                document_id=metadata["document_id"],
                title=metadata["title"],
                url=metadata["source_url"],
                source_type=metadata["source_type"],
                published_on=metadata["published_on"] or None,
                location=metadata["location"],
                excerpt=excerpt,
            ))
            if len(citations) == limit:
                break
        return citations

