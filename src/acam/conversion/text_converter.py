from __future__ import annotations

from pathlib import Path

from . import ConversionResult
from .structure import structure_text


def _read(path: Path) -> tuple[str, list[str]]:
    data = path.read_bytes()
    try:
        return data.decode("utf-8-sig"), []
    except UnicodeDecodeError:
        return data.decode("latin-1"), ["File was not valid UTF-8; decoded as Latin-1"]


def convert_txt(path: Path) -> ConversionResult:
    text, warnings = _read(path)
    return ConversionResult(markdown=structure_text(text), converter="text", warnings=warnings)


def convert_md(path: Path) -> ConversionResult:
    text, warnings = _read(path)
    return ConversionResult(markdown=text, converter="markdown-passthrough", warnings=warnings)
