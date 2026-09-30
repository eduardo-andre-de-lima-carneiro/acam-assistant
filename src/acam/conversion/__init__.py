"""Format conversion: every supported format -> canonical Markdown.

The analytical engine never reads the original file; it only sees the output
of :func:`convert`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class ConversionResult:
    markdown: str
    converter: str
    # Embedded metadata found in the file itself (e.g. PDF docinfo). Treated as
    # candidate metadata only.
    embedded_metadata: dict = field(default_factory=dict)
    page_count: int | None = None
    warnings: list[str] = field(default_factory=list)


class ConversionError(Exception):
    pass


def _converters() -> dict[str, Callable[[Path], ConversionResult]]:
    from . import docx_converter, html_converter, pdf_converter, text_converter

    return {
        "pdf": pdf_converter.convert,
        "docx": docx_converter.convert,
        "html": html_converter.convert,
        "htm": html_converter.convert,
        "txt": text_converter.convert_txt,
        "md": text_converter.convert_md,
        "markdown": text_converter.convert_md,
    }


def supported_formats() -> list[str]:
    return sorted(_converters())


def detect_format(path: Path) -> str:
    return path.suffix.lower().lstrip(".")


def convert(path: Path) -> ConversionResult:
    fmt = detect_format(path)
    converter = _converters().get(fmt)
    if converter is None:
        raise ConversionError(
            f"Unsupported format '.{fmt}'. Supported: {', '.join(supported_formats())}")
    try:
        result = converter(path)
    except ConversionError:
        raise
    except Exception as exc:  # third-party parsers raise many exception types
        raise ConversionError(f"Failed to convert {path.name}: {exc}") from exc
    result.markdown = normalize_markdown(result.markdown)
    return result


def normalize_markdown(md: str) -> str:
    lines = [ln.rstrip() for ln in md.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    out: list[str] = []
    blank = 0
    for ln in lines:
        if ln.strip():
            blank = 0
            out.append(ln)
        else:
            blank += 1
            if blank == 1:
                out.append("")
    return "\n".join(out).strip() + "\n"
