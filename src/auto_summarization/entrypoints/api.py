try:  # pragma: no cover - prefer the real FastAPI when available
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ModuleNotFoundError:  # pragma: no cover - lightweight fallback for tests
    class FastAPI:  # pragma: no cover - small facade used in tests
        def __init__(self, title: str = "", description: str = "") -> None:
            self.title = title
            self.description = description
            self._routes = []
            self._middleware = []

        def add_middleware(self, middleware_class, **kwargs):
            self._middleware.append((middleware_class, kwargs))

        def get(self, *args, **kwargs):
            def decorator(func):
                self._routes.append(("GET", args, kwargs, func))
                return func

            return decorator

        def include_router(self, router, **kwargs):
            self._routes.append(("ROUTER", router, kwargs))


    class CORSMiddleware:  # pragma: no cover - placeholder
        def __init__(self, app, **kwargs):
            self.app = app
            self.kwargs = kwargs

from auto_summarization.entrypoints.routers import analysis, session, user
from auto_summarization.services import config


class API(FastAPI):
    def __init__(self) -> None:
        super().__init__(title="FastAPI", description="Auto Summarization API")

        self.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @self.get("/health")
        async def health():
            return {"status": "ok"}


app = API()
prefix = config.settings.AUTO_SUMMARIZATION_URL_PREFIX
app.include_router(user.router, prefix=f"{prefix}/user", tags=["users"])
app.include_router(session.router, prefix=f"{prefix}/chat_session", tags=["sessions"])
app.include_router(analysis.router, prefix=f"{prefix}/analysis", tags=["analysis"])
