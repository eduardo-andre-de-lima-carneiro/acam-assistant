from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from . import ConversionError, ConversionResult
from .structure import structure_text


def convert(path: Path) -> ConversionResult:
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ConversionError(f"{path.name} is encrypted") from exc

    parts: list[str] = []
    warnings: list[str] = []
    empty_pages = 0
    for number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if not text.strip():
            empty_pages += 1
        # Page markers keep extracted claims traceable to a page number.
        parts.append(f"<!-- page: {number} -->\n{text}")

    if empty_pages:
        warnings.append(f"{empty_pages} page(s) had no extractable text (scanned images need OCR)")

    embedded = {}
    info = reader.metadata
    if info:
        if info.title and info.title.strip():
            embedded["title"] = info.title.strip()
        if info.author and info.author.strip():
            embedded["authors"] = info.author.strip()

    return ConversionResult(
        markdown=structure_text("\n\n".join(parts)),
        converter="pypdf",
        embedded_metadata=embedded,
        page_count=len(reader.pages),
        warnings=warnings,
    )
