# Architecture Overview

## System context

```text
                ┌──────────────┐        ┌──────────────┐
 Researchers ──►│  Web browser │        │   Terminal   │◄── Researchers / admins
                └──────┬───────┘        └──────┬───────┘
                       │ HTTP(S)               │ process
                ┌──────▼───────────────────────▼──────┐
                │               acam              │
                │  web/ (Flask)        cli.py          │
                │          \            /              │
                │           core pipeline              │
                └──────┬──────────────────────┬────────┘
                       │ files                │ HTTPS (optional)
                ┌──────▼───────┐       ┌──────▼──────────────┐
                │  Data root   │       │  Anthropic Claude   │
                │ (JSON, MD,   │       │  API (LLM engine)   │
                │  originals)  │       └─────────────────────┘
                └──────────────┘
```

ACAM Assistant is one Python package. It has no database, message queue or other
service. The only external dependency at runtime is the Anthropic API, and only
when the LLM engine is used.

## Layers and modules

```text
┌─────────────────────────────── Interfaces ───────────────────────────────┐
│  cli.py                         web/__init__.py  web/wsgi.py  templates/ │
└───────────────────────────────────┬──────────────────────────────────────┘
┌──────────────────────────── Application ─────────────────────────────────┐
│  pipeline.py   (import, analyze, researcher operations, locking)         │
│  accounts.py   (users, authentication, per-user workspaces)              │
│  jobs.py       (durable SQLite job queue)   worker.py (queue consumer)   │
│  artifacts/    (matrix, references list, reports, export)                │
└───────────────────────────────────┬──────────────────────────────────────┘
┌──────────────────────────────── Domain ──────────────────────────────────┐
│  conversion/  validation.py  extraction/  analysis/  references/         │
│  markdown_doc.py   models.py                                             │
└───────────────────────────────────┬──────────────────────────────────────┘
┌──────────────────────────── Infrastructure ──────────────────────────────┐
│  storage.py   (file repository, id validation)   locks.py (flock locks)  │
└──────────────────────────────────────────────────────────────────────────┘
```

| Module | Responsibility | Depends on |
| ------ | -------------- | ---------- |
| `models.py` | vocabularies (types, statuses, fields), record constructors, provenance helpers | — |
| `locks.py` | `InterProcessLock`: re-entrant thread lock + `flock` on a lock file, with timeout; `lock_for(path)` registry | — |
| `storage.py` | project directories, JSON read/write (unique temp file, fsync, atomic rename), per-project `Project.lock()`, id validation, project create/list/delete | models, locks |
| `conversion/` | format → Markdown converters (`pdf_converter`, `docx_converter`, `html_converter`, `text_converter`) and shared `structure` heuristics | pypdf, python-docx |
| `validation.py` | conversion quality checks | markdown_doc |
| `markdown_doc.py` | parses Markdown into sections with page numbers | — |
| `extraction/metadata.py` | candidate bibliographic metadata, source-type guess | markdown_doc, references (institution check) |
| `references/abnt.py` | ABNT reference strings, author formatting | models |
| `analysis/` | engine selection; `llm.py` (Claude), `heuristic.py`, `schema.py` (shared output schema) | anthropic (LLM only) |
| `pipeline.py` | orchestration and every state change | all domain modules, storage |
| `artifacts/` | derived documents, read-only over the catalog | storage, models |
| `accounts.py` | `users.json` (under its own file lock), password hashing, user workspaces, legacy adoption | werkzeug.security, storage, locks |
| `jobs.py` | SQLite job queue (`<root>/jobs.db`): submit, atomic claim, heartbeat, finish, stale recovery, worker registry, owner-scoped queries | sqlite3 (stdlib) |
| `worker.py` | `Worker`: claims and runs jobs in N threads, heartbeats, graceful stop; used by `acam worker` and embedded in the web app | jobs, pipeline |
| `cli.py` | argparse commands | pipeline, artifacts, accounts |
| `web/` | Flask app factory, routes, auth, CSRF, job submission (+ optional embedded worker), templates, static assets | Flask, pipeline, artifacts, accounts, jobs, worker |

Rules the code follows:

- Interfaces call `pipeline`/`artifacts`/`accounts` and never write catalog files
  themselves.
- Domain modules are pure: text in, data out, no file I/O. The exception is
  converters, which read the one file they are given.
- Only `pipeline` changes source records, so locking and history live in one place.
  (Project settings use `Project.update_info`, which takes the same lock.)
- Artifacts only read.

## Runtime views

### Importing a file (web)

```text
Browser ─POST /p/<pid>/upload (multipart, csrf_token)─► Flask
  load_user → check_csrf → upload()
    save to TemporaryDirectory (secure_filename)
    pipeline.import_source(...)
      sha256 (no lock)
      project.lock(): duplicate check, next id, empty original/<id>, placeholder record   (ms)
      copy file, conversion.convert → markdown/, validate, extract metadata            (no lock)
      project.lock(): re-read record, apply results, build reference, save            (ms)
    if "analyze after import": JobQueue.submit(...)  → row in jobs.db
  ◄─ 302 → /p/<pid>  (flash messages)
```

### Background analysis

```text
jobs.db (SQLite, WAL)  ◄── submit (web / CLI --queue)
   │  claim: BEGIN IMMEDIATE → oldest queued → running (worker id, attempts+1)
   ▼
Worker thread (acam worker process, or embedded in a web process)
   heartbeat thread: every 15 s → jobs.heartbeat_ts, workers.seen_ts
   pipeline.analyze_source
      read Markdown (no lock)
      analysis.analyze → Claude or heuristic         (can take minutes; no lock held)
      project.lock(): re-read record, write analysis/<id>.json, merge, save
   finish → done / failed (error message)
Every poll: requeue_stale(120 s) — jobs of crashed workers go back to the queue (max 3 attempts).
Browser polls GET /api/p/<pid>/jobs every 2.5 s and reloads when the active count drops.
```

### Request authentication

```text
before_request #1 load_user:  session["user"] → accounts.get_user → g.user
                              anonymous + non-public endpoint → 302 /login (API: 401)
before_request #2 check_csrf: POST only → reject cross-site (Sec-Fetch-Site / Origin)
                              → compare form csrf_token with session token (constant time)
route: ws() = <root>/users/<g.user.username>; every project lookup goes through ws()
```

## Concurrency model

ACAM Assistant is safe with **any number of threads, processes and containers on one
host** that share a data root ([ADR-010](decisions/ADR-010-multi-process-concurrency.md)):

| Shared state | Protection |
| ------------ | ---------- |
| a project's `sources.json` / `project.json` | `Project.lock()`: `flock` on `<project>/.lock` plus a thread lock; re-entrant; 30 s timeout (the web interface then shows "project busy") |
| `users.json` | `flock` on `<root>/users.json.lock` |
| source ids | reserved under the project lock by creating `original/<id>.<ext>`; ids of interrupted imports are never reused |
| analysis jobs | SQLite transactions in `jobs.db`: atomic claim, one active job per source, heartbeats |
| JSON files | written to a unique temp file, fsynced, then atomically renamed, so readers never see partial files |

Rules:

- **Keep critical sections short.** Hold a project lock only for in-memory
  read-modify-write. Never hold it for conversion, network calls or LLM analysis.
- **Re-read before writing.** After slow work, re-read the record under the lock
  and apply only the changes, so concurrent edits are kept.
- **Local disk only.** `flock` and SQLite are not reliable on NFS or SMB, so the
  data root must be on a local filesystem or block volume.

Deployment shapes:

| Shape | Web | Analyses |
| ----- | --- | -------- |
| `acam web` (laptop) | Flask dev server, threads | embedded worker (2 threads) |
| gunicorn | `-w N --threads M` | embedded worker in each process, or `ACAM_EMBEDDED_WORKER=false` + `acam worker` |
| Docker Compose | `acam` service, `ACAM_WORKERS` processes | `worker` service; `--scale worker=N` |

## Multi-tenancy

Each account's data lives in its own directory, `<root>/users/<username>/`.
Isolation is enforced at three points:

1. **Routing:** every web request resolves projects through `ws()`, which is built
   from the logged-in username. No request parameter can choose the user.
2. **Identifiers:** usernames and project ids must match strict patterns, so
   `..`, `/` and other path tricks are rejected before any path is built.
3. **Jobs:** each job records its owner, and every job query filters by owner.

Rationale: [ADR-007](decisions/ADR-007-filesystem-multi-tenancy.md).

## Error handling

| Where | Strategy |
| ----- | -------- |
| Conversion | converter exceptions become `ConversionError`; the source is kept with `conversion.status: "failed"` |
| Analysis | `LLMAnalysisError` (refusal, `max_tokens`, bad JSON, input too large) or any exception → nothing stored; CLI exit 1 / job `failed` with the message |
| Web user errors | `StorageError`, `AccountError`, `ValueError` → flash message + redirect back |
| Web access | unknown project/source → 404 (the same response whether it doesn't exist or belongs to someone else); non-admin on admin route → 403; bad CSRF → 400 |
| CLI | user errors → message on stderr, exit 2; import failures → exit 1 after processing the other files |

## Source tree

```text
src/acam/
├── __init__.py            version
├── models.py              vocabularies and record constructors
├── storage.py             file repository
├── markdown_doc.py        Markdown section parser
├── validation.py          conversion checks
├── conversion/            __init__ (registry), structure, pdf/docx/html/text converters
├── extraction/metadata.py
├── references/abnt.py
├── analysis/              __init__ (engine switch), schema, llm, heuristic
├── pipeline.py
├── artifacts/__init__.py
├── accounts.py
├── cli.py
├── container.py           container start-up (admin bootstrap)
├── locks.py               inter-process file locks
├── jobs.py                SQLite job queue
├── worker.py              analysis worker
└── web/
    ├── __init__.py        app factory, auth, routes, /healthz
    ├── wsgi.py            `app` for gunicorn, configured from the environment
    ├── templates/         Jinja2 (base, _macros, index, project, source, markdown,
    │                       matrix, references, login, signup, account)
    └── static/            style.css, app.js
docker/                    gunicorn.conf.py, entrypoint.sh, Caddyfile
tools/                     check_coverage.py (per-file coverage gate)
Dockerfile, docker-compose.yml, .env.example
schemas/                   JSON Schemas
tests/                     pytest suite + fixture builders
examples/                  sample article
docs/                      this documentation
```
