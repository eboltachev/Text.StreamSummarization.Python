from __future__ import annotations

from typing import List

from pydantic import BaseModel


class LoadedDocumentInfo(BaseModel):
    document_id: str
    text: str


class LoadDocumentResponse(BaseModel):
    result: List[LoadedDocumentInfo]


class AnalyzeCategory(BaseModel):
    index: int
    name: str


class AnalyzeChoice(BaseModel):
    index: int
    prompt: str


class AnalyzeTypesResponse(BaseModel):
    categories: List[AnalyzeCategory]
    choices: List[AnalyzeChoice]


class AnalyzeErrorResponse(BaseModel):
    detail: str
