from __future__ import annotations

from typing import List

from pydantic import BaseModel


class LoadDocumentResponse(BaseModel):
    contents: List[str]


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
