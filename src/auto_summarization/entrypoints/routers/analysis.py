from pathlib import Path
from typing import List

try:  # pragma: no cover - prefer the real FastAPI when available
    from fastapi import APIRouter, File, Form, HTTPException, UploadFile
except ModuleNotFoundError:  # pragma: no cover - lightweight fallback for tests
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class UploadFile:  # type: ignore[override]
        def __init__(self, filename: str, content: bytes | str) -> None:
            self.filename = filename
            if isinstance(content, str):
                content = content.encode("utf-8")
            self._content = bytes(content)

        async def read(self) -> bytes:
            return self._content

    class APIRouter:  # pragma: no cover - decorator no-op stub
        def post(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def get(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    def Form(default):  # type: ignore
        return default

    def File(default):  # type: ignore
        return default

from auto_summarization.entrypoints.schemas.analysis import (
    AnalyzeCategory,
    AnalyzeTypesResponse,
    LoadDocumentResponse,
    LoadedDocumentInfo,
)
from auto_summarization.services.data.unit_of_work import AnalysisTemplateUoW
from auto_summarization.services.handlers.analysis import extract_text, get_analyze_types

router = APIRouter()


@router.post("/load_documents", response_model=LoadDocumentResponse, status_code=200)
async def load_document(
    input_ids: List[str] = Form(...),
    documents: List[UploadFile] = File(...),
) -> LoadDocumentResponse:
    if len(input_ids) != len(documents):
        raise HTTPException(status_code=400, detail="Количество идентификаторов и файлов должно совпадать")

    results: List[LoadedDocumentInfo] = []
    for input_id, document in zip(input_ids, documents):
        filename = document.filename or f"document_{input_id}.txt"
        suffix = Path(filename).suffix or ".txt"
        try:
            content = await document.read()
            text = extract_text(content, suffix)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
        except RuntimeError as error:
            raise HTTPException(status_code=500, detail=str(error))
        results.append(LoadedDocumentInfo(input_id=str(input_id), text=text))

    return LoadDocumentResponse(result=results)


@router.get("/analyze_types", response_model=AnalyzeTypesResponse, status_code=200)
async def analyze_types() -> AnalyzeTypesResponse:
    templates = get_analyze_types(AnalysisTemplateUoW())
    categories = [
        AnalyzeCategory(
            index=item["index"],
            category=item["category"],
            prompt=item["prompt"],
            model_type=item.get("model_type"),
        )
        for item in templates
    ]
    return AnalyzeTypesResponse(categories=categories)


