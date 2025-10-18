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

class ShortSessionInfo(BaseModel):
    session_id: str
    version: int
    title: str
    inserted_at: float
    updated_at: float

class DocText(BaseModel):
    text: str
    title: str = ""
    url: str = ""
    date: str = ""
    source: str = ""

class SessionInfo(BaseModel):
    session_id: str
    version: int
    title: str
    documents: List[DocText]
    summary: str
    inserted_at: float
    updated_at: float


class FetchSessionResponse(BaseModel):
    sessions: List[ShortSessionInfo]

class CreateSessionRequest(BaseModel):
    title: str = ""
    documents: List[DocText]
    report_index: int
    temporary: Optional[bool] = False


class CreateSessionResponse(BaseModel):
    session_id: str
    summary: str
    error: str | None


class UpdateSessionSummarizationRequest(BaseModel):
    session_id: str
    documents: List[DocText]
    report_index: int
    version: int


class UpdateSessionSummarizationResponse(BaseModel):
    summary: str
    error: str | None


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
