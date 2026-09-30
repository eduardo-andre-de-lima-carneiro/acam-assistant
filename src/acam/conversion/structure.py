"""Heuristics shared by converters that receive unstructured text (PDF, TXT).

Only *recognized academic section names* are promoted to headings. The
converter never invents a title or headings it cannot justify.
"""

from __future__ import annotations

import re

SECTION_NAMES = (
    "abstract", "resumo", "resumen", "résumé", "keywords", "key words", "palavras-chave",
    "introduction", "introdução", "background", "related work", "literature review",
    "theoretical framework", "referencial teórico", "fundamentação teórica",
    "method", "methods", "methodology", "materials and methods", "metodologia",
    "research design", "results", "resultados", "findings", "discussion", "discussão",
    "results and discussion", "conclusion", "conclusions", "conclusão",
    "considerações finais", "final remarks", "limitations", "limitações",
    "future work", "acknowledgments", "acknowledgements", "agradecimentos",
    "references", "referências", "bibliography", "appendix", "apêndice", "anexo",
)

_NUMBERED = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[IVX]+\.)\s+(.+)$")


def heading_level(line: str) -> int | None:
    """Return a Markdown heading level if ``line`` looks like a section heading."""
    text = line.strip()
    if not text or len(text) > 80 or text.endswith((".", ",", ";")) and not _NUMBERED.match(text):
        return None
    m = _NUMBERED.match(text)
    core = (m.group(1) if m else text).strip().rstrip(":").lower()
    if core in SECTION_NAMES:
        if m and "." in text.split()[0].rstrip("."):
            return 3  # e.g. "2.1 Data collection" style subsection numbers
        return 2
    return None


def is_keywords_line(line: str) -> bool:
    return bool(re.match(r"^\s*(key\s*words|keywords|palavras-chave)\s*[:—-]", line, re.I))


def structure_text(text: str) -> str:
    """Turn raw extracted text into Markdown paragraphs with recognized headings."""
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # join hyphenated line breaks
    lines = text.split("\n")
    lengths = sorted(len(ln.strip()) for ln in lines if ln.strip())
    typical = lengths[int(len(lengths) * 0.8)] if lengths else 80

    out: list[str] = []
    para: list[str] = []
    # Before the first section heading (title page / front matter) each line is
    # usually a separate unit: title, author list, affiliation, journal line.
    in_front_matter = True
    front_lines = 0

    def flush() -> None:
        if para:
            out.append(" ".join(para))
            out.append("")
            para.clear()

    for raw in lines:
        line = raw.strip()
        if not line:
            flush()
            continue
        if line.startswith("<!-- page:"):
            flush()
            out.extend([line, ""])
            continue
        level = heading_level(line)
        if level:
            in_front_matter = False
            flush()
            out.extend(["#" * level + " " + line.rstrip(":"), ""])
            continue
        if is_keywords_line(line):
            flush()
            out.extend([line, ""])
            continue
        para.append(line)
        if in_front_matter and front_lines < 25:
            front_lines += 1
            flush()
            continue
        # A short line that ends a sentence usually closes a paragraph.
        if line.endswith((".", "?", "!", ":")) and len(line) < 0.7 * typical:
            flush()
    flush()
    return "\n".join(out)
