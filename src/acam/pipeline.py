"""End-to-end MVP pipeline:

Import -> Convert -> Validate Markdown -> Extract Metadata -> (Analyze -> Summary) -> Store JSON
"""

from __future__ import annotations

import functools
import hashlib
import shutil
from pathlib import Path

from . import __version__, analysis, conversion, models
from .extraction.metadata import extract_metadata, guess_source_type
from .references.abnt import build_reference
from .storage import Project, StorageError
from .validation import validate_markdown


class DuplicateSourceError(StorageError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _log(record: dict, event: str, **details) -> None:
    record.setdefault("history", []).append({"at": models.now_iso(), "event": event, **details})


def refresh_reference(record: dict) -> None:
    ref = build_reference(record, today=record.get("imported_at"))
    record["bibliographic_reference"] = {
        "style": ref.style,
        "text": ref.text,
        "missing_fields": ref.missing,
        "requires_validation": not all(
            (record["metadata"].get(f) or {}).get("validated") for f in ("title", "authors")),
    }


def import_source(project: Project, file_path: Path, source_type: str | None = None,
                  tags: list[str] | None = None, allow_duplicate: bool = False,
                  original_name: str | None = None) -> dict:
    """Import one file. Safe to run concurrently from several threads or processes:
    the project lock is held only to reserve the id and to save the record, never
    during copying or conversion."""
    file_path = Path(file_path)
    if not file_path.is_file():
        raise StorageError(f"File not found: {file_path}")
    fmt = conversion.detect_format(file_path)
    if fmt not in conversion.supported_formats():
        raise conversion.ConversionError(
            f"Unsupported format '.{fmt}'. Supported: {', '.join(conversion.supported_formats())}")
    if source_type and source_type not in models.SOURCE_TYPES:
        raise ValueError(f"Unknown source type '{source_type}'. Use one of: {', '.join(models.SOURCE_TYPES)}")
    name = original_name or file_path.name
    digest = _sha256(file_path)

    # 1. Reserve: duplicate check, id, empty original file, placeholder record (milliseconds).
    with project.lock():
        if not allow_duplicate:
            for existing in project.sources():
                if existing["original_file"].get("sha256") == digest:
                    raise DuplicateSourceError(f"{name} was already imported as {existing['id']}")
        source_id = project.next_source_id()
        stored = f"original/{source_id}.{fmt}"
        project.path(stored).touch(exist_ok=False)
        record = models.new_source(source_id, name, fmt, stored, digest)
        record["tags"] = sorted(set(tags or []))
        project.put_source(record)

    # 2. Copy and convert without holding the lock (seconds for large documents).
    shutil.copy2(file_path, project.path(stored))
    changes: dict = {}
    try:
        result = conversion.convert(project.path(stored))
    except conversion.ConversionError as exc:
        changes["conversion"] = {"status": "failed", "error": str(exc)}
        _log(changes, "conversion_failed", error=str(exc))
        _apply_import(project, source_id, changes)
        raise
    md_rel = f"markdown/{source_id}.md"
    project.path(md_rel).write_text(result.markdown, encoding="utf-8")
    changes["markdown_file"] = md_rel

    report = validate_markdown(result.markdown, result.page_count)
    changes["conversion"] = {
        "status": report["status"],
        "converter": result.converter,
        "processor_version": __version__,
        "converted_at": models.now_iso(),
        "page_count": result.page_count,
        "warnings": result.warnings,
        "validation": report,
    }
    changes["status"] = "converted"
    _log(changes, "converted", converter=result.converter, validation=report["status"])

    if report["passed"]:
        meta, abstract = extract_metadata(result.markdown, result.embedded_metadata)
        changes["metadata"] = meta
        changes["original_abstract"] = abstract["original_abstract"]
        if not source_type:
            guessed, conf = guess_source_type(result.markdown, fmt)
            changes["type"] = guessed
            changes["type_provenance"] = {"source": "extracted", "confidence": conf}
        changes["status"] = "extracted"
        _log(changes, "metadata_extracted")
    if source_type:
        changes["type"] = source_type
        changes["type_provenance"] = {"source": "researcher", "confidence": None}

    # 3. Save under the lock, on top of whatever is stored now.
    return _apply_import(project, source_id, changes)


def _apply_import(project: Project, source_id: str, changes: dict) -> dict:
    with project.lock():
        record = project.get_source(source_id)
        events = changes.pop("history", [])
        original_abstract = changes.pop("original_abstract", None)
        record.update(changes)
        if original_abstract is not None:
            record["abstract"]["original_abstract"] = original_abstract
        record.setdefault("history", []).extend(events)
        refresh_reference(record)
        project.put_source(record)
        return record


def _merge_candidates(record: dict, candidates: dict | None, origin: str) -> list[str]:
    """Fill metadata fields from analysis candidates without overriding validated
    or high-confidence values. Returns the list of updated fields."""
    if not candidates:
        return []
    updated = []
    meta = record["metadata"]
    for name in models.METADATA_FIELDS:
        new = candidates.get(name)
        if new in (None, "", [], "unknown"):
            continue
        current = meta.get(name) or models.field()
        if current.get("validated"):
            continue
        if current.get("value") in (None, "", []) or (current.get("confidence") or 0) < 0.8:
            meta[name] = {**models.field(new, "extracted", 0.8), "extractor": origin}
            updated.append(name)
    st = candidates.get("source_type")
    prov = record.get("type_provenance") or {}
    if st in models.SOURCE_TYPES and st != "other" and prov.get("source") != "researcher":
        record["type"] = st
        record["type_provenance"] = {"source": "extracted", "confidence": 0.8, "extractor": origin}
        updated.append("type")
    return updated


def analyze_source(project: Project, source_id: str, engine: str = "auto", client=None,
                   model: str | None = None) -> dict:
    record = project.get_source(source_id)
    if record["status"] == "imported" or not record.get("markdown_file"):
        raise StorageError(f"{source_id} has no valid Markdown; re-import it first")
    markdown = project.read_markdown(record)
    result = analysis.analyze(markdown, record, project.info(), engine=engine, client=client,
                              model=model)
    with project.lock():
        # Re-read: the researcher may have edited the record while analysis ran.
        return _store_analysis(project, source_id, result)


def _store_analysis(project: Project, source_id: str, result: dict) -> dict:
    record = project.get_source(source_id)
    record["analysis_file"] = project.write_analysis(source_id, result)

    updated = _merge_candidates(record, result.get("metadata_candidates"), result["engine"])
    record["abstract"].update({
        "generated_summary": result.get("summary"),
        "summary_type": result.get("summary_type", "structured"),
        "generated_at": result["processing"]["processed_at"],
        "requires_validation": True,
    })
    if record["status"] in ("imported", "converted", "extracted", "analyzed"):
        record["status"] = "analyzed"
    record["analysis"] = {
        "status": "pending_review",
        "engine": result["engine"],
        "model": result["processing"].get("analysis_model"),
        "analyzed_at": result["processing"]["processed_at"],
        "confidence": result.get("confidence"),
    }
    refresh_reference(record)
    _log(record, "analyzed", engine=result["engine"], metadata_updated=updated)
    project.put_source(record)
    return record


# --- researcher-in-the-loop operations ----------------------------------------

def _locked(fn):
    """Run a read-modify-write of one record under its project's lock
    (the project is the first argument)."""
    @functools.wraps(fn)
    def wrapper(project: Project, *args, **kwargs):
        with project.lock():
            return fn(project, *args, **kwargs)
    return wrapper


@_locked
def set_metadata(project: Project, source_id: str, name: str, value) -> dict:
    """Researcher-entered value: authoritative and validated."""
    if name == "type":
        if value not in models.SOURCE_TYPES:
            raise ValueError(f"Unknown source type '{value}'")
        record = project.get_source(source_id)
        record["type"] = value
        record["type_provenance"] = {"source": "researcher", "confidence": None}
    else:
        if name not in models.METADATA_FIELDS:
            raise ValueError(f"Unknown metadata field '{name}'. Fields: {', '.join(models.METADATA_FIELDS)}")
        record = project.get_source(source_id)
        if name in models.LIST_FIELDS and isinstance(value, str):
            value = [v.strip() for v in value.split(";") if v.strip()]
        if name == "publication_year" and value not in (None, ""):
            value = int(value)
        record["metadata"][name] = models.field(value, "researcher", None, True)
    refresh_reference(record)
    _log(record, "metadata_set", field=name)
    project.put_source(record)
    return record


@_locked
def confirm_metadata(project: Project, source_id: str, names: list[str]) -> dict:
    """Mark extracted values as validated by the researcher, keeping their origin."""
    record = project.get_source(source_id)
    for name in names:
        if name not in record["metadata"]:
            raise ValueError(f"Unknown metadata field '{name}'")
        if record["metadata"][name].get("value") in (None, "", []):
            raise ValueError(f"Cannot confirm empty field '{name}'; set it instead")
        record["metadata"][name]["validated"] = True
    refresh_reference(record)
    _log(record, "metadata_confirmed", fields=names)
    project.put_source(record)
    return record


@_locked
def set_status(project: Project, source_id: str, status: str, note: str | None = None) -> dict:
    if status not in models.STATUSES:
        raise ValueError(f"Unknown status '{status}'. Use one of: {', '.join(models.STATUSES)}")
    record = project.get_source(source_id)
    record["status"] = status
    if record.get("analysis") and status in ("validated", "rejected", "included"):
        record["analysis"]["status"] = "rejected" if status == "rejected" else "validated"
    _log(record, "status_changed", status=status, **({"note": note} if note else {}))
    project.put_source(record)
    return record


@_locked
def add_note(project: Project, source_id: str, note: str) -> dict:
    record = project.get_source(source_id)
    record["researcher_notes"] = (record.get("researcher_notes", "") + "\n" + note).strip()
    _log(record, "note_added")
    project.put_source(record)
    return record


@_locked
def set_tags(project: Project, source_id: str, add: list[str], remove: list[str]) -> dict:
    record = project.get_source(source_id)
    record["tags"] = sorted((set(record.get("tags", [])) | set(add)) - set(remove))
    project.put_source(record)
    return record
