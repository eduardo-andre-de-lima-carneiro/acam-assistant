# Technology Stack

## Summary

| Layer | Technology | Version tested | Why |
| ----- | ---------- | -------------- | --- |
| Language | Python | 3.10 (requires ≥ 3.10) | mature document-processing libraries; researchers can read it |
| PDF text extraction | [pypdf](https://pypi.org/project/pypdf/) | 6.19 | pure Python, no system dependencies, page-level extraction |
| DOCX reading | [python-docx](https://pypi.org/project/python-docx/) | 1.2 | reads styles (Title, Heading N), lists and tables in body order |
| HTML parsing | Python stdlib `html.parser` | — | no dependency; enough for article pages |
| LLM | [Anthropic Python SDK](https://pypi.org/project/anthropic/) → Claude `claude-opus-5-5` | anthropic 1.9 | structured outputs, streaming, server-side refusal fallback |
| Web framework | [Flask](https://pypi.org/project/Flask/) + Jinja2 + Werkzeug | 3.1 / 3.1 / 3.1 | small, server-rendered, factory pattern; Werkzeug provides scrypt password hashing and safe file names |
| Front end | hand-written CSS + vanilla JavaScript | — | no build step, no CDN, works offline |
| Production server | [gunicorn](https://gunicorn.org/) (extra `[server]`) | 26.2 | WSGI server with threaded workers |
| Container | Docker image on `python:3.12-slim`, Compose, optional [Caddy 2](https://caddyserver.com/) for HTTPS | Docker 28 | reproducible deployment, automatic TLS |
| Job queue | Python stdlib `sqlite3` (WAL mode) | SQLite ≥ 3.24 | durable, multi-process analysis queue without a new service |
| Locking | `fcntl.flock` (stdlib) | — | cross-process locks on project files |
| Tests | pytest, pytest-cov, jsonschema | 9.1 / 7 / 4.26 | test suite, coverage gate, schema validation of stored records |
| Packaging | setuptools via `pyproject.toml` | — | `pip install -e ".[dev]"`, console script `acam` |

Runtime dependencies are declared in `pyproject.toml`:
`pypdf>=4.0`, `python-docx>=1.1`, `anthropic>=1.0`, `flask>=3.0`.
Development extras (`[dev]`): `pytest>=8`, `pytest-cov>=5`, `jsonschema>=4`.
Server extra (`[server]`): `gunicorn>=23`.

There is no database, cache, queue or JavaScript toolchain. See
[ADR-002](../architecture/decisions/ADR-002-file-based-storage.md) and
[ADR-006](../architecture/decisions/ADR-006-server-rendered-web-ui.md).

## Repository layout

```text
.
├── README.md              project front page: quick start, features, usage
├── pyproject.toml         package metadata, dependencies, pytest config
├── src/acam/         application package (see Architecture overview)
├── schemas/               JSON Schemas for project, source and analysis records
├── tests/                 pytest suite
│   ├── conftest.py        fixtures: builds PDF/DOCX/TXT/HTML from the sample article
│   ├── pdfgen.py          minimal PDF writer (no binary fixtures in the repo)
│   └── test_*.py          conversion, extraction, references, pipeline, cli, web, tenancy
├── examples/              sample-article.md (fictional) for trying the tool
└── docs/                  this documentation
```

## Development setup

```bash
git clone <repo> && cd acam-s2
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest                              # 133 tests + coverage (~50 s), no network or API key needed
python tools/check_coverage.py      # every file must be ≥ 85% covered
docker build --target test .        # both, inside the container image (Python 3.12)
acam --workspace /tmp/lr web        # try the web UI with throwaway data
```

Optional: `export ANTHROPIC_API_KEY=…` to use the LLM engine. Tests never call
the API; they use a fake client.

## Testing strategy

| Test file | Covers |
| --------- | ------ |
| `test_conversion.py` | every format → structured Markdown; page markers; DOCX tables; HTML boilerplate removal; unsupported/empty/scanned/Latin-1 inputs |
| `test_extraction.py` | metadata extraction accuracy on the sample; candidates never validated; no invented values on uninformative text |
| `test_references.py` | author formatting (particles, suffixes, institutions); the specification's book/article/website examples exactly; placeholders; et al.; dates |
| `test_pipeline.py` | import of every format with schema validation; duplicates; failed conversion; heuristic analysis evidence; LLM request shape, provenance, merge rules and refusal (fake client); researcher workflow |
| `test_cli.py` | end-to-end CLI from `init` to `export`; error exit codes |
| `test_web.py` | every web route with a logged-in, CSRF-aware test browser; background jobs run inline |
| `test_locks.py` | lock re-entrancy, exclusion between threads and between processes, timeouts, atomic JSON writes |
| `test_jobs.py` | queue deduplication, FIFO claims, 8 threads claiming 40 jobs with no duplicates, ownership of heartbeat/finish, stale recovery and max attempts, worker registry, owner scoping, purge, rollback |
| `test_worker.py` | success/failure recording, injected LLM client, heartbeats during long jobs, heartbeat errors, crashed-job recovery, background threads start/stop, resilience to database errors |
| `test_concurrency.py` | **real OS processes**: 8 parallel CLI imports (unique ids, complete records), 6 parallel duplicate imports (one kept), 20 parallel notes + 10 tags on one source (nothing lost), 3 worker processes draining 9 jobs (each exactly once), crash recovery + SIGTERM shutdown of a worker process, gunicorn with 3 processes under 24 parallel HTTP edits + an analysis |
| `test_edge_cases.py` | LLM error paths (oversize, truncation, missing/invalid JSON, default client), engine selection, container bootstrap errors, encrypted and corrupt PDFs |
| `test_container.py` | configuration from the environment, `/healthz`, admin bootstrap from env or secret file, WSGI module |
| `test_tenancy.py` | password hashing and file permissions; username/project-id validation and path traversal; login/sign-up rules; admin rights; isolation between users; multiple projects and deletion; `user` CLI |

### Coverage policy

- Every `pytest` run measures **line and branch** coverage (`pyproject.toml`)
  and fails if the total is below **85%**.
- `tools/check_coverage.py` also holds **every file** to 85%. It runs in the
  Docker `test` stage, so an image can't be built from code that misses the bar.
- Current state: 93% total; every file ≥ 86%; the concurrency modules (`locks`,
  `jobs`, `worker`) at 100%.
- Lines excluded from measurement: the Windows fallback without `fcntl`, and the
  blocking `serve_forever` loop. The latter is exercised by the process tests,
  which coverage doesn't instrument.
- Negative control for the locks: with `flock` disabled, the 20-parallel-notes
  scenario kept only 10 of 20 notes. With it enabled, all 20 were kept.

Principles:

- **No binary fixtures.** PDF and DOCX files are generated at test time from
  `examples/sample-article.md`.
- **No network.** The Claude client is injected (`client=` parameter) and faked.
- **Schemas are checked.** Stored records must validate against `schemas/*.json`.

Before relying on the LLM engine in a new environment, run one real analysis with
a key. The automated suite checks the request shape but not live responses.

## Coding conventions

- `from __future__ import annotations`, type hints on public functions.
- Modules match the comment density and naming of existing code; docstrings
  explain *why* when a rule is not obvious.
- Domain functions are pure where possible. State changes happen in `pipeline.py`.
- User-facing errors raise `StorageError`, `ConversionError`, `AccountError` or
  `ValueError` with a message that makes sense to a researcher.
- New formats, engines or reference styles follow
  [Extending ACAM Assistant](../integration/extending.md).

## Upgrading dependencies

1. Bump the range in `pyproject.toml`.
2. `pip install -e ".[dev]" --upgrade && pytest`.
3. For `anthropic`: check the request in `analysis/llm.py` against the SDK
   changelog (parameters `output_config`, `fallbacks`, `betas`), then run one real
   analysis.
4. For `flask`/`werkzeug`: check the session cookie settings and
   `generate_password_hash` defaults. Existing hashes keep working because the
   algorithm is stored in the hash string.
