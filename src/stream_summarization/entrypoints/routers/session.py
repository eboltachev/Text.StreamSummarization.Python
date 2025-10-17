import base64
import mimetypes
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from stream_summarization.entrypoints.schemas.session import (
    CreateSessionRequest,
    CreateSessionResponse,
    DeleteSessionRequest,
    DeleteSessionResponse,
    FetchSessionResponse,
    SearchSessionsResponse,
    SessionInfo,
    SessionSearchResult,
    UpdateSessionSummarizationRequest,
    UpdateSessionSummarizationResponse,
    UpdateSessionTitleRequest,
    UpdateSessionTitleResponse,
)
from stream_summarization.services.config import authorization
from stream_summarization.services.data.unit_of_work import ReportTemplateUoW, UserUoW
from stream_summarization.services.handlers.session import (
    create_new_session,
    delete_exist_session,
    download_session_file,
    get_session_list,
    search_similarity_sessions,
    update_session_summarization,
    update_title_session,
)

router = APIRouter()


@router.get("/fetch_page", response_model=FetchSessionResponse, status_code=200)
async def fetch_page(auth: str = Header(default=None, alias=authorization)) -> FetchSessionResponse:
    if auth is None:
        raise HTTPException(status_code=400, detail="Authorization header is required")
    try:
        sessions = [SessionInfo(**session) for session in get_session_list(user_id=auth, uow=UserUoW())]
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return FetchSessionResponse(sessions=sessions)


@router.post("/create", response_model=CreateSessionResponse, status_code=200)
async def create(
    request: CreateSessionRequest,
    auth: str = Header(default=None, alias=authorization),
) -> CreateSessionResponse:
    if auth is None:
        raise HTTPException(status_code=400, detail="Authorization header is required")
    try:
        session_id, summary, error = create_new_session(
            user_id=auth,
            text=request.text,
            report_index=request.report_index,
            temporary=request.temporary,
            user_uow=UserUoW(),
            report_uow=ReportTemplateUoW(),
        )
        return CreateSessionResponse(session_id=session_id, summary=summary, error=error)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/update_summarization", response_model=UpdateSessionSummarizationResponse, status_code=200)
async def update_summarization(
    request: UpdateSessionSummarizationRequest,
    auth: str = Header(default=None, alias=authorization),
) -> UpdateSessionSummarizationResponse:
    if auth is None:
        raise HTTPException(status_code=400, detail="Authorization header is required")
    try:
        summary, error = update_session_summarization(
            user_id=auth,
            session_id=request.session_id,
            text=request.text,
            report_index=request.report_index,
            version=request.version,
            user_uow=UserUoW(),
            report_uow=ReportTemplateUoW(),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return UpdateSessionSummarizationResponse(summary=summary, error=error)


@router.post("/update_title", response_model=UpdateSessionTitleResponse, status_code=200)
async def update_title(
    request: UpdateSessionTitleRequest,
    auth: str = Header(default=None, alias=authorization),
) -> UpdateSessionTitleResponse:
    if auth is None:
        raise HTTPException(status_code=400, detail="Authorization header is required")
    try:
        session = update_title_session(
            user_id=auth,
            session_id=request.session_id,
            title=request.title,
            version=request.version,
            user_uow=UserUoW(),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return UpdateSessionTitleResponse(**session)


@router.get("/search", response_model=SearchSessionsResponse, status_code=200)
async def similarity_sessions(
    query: str = Query(..., min_length=1),
    auth: str = Header(default=None, alias=authorization),
) -> SearchSessionsResponse:
    if auth is None:
        raise HTTPException(status_code=400, detail="Authorization header is required")
    try:
        results = search_similarity_sessions(user_id=auth, query=query, uow=UserUoW())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return SearchSessionsResponse(results=[SessionSearchResult(**item) for item in results])


@router.get(
    "/download/{session_id}/{format}",
    responses={
        200: {
            "description": "Файл",
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}},
                "application/pdf": {"schema": {"type": "string", "format": "binary"}},
                "text/plain": {"schema": {"type": "string", "format": "binary"}},
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "filename": {"type": "string"},
                            "content_type": {"type": "string"},
                            "data": {"type": "string", "description": "base64-encoded file"},
                        },
                        "required": ["filename", "content_type", "data"],
                    }
                },
            },
        }
    },
)
async def download_file(
    session_id: str,
    format: Literal["pdf"],
    auth: str = Header(default=None, alias=authorization),
    accept: str = Header(default="*/*", alias="Accept"),
):
    user_id = auth
    if user_id is None:
        raise HTTPException(status_code=400, detail="Bad Request")

    try:
        path = download_session_file(
            session_id=session_id,
            format=format,
            user_id=user_id,
            uow=UserUoW(),
        )
        if not path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        filename = f"{session_id}.{format}"

        guessed_type, _ = mimetypes.guess_type(filename)
        media_type = guessed_type or ("application/pdf" if format.lower() == "pdf" else "application/octet-stream")

        if "application/json" in (accept or ""):
            with path.open("rb") as file_handle:
                payload = base64.b64encode(file_handle.read()).decode("ascii")
            return JSONResponse(
                content={"filename": filename, "content_type": media_type, "data": payload},
                headers={"X-Served-For-User": user_id or "", "Access-Control-Expose-Headers": "*"},
            )

        return FileResponse(
            path=str(path),
            media_type=media_type,
            filename=filename,
            headers={"X-Served-For-User": user_id or "", "Access-Control-Expose-Headers": "*"},
        )
    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.delete("/delete", response_model=DeleteSessionResponse, status_code=200)
async def delete(
    request: DeleteSessionRequest,
    auth: str = Header(default=None, alias=authorization),
) -> DeleteSessionResponse:
    if auth is None:
        raise HTTPException(status_code=400, detail="Authorization header is required")
    try:
        status = delete_exist_session(session_id=request.session_id, user_id=auth, uow=UserUoW())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return DeleteSessionResponse(status=status)
