# ADR-010: Multi-process concurrency with file locks and a SQLite job queue

- **Status:** Accepted, supersedes [ADR-008](ADR-008-in-process-jobs-single-process.md)
- **Date:** 2026-09-30

## Context

ADR-008 kept the catalog write lock and the analysis job list in the memory of one
process. That caused four problems:

- **One CPU core.** The web tier used a single core, so PDF parsing (pure Python)
  held up other requests.
- **Lost analyses.** Restarting or redeploying the web server killed running
  analyses and forgot queued ones.
- **Cross-user stalls.** The lock was global and held during file conversion
  (measured: 0.5 s for 20 pages, 2.8 s for 200 pages), so one user's upload
  blocked every other user's saves.
- **No scaling.** Neither web processes nor analysis workers could be added.

A negative control confirmed the risk: with the process-local lock removed, 20
parallel note commands on the same source kept only 10 notes.

## Decision

1. **Per-project inter-process locks** (`acam/locks.py`). Each project has a
   lock file (`<project>/.lock`) locked with `flock`, plus a thread lock. The lock
   is re-entrant within a thread and times out after 30 s. `users.json` has its
   own lock.
2. **Short critical sections.** An import reserves its id, creates an empty
   original file and saves a placeholder record under the lock, then copies and
   converts *without* the lock, then saves the result under the lock again.
   Analysis already ran outside the lock and re-reads the record before merging.
3. **Durable job queue in SQLite** (`acam/jobs.py`, `<root>/jobs.db`, WAL mode).
   - Claims are atomic (`BEGIN IMMEDIATE`).
   - A partial unique index allows only one queued or running job per source.
   - Running jobs heartbeat; stalled jobs are re-queued and fail after 3 attempts.
   - A worker registry backs liveness checks.
   - Queries are scoped by owner.
   - Python's `sqlite3` is in the standard library, so there is no new dependency.
4. **Worker** (`acam/worker.py`, `acam worker`). Any number of processes
   and threads can consume the queue. By default the web process embeds a worker
   (`ACAM_EMBEDDED_WORKER`). The container setup runs a separate `worker`
   service instead.
5. **The single-worker rule is lifted.** gunicorn runs `ACAM_WORKERS`
   processes (default 2).

Research data stays in plain files (ADR-002). Only operational job state moved
to SQLite.

## Consequences

- Imports, edits and analyses are safe across threads, processes and containers
  on one host. Tests prove it with real parallel processes: 8 concurrent imports,
  20 concurrent edits on one source, 3 workers draining one queue, and gunicorn
  with 3 processes taking 24 concurrent HTTP edits. Nothing is lost or duplicated.
- One user's large upload no longer blocks other users or projects.
- Analyses survive web restarts and deploys. Jobs whose worker crashed are
  recovered automatically.
- Analysis capacity scales with worker threads or containers
  (`docker compose up --scale worker=N`) up to the Anthropic rate limit.
- **Constraint:** `flock` and SQLite are only reliable on local filesystems or
  block volumes, not on NFS or SMB shares. This design scales up on one host,
  not across hosts.
- A crash between reservation and completion leaves a source in `imported` with an
  empty original file. Its id is not reused.

## Alternatives considered

- *Job queue as files (atomic rename between folders):* no database, but claiming,
  retries, deduplication and recovery would all be hand-written.
- *SQLite for everything:* more refactoring and loses diffable project files, for
  little extra concurrency at this scale.
- *Redis + Celery/RQ:* an extra service, and it doesn't solve lost updates on the
  catalog files.
- *PostgreSQL + object storage:* needed only for multi-host or high availability.
  The lock and queue are behind small interfaces, so this remains possible later.
