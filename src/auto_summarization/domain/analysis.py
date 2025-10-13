from __future__ import annotations

from typing import Optional

from .base import IDomain


class AnalysisTemplate(IDomain):
    def __init__(
        self,
        template_id: str,
        category_index: int,
        category: str,
        prompt: str,
    ) -> None:
        self.template_id = template_id
        self.category = category
        self.prompt = prompt

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "choice_index": self.choice_index,
            "category": self.category,
            "prompt": self.prompt,
        }
