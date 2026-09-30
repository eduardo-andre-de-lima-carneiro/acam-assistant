"""Durable analysis job queue in SQLite (``<data root>/jobs.db``).

Jobs are operational state, not research data, so they live in a small SQLite
database (WAL mode) rather than in the project files. Any number of processes can
enqueue and claim jobs concurrently:

* a partial unique index allows only one queued/running job per source;
* claiming happens inside ``BEGIN IMMEDIATE``, so each job goes to one worker;
* workers heartbeat running jobs; jobs whose worker died are re-queued (or failed
  after ``MAX_ATTEMPTS``);
* workers register themselves, so the UI can tell when nobody is processing.

Like the file locks, SQLite needs a local filesystem (not NFS/SMB).
"""

from __future__ import annotations

import contextlib
import os
import socket
import sqlite3
import time
from pathlib import Path

from . import models

MAX_ATTEMPTS = 3
ACTIVE = ("queued", "running")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner         TEXT NOT NULL,
    workspace     TEXT NOT NULL,
    project       TEXT NOT NULL,
    source        TEXT NOT NULL,
    engine        TEXT NOT NULL,
    model         TEXT,
    state         TEXT NOT NULL CHECK (state IN ('queued', 'running', 'done', 'failed')),
    error         TEXT,
    attempts      INTEGER NOT NULL DEFAULT 0,
    worker        TEXT,
    queued_at     TEXT NOT NULL,
    started_at    TEXT,
    finished_at   TEXT,
    heartbeat_ts  REAL
);
CREATE UNIQUE INDEX IF NOT EXISTS jobs_one_active_per_source
    ON jobs (workspace, project, source) WHERE state IN ('queued', 'running');
CREATE INDEX IF NOT EXISTS jobs_by_state ON jobs (state, id);
CREATE INDEX IF NOT EXISTS jobs_by_project ON jobs (owner, project, id);
CREATE TABLE IF NOT EXISTS workers (
    id       TEXT PRIMARY KEY,
    host     TEXT NOT NULL,
    pid      INTEGER NOT NULL,
    threads  INTEGER NOT NULL,
    seen_ts  REAL NOT NULL
);
"""

_PUBLIC = ("id", "owner", "project", "source", "engine", "state", "error", "attempts",
           "worker", "queued_at", "started_at", "finished_at")


def worker_identity() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


class JobQueue:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(_SCHEMA)

    # --- connection -----------------------------------------------------------------

    @contextlib.contextmanager
    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA busy_timeout=30000")
            db.execute("PRAGMA synchronous=NORMAL")
            yield db
        finally:
            db.close()

    @contextlib.contextmanager
    def _transaction(self):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
            except BaseException:
                db.execute("ROLLBACK")
                raise
            db.execute("COMMIT")

    @staticmethod
    def _public(row: sqlite3.Row | None) -> dict | None:
        return {k: row[k] for k in _PUBLIC} if row is not None else None

    # --- producers --------------------------------------------------------------------

    def submit(self, owner: str, workspace: Path, project: str, source: str,
               engine: str = "auto", model: str | None = None) -> dict:
        """Queue an analysis; returns the already-active job for that source if any."""
        workspace = str(Path(workspace).resolve())
        with self._transaction() as db:
            row = db.execute(
                "SELECT * FROM jobs WHERE workspace=? AND project=? AND source=? "
                "AND state IN ('queued','running')", (workspace, project, source)).fetchone()
            if row is None:
                cur = db.execute(
                    "INSERT INTO jobs (owner, workspace, project, source, engine, model, state, "
                    "queued_at) VALUES (?,?,?,?,?,?, 'queued', ?)",
                    (owner, workspace, project, source, engine, model, models.now_iso()))
                row = db.execute("SELECT * FROM jobs WHERE id=?", (cur.lastrowid,)).fetchone()
        return self._public(row)

    # --- consumers --------------------------------------------------------------------

    def claim(self, worker: str) -> dict | None:
        """Atomically take the oldest queued job. Returns the full row (incl. workspace)."""
        with self._transaction() as db:
            row = db.execute(
                "SELECT id FROM jobs WHERE state='queued' ORDER BY id LIMIT 1").fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE jobs SET state='running', worker=?, attempts=attempts+1, "
                "started_at=?, heartbeat_ts=? WHERE id=?",
                (worker, models.now_iso(), time.time(), row["id"]))
            return dict(db.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone())

    def heartbeat(self, job_id: int, worker: str) -> bool:
        """Refresh a running job; False if the job is no longer ours."""
        with self._connect() as db:
            cur = db.execute(
                "UPDATE jobs SET heartbeat_ts=? WHERE id=? AND worker=? AND state='running'",
                (time.time(), job_id, worker))
            return cur.rowcount == 1

    def finish(self, job_id: int, worker: str, error: str | None = None) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE jobs SET state=?, error=?, finished_at=? "
                "WHERE id=? AND worker=? AND state='running'",
                ("failed" if error else "done", error, models.now_iso(), job_id, worker))

    def requeue_stale(self, stale_after: float) -> int:
        """Recover jobs whose worker stopped heartbeating (crash, kill, OOM)."""
        cutoff = time.time() - stale_after
        with self._transaction() as db:
            failed = db.execute(
                "UPDATE jobs SET state='failed', finished_at=?, "
                "error='worker stopped responding; giving up after ' || attempts || ' attempts' "
                "WHERE state='running' AND heartbeat_ts < ? AND attempts >= ?",
                (models.now_iso(), cutoff, MAX_ATTEMPTS)).rowcount
            requeued = db.execute(
                "UPDATE jobs SET state='queued', worker=NULL, started_at=NULL "
                "WHERE state='running' AND heartbeat_ts < ?", (cutoff,)).rowcount
        return failed + requeued

    def register_worker(self, worker: str, threads: int) -> None:
        host, _, pid = worker.rpartition(":")
        with self._connect() as db:
            db.execute(
                "INSERT INTO workers (id, host, pid, threads, seen_ts) VALUES (?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET seen_ts=excluded.seen_ts, threads=excluded.threads",
                (worker, host, int(pid), threads, time.time()))

    def unregister_worker(self, worker: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM workers WHERE id=?", (worker,))

    def live_workers(self, max_age: float = 60.0, host: str | None = None) -> list[dict]:
        sql = "SELECT * FROM workers WHERE seen_ts >= ?"
        args: list = [time.time() - max_age]
        if host:
            sql += " AND host=?"
            args.append(host)
        with self._connect() as db:
            return [dict(r) for r in db.execute(sql + " ORDER BY id", args)]

    # --- queries (always scoped by owner) ----------------------------------------------

    def for_project(self, owner: str, project: str, limit: int = 50) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM jobs WHERE owner=? AND project=? "
                              "ORDER BY id DESC LIMIT ?", (owner, project, limit)).fetchall()
        return [self._public(r) for r in rows]

    def active_for(self, owner: str, project: str, source: str | None = None) -> dict | None:
        sql = "SELECT * FROM jobs WHERE owner=? AND project=? AND state IN ('queued','running')"
        args: list = [owner, project]
        if source is not None:
            sql += " AND source=?"
            args.append(source)
        with self._connect() as db:
            return self._public(db.execute(sql + " ORDER BY id LIMIT 1", args).fetchone())

    def latest_for_source(self, owner: str, project: str, source: str) -> dict | None:
        with self._connect() as db:
            return self._public(db.execute(
                "SELECT * FROM jobs WHERE owner=? AND project=? AND source=? "
                "ORDER BY id DESC LIMIT 1", (owner, project, source)).fetchone())

    def counts(self) -> dict[str, int]:
        with self._connect() as db:
            rows = db.execute("SELECT state, COUNT(*) AS n FROM jobs GROUP BY state").fetchall()
        return {r["state"]: r["n"] for r in rows}

    def purge(self, older_than_days: float = 30) -> int:
        """Delete finished jobs older than the given age (their results stay in the projects)."""
        cutoff = time.time() - older_than_days * 86400
        with self._connect() as db:
            return db.execute(
                "DELETE FROM jobs WHERE state IN ('done','failed') AND "
                "COALESCE(heartbeat_ts, 0) < ?", (cutoff,)).rowcount
