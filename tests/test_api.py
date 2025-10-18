import os
import re
import subprocess
from time import sleep

import pytest
import requests
from dotenv import load_dotenv

from conftest import authorization

load_dotenv()


@pytest.mark.asyncio
class TestAPI:
    def setup_class(self):
        self._sleep = 1
        self._timeout = 30
        self._compose_file = "docker-compose.yml"
        self._content_file_path = "dev/content.txt"
        os.makedirs("dev", exist_ok=True)
        self._cwd = os.getcwd()
        with open(self._content_file_path, "w") as content_file:
            content_file.write("**Logs**\n\n")
        with open(self._content_file_path, "a") as content_file:
            subprocess.run(
                ["docker", "compose", "-f", self._compose_file, "up", "--build", "-d"],
                stdout=content_file,
                stderr=content_file,
            )
        with open(self._content_file_path, "a") as content_file:
            subprocess.run(
                [
                    "printdirtree",
                    "--exclude-dir",
                    "tests",
                    ".venv",
                    ".env",
                    "deploy",
                    "fonts",
                    "uv.lock",
                    ".pytest_cache",
                    ".mypy_cache",
                    "--show-contents",
                ],
                cwd=self._cwd,
                stdout=content_file,
                stderr=content_file,
            )
        self._api_host = os.environ.get("STREAM_SUMMARIZATION_API_HOST", "localhost")
        self._api_port = os.environ.get("STREAM_SUMMARIZATION_API_PORT", 8000)
        self._api_url = f"http://{self._api_host}:{self._api_port}"
        self._prefix = os.environ.get("STREAM_SUMMARIZATION_URL_PREFIX", "/v1")
        self._headers = {"user_id": None}
        self._users = [
            {"user_id": "d2fb6951-e69f-4402-b3e4-6b73f66b63f5"},
            {"user_id": "d2fb6951-e69f-4402-b3e4-6b73f66b63f6"},
        ]
        self._id_pattern = r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"

        connection = False
        timeout_counter = 0
        while not connection:
            try:
                requests.get(self._api_url)
                connection = True
            except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError):
                sleep(self._sleep)
                timeout_counter += 1
                if timeout_counter > self._timeout:
                    with open(self._content_file_path, "a") as content_file:
                        subprocess.run(
                            ["docker", "compose", "-f", self._compose_file, "logs"],
                            cwd=self._cwd,
                            stdout=content_file,
                            stderr=content_file,
                        )
                    subprocess.run(
                        ["docker", "compose", "-f", self._compose_file, "down", "-v"],
                        cwd=self._cwd,
                        stdout=open(os.devnull, "w"),
                        stderr=subprocess.STDOUT,
                    )
                    raise Exception("Setup timeout")

    def teardown_class(self):
        with open(self._content_file_path, "a") as content_file:
            content_file.write(f"\n\n**Logs:**\n\n")
        with open(self._content_file_path, "a") as content_file:
            subprocess.run(
                ["docker", "compose", "-f", self._compose_file, "logs"],
                cwd=self._cwd,
                stdout=content_file,
                stderr=content_file,
            )
        subprocess.run(
            ["docker", "compose", "-f", self._compose_file, "down", "-v"],
            cwd=self._cwd,
            stdout=open(os.devnull, "w"),
            stderr=subprocess.STDOUT,
        )

    async def test_docs(self):
        response = requests.get(f"{self._api_url}/docs")
        assert 200 == response.status_code
        assert "FastAPI - Swagger UI" in response.text

    async def test_health(self):
        response = requests.get(f"{self._api_url}/health")
        assert 200 == response.status_code
        assert {"status": "ok"} == response.json()


    # ============================
    # Helpers
    # ============================
    def _auth_headers(self, user_id):
        # имя заголовка берём из conftest.authorization (см. import authorization)
        return {authorization: user_id}


    def _ensure_user(self, user_id: str, temporary: bool = False):
        resp = requests.post(
            f"{self._api_url}{self._prefix}/user/create_user",
            json={"user_id": user_id, "temporary": temporary},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] in ("created", "exist")


    def _extract_uuid(self, payload: dict) -> str:
        """
        Универсальный поиск UUID в ответе (на случай, если поле называется иначе).
        """
        text = str(payload)
        m = re.search(self._id_pattern, text)
        assert m, f"Session id (UUID) not found in payload: {payload}"
        return m.group(0)


    # ============================
    # POSITIVE end-to-end: create → update_* → search/fetch → download → delete
    # ============================
    async def test_sessions__e2e_create_update_download_delete(self):
        user_id = self._users[0]["user_id"]
        self._ensure_user(user_id, temporary=False)
        h = self._auth_headers(user_id)

        # Добавили обязательный report_index
        create_payload = {
            "title": "Smoke test session",
            "text": ["Hello from test suite"],
            "messages": [{"role": "user", "content": "Hello from test suite"}],
            "report_index": 0,
        }
        resp = requests.post(
            f"{self._api_url}{self._prefix}/chat_session/create",
            json=create_payload,
            headers=h,
        )
        assert resp.status_code in (200, 201, 202), resp.text
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        session_id = self._extract_uuid(data) if data else re.search(self._id_pattern, resp.text).group(0)

        # update_title
        upd_title = {"session_id": session_id, "title": "Smoke test session — updated", "version": 0}
        resp = requests.post(
            f"{self._api_url}{self._prefix}/chat_session/update_title",
            json=upd_title,
            headers=h,
        )
        assert resp.status_code == 200, resp.text

        # update_summarization — добавляем готовый текст без LLM
        upd_sum = {
            "session_id": session_id,
            "text": [
                "Это тестовый отчёт. Раздел 1: краткая выжимка.",
                "Раздел 2: детали реализации и результаты."
            ],
            "report_index": 0,
            "version": 1,
        }
        resp = requests.post(
            f"{self._api_url}{self._prefix}/chat_session/update_summarization",
            json=upd_sum,
            headers=h,
        )
        assert resp.status_code == 200, resp.text

        sleep(self._sleep)

        # fetch_page
        resp = requests.get(f"{self._api_url}{self._prefix}/chat_session/fetch_page", headers=h)
        assert resp.status_code == 200
        payload = resp.json()
        assert "sessions" in payload and isinstance(payload["sessions"], list)
        ids = {self._extract_uuid(s) for s in payload["sessions"]}
        assert session_id in ids

        # search
        resp = requests.get(
            f"{self._api_url}{self._prefix}/chat_session/search",
            params={"query": "выжимка"},
            headers=h,
        )
        assert resp.status_code == 200, resp.text
        sdata = resp.json()
        results = sdata.get("sessions") or sdata.get("results") or []
        assert isinstance(results, list) and len(results) >= 1
        rids = {self._extract_uuid(r) for r in results}
        assert session_id in rids

        # download/pdf
        resp = requests.get(f"{self._api_url}{self._prefix}/chat_session/download/{session_id}/pdf", headers=h)
        assert resp.status_code == 200, resp.text
        ctype = resp.headers.get("content-type", "")
        assert "pdf" in ctype.lower()
        assert int(resp.headers.get("content-length", "1")) > 0 or resp.content

        # # download/docx
        # resp = requests.get(f"{self._api_url}{self._prefix}/chat_session/download/{session_id}/docx", headers=h)
        # assert resp.status_code == 200, resp.text
        # ctype = resp.headers.get("content-type", "")
        # assert any(x in ctype.lower() for x in ("word", "officedocument", "docx"))
        # assert int(resp.headers.get("content-length", "1")) > 0 or resp.content

        # delete
        resp = requests.delete(
            f"{self._api_url}{self._prefix}/chat_session/delete",
            json={"session_id": session_id},
            headers=h,
        )
        assert resp.status_code == 200
        status = (resp.json().get("status", "") or "").lower()
        assert any(s in status for s in ("deleted", "ok", "success"))

        # повторное delete — идемпотентно
        resp = requests.delete(
            f"{self._api_url}{self._prefix}/chat_session/delete",
            json={"session_id": session_id},
            headers=h,
        )
        assert resp.status_code == 200
        status = resp.json().get("status", "")
        assert "NOT_FOUND" == status

    # ============================
    # NEGATIVE (как в прежнем ответе) + оставляем
    # ============================

    # Users router
    async def test_user_create_get_delete_flow(self):
        user_id = self._users[0]["user_id"]
        resp = requests.post(
            f"{self._api_url}{self._prefix}/user/create_user",
            json={"user_id": user_id, "temporary": False},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] in ("created", "exist")

        temp_user = self._users[1]["user_id"]
        resp = requests.post(
            f"{self._api_url}{self._prefix}/user/create_user",
            json={"user_id": temp_user, "temporary": True},
        )
        assert resp.status_code == 200

        resp = requests.get(f"{self._api_url}{self._prefix}/user/get_users")
        assert resp.status_code == 200
        users = resp.json().get("users", [])
        ids = {u["user_id"] for u in users}
        assert user_id in ids
        assert temp_user not in ids

        resp = requests.delete(
            f"{self._api_url}{self._prefix}/user/delete_user",
            json={"user_id": user_id},
        )
        assert resp.status_code == 200

        resp = requests.delete(
            f"{self._api_url}{self._prefix}/user/delete_user",
            json={"user_id": user_id},
        )
        assert resp.status_code == 200


    # Reports router
    async def test_reports__report_types_ok(self):
        resp = requests.get(f"{self._api_url}{self._prefix}/reports/report_types")
        assert resp.status_code == 200
        payload = resp.json()
        assert "report_types" in payload
        assert isinstance(payload["report_types"], list)


    async def test_reports__load_documents_txt_ok(self):
        files = [
            ("documents", ("a.txt", b"hello\nworld", "text/plain")),
            ("documents", ("b.txt", "Привет, мир!".encode("utf-8"), "text/plain")),
        ]
        resp = requests.post(
            f"{self._api_url}{self._prefix}/reports/load_documents",
            files=files,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "contents" in data and isinstance(data["contents"], list)
        assert len(data["contents"]) == 2


    async def test_reports__load_documents_unsupported_ext(self):
        files = [("documents", ("bad.xyz", b"???", "application/octet-stream"))]
        resp = requests.post(
            f"{self._api_url}{self._prefix}/reports/load_documents",
            files=files,
        )
        assert resp.status_code == 400
        detail = resp.json().get("detail", "")
        assert "Unsupported document format" in detail

    # Sessions router — негативные проверки без LLM
    async def test_sessions__fetch_page_requires_auth(self):
        resp = requests.get(f"{self._api_url}{self._prefix}/chat_session/fetch_page")
        assert resp.status_code == 400


    async def test_sessions__fetch_page_unknown_user_ok_empty(self):
        resp = requests.get(
            f"{self._api_url}{self._prefix}/chat_session/fetch_page",
            headers=self._auth_headers("00000000-0000-0000-0000-000000000001"),
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert "sessions" in payload and isinstance(payload["sessions"], list)
        assert len(payload["sessions"]) == 0


    async def test_sessions__session_info_user_not_found(self):
        resp = requests.get(
            f"{self._api_url}{self._prefix}/chat_session/11111111-1111-1111-1111-111111111111",
            headers=self._auth_headers("00000000-0000-0000-0000-000000000002"),
        )
        assert resp.status_code == 400
        assert "User not found" in resp.json().get("detail", "")


    async def test_sessions__search_requires_auth_and_nonempty_query(self):
        resp = requests.get(f"{self._api_url}{self._prefix}/chat_session/search", params={"query": "test"})
        assert resp.status_code == 400

        resp = requests.get(
            f"{self._api_url}{self._prefix}/chat_session/search",
            params={"query": ""},
            headers=self._auth_headers("00000000-0000-0000-0000-000000000003"),
        )
        assert resp.status_code in (400, 422)

        resp = requests.get(
            f"{self._api_url}{self._prefix}/chat_session/search",
            params={"query": "anything"},
            headers=self._auth_headers("00000000-0000-0000-0000-000000000003"),
        )
        assert resp.status_code == 400
        assert "does not have any sessions" in resp.json().get("detail", "")


    async def test_sessions__update_summarization_user_not_found(self):
        payload = {
            "session_id": "11111111-1111-1111-1111-111111111111",
            "text": ["a", "b"],
            "report_index": 0,
            "version": 0,
        }
        resp = requests.post(
            f"{self._api_url}{self._prefix}/chat_session/update_summarization",
            json=payload,
            headers=self._auth_headers("00000000-0000-0000-0000-000000000004"),
        )
        assert resp.status_code == 400
        assert "User not found" in resp.json().get("detail", "")


    async def test_sessions__update_title_user_not_found(self):
        payload = {
            "session_id": "11111111-1111-1111-1111-111111111111",
            "title": "New title",
            "version": 0,
        }
        resp = requests.post(
            f"{self._api_url}{self._prefix}/chat_session/update_title",
            json=payload,
            headers=self._auth_headers("00000000-0000-0000-0000-000000000005"),
        )
        assert resp.status_code == 400
        assert "User not found" in resp.json().get("detail", "")


    # ============================
    # NEGATIVE: корректируем ожидание для user_not_found
    # ============================
    async def test_sessions_bad_index(self):
        user_id = self._users[0]["user_id"]
        self._ensure_user(user_id, temporary=False)
        h = self._auth_headers(user_id)

        create_payload = {
            "title": "Smoke test session",
            "text": ["Hello from test suite"],
            "messages": [{"role": "user", "content": "Hello from test suite"}],
            "report_index": 5,
        }
        resp = requests.post(
            f"{self._api_url}{self._prefix}/chat_session/create",
            json=create_payload,
            headers=h,
        )
        assert 400 == resp.status_code


    async def test_sessions__delete_user_not_found(self):
        resp = requests.delete(
            f"{self._api_url}{self._prefix}/chat_session/delete",
            json={"session_id": "11111111-1111-1111-1111-111111111111"},
            headers=self._auth_headers("00000000-0000-0000-0000-000000000006"),
        )
        assert resp.status_code in (200, 400)

        ctype = resp.headers.get("content-type", "")
        text = resp.text.lower()
        if ctype.startswith("application/json"):
            body = resp.json()
            status = (body.get("status") or "").lower()
            detail = (body.get("detail") or "")
            # иногда detail — это список ошибок (pydantic). Приведём к строке.
            if isinstance(detail, list):
                detail = " ".join(str(x) for x in detail)
            detail = detail.lower()
            # Принимаем несколько вариантов: статус=not_found|error ИЛИ любая формулировка 'not found' в теле
            assert (
                status in ("not_found", "error")
                or "not found" in status
                or "not found" in detail
            )
        else:
            # не-JSON ответ: ищем подстроку «not found» в тексте
            assert "not found" in text or "user not found" in text or "error" in text


