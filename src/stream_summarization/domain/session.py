from __future__ import annotations

import json
from typing import Iterable, List, Dict, Any, Sequence, Mapping

from .base import IDomain


class Session(IDomain):
    def __init__(
        self,
        session_id: str,
        version: int,
        title: str,
        text: Iterable[Any],
        summary: str,
        inserted_at: float,
        updated_at: float,
    ) -> None:
        self.session_id = session_id
        self.version = version
        self.title = title
        self.update_docs(text)
        self.summary = summary
        self.inserted_at = inserted_at
        self.updated_at = updated_at


    def __str__(self) -> str:
        first = ""
        docs = self.doc_texts
        if docs:
            first = (docs[0].get("title") or docs[0].get("text") or "")[:40]
        preview_source = self.title or first
        return (preview_source or "").strip()[:40]

    @property
    def doc_texts(self) -> List[Dict[str, str]]:
        """
        Возвращает нормализованный List[DocText] как список словарей:
        {text, title, url, date, source}
        """
        raw = getattr(self, "text", "")
        if isinstance(raw, list):
            payload = raw
        elif isinstance(raw, str) and raw:
            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                payload = [{"text": str(raw)}]
        else:
            payload = []

        out: List[Dict[str, str]] = []
        for item in payload:
            if isinstance(item, Mapping):
                text = str(item.get("text", "")).strip()
                if not text:
                    continue
                out.append({
                    "text": text,
                    "title": str(item.get("title", "")).strip(),
                    "url": str(item.get("url", "")).strip(),
                    "date": str(item.get("date", "")).strip(),
                    "source": str(item.get("source", "")).strip(),
                })
            else:
                s = str(item).strip()
                if s:
                    out.append({"text": s, "title": "", "url": "", "date": "", "source": ""})
        return out

    @property
    def text_chunks(self) -> List[str]:
        """Legacy: только тексты для обратной совместимости."""
        return [d["text"] for d in self.doc_texts]

    def update_docs(self, docs: Iterable[Any]) -> None:
        """
        Принимает List[DocText | dict | str] и сохраняет JSON.
        """
        norm: List[Dict[str, str]] = []
        for item in docs:
            if isinstance(item, Mapping):
                txt = str(item.get("text", "")).strip()
                if not txt:
                    continue
                norm.append({
                    "text": txt,
                    "title": str(item.get("title", "")).strip(),
                    "url": str(item.get("url", "")).strip(),
                    "date": str(item.get("date", "")).strip(),
                    "source": str(item.get("source", "")).strip(),
                })
            else:
                s = str(item).strip()
                if s:
                    norm.append({"text": s, "title": "", "url": "", "date": "", "source": ""})
        self.text = json.dumps(norm, ensure_ascii=False)
