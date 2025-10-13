import asyncio
import os
from pathlib import Path
from typing import List
from uuid import uuid4

import pytest

from conftest import authorization
try:  # pragma: no cover - prefer real FastAPI when present
    from fastapi import HTTPException, UploadFile
except ModuleNotFoundError:  # pragma: no cover - lightweight fallback for tests
    from auto_summarization.entrypoints.routers import analysis as analysis_router
    from auto_summarization.entrypoints.routers import session as session_router

    HTTPException = (analysis_router.HTTPException, session_router.HTTPException)
    UploadFile = analysis_router.UploadFile

TEST_DB_PATH = Path(__file__).resolve().parents[1] / "test.db"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ.setdefault("AUTO_SUMMARIZATION_DB_TYPE", "sqlite")
os.environ.setdefault("AUTO_SUMMARIZATION_DB_NAME", str(TEST_DB_PATH))
os.environ.setdefault(
    "AUTO_SUMMARIZATION_ANALYZE_TYPES_PATH",
    str(Path(__file__).resolve().parents[1] / "analyze_types.json"),
)

from auto_summarization.entrypoints.routers import analysis, session  # noqa: E402
from auto_summarization.entrypoints.schemas.session import (  # noqa: E402
    CreateSessionRequest,
    UpdateSessionSummarizationRequest,
)
from auto_summarization.services.config import register_analysis_templates  # noqa: E402

register_analysis_templates()


@pytest.fixture(scope="module", autouse=True)
def cleanup_db():
    yield
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture
def auth_header() -> str:
    return str(uuid4())


def test_analyze_types_returns_categories() -> None:
    response = asyncio.run(analysis.analyze_types())
    assert len(response.categories) == 3
    assert response.categories[0].category == "Экономика"
    assert response.categories[1].category == "Спорт"
    assert response.categories[2].category == "Путешествия"


def test_load_documents_success() -> None:
    documents = [
        UploadFile("note1.txt", "Первый документ".encode("utf-8")),
        UploadFile("note2.txt", "Второй документ".encode("utf-8")),
    ]
    response = asyncio.run(analysis.load_document(input_ids=["doc-1", "doc-2"], documents=documents))
    assert [item.input_id for item in response.result] == ["doc-1", "doc-2"]
    assert "Первый документ" in response.result[0].text
    assert "Второй документ" in response.result[1].text


def test_load_documents_mismatched_lengths() -> None:
    documents = [UploadFile("note1.txt", "Первый документ".encode("utf-8"))]
    with pytest.raises(HTTPException) as error:
        asyncio.run(analysis.load_document(input_ids=["doc-1", "doc-2"], documents=documents))
    assert error.value.status_code == 400


def test_create_session_success(auth_header: str) -> None:
    request = CreateSessionRequest(text=["Компания увеличила выручку", "Планы на квартал"], category=0)
    response = asyncio.run(session.create(request=request, auth=auth_header))
    assert response.content is not None
    assert "Сформулируй ключевые выводы" in (response.content.full_summary or "")

    page = asyncio.run(session.fetch_page(auth=auth_header))
    assert len(page.sessions) == 1
    assert page.sessions[0].version == 0


def test_create_session_requires_authorization() -> None:
    request = CreateSessionRequest(text=["Любой текст"], category=0)
    with pytest.raises(HTTPException) as error:
        asyncio.run(session.create(request=request, auth=None))
    assert error.value.status_code == 400


def test_update_session_success(auth_header: str) -> None:
    create_request = CreateSessionRequest(text=["Матч завершился победой"], category=1)
    asyncio.run(session.create(request=create_request, auth=auth_header))
    page = asyncio.run(session.fetch_page(auth=auth_header))
    item = page.sessions[0]

    update_request = UpdateSessionSummarizationRequest(
        session_id=item.session_id,
        text=["Матч завершился поражением", "Команда готовится к реваншу"],
        category=1,
        version=item.version,
    )
    response = asyncio.run(session.update_summarization(request=update_request, auth=auth_header))
    assert "перспективах участников" in (response.content.full_summary or "")
    refreshed = asyncio.run(session.fetch_page(auth=auth_header))
    assert refreshed.sessions[0].version == item.version + 1


def test_update_session_version_mismatch(auth_header: str) -> None:
    create_request = CreateSessionRequest(text=["Путешествие по Европе"], category=2)
    asyncio.run(session.create(request=create_request, auth=auth_header))
    page = asyncio.run(session.fetch_page(auth=auth_header))
    item = page.sessions[0]

    update_request = UpdateSessionSummarizationRequest(
        session_id=item.session_id,
        text=["Новая программа"],
        category=2,
        version=item.version + 10,
    )
    with pytest.raises(HTTPException) as error:
        asyncio.run(session.update_summarization(request=update_request, auth=auth_header))
    assert error.value.status_code == 400


def test_create_session_invalid_category(auth_header: str) -> None:
    request = CreateSessionRequest(text=["Неизвестная категория"], category=99)
    with pytest.raises(HTTPException) as error:
        asyncio.run(session.create(request=request, auth=auth_header))
    assert "категория" in str(error.value.detail)
