"""Rule-based candidate metadata extraction from canonical Markdown.

Everything returned here is *candidate* metadata (``source="extracted"``,
``validated=False``). When a value cannot be found it stays ``None`` — the
extractor never guesses.
"""

from __future__ import annotations

import re

from .. import models
from ..markdown_doc import body_text, find_section, parse_sections
from ..conversion.structure import heading_level
from ..references.abnt import is_institution

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>)\]]+)", re.I)
URL_RE = re.compile(r"https?://[^\s)>\]]+")
YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
KEYWORDS_RE = re.compile(r"^\s*\**(key\s*words|keywords|palavras-chave|index terms)\**\s*[:—.-]\s*(.+)$",
                         re.I | re.M)
ISSN_JOURNAL_RE = re.compile(r"^(?P<journal>[A-Z][\w&,.' -]{3,80}?),?\s+(?:v\.|vol\.?|volume)\s*(?P<vol>\d+)",
                             re.I | re.M)
ISSUE_RE = re.compile(r"\b(?:n\.|no\.|issue|number)\s*(\d+)", re.I)
PAGES_RE = re.compile(r"\b(?:p\.|pp\.|pages)\s*(\d+\s*[-–]\s*\d+)", re.I)

_NOT_AUTHOR = re.compile(
    r"(universi|institut|department|departamento|faculdade|faculty|school|college|abstract|resumo|"
    r"@|http|doi|journal|vol\.|received|accepted|copyright|©|\d{3,})", re.I)


def _clean(text: str) -> str:
    return re.sub(r"[*_`]+", "", text).strip()


def _title(sections, lines: list[str], embedded: dict) -> tuple[str | None, float, int | None]:
    """Return (title, confidence, index of title line in ``lines``)."""
    for s in sections:
        if s.level == 1:
            idx = next((i for i, ln in enumerate(lines) if ln.strip().lstrip("# ").strip() == s.title), None)
            return _clean(s.title), 0.85, idx
    # First substantive line that is not a recognized section heading.
    for i, ln in enumerate(lines[:30]):
        text = _clean(ln.strip().lstrip("#").strip())
        if (text and not text.startswith("<!--") and 15 <= len(text) <= 250
                and not heading_level(text) and not DOI_RE.search(text) and not URL_RE.search(text)):
            if embedded.get("title") and embedded["title"].lower() in text.lower():
                return text, 0.8, i
            return text, 0.5, i
    if embedded.get("title"):
        return embedded["title"], 0.6, None
    return None, 0.0, None


def _split_names(line: str) -> list[str]:
    line = re.sub(r"[\d*†‡§¹²³⁴⁵⁶⁷⁸⁹]+", "", _clean(line))
    parts = re.split(r"\s*(?:,|;|\band\b|\be\b|&)\s*", line)
    names = []
    for p in parts:
        p = p.strip(" .")
        tokens = p.split()
        if 2 <= len(tokens) <= 5 and all(t[0].isupper() for t in tokens if t[0].isalpha()):
            names.append(p)
    return names


def _authors(lines: list[str], title_idx: int | None, embedded: dict) -> tuple[list[str], float]:
    if embedded.get("authors"):
        if is_institution(embedded["authors"]):
            return [embedded["authors"].strip()], 0.6
        names = _split_names(embedded["authors"])
        if names:
            return names, 0.75
    if title_idx is None:
        return [], 0.0
    for ln in lines[title_idx + 1:title_idx + 6]:
        text = ln.strip()
        if not text or text.startswith("<!--"):
            continue
        if text.startswith("#") or heading_level(text.lstrip("# ")):
            break
        if len(text) > 200 or _NOT_AUTHOR.search(text):
            continue
        names = _split_names(text)
        if names:
            return names, 0.45
    return [], 0.0


def _abstract(sections) -> str | None:
    s = find_section(sections, "abstract", "resumo", "resumen", "summary")
    if not s:
        return None
    paras = [p for p in s.paragraphs if not KEYWORDS_RE.match(p)]
    return "\n\n".join(paras).strip() or None


def extract_metadata(markdown: str, embedded: dict | None = None) -> tuple[dict, dict]:
    """Return ``(metadata, abstract_info)`` built from provenance fields."""
    embedded = embedded or {}
    meta = models.empty_metadata()
    sections = parse_sections(markdown)
    text = body_text(markdown)
    lines = text.split("\n")
    head = "\n".join(lines[:80])  # front matter area for year/journal heuristics

    def put(name: str, value, confidence: float) -> None:
        if value not in (None, "", []):
            meta[name] = models.field(value, "extracted", round(confidence, 2))

    title, conf, title_idx = _title(sections, lines, embedded)
    put("title", title, conf)

    authors, conf = _authors(lines, title_idx, embedded)
    put("authors", authors, conf)

    doi = embedded.get("doi")
    if not doi and (m := DOI_RE.search(text)):
        doi = m.group(1)
    if doi:
        put("doi", doi.rstrip(".,;"), 0.95)

    # Prefer years in the front matter; fall back to nothing rather than the
    # most frequent year in the reference list.
    if years := YEAR_RE.findall(head):
        put("publication_year", int(years[0]), 0.5)

    if m := KEYWORDS_RE.search(text):
        kws = [k.strip(" .") for k in re.split(r"[;,·•]", m.group(2)) if k.strip(" .")]
        put("keywords", kws, 0.85)

    if m := ISSN_JOURNAL_RE.search(head):
        put("journal", m.group("journal").strip(" ,"), 0.5)
        put("volume", m.group("vol"), 0.6)
    if m := ISSUE_RE.search(head):
        put("issue", m.group(1), 0.5)
    if m := PAGES_RE.search(head):
        put("pages", re.sub(r"\s+", "", m.group(1)).replace("–", "-"), 0.5)

    urls = [u for u in URL_RE.findall(head) if "doi.org" not in u]
    if urls:
        put("url", urls[0].rstrip(".,;"), 0.5)

    original_abstract = _abstract(sections)
    abstract = {
        "original_abstract": original_abstract,
        "original_abstract_source": "extracted" if original_abstract else None,
    }
    return meta, abstract


def guess_source_type(markdown: str, fmt: str) -> tuple[str, float]:
    """Very conservative source-type guess. Researcher should confirm."""
    low = body_text(markdown[:20000]).lower()
    if fmt in ("html", "htm"):
        return "website", 0.5
    if re.search(r"\b(dissertação|dissertation)\b", low):
        return "dissertation", 0.4
    if re.search(r"\b(tese|thesis|doctor of philosophy)\b", low):
        return "thesis", 0.4
    if re.search(r"\b(proceedings|conference|symposium|workshop)\b", low):
        return "conference_paper", 0.4
    if re.search(r"\barxiv\b|\bpreprint\b", low):
        return "preprint", 0.5
    if re.search(r"\b(journal|revista)\b", low) or re.search(r"\bvol(ume)?\.?\s*\d+", low):
        return "journal_article", 0.5
    if re.search(r"\bisbn\b", low):
        return "book", 0.5
    return "other", 0.0
