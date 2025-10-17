from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile

from stream_summarization.entrypoints.schemas.documents import (
    LoadDocumentResponse,
    ReportTypesResponse,
)
from stream_summarization.services.data.unit_of_work import DocumentTemplateUoW
from stream_summarization.services.handlers.documents import extract_text, get_report_types

router = APIRouter()


@router.post("/load_documents", response_model=LoadDocumentResponse, status_code=200)
async def load_document(
    documents: List[UploadFile] = File(...),
) -> LoadDocumentResponse:

    contents: List[str] = []

    for document in documents:
        filename = document.filename or "document.txt"
        suffix = Path(filename).suffix or ".txt"
        try:
            content = await document.read()
            text = extract_text(content, suffix)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=f"{error}") from error
        except RuntimeError as error:
            raise HTTPException(status_code=500, detail=f"{error}") from error
        contents.append(text)

    return LoadDocumentResponse(contents=contents)


@router.get("/report_types", response_model=ReportTypesResponse, status_code=200)
async def report_types() -> ReportTypesResponse:
    report_types = get_report_types(DocumentTemplateUoW())
    return ReportTypesResponse(report_types=report_types)
