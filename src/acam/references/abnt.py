"""Bibliographic references following the specification's ABNT-based structures.

Missing data is never invented; ABNT placeholders are used instead
(``[s.l.]`` unknown place, ``[s.n.]`` unknown publisher, ``[s.d.]`` unknown
date) and the missing fields are reported so the researcher can fill them in.
The main title element is emphasised with Markdown bold, as ABNT requires.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from ..models import value_of

MONTHS_PT = ("jan.", "fev.", "mar.", "abr.", "maio", "jun.",
             "jul.", "ago.", "set.", "out.", "nov.", "dez.")

_PARTICLES = {"da", "de", "do", "das", "dos", "e", "van", "von", "der", "del", "la", "le", "di"}
_SUFFIXES = {"junior", "júnior", "jr", "jr.", "filho", "neto", "sobrinho"}
_INSTITUTION = re.compile(
    r"\([A-Z]{2,}\)|\b(institut[oe]?|university|universidade|ministry|ministério|organi[sz]ation|"
    r"organização|association|associação|agency|agência|department|secretaria|council|conselho|"
    r"foundation|fundação|society|sociedade|committee|comitê|group|grupo|bank|banco)\b", re.I)


def is_institution(name: str) -> bool:
    return bool(_INSTITUTION.search(name))


@dataclass
class Reference:
    text: str
    missing: list[str] = field(default_factory=list)
    style: str = "abnt"

    @property
    def complete(self) -> bool:
        return not self.missing


def format_author(name: str) -> str:
    """'João Alberto da Silva' or 'Silva, João Alberto' -> 'SILVA, J. A.'"""
    name = " ".join(name.split()).strip(" .")
    if not name:
        return ""
    if _INSTITUTION.search(name) or name.isupper() and "," not in name:
        return name.upper()  # institutional author, e.g. IBGE
    if "," in name:
        last, given = [p.strip() for p in name.split(",", 1)]
    else:
        tokens = name.split()
        if len(tokens) == 1:
            return name.upper()
        last_tokens = [tokens.pop()]
        if last_tokens[0].lower().strip(".") in _SUFFIXES and tokens:
            last_tokens.insert(0, tokens.pop())
        last, given = " ".join(last_tokens), " ".join(tokens)
    initials = " ".join(f"{t[0].upper()}." for t in given.split()
                        if t.lower() not in _PARTICLES and t[0].isalpha())
    return f"{last.upper()}, {initials}".strip().rstrip(",")


def format_authors(authors: list[str]) -> str:
    formatted = [a for a in (format_author(x) for x in authors) if a]
    if not formatted:
        return ""
    if len(formatted) > 3:
        return f"{formatted[0]} et al."
    return "; ".join(formatted)


def format_access_date(iso: str | None) -> str:
    d = date.fromisoformat(iso[:10]) if iso else date.today()
    return f"{d.day} {MONTHS_PT[d.month - 1]} {d.year}"


def _sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "?", "!")) else text + "."


def _title_parts(title: str) -> tuple[str, str | None]:
    if ":" in title:
        main, sub = title.split(":", 1)
        return main.strip(), sub.strip()
    return title.strip(), None


def build_reference(record: dict, today: str | None = None) -> Reference:
    meta = record.get("metadata", {})
    kind = record.get("type", "other")
    missing: list[str] = []

    def need(name: str, placeholder: str | None = None):
        v = value_of(meta, name)
        if v in (None, "", []):
            missing.append(name)
            return placeholder
        return v

    authors = need("authors", [])
    author_txt = format_authors(authors) if authors else ""
    title = need("title", "[Título não identificado]")
    year = need("publication_year", "[s.d.]")
    parts: list[str] = []

    if kind in ("book", "thesis", "dissertation", "technical_report"):
        main, sub = _title_parts(title)
        title_txt = f"**{main}**" + (f": {sub}" if sub else "")
        if author_txt:
            parts.append(_sentence(author_txt))
        parts.append(_sentence(title_txt))
        edition = value_of(meta, "edition")
        if edition and str(edition).strip() not in ("1", "1."):
            parts.append(f"{str(edition).rstrip('.')}. ed.")
        place = need("publication_place", "[s.l.]")
        publisher = need("publisher", "[s.n.]")
        parts.append(f"{place}: {publisher}, {year}.")

    elif kind in ("journal_article", "conference_paper", "preprint", "book_chapter"):
        if author_txt:
            parts.append(_sentence(author_txt))
        parts.append(_sentence(title))
        container = need("journal", "[Periódico não identificado]")
        segs = [f"**{container}**"]
        if place := value_of(meta, "publication_place"):
            segs.append(place)
        if vol := need("volume"):
            segs.append(f"v. {vol}")
        if issue := value_of(meta, "issue"):
            segs.append(f"n. {issue}")
        if pages := need("pages"):
            segs.append(f"p. {pages}")
        segs.append(str(year))
        parts.append(", ".join(segs) + ".")
        if doi := value_of(meta, "doi"):
            parts.append(f"DOI: {doi}.")

    else:  # website, online_article, other
        if author_txt:
            parts.append(_sentence(author_txt))
        parts.append(_sentence(f"**{title}**" if kind == "other" else title))
        site = value_of(meta, "publisher") or value_of(meta, "journal")
        if site:
            parts.append(f"{site}, {year}." if year != "[s.d.]" else _sentence(site))
        elif year != "[s.d.]":
            parts.append(f"{year}.")
        url = value_of(meta, "url")
        if url or kind in ("website", "online_article"):
            url = url or need("url", "[URL não identificada]")
            access = value_of(meta, "access_date") or today
            parts.append(f"Disponível em: {url}. Acesso em: {format_access_date(access)}.")

    text = re.sub(r"\s+", " ", " ".join(parts)).replace("..", ".")
    return Reference(text=text, missing=missing)
