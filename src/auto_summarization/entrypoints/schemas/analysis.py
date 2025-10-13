from typing import List, Optional

from auto_summarization.entrypoints.schemas import BaseModel

class LoadedDocumentInfo(BaseModel):
    input_id: str
    text: str

class LoadDocumentResponse(BaseModel):
    result: List[LoadedDocumentInfo]

class AnalyzeCategory(BaseModel):
    index: int
    category: str
    prompt: str
    model_type: Optional[str] = None


class AnalyzeTypesResponse(BaseModel):
    categories: List[AnalyzeCategory]

class AnalyzeErrorResponse(BaseModel):
    detail: str

class LoadDocumentRequest(BaseModel):
    document: Optional[str]
