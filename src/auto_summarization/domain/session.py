from __future__ import annotations

import json
from typing import Iterable, List

from .base import IDomain


class Session(IDomain):
    def __init__(
        self,
        session_id: str,
        version: int,
        title: str,
        text: Iterable[str],
        summary: str,
        inserted_at: float,
        updated_at: float,
    ) -> None:
        self.session_id = session_id
        self.version = version
        self.title = title
        self.update_text(text)
        self.summary = summary
        self.inserted_at = inserted_at
        self.updated_at = updated_at

    def __str__(self) -> str:
        preview_source = self.title or " ".join(self.text_chunks)
        return preview_source[:40]

    @property
    def text_chunks(self) -> List[str]:
        raw = getattr(self, "text", "")
        if isinstance(raw, list):
            return [str(item) for item in raw]
        if not isinstance(raw, str) or not raw:
            return []
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return [raw]
        if isinstance(payload, list):
            return [str(item) for item in payload]
        return [str(payload)]

    def update_text(self, text: Iterable[str]) -> None:
        cleaned = [str(item).strip() for item in text if str(item).strip()]
        self.text = json.dumps(cleaned, ensure_ascii=False)
