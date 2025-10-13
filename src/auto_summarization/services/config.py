from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from json import JSONDecodeError
from pathlib import Path
from typing import Dict, Tuple, TYPE_CHECKING
from uuid import uuid4

from auto_summarization.domain.analysis import AnalysisTemplate

logger = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from auto_summarization.domain.user import User


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip() in {"1", "true", "True", "yes"}


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _parse_formats(value: str | None, default: Tuple[str, ...]) -> Tuple[str, ...]:
    if not value:
        return default
    formats = [item.strip().lower() for item in value.split(",") if item.strip()]
    return tuple(dict.fromkeys(formats)) or default


@dataclass
class Settings:
    AUTO_SUMMARIZATION_SUPPORTED_FORMATS: Tuple[str, ...] = field(
        default_factory=lambda: ("txt", "doc", "docx", "pdf", "odt")
    )
    AUTO_SUMMARIZATION_MAX_SESSIONS: int = 100
    AUTO_SUMMARIZATION_URL_PREFIX: str = "/v1"
    AUTO_SUMMARIZATION_ANALYZE_TYPES_PATH: str = str(Path.cwd() / "analyze_types.json")
    AUTO_SUMMARIZATION_CONNECTION_TIMEOUT: int = 60
    AUTO_SUMMARIZATION_DB_TYPE: str = "memory"
    AUTO_SUMMARIZATION_DB_NAME: str = "autosummarization"
    AUTO_SUMMARIZATION_DB_USER: str = "autosummary"
    AUTO_SUMMARIZATION_DB_PASSWORD: str | None = None
    OPENAI_API_HOST: str = "http://localhost:8000/v1"
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL_NAME: str = "Qwen/Qwen3-4B-AWQ"
    DEBUG: int = 0

    def __post_init__(self) -> None:
        env = os.environ
        self.AUTO_SUMMARIZATION_SUPPORTED_FORMATS = _parse_formats(
            env.get("AUTO_SUMMARIZATION_SUPPORTED_FORMATS"),
            self.AUTO_SUMMARIZATION_SUPPORTED_FORMATS,
        )
        self.AUTO_SUMMARIZATION_MAX_SESSIONS = _parse_int(
            env.get("AUTO_SUMMARIZATION_MAX_SESSIONS"),
            self.AUTO_SUMMARIZATION_MAX_SESSIONS,
        )
        self.AUTO_SUMMARIZATION_URL_PREFIX = env.get(
            "AUTO_SUMMARIZATION_URL_PREFIX", self.AUTO_SUMMARIZATION_URL_PREFIX
        )
        self.AUTO_SUMMARIZATION_ANALYZE_TYPES_PATH = env.get(
            "AUTO_SUMMARIZATION_ANALYZE_TYPES_PATH", self.AUTO_SUMMARIZATION_ANALYZE_TYPES_PATH
        )
        self.AUTO_SUMMARIZATION_CONNECTION_TIMEOUT = _parse_int(
            env.get("AUTO_SUMMARIZATION_CONNECTION_TIMEOUT"),
            self.AUTO_SUMMARIZATION_CONNECTION_TIMEOUT,
        )
        self.DEBUG = 1 if _parse_bool(env.get("DEBUG")) else 0


@dataclass
class InMemoryDatabase:
    users: Dict[str, "User"] = field(default_factory=dict)
    templates: Dict[int, AnalysisTemplate] = field(default_factory=dict)


settings = Settings()
authorization = "Authorization" if not settings.DEBUG else "user_id"
database = InMemoryDatabase()


def register_analysis_templates() -> None:
    path = Path(settings.AUTO_SUMMARIZATION_ANALYZE_TYPES_PATH)
    if not path.exists():
        logger.warning("Analyze types configuration not found at %s", path)
        database.templates.clear()
        return

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, JSONDecodeError) as exc:
        logger.error("Failed to load analyze types: %s", exc)
        database.templates.clear()
        return

    database.templates.clear()
    for category_index, item in enumerate(payload.get("types", [])):
        category = item.get("category")
        if not category:
            continue
        prompt = item.get("prompt", "")
        model_type = item.get("model_type")
        template = AnalysisTemplate(
            template_id=str(uuid4()),
            category_index=category_index,
            category=category,
            prompt=prompt,
            model_type=model_type,
        )
        database.templates[category_index] = template


register_analysis_templates()
