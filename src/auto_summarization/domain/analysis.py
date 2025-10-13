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
        model_type: Optional[str] = None,
    ) -> None:
        self.template_id = template_id
        self.choice_index = choice_index
        self.category = category
        self.prompt = prompt
        self.model_type = model_type

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "choice_index": self.choice_index,
            "category": self.category,
            "prompt": self.prompt,
            "model_type": self.model_type,
        }
