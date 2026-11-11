"""Compare chunk sizes on the development questions using temporary indexes."""

import gc
import json
import tempfile
from pathlib import Path
from time import perf_counter
from time import sleep

from langchain_text_splitters import RecursiveCharacterTextSplitter

from carwise.config import Settings
from carwise.knowledge import KnowledgeBase, OllamaEmbeddings


SIZES = (200, 350, 500, 800)


class RetryingEmbeddings(OllamaEmbeddings):
    def embed(self, texts: list[str]) -> list[list[float]]:
        for attempt in range(3):
            try:
                return super().embed(texts)
            except RuntimeError:
                if attempt == 2:
                    raise
                sleep(2 * (attempt + 1))
        raise AssertionError("unreachable")


def main() -> None:
    settings = Settings()
    questions = json.loads((settings.project_root / "evaluation" / "questions.json").read_text(encoding="utf-8"))
    page_questions = [item for item in questions if item["expected_pages"]]
    runs = []
    with tempfile.TemporaryDirectory(prefix="carwise-chunk-ablation-") as temporary:
        for size in SIZES:
            overlap = round(size * 0.17)
            isolated_settings = Settings(storage_dir=Path(temporary) / str(size))
            kb = KnowledgeBase(isolated_settings, embeddings=RetryingEmbeddings(isolated_settings))
            try:
                kb.splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)
                kb.ingest(kb.records)
                elapsed = []
                hits = 0
                for item in questions:
                    started = perf_counter()
                    citations = kb.search(item["question"], [item["vehicle_id"]], limit=3)
                    elapsed.append((perf_counter() - started) * 1000)
                    pages = {
                        int(citation.location.split()[1])
                        for citation in citations
                        if citation.location and citation.location.startswith("第 ")
                    }
                    if item["expected_pages"] and pages.intersection(item["expected_pages"]):
                        hits += 1
                run = {
                    "chunk_size": size,
                    "chunk_overlap": overlap,
                    "chunks": kb.count(),
                    "top3_page_hits": hits,
                    "top3_page_total": len(page_questions),
                    "average_retrieval_ms": round(sum(elapsed) / len(elapsed), 2),
                }
                runs.append(run)
                print(json.dumps(run, ensure_ascii=False), flush=True)
            finally:
                del kb
                gc.collect()
    report = {
        "dataset": "evaluation/questions.json",
        "question_count": len(questions),
        "page_question_count": len(page_questions),
        "overlap_ratio": 0.17,
        "retrieval_limit": 3,
        "embedding_model": settings.ollama_embed_model,
        "runs": runs,
    }
    output = settings.project_root / "evaluation" / "chunk-size-ablation.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
