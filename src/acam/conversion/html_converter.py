from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from . import ConversionResult

_SKIP = {"script", "style", "nav", "footer", "header", "noscript", "svg", "form", "aside"}
_BLOCK = {"p", "div", "section", "article", "main", "blockquote", "figure", "figcaption",
          "table", "tr", "ul", "ol", "pre"}


class _Converter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip_depth = 0
        self.href: str | None = None
        self.title = ""
        self.in_title = False
        self.meta: dict[str, str] = {}
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.table_rows: list[list[str]] = []

    def _emit(self, text: str) -> None:
        if self.cell is not None:
            self.cell.append(text)
        else:
            self.out.append(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in _SKIP:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag == "title":
            self.in_title = True
        elif tag == "meta":
            name = (attrs.get("name") or attrs.get("property") or "").lower()
            if name and attrs.get("content"):
                self.meta[name] = attrs["content"]
        elif re.fullmatch(r"h[1-6]", tag):
            self.out.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "li":
            self.out.append("\n- ")
        elif tag == "br":
            self._emit("\n")
        elif tag in ("strong", "b"):
            self._emit("**")
        elif tag in ("em", "i"):
            self._emit("*")
        elif tag == "a":
            self.href = attrs.get("href")
            self._emit("[")
        elif tag == "table":
            self.table_rows = []
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []
        elif tag in _BLOCK:
            self.out.append("\n\n")

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return
        if tag == "title":
            self.in_title = False
        elif re.fullmatch(r"h[1-6]", tag):
            self.out.append("\n\n")
        elif tag in ("strong", "b"):
            self._emit("**")
        elif tag in ("em", "i"):
            self._emit("*")
        elif tag == "a":
            self._emit(f"]({self.href})" if self.href else "]")
            self.href = None
        elif tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()).replace("|", "\\|"))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table_rows.append(self.row)
            self.row = None
        elif tag == "table":
            self._flush_table()
        elif tag in _BLOCK:
            self.out.append("\n\n")

    def _flush_table(self) -> None:
        rows = [r for r in self.table_rows if r]
        if not rows:
            return
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        lines = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * width]
        lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        self.out.append("\n\n" + "\n".join(lines) + "\n\n")
        self.table_rows = []

    def handle_data(self, data):
        if self.skip_depth:
            return
        if self.in_title:
            self.title += data
            return
        text = re.sub(r"\s+", " ", data)
        if text.strip() or (self.out and not self.out[-1].endswith((" ", "\n"))):
            self._emit(text)


def convert(path: Path) -> ConversionResult:
    raw = path.read_bytes().decode("utf-8", errors="replace")
    parser = _Converter()
    parser.feed(raw)
    parser.close()
    md = "".join(parser.out)
    md = "\n".join(ln.strip() for ln in md.split("\n"))

    embedded = {}
    title = parser.meta.get("citation_title") or parser.meta.get("og:title") or parser.title.strip()
    if title:
        embedded["title"] = title
    author = parser.meta.get("citation_author") or parser.meta.get("author")
    if author:
        embedded["authors"] = author
    if parser.meta.get("citation_doi"):
        embedded["doi"] = parser.meta["citation_doi"]
    return ConversionResult(markdown=md, converter="html.parser", embedded_metadata=embedded)
