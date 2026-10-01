# ACAM Assistant

**ACAM** stands for **Academic Management**. ACAM Assistant helps students,
researchers and professors manage academic work, starting with **literature
reviews**: it organizes sources, converts them to a standard format, catalogs
their bibliographic data, analyzes each one, and produces academic artifacts.
The researcher stays in control of every interpretation and decision.

> The goal is not to automate the researcher's thinking. The goal is to remove
> repetitive work so researchers can spend more time thinking.

**Version 0.1.0 (MVP)** · Python 3.10+ · MIT License

---

## Contents

- [Quick start](#quick-start)
- [Features](#features)
- [How it works](#how-it-works)
- [Using the web interface](#using-the-web-interface)
- [Using the command line](#using-the-command-line)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Documentation](#documentation)
- [Development](#development)
- [Project status and roadmap](#project-status-and-roadmap)
- [License](#license)

---

## Quick start

### Option A: on your computer

```bash
git clone <repository-url> acam-assistant && cd acam-assistant
python3 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
acam web                               # open http://127.0.0.1:8000
```

The first visit asks you to create the **administrator** account. Then create a
project, drag in some PDFs, and they are converted and analyzed. You can try it
with [`examples/sample-article.md`](examples/sample-article.md).

### Option B: with Docker

```bash
cp .env.example .env                   # optional: API key, first admin, HTTPS domain
docker compose up -d --build           # open http://127.0.0.1:8000
```

### Enable AI analysis (optional)

Without an API key, the offline **heuristic** engine is used. To have Claude read
and analyze each source:

```bash
export ANTHROPIC_API_KEY=sk-ant-...    # or put it in .env for Docker
```

The header of the web interface shows which engine is active.

---

## Features

**Sources and conversion**
- Import **PDF, DOCX, TXT, Markdown and HTML**. Each file is converted to a
  canonical **Markdown** representation that keeps headings, tables and page
  numbers.
- Conversion quality checks: empty or garbled text, missing sections, and
  scanned PDFs that need OCR.
- The original file is kept unchanged. Duplicates are detected.

**Cataloging**
- Candidate bibliographic metadata (title, authors, year, DOI, journal, volume,
  pages, keywords, abstract), each with a **confidence score** and its
  **origin**.
- **ABNT-style references** for books, articles and websites, with placeholders
  for missing data instead of invented values.
- Tags, notes, and a review status lifecycle (`imported → … → validated / rejected → included`).

**Analysis**
- Per-source analysis: research problem, objective, questions, methodology,
  findings, limitations, contributions, research gaps, concepts and theories.
- Every finding carries its **section, page and a verbatim quote**.
- Two engines: **Claude** (structured outputs) or an **offline heuristic** engine.
- The author's abstract and the generated summary are always kept apart.

**Researcher in the loop**
- Nothing machine-generated counts as validated until you **confirm** or **edit** it.
- Values you validated are never overwritten by later analyses.
- Full event history per source; every analysis records engine, model and prompt version.

**Artifacts**
- Literature matrix (Markdown / CSV), ABNT reference list, per-source analysis
  reports, and a complete JSON export.

**Multi-user and operations**
- **Accounts with private workspaces:** each user has their own space with any
  number of projects.
- Web interface and command line over the same core.
- Background analysis through a durable job queue and separate workers. Safe
  concurrent use by many users and processes.
- Container image with Docker Compose, optional automatic HTTPS, and health checks.

---

## How it works

```text
Original file ─► Markdown ─► Validation ─► Candidate metadata ─► Analysis ─► Researcher validation ─► Artifacts
 (kept as is)    (canonical)                 (with confidence)     (evidence)    (confirm / edit)        (matrix, references…)
```

1. **Original documents** stay authoritative and are never modified.
2. **Markdown** is the only input to analysis, whatever the original format.
3. **Structured JSON** holds everything derived, with provenance and validation status.
4. **Artifacts** are always regenerated from the JSON, never edited by hand.

Projects are plain folders of JSON and Markdown, easy to back up, move or put
under Git. Details: [design overview](docs/design/overview.md) and
[processing pipeline](docs/design/processing-pipeline.md).

---

## Using the web interface

```bash
acam web                               # http://127.0.0.1:8000 (listens on this computer only)
```

| Page | What you do there |
| ---- | ----------------- |
| **My projects** | create projects; each user only ever sees their own |
| **Project** | define research questions, objectives, scope and inclusion/exclusion criteria; drag and drop files; filter sources; analyze in bulk; follow analysis jobs |
| **Source** | compare the author's abstract with the generated summary; confirm or correct metadata (badges show each value's origin and confidence); read the analysis with evidence; set review status, tags and notes; open the Markdown or the original file |
| **Literature matrix / References** | view and download the matrix (`.md`, `.csv`) and the ABNT reference list |
| **Account** | change your password; administrators create accounts |

Accounts: the first visitor becomes the administrator. Administrators add users
on the Account page. Start with `acam web --allow-signup` to let people register
themselves.

---

## Using the command line

The `acam` command covers the same workflow, plus administration:

```bash
# Create a project and import sources
acam init "AI in Software Engineering" --id ai-se -q "How is AI applied to code review?"
acam import ai-se examples/sample-article.md papers/*.pdf --tag llm

# Analyze (use --engine heuristic to stay offline, --queue to hand it to the worker)
acam analyze ai-se

# Review and validate
acam list ai-se
acam show ai-se source-001
acam confirm ai-se source-001 title authors doi
acam set ai-se source-001 publisher "Springer"
acam status ai-se source-001 validated --note "meets inclusion criteria"

# Produce artifacts (written to <project>/artifacts/)
acam matrix ai-se            # literature-matrix.md   (--csv for spreadsheets)
acam references ai-se        # references.md          (ABNT, alphabetical)
acam export ai-se            # catalog.json
```

Accounts and multi-user use:

```bash
acam user add maria --name "Maria"     # prompts for a password
acam user list
acam --user maria projects             # any command can work in a user's workspace
acam worker                            # background analysis worker
acam jobs                              # queue status
```

Without `--user`, commands work in the data root as a single-user workspace.
Run `acam --help` or see the full [CLI reference](docs/integration/cli-reference.md).

---

## Configuration

Everything is configured through environment variables (or `.env` for Docker).
The most common ones:

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `ACAM_HOME` | `./projects` | data root: accounts, workspaces, job queue |
| `ANTHROPIC_API_KEY` | — | enables Claude analysis (on servers prefer `ANTHROPIC_API_KEY_FILE`, a secret file) |
| `ACAM_MODEL` | `claude-opus-5-5` | Claude model |
| `ACAM_ALLOW_SIGNUP` | `false` | let anyone create an account |
| `ACAM_SECURE_COOKIES` | `false` | set to `true` when served over HTTPS |
| `ACAM_ADMIN_USER` / `ACAM_ADMIN_PASSWORD_FILE` | — | create the first administrator at start-up (containers) |
| `ACAM_WORKER_THREADS` | `2` | concurrent analyses per worker |

All settings, flags and limits: [configuration reference](docs/deployment/configuration.md).
Every variable is documented in [`.env.example`](.env.example).

---

## Deployment

| Scenario | Guide |
| -------- | ----- |
| Personal use on a laptop | [Local installation](docs/deployment/local.md) |
| Research group server, **recommended** | [Container deployment](docs/deployment/container.md): Docker Compose with web + worker services, optional automatic HTTPS (`docker compose --profile tls up -d`) |
| Server without containers | [Server deployment](docs/deployment/server.md): gunicorn, systemd, nginx |

Keep the data root on a local disk (not an NFS/SMB share), and use HTTPS for
anything beyond your own computer. See [Security](docs/security/security.md),
including what the Claude engine sends to Anthropic.

---

## Documentation

The full documentation is in [`docs/`](docs/README.md).

| Topic | Documents |
| ----- | --------- |
| Design | [overview & principles](docs/design/overview.md) · [product specification](docs/design/specification.md) · [data model](docs/design/data-model.md) · [processing pipeline](docs/design/processing-pipeline.md) · [user experience](docs/design/user-experience.md) |
| Architecture | [overview](docs/architecture/overview.md) · [decision records](docs/architecture/decisions/README.md) |
| Technology | [stack, development setup & testing](docs/technology/stack.md) |
| Security | [threat model, controls & known gaps](docs/security/security.md) |
| Deployment | [local](docs/deployment/local.md) · [container](docs/deployment/container.md) · [server](docs/deployment/server.md) · [configuration](docs/deployment/configuration.md) |
| Integration | [Claude API](docs/integration/claude-api.md) · [CLI](docs/integration/cli-reference.md) · [HTTP](docs/integration/http-interface.md) · [data exchange](docs/integration/data-exchange.md) · [extending](docs/integration/extending.md) |
| Planning | [MVP plan & roadmap](docs/planning/mvp-plan.md) |

---

## Development

```bash
pip install -e ".[dev,server]"
pytest                                 # tests + coverage report; fails below 85%
python tools/check_coverage.py         # every file must also reach 85%
docker build --target test .           # the same checks inside the container image
```

The tests need no network or API key. They include real multi-process tests:
parallel imports, parallel edits, several workers, and gunicorn with several processes.

```text
src/acam/          application package (conversion, extraction, analysis, references,
                   pipeline, artifacts, accounts, jobs/worker, web, cli)
schemas/           JSON Schemas of project, source and analysis records
tests/             pytest suite (fixtures generate PDF/DOCX at test time)
docker/            gunicorn config, entrypoint, Caddyfile
docs/              documentation
examples/          sample article
tools/             per-file coverage check
```

Before adding a format, analysis engine, reference style or artifact, read
[Extending ACAM Assistant](docs/integration/extending.md). Significant design
changes get a new [decision record](docs/architecture/decisions/README.md).

---

## Project status and roadmap

**0.1.0 (MVP) delivered:**
- import and conversion of 5 formats;
- validation, metadata extraction and ABNT references;
- per-source analysis (Claude or offline);
- researcher validation workflow and artifacts;
- multi-user web interface and CLI;
- durable background jobs;
- container deployment.

**Next:** cross-source synthesis (themes, methods, contradictions, gap reports),
batch analysis, OCR and EPUB, smarter duplicate detection (DOI/title), more
artifact templates, PRISMA tracking, and project sharing between users. The full
plan is in [docs/planning/mvp-plan.md](docs/planning/mvp-plan.md). The original
product vision is in the [product specification](docs/design/specification.md).

**By design**, ACAM Assistant does not decide whether a study is valid, whether
evidence is sufficient, whether a gap really exists, or whether a source belongs
in a review. Those decisions stay with the researcher.

---

## License

[MIT](LICENSE)
