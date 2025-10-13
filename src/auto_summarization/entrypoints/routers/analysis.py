from pathlib import Path

from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from auto_summarization.entrypoints.schemas.analysis import AnalyzeTypesResponse, LoadDocumentResponse, LoadedDocumentInfo
from auto_summarization.services.data.unit_of_work import AnalysisTemplateUoW
from auto_summarization.services.handlers.analysis import extract_text, get_analyze_types

router = APIRouter()


@router.post("/load_documents", response_model=LoadDocumentResponse, status_code=200)
async def load_document(
    document: UploadFile = File(...)
) -> LoadDocumentResponse:
    filename = document.filename or "document.txt"
    suffix = Path(filename).suffix or ".txt"
    try:
        content = await document.read()
        result = extract_text(content, suffix)
        return LoadDocumentResponse(result=LoadedDocumentInfo(**result))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error))


@router.get("/analyze_types", response_model=AnalyzeTypesResponse, status_code=200)
async def analyze_types() -> AnalyzeTypesResponse:
    categories, choices = get_analyze_types(AnalysisTemplateUoW())
    return AnalyzeTypesResponse(categories=categories, choices=choices)


