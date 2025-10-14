from pathlib import Path
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from auto_summarization.entrypoints.schemas.analysis import (
    AnalyzeTypesResponse,
    LoadDocumentResponse,
    LoadedDocumentInfo,
)
from auto_summarization.services.data.unit_of_work import AnalysisTemplateUoW
from auto_summarization.services.handlers.analysis import extract_text, get_analyze_types

router = APIRouter()


@router.post("/load_documents", response_model=LoadDocumentResponse, status_code=200)
async def load_document(
    documents: List[UploadFile] = File(...),
    document_ids: List[str] = Form(...),
) -> LoadDocumentResponse:
    if len(documents) != len(document_ids):
        raise HTTPException(status_code=400, detail="Каждый документ должен иметь идентификатор")

    results: List[LoadedDocumentInfo] = []

    for document, doc_id in zip(documents, document_ids):
        filename = document.filename or "document.txt"
        suffix = Path(filename).suffix or ".txt"
        try:
            content = await document.read()
            text = extract_text(content, suffix)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=f"{doc_id}: {error}") from error
        except RuntimeError as error:
            raise HTTPException(status_code=500, detail=f"{doc_id}: {error}") from error
        results.append(LoadedDocumentInfo(document_id=doc_id, text=text))

    return LoadDocumentResponse(result=results)


@router.get("/analyze_types", response_model=AnalyzeTypesResponse, status_code=200)
async def analyze_types() -> AnalyzeTypesResponse:
    categories, choices = get_analyze_types(AnalysisTemplateUoW())
    return AnalyzeTypesResponse(categories=categories, choices=choices)


