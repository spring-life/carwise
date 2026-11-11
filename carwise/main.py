from contextlib import asynccontextmanager
import json
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .catalog import Catalog
from .config import Settings
from .extraction import FactExtractor
from .knowledge import KnowledgeBase
from .llm import ChatModel
from .models import AskRequest, AskResponse, Citation, CompareRequest, DocumentRecord, ExtractRequest, ExtractResponse, VehicleVariant


settings = Settings()
upload_lock = Lock()
MAX_UPLOAD_SIZE = 50 * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".html", ".htm", ".md", ".txt"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.catalog = Catalog.from_file(settings.data_dir / "catalog.json")
    app.state.knowledge = KnowledgeBase(settings)
    app.state.chat = ChatModel(settings)
    app.state.extractor = FactExtractor(settings)
    yield


app = FastAPI(title="购车资料助手", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/health")
def health() -> dict[str, int | str]:
    return {
        "status": "ok",
        "vehicles": len(app.state.catalog.list()),
        "indexed_chunks": app.state.knowledge.count(),
    }


@app.get("/api/vehicles", response_model=list[VehicleVariant])
def vehicles() -> list[VehicleVariant]:
    return app.state.catalog.list()


@app.get("/api/documents")
def documents() -> list[dict]:
    return [
        {
            **record.model_dump(mode="json"),
            "linked_vehicle_ids": app.state.knowledge.linked_vehicle_ids(record),
            "indexed_chunks": app.state.knowledge.store.count_document(record.id),
        }
        for record in app.state.knowledge.records
    ]


@app.post("/api/documents", status_code=201)
def add_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    source_url: str = Form(...),
    source_type: str = Form(...),
    vehicle_ids: str = Form(...),
    published_on: str = Form(""),
) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="仅支持 PDF、HTML、Markdown 和 TXT 文件")
    try:
        ids = json.loads(vehicle_ids)
        if not isinstance(ids, list) or not ids or any(not isinstance(item, str) for item in ids):
            raise ValueError("车型关联必须是非空 ID 列表")
        selected = [app.state.catalog.get(vehicle_id) for vehicle_id in ids]
        if len({item.market for item in selected}) != 1:
            raise ValueError("资料不能跨市场关联车型")
        document_id = f"user-{uuid4().hex[:16]}"
        record = DocumentRecord.model_validate({
            "id": document_id,
            "title": title.strip(),
            "source_url": source_url.strip(),
            "source_type": source_type,
            "published_on": published_on or None,
            "market": selected[0].market,
            "vehicle_ids": ids,
            "path": f"{document_id}{suffix}",
        })
        if not record.title:
            raise ValueError("资料标题不能为空")
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    raw_path = settings.data_dir / "raw" / record.path
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with upload_lock:
        try:
            with raw_path.open("wb") as output:
                while chunk := file.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD_SIZE:
                        raise ValueError("文件不能超过 50 MB")
                    output.write(chunk)
            if not size:
                raise ValueError("文件为空")
            if suffix == ".pdf" and raw_path.open("rb").read(5) != b"%PDF-":
                raise ValueError("文件不是有效 PDF")
            counts = app.state.knowledge.ingest([record])
            if not counts[document_id]:
                raise ValueError("文件中没有可索引的文字")
            manifest_path = settings.storage_dir / "user_documents.json"
            saved = [item.model_dump(mode="json") for item in app.state.knowledge.records if item.id.startswith("user-")]
            saved.append(record.model_dump(mode="json"))
            temporary = manifest_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temporary.replace(manifest_path)
            app.state.knowledge.records.append(record)
        except Exception as exc:
            raw_path.unlink(missing_ok=True)
            if isinstance(exc, (ValueError, RuntimeError)):
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            raise
    return {"id": document_id, "indexed_chunks": counts[document_id]}


@app.post("/api/compare", response_model=list[VehicleVariant])
def compare(request: CompareRequest) -> list[VehicleVariant]:
    try:
        return app.state.catalog.compare(request.vehicle_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/search", response_model=list[Citation])
def search(request: AskRequest) -> list[Citation]:
    try:
        scope = app.state.catalog.scope_for_question(request.question, request.vehicle_ids)
        if not scope:
            return []
        return app.state.knowledge.search(request.question, scope)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    try:
        scope = app.state.catalog.scope_for_question(request.question, request.vehicle_ids)
        citations = app.state.knowledge.search(request.question, scope) if scope else []
        return app.state.chat.answer(request.question, citations)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/extract", response_model=ExtractResponse)
def extract(request: ExtractRequest) -> ExtractResponse:
    try:
        record, text = app.state.knowledge.page_text(request.document_id, request.page_number)
        return app.state.extractor.extract(record, request.page_number, text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

