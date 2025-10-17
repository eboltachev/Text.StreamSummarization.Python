from pathlib import Path
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from auto_summarization.entrypoints.schemas.analysis import AnalyzeTypesResponse, LoadDocumentResponse
from auto_summarization.services.data.unit_of_work import AnalysisTemplateUoW
from auto_summarization.services.handlers.analysis import extract_text, get_analyze_types

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


@router.get("/analyze_types", response_model=AnalyzeTypesResponse, status_code=200)
async def analyze_types() -> AnalyzeTypesResponse:
    report_types = get_analyze_types(AnalysisTemplateUoW())
    return AnalyzeTypesResponse(report_types=report_types)
