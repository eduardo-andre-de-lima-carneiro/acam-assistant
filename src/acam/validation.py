"""Conversion validation (specification "Step 4 — Validate Conversion")."""

from __future__ import annotations

import re

from .markdown_doc import body_text, parse_sections

MIN_CHARS = 200
EXPECTED_SECTIONS = ("abstract", "introduction", "method", "results", "conclusion", "references")


def validate_markdown(markdown: str, page_count: int | None = None) -> dict:
    text = body_text(markdown)
    chars = len(text.strip())
    words = len(text.split())
    sections = [s for s in parse_sections(markdown) if s.level > 0]
    keys = [s.key for s in sections]
    found = [name for name in EXPECTED_SECTIONS if any(name in k for k in keys)]

    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str, severity: str = "error") -> None:
        checks.append({"check": name, "passed": ok, "severity": severity, "detail": detail})

    check("not_empty", chars > 0, f"{chars} characters extracted")
    check("minimum_length", chars >= MIN_CHARS, f"{words} words (minimum {MIN_CHARS} characters)")

    replacement = text.count("�")
    control = len(re.findall(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text))
    bad_ratio = (replacement + control) / max(chars, 1)
    check("encoding", bad_ratio < 0.01,
          f"{replacement} replacement and {control} control characters")

    check("headings_present", bool(sections), f"{len(sections)} heading(s) detected", "warning")
    check("academic_sections", len(found) >= 2,
          f"recognized sections: {', '.join(found) or 'none'}", "warning")

    if page_count:
        per_page = words / page_count
        check("text_density", per_page >= 50,
              f"{per_page:.0f} words per page (low values suggest scanned pages)", "warning")

    errors = [c for c in checks if not c["passed"] and c["severity"] == "error"]
    warnings = [c for c in checks if not c["passed"] and c["severity"] == "warning"]
    return {
        "passed": not errors,
        "status": "failed" if errors else ("passed_with_warnings" if warnings else "passed"),
        "characters": chars,
        "words": words,
        "headings": len(sections),
        "recognized_sections": found,
        "checks": checks,
    }
