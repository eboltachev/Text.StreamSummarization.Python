from __future__ import annotations

import logging
import math
import sys
import tempfile
from collections.abc import Iterable, Sequence
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from time import time
from typing import TYPE_CHECKING, Any, Dict, List, Tuple
from uuid import uuid4

import httpx

from stream_summarization.domain.enums import StatusType
from stream_summarization.domain.session import Session
from stream_summarization.domain.user import User
from stream_summarization.services.config import settings
from stream_summarization.services.data.unit_of_work import ReportTemplateUoW, IUoW

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from langchain_openai import ChatOpenAI
else:
    ChatOpenAI = Any


def get_session_list(user_id: str, uow: IUoW) -> List[Dict[str, Any]]:
    logger.info("start get_session_list")
    sessions: List[Dict[str, Any]] = []
    with uow:
        user = uow.users.get(object_id=user_id)
        if not user:
            return []
        for session in user.get_sessions()[: settings.STREAM_SUMMARIZATION_MAX_SESSIONS]:
            sessions.append(_session_to_dict(session, short=True))
    logger.info("finish get_session_list")
    return sessions


def create_new_session(
    user_id: str,
    title: str,
    documents: Sequence[Any],
    report_index: int,
    temporary: bool,
    user_uow: IUoW,
    report_uow: ReportTemplateUoW,
) -> Tuple[str, str, str | None]:
    logger.info("start create_new_session")
    docs = _prepare_doc_texts(documents)
    cleaned_text = [d["text"] for d in docs]
    now = time()
    summary = _generate_report_types(
        text=cleaned_text,
        report_index=report_index,
        report_uow=report_uow,
    )

    title_source = summary.strip() or cleaned_text[0]
    session_id = str(uuid4())
    session = Session(
        session_id=session_id,
        version=0,
        title=title.strip() or title_source[:40],
        text=docs,
        summary=summary,
        inserted_at=now,
        updated_at=now,
    )
    with user_uow:
        user = user_uow.users.get(object_id=user_id)
        if user is None:
            user = User(
                user_id=user_id,
                temporary=temporary,
                started_using_at=now,
                last_used_at=now,
                sessions=[],
            )
            user_uow.users.add(user)
        user.sessions.append(session)
        user.update_time(last_used_at=now)
        user_uow.commit()
    logger.info("finish create_new_session")
    response = session.summary
    return session_id, response, None


def update_session_summarization(
    user_id: str,
    session_id: str,
    documents: Sequence[Any],
    report_index: int,
    version: int,
    user_uow: IUoW,
    report_uow: ReportTemplateUoW,
) -> Tuple[str, str | None]:
    logger.info("start update_session_summarization")
    with user_uow:
        user = user_uow.users.get(object_id=user_id)
        if user is None:
            raise ValueError("User not found")
        session = user.get_session(session_id)
        if session is None:
            raise ValueError("Session not found")
        if int(session.version) != int(version):
            raise ValueError("Version mismatch")
        now = time()

        docs = _prepare_doc_texts(documents)
        cleaned_text = [d["text"] for d in docs]

        summary = _generate_report_types(
            text=cleaned_text,
            report_index=report_index,
            report_uow=report_uow,
        )
        session.update_docs(docs)
        session.summary = summary
        session.version = version + 1
        session.updated_at = now
        user.update_time(last_used_at=now)
        user_uow.commit()
    logger.info("finish update_session_summarization")
    response = session.summary
    return response, None


def update_title_session(
    user_id: str,
    session_id: str,
    title: str,
    version: int,
    user_uow: IUoW,
) -> Dict[str, Any]:
    logger.info("start update_title_session")
    with user_uow:
        user = user_uow.users.get(object_id=user_id)
        if user is None:
            raise ValueError("User not found")
        session = user.get_session(session_id)
        if session is None:
            raise ValueError("Session not found")
        if int(session.version) != int(version):
            raise ValueError("Version mismatch")
        now = time()
        session.title = title
        session.version = version + 1
        session.updated_at = now
        user.update_time(last_used_at=now)
        user_uow.commit()
    logger.info("finish update_title_session")
    return _session_to_dict(session)

def get_session_info(session_id: str, user_id: str, user_uow: IUoW) -> Dict[str, Any]:
    with user_uow:
        user = user_uow.users.get(object_id=user_id)
        if user is None:
            raise ValueError("User not found")
        session = user.get_session(session_id)
        if session is None:
            raise ValueError("Session not found")
        return _session_to_dict(session)


def download_session_file(session_id: str, format: str, user_id: str, uow: IUoW) -> Path:
    with uow:
        user = uow.users.get(object_id=user_id)
        if user is None:
            raise ValueError("User not found")
        session = user.get_session(session_id)
        if session is None:
            raise ValueError("Session not found")
        title = session.title or "Untitled session"
        doc_lines = []
        for i, d in enumerate(session.doc_texts, 1):
            meta = " | ".join(filter(None, [d.get("title", ""), d.get("source", ""), d.get("date", ""), d.get("url", "")]))
            header = f"[{i}] {meta}".strip(" |")
            doc_lines.append(header if header else f"[{i}]")
            doc_lines.append(d.get("text", ""))
        query = "\n\n".join(doc_lines).strip()
        summary = session.summary or ""

    normalized_format = format.lower()
    if normalized_format == "pdf":
        import os

        from fpdf import FPDF

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as fp:
            pdf = FPDF()
            pdf.add_page()
            font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")
            pdf.add_font("DejaVu", "", font_path, uni=True)
            pdf.set_font("DejaVu", "", 12)
            pdf.cell(0, 10, f"Session: {title}", ln=1)
            pdf.ln(5)
            pdf.set_font("DejaVu", "", 11)
            pdf.multi_cell(0, 8, f"Documents:\n{query}")
            pdf.ln(2)
            pdf.multi_cell(0, 8, f"Summary:\n{summary}")
            pdf.output(fp.name)
            return Path(fp.name)
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{format}") as fp:
            with open(fp.name, "w", encoding="utf-8") as f:
                f.write(f"{query} : {summary}")
            return Path(fp.name)


def delete_exist_session(session_id: str, user_id: str, uow: IUoW) -> StatusType:
    logger.info("start delete_exist_session")
    with uow:
        user = uow.users.get(object_id=user_id)
        if user is None:
            return StatusType.ERROR
        status = user.delete_session(session_id)
        if status:
            uow.commit()
            logger.info("session deleted")
            return StatusType.SUCCESS
    logger.info("finish delete_exist_session")
    return StatusType.NOT_FOUND


def search_similarity_sessions(user_id: str, query: str, uow: IUoW) -> List[Dict[str, Any]]:
    logger.info("start search_similarity_sessions")
    if not query or not query.strip():
        raise ValueError("Request is empty")
    results: List[Dict[str, Any]] = []
    with uow:
        user = uow.users.get(object_id=user_id)
        if user is None:
            raise ValueError("User does not have any sessions")
        for session in user.get_sessions():
            parts = [session.title or "", session.summary or ""]
            # Документы: учитываем title/text/source/url/date
            for d in session.doc_texts:
                parts.extend([
                    d.get("title", ""),
                    d.get("text", ""),
                    d.get("source", ""),
                    d.get("url", ""),
                    d.get("date", ""),
                ])
            text_blob = " | ".join(part for part in parts if part)
            score = _match_score(text_blob, query)
            if score <= 0:
                continue
            results.append((_session_to_dict(session, short=True), score))
    results.sort(key=lambda item: item[1], reverse=True)
    results = results[:settings.STREAM_SUMMARIZATION_MAX_SESSIONS]
    results = [result[0] for result in results]
    logger.info(f"finish search_similarity_sessions, found={len(results)}")
    return results


def _normalize_text(value: str) -> str:
    if not value:
        return ""
    return " ".join(value.lower().split())


def _match_score(text_blob: str, query: str) -> float:
    normalized_blob = _normalize_text(text_blob)
    normalized_query = _normalize_text(query)
    if not normalized_blob or not normalized_query:
        return 0.0
    matcher_score = SequenceMatcher(None, normalized_blob, normalized_query).ratio()
    blob_tokens = set(normalized_blob.split())
    query_tokens = set(normalized_query.split())
    if not query_tokens:
        return 0.0
    overlap_score = len(blob_tokens & query_tokens) / len(query_tokens)
    return float(max(matcher_score, overlap_score))


@lru_cache(maxsize=1)
def _get_context_window(model_name: str) -> int:
    """Fetch the context window for the configured model."""

    fallback_window = 4096
    base_url = settings.OPENAI_API_HOST.rstrip("/")
    model_path = f"{base_url}/models/{model_name}"
    try:
        with httpx.Client(timeout=settings.STREAM_SUMMARIZATION_CONNECTION_TIMEOUT) as client:
            response = client.get(model_path)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:  # pragma: no cover - network error path
        logger.warning("Failed to fetch model metadata for context window: %s", exc)
        return fallback_window

    def _extract_from_item(item: Dict[str, Any]) -> int | None:
        for key in ("context_window", "context_length", "max_input_tokens", "max_context", "max_tokens"):
            value = item.get(key)
            if isinstance(value, int) and value > 0:
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
        return None

    if isinstance(payload, dict):
        direct_value = _extract_from_item(payload)
        if direct_value:
            return direct_value
        data = payload.get("data")
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("id") == model_name:
                    extracted = _extract_from_item(item)
                    if extracted:
                        return extracted
    return fallback_window


def _estimate_token_length(text: str, context_window: int) -> int:
    if not text:
        return 0
    # Approximate 4 characters per token as a conservative heuristic
    estimated = max(1, math.ceil(len(text) / 4))
    # Guard against overflow for exceptionally long strings
    return min(estimated, len(text)) if context_window else estimated


def _apply_map_reduce(text: str, context_window: int) -> str:
    try:
        from langchain.chains.summarize import load_summarize_chain  # type: ignore
        from langchain.docstore.document import Document  # type: ignore
        from langchain.text_splitter import RecursiveCharacterTextSplitter  # type: ignore
    except ModuleNotFoundError:
        logger.warning("LangChain is not installed; skipping map-reduce summarization and returning the original text.")
        return text

    chunk_size = max(200, context_window * 4)
    chunk_overlap = max(50, int(chunk_size * 0.1))
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    documents = [Document(page_content=chunk) for chunk in splitter.split_text(text)]
    if len(documents) <= 1:
        return text
    llm = _build_llm()
    chain = load_summarize_chain(llm, chain_type="map_reduce")
    summary = chain.run(documents)
    return summary.strip() or text


def _sanitize_prompt_text(text: str) -> str:
    """Ensure the text passed to the LLM fits inside the model context window."""

    if not text:
        return ""

    context_window = _get_context_window(settings.OPENAI_MODEL_NAME)
    if context_window <= 0:
        return text

    safe_window = max(512, int(context_window * 0.8))
    estimated_tokens = _estimate_token_length(text, context_window)
    if estimated_tokens <= safe_window:
        return text

    logger.info("Condensing prompt text due to context window overflow")
    condensed = _apply_map_reduce(text, context_window)
    condensed = condensed or text

    # If condensation is still too large, truncate to the safe character budget
    if _estimate_token_length(condensed, context_window) > safe_window:
        char_budget = safe_window * 4
        condensed = condensed[:char_budget].strip()

    return condensed or text[: safe_window * 4]


def _extract_message_content(result: Any) -> str:
    """Normalize LLM responses to plain text and condense oversized payloads."""

    if result is None:
        return ""
    if isinstance(result, str):
        text = result.strip()
    else:
        content = getattr(result, "content", result)
        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(str(item.get("text", "")))
                else:
                    parts.append(str(item))
            text = "".join(parts).strip()
        else:
            text = str(content).strip()

    if not text:
        return ""

    context_window = _get_context_window(settings.OPENAI_MODEL_NAME)
    if _estimate_token_length(text, context_window) > context_window:
        logger.info("Applying map-reduce summarization due to context window overflow")
        return _apply_map_reduce(text, context_window)

    return text


def _normalize_label(output: str, candidates: List[str]) -> str:
    """Pick the most suitable label from candidates based on LLM output."""

    if not candidates:
        return output.strip()
    normalized_output = output.strip().lower()
    for candidate in candidates:
        if candidate.lower() in normalized_output:
            return candidate
    return candidates[0]


def _load_prompt(
    report_index: int,
    report_uow: ReportTemplateUoW,
) -> str:
    with report_uow:
        templates = report_uow.templates.list_by_report_types(report_index)
        if not templates:
            raise ValueError("Prompt template not found for the given report types")

        template = min(templates, key=lambda item: item.template_id)
        prompt = template.prompt

    return prompt


def _build_llm() -> "ChatOpenAI":
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured. Set the environment variable to use the LLM client.")
    try:
        from langchain_openai import ChatOpenAI as _ChatOpenAI  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError(
            "langchain-openai is required to build the LLM client. Install the 'langchain-openai' package."
        ) from exc

    return _ChatOpenAI(
        base_url=settings.OPENAI_API_HOST,
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_MODEL_NAME,
        temperature=0,
        timeout=settings.STREAM_SUMMARIZATION_CONNECTION_TIMEOUT,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )

def _prepare_doc_texts(chunks: Iterable[Any]) -> List[Dict[str, str]]:
    """
    Принимает List[DocText | dict | str] и возвращает нормализованный List[dict].
    """
    if isinstance(chunks, (str, bytes)) or not isinstance(chunks, Iterable):
        raise ValueError("Текст должен быть передан списком DocText/объектов")

    # Лимит на количество документов
    max_docs = settings.STREAM_SUMMARIZATION_MAX_DOCUMENTS
    items = list(chunks)
    if len(items) > max_docs:
        raise ValueError(f"Превышен лимит документов: {len(items)} > {max_docs}")

    docs: List[Dict[str, str]] = []
    max_chars = settings.STREAM_SUMMARIZATION_MAX_CHARS
    for item in items:
        # Поддержка Pydantic v2 (model_dump) и v1 (dict)
        if hasattr(item, "model_dump"):
            item = item.model_dump()  # type: ignore[attr-defined]
        elif hasattr(item, "dict"):
            item = item.dict()  # type: ignore[attr-defined]

        if isinstance(item, dict):
            txt = str(item.get("text", "")).strip()
            if not txt:
                continue
            if len(txt) > max_chars:
                raise ValueError(f"Длина одного документа превышает лимит {max_chars} символов")
            docs.append({
                "text": txt,
                "title": str(item.get("title", "")).strip(),
                "url": str(item.get("url", "")).strip(),
                "date": str(item.get("date", "")).strip(),
                "source": str(item.get("source", "")).strip(),
            })
        else:
            s = str(item).strip()
            if s:
                if len(s) > max_chars:
                    raise ValueError(f"Длина одного документа превышает лимит {max_chars} символов")
                docs.append({"text": s, "title": "", "url": "", "date": "", "source": ""})

    if not docs:
        raise ValueError("Передан пустой текст для суммаризации")
    return docs


def _generate_report_types(
    text: Sequence[str],
    report_index: int,
    report_uow: ReportTemplateUoW,
) -> str:
    prompt = _load_prompt(report_index, report_uow)
    llm: ChatOpenAI | None = None
    if llm is None:
        llm = _build_llm()
    combined_text = "\n\n".join(text)
    sanitized_text = _sanitize_prompt_text(combined_text)
    message_prompt = f"{prompt.strip()}\n\nТексты:\n{sanitized_text.strip()}"
    response = _extract_message_content(llm.invoke(message_prompt))
    return response


def _session_to_dict(session: Session, short: bool = False) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "session_id": session.session_id,
        "version": session.version,
        "title": session.title,
        "documents": session.doc_texts,
        "summary": session.summary,
        "inserted_at": session.inserted_at,
        "updated_at": session.updated_at,
    }
    if short:
        payload.pop("documents", None)
        payload.pop("summary", None)
    return payload

