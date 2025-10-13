import os
import re
import shutil
import subprocess
from contextlib import closing
from time import sleep
from typing import Any, Dict, Iterable, List
from uuid import uuid4

import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor
import pytest
import requests
from conftest import authorization
from dotenv import load_dotenv

load_dotenv()


@pytest.mark.asyncio
class TestAPI:
    def setup_class(self):
        if shutil.which("docker") is None:
            pytest.skip("Docker is required to run integration tests", allow_module_level=True)
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
                    "hf_models",
                    ".venv",
                    "uv.lock",
                    ".pytest_cache",
                    ".mypy_cache",
                    "--show-contents",
                ],
                cwd=self._cwd,
                stdout=content_file,
                stderr=content_file,
            )
        self._api_host = os.environ.get("AUTO_SUMMARIZATION_API_HOST", "localhost")
        self._api_port = os.environ.get("AUTO_SUMMARIZATION_API_PORT", 8000)
        self._api_url = f"http://{self._api_host}:{self._api_port}"
        self._prefix = os.environ.get("AUTO_SUMMARIZATION_URL_PREFIX", "/v1")
        self._headers = {authorization: str(uuid4())}
        self._id_pattern = r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"

        db_host = os.environ.get("AUTO_SUMMARIZATION_DB_HOST", "localhost")
        self._db_host = self._normalize_host(db_host)
        self._db_port = int(os.environ.get("AUTO_SUMMARIZATION_DB_PORT", 5432))
        self._db_name = os.environ.get("AUTO_SUMMARIZATION_DB_NAME", "autosummarization")
        self._db_user = os.environ.get("AUTO_SUMMARIZATION_DB_USER", "autosummary")
        self._db_password = os.environ.get("AUTO_SUMMARIZATION_DB_PASSWORD")
        if not self._db_password:
            pytest.skip("Database credentials are required to run integration tests", allow_module_level=True)
        self._db_connect_kwargs = {
            "host": self._db_host,
            "port": self._db_port,
            "dbname": self._db_name,
            "user": self._db_user,
            "password": self._db_password,
        }

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

        db_ready = False
        timeout_counter = 0
        while not db_ready:
            try:
                with closing(psycopg2.connect(**self._db_connect_kwargs)) as connection:
                    connection.close()
                db_ready = True
            except OperationalError:
                sleep(self._sleep)
                timeout_counter += 1
                if timeout_counter > self._timeout:
                    pytest.skip("Database is not ready for integration tests", allow_module_level=True)

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

    @staticmethod
    def _normalize_host(host: str | None) -> str:
        if not host or host in {"db", "0.0.0.0"}:
            return "localhost"
        return host

    def _db_execute(self, query: str, params: Iterable[Any] | None = None) -> List[Dict[str, Any]]:
        with closing(psycopg2.connect(**self._db_connect_kwargs)) as connection:
            connection.autocommit = True
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, tuple(params or ()))
                if cursor.description is None:
                    return []
                return list(cursor.fetchall())

    def _db_fetchone(self, query: str, params: Iterable[Any] | None = None) -> Dict[str, Any] | None:
        results = self._db_execute(query, params)
        return results[0] if results else None

    async def test_docs(self):
        response = requests.get(f"{self._api_url}/docs")
        assert response.status_code == 200
        assert "FastAPI - Swagger UI" in response.text

    async def test_health(self):
        response = requests.get(f"{self._api_url}/health")
        assert response.status_code == 200
        assert {"status": "ok"} == response.json()

    async def test_analyze_types_and_load_documents(self):
        # to-do

    async def test_session_create_performs_analysis(self):
        # to-do

    async def test_users_and_sessions(self):
        # to-do

    async def test_session_create_requires_authorization(self):
        # to-do

    async def test_session_create_invalid_category(self):
        # to-do