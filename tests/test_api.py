from __future__ import annotations

import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence
from uuid import uuid4

import pytest


def _install_sqlalchemy_stub() -> None:
    if "sqlalchemy" in sys.modules:
        return

    class FakeEngine:
        def dispose(self) -> None:  # pragma: no cover - optional cleanup
            return None

    class FakeSession:
        class _Query:
            def delete(self) -> None:  # pragma: no cover - not used
                return None

            def filter_by(self, **kwargs):  # pragma: no cover - not used
                return self

            def all(self):  # pragma: no cover - not used
                return []

            def first(self):  # pragma: no cover - not used
                return None

        def query(self, *_args, **_kwargs) -> FakeSession._Query:
            return FakeSession._Query()

        def add(self, *_args, **_kwargs) -> None:  # pragma: no cover - not used
            return None

        def commit(self) -> None:  # pragma: no cover - not used
            return None

        def close(self) -> None:  # pragma: no cover - not used
            return None

    sqlalchemy_stub = types.ModuleType("sqlalchemy")

    def create_engine(*_args, **_kwargs) -> FakeEngine:
        return FakeEngine()

    sqlalchemy_stub.create_engine = create_engine
    sqlalchemy_stub.MetaData = lambda: types.SimpleNamespace(create_all=lambda _engine: None)

    def _placeholder(*_args, **_kwargs) -> None:  # pragma: no cover - placeholder factory
        return None

    for name in ["Boolean", "Column", "Float", "ForeignKey", "Integer", "String", "Table", "Text"]:
        setattr(sqlalchemy_stub, name, _placeholder)

    sqlalchemy_stub.engine = types.ModuleType("sqlalchemy.engine")
    sqlalchemy_stub.engine.Engine = FakeEngine

    sqlalchemy_stub.exc = types.ModuleType("sqlalchemy.exc")
    sqlalchemy_stub.exc.OperationalError = RuntimeError

    orm_stub = types.ModuleType("sqlalchemy.orm")
    orm_stub.registry = lambda: types.SimpleNamespace(map_imperatively=lambda *args, **kwargs: None)
    orm_stub.relationship = _placeholder

    def sessionmaker(**_kwargs):
        def _factory():
            return FakeSession()

        return _factory

    orm_stub.sessionmaker = sessionmaker
    orm_session_stub = types.ModuleType("sqlalchemy.orm.session")
    orm_session_stub.Session = FakeSession

    sqlalchemy_stub.FakeSession = FakeSession
    sys.modules["sqlalchemy"] = sqlalchemy_stub
    sys.modules["sqlalchemy.engine"] = sqlalchemy_stub.engine
    sys.modules["sqlalchemy.exc"] = sqlalchemy_stub.exc
    sys.modules["sqlalchemy.orm"] = orm_stub
    sys.modules["sqlalchemy.orm.session"] = orm_session_stub


_install_sqlalchemy_stub()

config_stub = types.ModuleType("auto_summarization.services.config")
config_stub.settings = types.SimpleNamespace(
    AUTO_SUMMARIZATION_SUPPORTED_FORMATS=("txt", "doc", "docx", "pdf", "odt"),
    AUTO_SUMMARIZATION_MAX_SESSIONS=100,
    OPENAI_MODEL_NAME="test-model",
    AUTO_SUMMARIZATION_CONNECTION_TIMEOUT=60,
    OPENAI_API_KEY="test-key",
)
config_stub.authorization = "Authorization"
config_stub.Session = sys.modules["sqlalchemy"].FakeSession
config_stub.session_factory = lambda *args, **kwargs: sys.modules["sqlalchemy"].FakeSession()
sys.modules["auto_summarization.services.config"] = config_stub
if "auto_summarization.services" in sys.modules:
    setattr(sys.modules["auto_summarization.services"], "config", config_stub)

httpx_stub = types.ModuleType("httpx")


class _FakeResponse:
    def raise_for_status(self) -> None:  # pragma: no cover - network disabled
        return None

    def json(self) -> Dict[str, object]:
        return {}


class _FakeClient:
    def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - parameters ignored
        return None

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *args) -> None:
        return None

    def get(self, *args, **kwargs) -> _FakeResponse:
        return _FakeResponse()


httpx_stub.Client = _FakeClient
sys.modules["httpx"] = httpx_stub

from auto_summarization.domain.analysis import AnalysisTemplate
from auto_summarization.domain.user import User
from auto_summarization.services.handlers import analysis as analysis_handler
from auto_summarization.services.handlers import session as session_handler

ANALYZE_PATH = Path(__file__).resolve().parents[1] / "analyze_types.json"


def _load_templates() -> List[AnalysisTemplate]:
    payload = json.loads(ANALYZE_PATH.read_text(encoding="utf-8"))
    templates: List[AnalysisTemplate] = []
    for index, item in enumerate(payload.get("types", [])):
        templates.append(
            AnalysisTemplate(
                template_id=str(uuid4()),
                category_index=index,
                category=str(item["category"]),
                prompt=str(item["prompt"]),
            )
        )
    return templates


@dataclass
class InMemoryTemplateRepository:
    templates: List[AnalysisTemplate]

    def list(self) -> List[AnalysisTemplate]:
        return list(self.templates)

    def list_by_category(self, category_index: int) -> List[AnalysisTemplate]:
        return [
            template
            for template in self.templates
            if template.category_index == category_index
        ]


class InMemoryAnalysisTemplateUoW:
    def __init__(self, templates: List[AnalysisTemplate]):
        self.templates = InMemoryTemplateRepository(templates)

    def __enter__(self) -> InMemoryAnalysisTemplateUoW:
        return self

    def __exit__(self, *args) -> None:  # pragma: no cover - no cleanup required
        return None

    def commit(self) -> None:  # pragma: no cover - not needed for in-memory store
        return None

    def rollback(self) -> None:  # pragma: no cover - not needed for in-memory store
        return None


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._storage: Dict[str, User] = {}

    def add(self, data: User) -> None:
        self._storage[data.user_id] = data

    def get(self, object_id: str) -> User | None:
        return self._storage.get(object_id)

    def delete(self, user_id: str) -> None:  # pragma: no cover - not used in tests
        self._storage.pop(user_id, None)

    def list(self) -> List[User]:  # pragma: no cover - not used in tests
        return list(self._storage.values())


class InMemoryUserUoW:
    def __init__(self) -> None:
        self.users = InMemoryUserRepository()

    def __enter__(self) -> InMemoryUserUoW:
        return self

    def __exit__(self, *args) -> None:  # pragma: no cover - no cleanup required
        return None

    def commit(self) -> None:  # pragma: no cover - state already updated
        return None

    def rollback(self) -> None:  # pragma: no cover - no rollback logic
        return None


@pytest.fixture()
def template_uow() -> InMemoryAnalysisTemplateUoW:
    return InMemoryAnalysisTemplateUoW(_load_templates())


@pytest.fixture()
def user_uow() -> InMemoryUserUoW:
    return InMemoryUserUoW()


@pytest.fixture()
def llm_stub(monkeypatch: pytest.MonkeyPatch):
    class DummyLLM:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.counter = 0

        def invoke(self, prompt: str) -> str:
            self.counter += 1
            self.calls.append(prompt)
            return f"summary-{self.counter}"

    dummy = DummyLLM()
    monkeypatch.setattr(session_handler, "_build_llm", lambda: dummy)
    monkeypatch.setattr(session_handler, "_get_context_window", lambda _model: 8192)
    return dummy


def _create_user_id() -> str:
    return str(uuid4())


def test_get_analyze_types_and_extract_texts(template_uow: InMemoryAnalysisTemplateUoW) -> None:
    categories, choices = analysis_handler.get_analyze_types(template_uow)
    assert categories and choices
    assert len(categories) == len(choices)
    documents = {
        "doc-1": analysis_handler.extract_text(b"First document", "txt"),
        "doc-2": analysis_handler.extract_text(b"Second document", "txt"),
    }
    assert documents["doc-1"].startswith("First")
    with pytest.raises(ValueError):
        analysis_handler.extract_text(b"text", "unsupported")


def test_create_session_success(
    llm_stub,
    user_uow: InMemoryUserUoW,
    template_uow: InMemoryAnalysisTemplateUoW,
) -> None:
    user_id = _create_user_id()
    summary, error = session_handler.create_new_session(
        user_id=user_id,
        text=["Первый текст", "Второй текст"],
        category_index=0,
        temporary=False,
        user_uow=user_uow,
        analysis_uow=template_uow,
    )
    assert summary == "summary-1"
    assert error is None
    assert llm_stub.calls
    sessions = session_handler.get_session_list(user_id=user_id, uow=user_uow)
    assert len(sessions) == 1
    assert sessions[0]["text"] == ["Первый текст", "Второй текст"]


def test_update_session_and_search(
    llm_stub,
    user_uow: InMemoryUserUoW,
    template_uow: InMemoryAnalysisTemplateUoW,
) -> None:
    user_id = _create_user_id()
    summary, _ = session_handler.create_new_session(
        user_id=user_id,
        text=["Исходный текст"],
        category_index=0,
        temporary=False,
        user_uow=user_uow,
        analysis_uow=template_uow,
    )
    assert summary == "summary-1"
    sessions = session_handler.get_session_list(user_id=user_id, uow=user_uow)
    session_id = sessions[0]["session_id"]
    summary, _ = session_handler.update_session_summarization(
        user_id=user_id,
        session_id=session_id,
        text=["Обновлённый текст"],
        category_index=0,
        version=sessions[0]["version"],
        user_uow=user_uow,
        analysis_uow=template_uow,
    )
    assert summary == "summary-2"
    updated = session_handler.get_session_list(user_id=user_id, uow=user_uow)[0]
    assert updated["text"] == ["Обновлённый текст"]
    session_handler.update_title_session(
        user_id=user_id,
        session_id=session_id,
        title="Новый заголовок",
        version=updated["version"],
        user_uow=user_uow,
    )
    results = session_handler.search_similarity_sessions(user_id=user_id, query="Обновлённый", uow=user_uow)
    assert results
    status = session_handler.delete_exist_session(session_id=session_id, user_id=user_id, uow=user_uow)
    assert status == "SUCCESS"
    assert session_handler.get_session_list(user_id=user_id, uow=user_uow) == []


@pytest.mark.parametrize(
    "payload",
    [
        [],
        ["   ", "  "],
    ],
)
def test_create_session_rejects_empty_text(
    payload: Sequence[str],
    user_uow: InMemoryUserUoW,
    template_uow: InMemoryAnalysisTemplateUoW,
) -> None:
    with pytest.raises(ValueError):
        session_handler.create_new_session(
            user_id=_create_user_id(),
            text=payload,
            category_index=0,
            temporary=False,
            user_uow=user_uow,
            analysis_uow=template_uow,
        )


def test_create_session_invalid_category(
    user_uow: InMemoryUserUoW,
    template_uow: InMemoryAnalysisTemplateUoW,
) -> None:
    with pytest.raises(ValueError):
        session_handler.create_new_session(
            user_id=_create_user_id(),
            text=["Текст"],
            category_index=999,
            temporary=False,
            user_uow=user_uow,
            analysis_uow=template_uow,
        )
