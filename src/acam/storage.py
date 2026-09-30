"""File-based project repository.

Layout of one project (README "Project-Based Organization")::

    <workspace>/<project-id>/
        project.json      research project definition
        sources.json      structured JSON catalog (one record per source)
        original/         immutable copies of imported files
        markdown/         canonical Markdown representations
        analysis/         per-source analysis JSON
        artifacts/        generated academic artifacts
"""

from __future__ import annotations

import json
import os
import re
import shutil
import threading
from pathlib import Path

from . import models
from .locks import InterProcessLock, LockTimeout, lock_for

SUBDIRS = ("original", "markdown", "analysis", "artifacts")
LOCK_FILE = ".lock"


class StorageError(Exception):
    pass


def default_workspace() -> Path:
    return Path(os.environ.get("ACAM_HOME", "projects")).resolve()


PROJECT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def check_project_id(project_id: str) -> str:
    """Reject ids that could escape the workspace (``..``, slashes, etc.)."""
    if not PROJECT_ID_RE.fullmatch(project_id or ""):
        raise StorageError(
            f"Invalid project id '{project_id}': use lowercase letters, digits, '-' or '_'")
    return project_id


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "project"


def _read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, data: dict) -> None:
    """Atomic, durable write: unique temp file, fsync, rename over the target."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


class Project:
    def __init__(self, root: Path):
        self.root = root
        if not (root / "project.json").exists():
            raise StorageError(f"Not a project directory: {root}")

    # --- paths -----------------------------------------------------------
    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    @property
    def id(self) -> str:
        return self.root.name

    def lock(self) -> InterProcessLock:
        """Exclusive lock for read-modify-write of this project's files, across
        threads and processes. Hold it only for short, in-memory work."""
        return lock_for(self.root / LOCK_FILE)

    # --- project.json ----------------------------------------------------
    def info(self) -> dict:
        return _read_json(self.path("project.json"))

    def save_info(self, info: dict) -> None:
        info["updated_at"] = models.now_iso()
        _write_json(self.path("project.json"), info)

    def update_info(self, changes: dict) -> dict:
        with self.lock():
            info = self.info()
            info.update(changes)
            self.save_info(info)
            return info

    # --- sources.json ----------------------------------------------------
    def sources(self) -> list[dict]:
        return _read_json(self.path("sources.json"))["sources"]

    def save_sources(self, sources: list[dict]) -> None:
        with self.lock():
            _write_json(self.path("sources.json"), {"project_id": self.id, "sources": sources})
            self.save_info(self.info())

    def get_source(self, source_id: str) -> dict:
        for s in self.sources():
            if s["id"] == source_id:
                return s
        raise StorageError(f"Source not found: {source_id}")

    def put_source(self, record: dict) -> None:
        with self.lock():
            sources = self.sources()
            for i, s in enumerate(sources):
                if s["id"] == record["id"]:
                    sources[i] = record
                    break
            else:
                sources.append(record)
            self.save_sources(sources)

    def next_source_id(self) -> str:
        """Next free id. Call under :meth:`lock` and persist the record before releasing."""
        nums = [int(m.group(1)) for s in self.sources()
                if (m := re.fullmatch(r"source-(\d+)", s["id"]))]
        # Files left by an interrupted import also hold their id.
        nums += [int(m.group(1)) for f in self.path("original").iterdir()
                 if (m := re.fullmatch(r"source-(\d+)", f.stem))]
        return f"source-{(max(nums) + 1) if nums else 1:03d}"

    # --- analysis --------------------------------------------------------
    def read_analysis(self, source_id: str) -> dict | None:
        p = self.path("analysis", f"{source_id}.json")
        return _read_json(p) if p.exists() else None

    def write_analysis(self, source_id: str, analysis: dict) -> str:
        rel = f"analysis/{source_id}.json"
        _write_json(self.path(rel), analysis)
        return rel

    def read_markdown(self, record: dict) -> str:
        if not record.get("markdown_file"):
            raise StorageError(f"{record['id']} has no Markdown representation yet")
        return self.path(record["markdown_file"]).read_text(encoding="utf-8")


def create_project(workspace: Path, title: str, project_id: str | None = None,
                   description: str = "", research_questions: list[str] | None = None) -> Project:
    project_id = check_project_id(project_id or slugify(title))
    root = workspace / project_id
    if root.exists():
        raise StorageError(f"Project already exists: {root}")
    for sub in SUBDIRS:
        (root / sub).mkdir(parents=True)
    _write_json(root / "project.json",
                models.new_project(project_id, title, description, research_questions))
    _write_json(root / "sources.json", {"project_id": project_id, "sources": []})
    return Project(root)


def open_project(workspace: Path, project_id: str) -> Project:
    return Project(workspace / check_project_id(project_id))


def delete_project(workspace: Path, project_id: str) -> None:
    project = open_project(workspace, project_id)
    with project.lock():
        shutil.rmtree(project.root)


def list_projects(workspace: Path) -> list[Project]:
    if not workspace.exists():
        return []
    return [Project(p) for p in sorted(workspace.iterdir())
            if p.is_dir() and (p / "project.json").exists()]
