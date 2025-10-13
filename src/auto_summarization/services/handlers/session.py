import logging
import sys
from difflib import SequenceMatcher
from time import time
from typing import Any, Dict, Iterable, List, Tuple
from uuid import uuid4

from auto_summarization.domain.enums import StatusType
from auto_summarization.domain.session import Session
from auto_summarization.domain.user import User
from auto_summarization.services.config import settings
from auto_summarization.services.data.unit_of_work import AnalysisTemplateUoW, IUoW

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


def get_session_list(user_id: str, uow: IUoW) -> List[Dict[str, Any]]:
    logger.info("start get_session_list")
    sessions: List[Dict[str, Any]] = []
    with uow:
        user = uow.users.get(object_id=user_id)
        if not user:
            return []
        for session in user.get_sessions()[: settings.AUTO_SUMMARIZATION_MAX_SESSIONS]:
            sessions.append(_session_to_dict(session))
    logger.info("finish get_session_list")
    return sessions


def create_new_session(
    user_id: str,
    text: List[str],
    category_index: int,
    temporary: bool,
    user_uow: IUoW,
    analysis_uow: AnalysisTemplateUoW,
) -> Tuple[Dict[str, Any], str | None]:
    logger.info("start create_new_session")
    now = time()
    combined_text = _combine_texts(text)
    summary = _generate_analysis(
        text=combined_text,
        category_index=category_index,
        analysis_uow=analysis_uow,
    )

    session = Session(
        session_id=str(uuid4()),
        version=0,
        title=(summary[:40] if summary else combined_text[:40]),
        text=combined_text,
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
    response = _build_session_content(session.summary)
    return response, None


def update_session_summarization(
    user_id: str,
    session_id: str,
    text: List[str],
    category_index: int,
    version: int,
    user_uow: IUoW,
    analysis_uow: AnalysisTemplateUoW,
) -> Tuple[Dict[str, Any], str | None]:
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

        combined_text = _combine_texts(text)
        summary = _generate_analysis(
            text=combined_text,
            category_index=category_index,
            analysis_uow=analysis_uow,
        )
        session.summary = summary
        session.text = combined_text
        session.version = version + 1
        session.updated_at = now
        user.update_time(last_used_at=now)
        user_uow.commit()
    logger.info("finish update_session_summarization")
    response = _build_session_content(session.summary)
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
    return StatusType.ERROR


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
            session_query = getattr(session, "query", None)
            if session_query:
                parts.append(session_query or "")
            text_value = getattr(session, "text", "")
            if text_value:
                parts.append(text_value)
            translation_value = getattr(session, "summary", None)
            if translation_value:
                parts.append(translation_value)
            text_blob = " | ".join(part for part in parts if part)
            score = _match_score(text_blob, query)
            if score <= 0:
                continue
            results.append(
                {
                    "title": session.title or "",
                    "query": session_query or text_value or "",
                    "summary": translation_value or "",
                    "inserted_at": float(session.inserted_at),
                    "session_id": session.session_id,
                    "score": float(score),
                }
            )
    results.sort(key=lambda item: item["score"], reverse=True)
    limited_results = results[:20]
    logger.info(f"finish search_similarity_sessions, found={len(limited_results)}")
    return limited_results


def _combine_texts(texts: Iterable[str]) -> str:
    cleaned_parts = [str(part).strip() for part in texts if isinstance(part, str) and part.strip()]
    if not cleaned_parts:
        raise ValueError("Текст для суммаризации пуст")
    return "\n\n".join(cleaned_parts)


def _build_session_content(summary: str) -> Dict[str, str | None]:
    normalized = (summary or "").strip()
    short = normalized[:200] if normalized else None
    return {
        "entities": None,
        "sentiments": None,
        "classifications": None,
        "short_summary": short,
        "full_summary": normalized or None,
    }


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


def _load_prompt(
    category_index: int,
    analysis_uow: AnalysisTemplateUoW,
) -> str:
    with analysis_uow:
        template = analysis_uow.templates.get_by_category(category_index)
    if template is None:
        raise ValueError("Неизвестная категория анализа")
    return template.prompt or ""


def _generate_analysis(
    text: str,
    category_index: int,
    analysis_uow: AnalysisTemplateUoW,
) -> str:
    prompt = (_load_prompt(category_index, analysis_uow) or "").strip()
    normalized_text = " ".join(text.split())
    if not normalized_text:
        raise ValueError("Текст для суммаризации пуст")
    preview = normalized_text[:500]
    if prompt:
        return f"{prompt} Ответ: {preview}".strip()
    return preview


def _session_to_dict(session: Session) -> Dict[str, Any]:
    return {
        "session_id": session.session_id,
        "version": session.version,
        "title": session.title,
        "text": session.text,
        "content": _build_session_content(session.summary),
        "inserted_at": session.inserted_at,
        "updated_at": session.updated_at,
    }
