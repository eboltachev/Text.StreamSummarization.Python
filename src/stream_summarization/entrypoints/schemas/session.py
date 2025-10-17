from typing import List, Optional

from pydantic import BaseModel

from stream_summarization.domain.enums import StatusType


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
    report_index: int
    temporary: Optional[bool] = False


class CreateSessionResponse(BaseModel):
    session_id: str
    summary: str
    error: Optional[str]


class UpdateSessionSummarizationRequest(BaseModel):
    session_id: str
    text: List[str]
    report_index: int
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
