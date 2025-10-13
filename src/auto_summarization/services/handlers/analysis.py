from __future__ import annotations

import io
import os
import tempfile
from typing import Dict, List, Tuple

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

def get_analyze_types(uow: AnalysisTemplateUoW) -> str:
    with uow:
        prompt = # to-do
    return prompt