"""Read-only view over a canonical Markdown document: sections and page numbers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_PAGE = re.compile(r"^<!-- page: (\d+) -->$")


@dataclass
class Section:
    title: str
    level: int
    page: int | None
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(ln for ln in self.lines if not _PAGE.match(ln.strip())).strip()

    @property
    def paragraphs(self) -> list[str]:
        return [p.strip() for p in re.split(r"\n\s*\n", self.text) if p.strip()]

    @property
    def key(self) -> str:
        """Section title without numbering, lower-cased."""
        return re.sub(r"^(?:\d+(?:\.\d+)*\.?|[IVX]+\.)\s+", "", self.title).strip().rstrip(":").lower()


def parse_sections(markdown: str) -> list[Section]:
    sections = [Section(title="", level=0, page=None)]
    page: int | None = None
    in_code = False
    for line in markdown.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
        m_page = _PAGE.match(stripped)
        if m_page:
            page = int(m_page.group(1))
            if sections[-1].page is None:
                sections[-1].page = page
        m = None if in_code else _HEADING.match(stripped)
        if m:
            sections.append(Section(title=m.group(2).strip(), level=len(m.group(1)), page=page))
        else:
            sections[-1].lines.append(line)
    return sections


def find_section(sections: list[Section], *names: str) -> Section | None:
    wanted = {n.lower() for n in names}
    for s in sections:
        if s.key in wanted:
            return s
    for s in sections:  # looser match, e.g. "Materials and Methods" for "methods"
        if any(n in s.key for n in wanted):
            return s
    return None


def body_text(markdown: str) -> str:
    return "\n".join(ln for ln in markdown.split("\n") if not _PAGE.match(ln.strip()))
