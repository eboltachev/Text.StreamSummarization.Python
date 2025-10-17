from __future__ import annotations

from typing import List

from pydantic import BaseModel


class LoadDocumentResponse(BaseModel):
    contents: List[str]
class ReportTypesResponse(BaseModel):
    report_types: List[str]


class DocumentErrorResponse(BaseModel):
    detail: str
