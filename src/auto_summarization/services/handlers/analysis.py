from __future__ import annotations

import io
import json
import os
import tempfile
from collections import OrderedDict
from json import JSONDecodeError
from pathlib import Path
from typing import List

from auto_summarization.services.config import settings
from auto_summarization.services.data.unit_of_work import AnalysisTemplateUoW


def extract_text(content: bytes, extension: str) -> str:
    ext = extension.lower().lstrip(".")
    if ext not in settings.AUTO_SUMMARIZATION_SUPPORTED_FORMATS:
        raise ValueError("Unsupported document format")

    if ext == "txt":
        return content.decode("utf-8", errors="ignore")

    if ext == "docx":
        try:
            from docx import Document  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency missing guard
            raise RuntimeError("Библиотека python-docx не установлена") from exc
        document = Document(io.BytesIO(content))
        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        return "\n".join(paragraphs)

    if ext == "pdf":
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency missing guard
            raise RuntimeError("Библиотека pypdf не установлена") from exc
        reader = PdfReader(io.BytesIO(content))
        fragments: List[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            fragments.append(text.strip())
        return "\n".join(fragment for fragment in fragments if fragment)

    if ext == "odt":
        try:
            from odf import teletype  # type: ignore
            from odf.opendocument import load  # type: ignore
            from odf.text import P  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency missing guard
            raise RuntimeError("Библиотека odfpy не установлена") from exc
        document = load(io.BytesIO(content))
        paragraphs = [
            teletype.extractText(node).strip()
            for node in document.getElementsByType(P)
            if teletype.extractText(node).strip()
        ]
        return "\n".join(paragraphs)

    if ext == "doc":
        try:
            import textract  # type: ignore
        except Exception:
            return (
                "Документ формата .doc успешно получен, однако автоматическое извлечение текста недоступно. "
                "Пожалуйста, сохраните файл в формате DOCX и повторите загрузку."
            )
        with tempfile.NamedTemporaryFile(delete=False, suffix=".doc") as tmp_file:
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        try:
            raw = textract.process(tmp_file_path)
            return raw.decode("utf-8", errors="ignore")
        finally:  # pragma: no cover - system cleanup
            try:
                os.remove(tmp_file_path)
            except OSError:
                pass

    raise ValueError("Unsupported document format")


def _load_report_types_from_file() -> List[str]:
    path = Path(settings.AUTO_SUMMARIZATION_ANALYZE_TYPES_PATH)
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, JSONDecodeError):
        return []

    if not isinstance(payload, dict):
        return []

    report_types: List[str] = []
    for item in payload.get("types", []):
        if not isinstance(item, dict):
            continue
        category = str(item.get("category", "")).strip()
        prompt = str(item.get("prompt", "")).strip()
        if not category or not prompt:
            continue
        report_types.append(category)
    return report_types


def get_analyze_types(
    uow: AnalysisTemplateUoW,
) -> List[str]:
    category_map: "OrderedDict[int, str]" = OrderedDict()

    with uow:
        templates = sorted(uow.templates.list(), key=lambda item: item.category_index)

        for template in templates:
            category_map.setdefault(template.category_index, template.category)

    report_types = _load_report_types_from_file() or list(category_map.values())
    return report_types
