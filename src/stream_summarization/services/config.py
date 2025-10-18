from __future__ import annotations

import json
import logging
from json import JSONDecodeError
from pathlib import Path
from typing import List, Tuple
from uuid import uuid4

from stream_summarization.adapters.orm import metadata, start_mappers
from stream_summarization.domain.report import ReportTemplate
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from pydantic_settings.sources import (
    EnvSettingsSource,
    PydanticBaseSettingsSource,
)
from pydantic_settings.sources.providers.dotenv import DotEnvSettingsSource
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        class LenientEnvSource(EnvSettingsSource):
            def decode_complex_value(self, field_name, field, value):  # type: ignore[override]
                try:
                    return super().decode_complex_value(field_name, field, value)
                except JSONDecodeError:
                    return value

        class LenientDotEnvSource(DotEnvSettingsSource):
            def decode_complex_value(self, field_name, field, value):  # type: ignore[override]
                try:
                    return super().decode_complex_value(field_name, field, value)
                except JSONDecodeError:
                    return value

        lenient_env = LenientEnvSource(
            settings_cls,
            case_sensitive=getattr(env_settings, "case_sensitive", None),
            env_prefix=getattr(env_settings, "env_prefix", None),
            env_nested_delimiter=getattr(env_settings, "env_nested_delimiter", None),
            env_nested_max_split=getattr(env_settings, "env_nested_max_split", None),
            env_ignore_empty=getattr(env_settings, "env_ignore_empty", None),
            env_parse_none_str=getattr(env_settings, "env_parse_none_str", None),
            env_parse_enums=getattr(env_settings, "env_parse_enums", None),
        )

        lenient_dotenv = LenientDotEnvSource(
            settings_cls,
            env_file=getattr(dotenv_settings, "env_file", None),
            env_file_encoding=getattr(dotenv_settings, "env_file_encoding", None),
            case_sensitive=getattr(dotenv_settings, "case_sensitive", None),
            env_prefix=getattr(dotenv_settings, "env_prefix", None),
            env_nested_delimiter=getattr(dotenv_settings, "env_nested_delimiter", None),
            env_nested_max_split=getattr(dotenv_settings, "env_nested_max_split", None),
            env_ignore_empty=getattr(dotenv_settings, "env_ignore_empty", None),
            env_parse_none_str=getattr(dotenv_settings, "env_parse_none_str", None),
            env_parse_enums=getattr(dotenv_settings, "env_parse_enums", None),
        )

        return (
            init_settings,
            lenient_env,
            lenient_dotenv,
            file_secret_settings,
        )

    @field_validator("STREAM_SUMMARIZATION_SUPPORTED_FORMATS", mode="before")
    @classmethod
    def parse_formats(cls, value: str | List[str] | Tuple[str, ...]) -> Tuple[str, ...]:
        if isinstance(value, str):
            formats = [item.strip().lower() for item in value.split(",") if item.strip()]
        elif isinstance(value, tuple):
            formats = [str(item).strip().lower() for item in value if str(item).strip()]
        else:
            formats = [str(item).strip().lower() for item in value if str(item).strip()]
        return tuple(sorted(set(formats), key=formats.index))

    STREAM_SUMMARIZATION_SUPPORTED_FORMATS: Tuple[str, ...] = Field(
        default=("txt", "doc", "docx", "pdf", "odt"), description="Allowed document formats"
    )
    STREAM_SUMMARIZATION_MAX_SESSIONS: int = Field(default=100, description="Max sessions per user")
    STREAM_SUMMARIZATION_MAX_DOCUMENTS: int = Field(default=1000, description="Max documents per request")
    STREAM_SUMMARIZATION_MAX_CHARS: int = Field(default=100000, description="Max characters per document")
    STREAM_SUMMARIZATION_URL_PREFIX: str = Field(default="/v1", description="API URL prefix")
    STREAM_SUMMARIZATION_REPORT_TYPES_PATH: str = Field(
        default="/app/report_types.json", description="Path to report types configuration"
    )
    STREAM_SUMMARIZATION_CONNECTION_TIMEOUT: int = Field(
        default=60, description="Timeout for knowledge base model requests"
    )
    STREAM_SUMMARIZATION_DB_TYPE: str = Field(default="postgresql", description="DB type")
    STREAM_SUMMARIZATION_DB_HOST: str = Field(default="db", description="DB host")
    STREAM_SUMMARIZATION_DB_PORT: int = Field(default=5432, description="DB port")
    STREAM_SUMMARIZATION_DB_NAME: str = Field(default="streamsummarization", description="DB name")
    STREAM_SUMMARIZATION_DB_USER: str = Field(default="streamsummary", description="DB user")
    STREAM_SUMMARIZATION_DB_PASSWORD: str | None = Field(
        default=None, description="DB password (optional for local development)"
    )
    OPENAI_API_HOST: str = Field(
        default="http://localhost:8000/v1", description="OpenAI compatible endpoint"
    )
    OPENAI_API_KEY: str | None = Field(default=None, description="API key for universal model")
    OPENAI_MODEL_NAME: str = Field(default="Qwen/Qwen3-4B-AWQ", description="Model name for universal model")
    DEBUG: int = Field(default=0, description="Debug mode flag")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
authorization = "Authorization" if not settings.DEBUG else "user_id"


def _build_db_uri(config: Settings) -> str:
    db_type = (config.STREAM_SUMMARIZATION_DB_TYPE or "").lower()
    if db_type.startswith("sqlite"):
        db_name = config.STREAM_SUMMARIZATION_DB_NAME
        if db_name.startswith("sqlite://"):
            return db_name
        return f"sqlite:///{db_name}"
    if config.STREAM_SUMMARIZATION_DB_PASSWORD is None:
        logger.warning(
            "Database password is not configured; using an in-memory SQLite database for temporary storage."
        )
        return "sqlite:///:memory:"
    return (
        f"{config.STREAM_SUMMARIZATION_DB_TYPE}://{config.STREAM_SUMMARIZATION_DB_USER}:{config.STREAM_SUMMARIZATION_DB_PASSWORD}@"
        f"{config.STREAM_SUMMARIZATION_DB_HOST}:{config.STREAM_SUMMARIZATION_DB_PORT}/{config.STREAM_SUMMARIZATION_DB_NAME}"
    )


FALLBACK_SQLITE_URI = "sqlite:///:memory:"


def _initialize_engine(primary_uri: str) -> tuple[str, Engine]:
    engine = create_engine(primary_uri)
    try:
        metadata.create_all(engine)
        return primary_uri, engine
    except OperationalError as exc:
        logger.warning(
            "Unable to initialize database at %s (%s); falling back to SQLite in-memory store.",
            primary_uri,
            exc,
        )
        engine.dispose()
        fallback_engine = create_engine(FALLBACK_SQLITE_URI)
        metadata.create_all(fallback_engine)
        return FALLBACK_SQLITE_URI, fallback_engine


DB_URI, engine = _initialize_engine(_build_db_uri(settings))
start_mappers()
session_factory = sessionmaker(bind=engine, expire_on_commit=False)


def register_report_templates(session: Session = session_factory()):
    path = Path(settings.STREAM_SUMMARIZATION_REPORT_TYPES_PATH)
    if not path.exists():
        session.close()
        return

    try:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except JSONDecodeError as exc:
            logger.error("Failed to parse report types configuration: %s", exc)
            return

        session.query(ReportTemplate).delete()
        session.commit()

        types = payload.get("types", []) if isinstance(payload, dict) else []
        for report_index, item in enumerate(types):
            report_type = str(item.get("category", "")).strip()
            prompt = str(item.get("prompt", "")).strip()
            if not report_type or not prompt:
                logger.warning(
                    "Skipping report template at index %s due to missing category or prompt",
                    report_index,
                )
                continue

            template = ReportTemplate(
                template_id=str(uuid4()),
                report_index=report_index,
                report_type=report_type,
                prompt=prompt,
            )
            session.add(template)
        session.commit()
    finally:
        session.close()


register_report_templates()