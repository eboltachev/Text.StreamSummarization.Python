from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from stream_summarization.entrypoints.routers import report, session, user
from stream_summarization.services import config


class API(FastAPI):
    def __init__(self) -> None:
        super().__init__(title="FastAPI", description="Stream Summarization API")

        self.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @self.get("/health", summary="Проверка состояния сервиса")
        async def health():
            return {"status": "ok"}


app = API()
prefix = config.settings.STREAM_SUMMARIZATION_URL_PREFIX
app.include_router(user.router, prefix=f"{prefix}/user", tags=["users"])
app.include_router(session.router, prefix=f"{prefix}/chat_session", tags=["sessions"])
app.include_router(report.router, prefix=f"{prefix}/reports", tags=["reports"])
