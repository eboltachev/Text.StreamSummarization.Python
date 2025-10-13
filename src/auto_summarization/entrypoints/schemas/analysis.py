from typing import List, Optional

from pydantic import BaseModel

class LoadedDocumentInfo(BaseModel):
    input_id: int
    text: str

class LoadDocumentResponse(BaseModel):
    result: List[LoadedDocumentInfo]

class AnalyzeTypesResponse(BaseModel):
    categories: List[str]

class AnalyzeErrorResponse(BaseModel):
    detail: str

class LoadDocumentRequest(BaseModel):
    document: Optional[str]
