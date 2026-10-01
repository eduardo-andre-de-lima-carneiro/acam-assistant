"""Controlled vocabularies and record constructors for the JSON catalog.

Every value that was produced by the system (not typed by the researcher) is
wrapped in a *provenance field* so it is never mistaken for validated data:

    {"value": ..., "source": "extracted", "confidence": 0.6, "validated": false}
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SOURCE_TYPES = (
    "book",
    "book_chapter",
    "journal_article",
    "conference_paper",
    "thesis",
    "dissertation",
    "technical_report",
    "website",
    "online_article",
    "preprint",
    "other",
)

# Source status lifecycle (specification "Source Status Lifecycle", docs/design/specification.md).
STATUSES = (
    "imported",
    "converted",
    "extracted",
    "analyzed",
    "under_review",
    "rejected",
    "validated",
    "included",
)

FIELD_ORIGINS = ("extracted", "generated", "researcher", "unknown")

METADATA_FIELDS = (
    "title",
    "authors",
    "publication_year",
    "publisher",
    "journal",
    "volume",
    "issue",
    "pages",
    "doi",
    "url",
    "edition",
    "publication_place",
    "access_date",
    "keywords",
)

# Fields that hold lists rather than scalars.
LIST_FIELDS = {"authors", "keywords"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def field(value: Any = None, source: str = "unknown", confidence: float | None = None,
          validated: bool = False) -> dict:
    return {"value": value, "source": source, "confidence": confidence, "validated": validated}


def empty_metadata() -> dict:
    return {name: field([] if name in LIST_FIELDS else None) for name in METADATA_FIELDS}


def value_of(meta: dict, name: str, default: Any = None) -> Any:
    """Return the plain value of a provenance field, or ``default`` when missing."""
    entry = meta.get(name) or {}
    v = entry.get("value")
    return default if v in (None, "", []) else v


def new_project(project_id: str, title: str, description: str = "",
                research_questions: list[str] | None = None) -> dict:
    ts = now_iso()
    return {
        "id": project_id,
        "title": title,
        "description": description,
        "research_problem": "",
        "research_questions": research_questions or [],
        "objectives": [],
        "scope": "",
        "inclusion_criteria": [],
        "exclusion_criteria": [],
        "created_at": ts,
        "updated_at": ts,
    }


def new_source(source_id: str, original_name: str, fmt: str, stored_as: str,
               sha256: str, source_type: str = "other") -> dict:
    return {
        "id": source_id,
        "type": source_type,
        "status": "imported",
        "original_file": {
            "name": original_name,
            "format": fmt,
            "stored_as": stored_as,
            "sha256": sha256,
        },
        "imported_at": now_iso(),
        "markdown_file": None,
        "analysis_file": None,
        "conversion": None,
        "metadata": empty_metadata(),
        "abstract": {
            "original_abstract": None,
            "generated_summary": None,
            "summary_type": None,
            "generated_at": None,
            "requires_validation": True,
        },
        "bibliographic_reference": None,
        "tags": [],
        "researcher_notes": "",
        "history": [{"at": now_iso(), "event": "imported"}],
    }
