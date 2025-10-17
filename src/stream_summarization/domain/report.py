from __future__ import annotations

from dataclasses import dataclass

from .base import IDomain


@dataclass
class ReportTemplate(IDomain):
    template_id: str
    report_index: int
    report_type: str
    prompt: str

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "report_index": self.report_index,
            "report_type": self.report_type,
            "prompt": self.prompt,
        }
