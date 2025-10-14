from __future__ import annotations

from __future__ import annotations

from dataclasses import dataclass

from .base import IDomain


@dataclass
class AnalysisTemplate(IDomain):
    template_id: str
    category_index: int
    category: str
    prompt: str

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "category_index": self.category_index,
            "category": self.category,
            "prompt": self.prompt,
        }
