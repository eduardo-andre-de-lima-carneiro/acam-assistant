from __future__ import annotations

import re
from pathlib import Path

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

from . import ConversionResult
from .structure import heading_level


def _escape_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _table_to_md(table: Table) -> str:
    rows = [[_escape_cell(c.text) for c in row.cells] for row in table.rows]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def _paragraph_to_md(p: Paragraph) -> str:
    text = p.text.strip()
    if not text:
        return ""
    style = (p.style.name if p.style is not None else "") or ""
    if style == "Title":
        return "# " + text
    m = re.match(r"Heading (\d)", style)
    if m:
        # Document headings start at H2; H1 is reserved for the title.
        return "#" * min(int(m.group(1)) + 1, 6) + " " + text
    if style.startswith("List"):
        return ("1. " if "Number" in style else "- ") + text
    level = heading_level(text)
    if level:
        return "#" * level + " " + text.rstrip(":")
    return text


def convert(path: Path) -> ConversionResult:
    document = docx.Document(str(path))
    blocks: list[str] = []
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            md = _paragraph_to_md(Paragraph(child, document))
        elif tag == "tbl":
            md = _table_to_md(Table(child, document))
        else:
            continue
        if md:
            blocks.append(md)

    embedded = {}
    props = document.core_properties
    if props.title and props.title.strip():
        embedded["title"] = props.title.strip()
    if props.author and props.author.strip():
        embedded["authors"] = props.author.strip()

    return ConversionResult(markdown="\n\n".join(blocks), converter="python-docx",
                            embedded_metadata=embedded)
