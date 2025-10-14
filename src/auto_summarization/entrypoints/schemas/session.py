from typing import List, Optional

from auto_summarization.domain.enums import StatusType
from pydantic import BaseModel


class SessionSearchResult(BaseModel):
    title: str
    query: str
    summary: str
    inserted_at: float
    session_id: str
    score: float


class SearchSessionsResponse(BaseModel):
    results: List[SessionSearchResult]


class SessionInfo(BaseModel):
    session_id: str
    version: int
    title: str
    text: List[str]
    summary: str
    inserted_at: float
    updated_at: float

class FetchSessionResponse(BaseModel):
    sessions: List[SessionInfo]


class CreateSessionRequest(BaseModel):
    text: List[str]
    category: int
    temporary: Optional[bool] = False

class CreateSessionResponse(BaseModel):
    summary: str
    error: Optional[str]

class UpdateSessionSummarizationRequest(BaseModel):
    session_id: str
    text: List[str]
    category: int
    version: int

class UpdateSessionSummarizationResponse(BaseModel):
    summary: str
    error: Optional[str]

class UpdateSessionTitleRequest(BaseModel):
    session_id: str
    title: str
    version: int

class UpdateSessionTitleResponse(SessionInfo):
    pass

class DeleteSessionRequest(BaseModel):
    session_id: str

class DeleteSessionResponse(BaseModel):
    status: StatusType
