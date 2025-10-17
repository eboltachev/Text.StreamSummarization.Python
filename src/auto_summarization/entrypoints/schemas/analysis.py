from __future__ import annotations

from typing import List

from pydantic import BaseModel


class LoadDocumentResponse(BaseModel):
    contents: List[str]
class AnalyzeTypesResponse(BaseModel):
    report_types: List[str]


class AnalyzeErrorResponse(BaseModel):
    detail: str
