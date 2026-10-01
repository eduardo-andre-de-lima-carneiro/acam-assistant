# MVP Implementation Plan

> Scope and delivery record for version 0.1.0. The detailed, maintained
> descriptions now live in the topic documents: [design](../design/overview.md),
> [architecture](../architecture/overview.md), [security](../security/security.md),
> [deployment](../deployment/server.md) and [integration](../integration/claude-api.md).

This document turns the [product specification](../design/specification.md) into the plan that was used to build
version 0.1.0, and records what is in scope, how it is built, and what comes next.

## 1. Goal of the MVP

Deliver the specification's **Initial MVP Scope** as a small, reliable, testable tool:

| MVP requirement (specification) | Delivered as |
| ------------------------------ | ------------ |
| Input: PDF, DOCX, Markdown, TXT | All four, plus HTML |
| Import                          | `acam import`: copies the original into `original/`, computes SHA-256, assigns `source-NNN` |
| Convert                         | `conversion/`: one converter per format, output is the canonical Markdown in `markdown/` |
| Validate Markdown               | `validation.py`: empty text, length, encoding, headings, academic sections, words per page |
| Extract metadata                | `extraction/metadata.py`: title, authors, year, DOI, journal, volume, issue, pages, URL, keywords, original abstract |
| Generate summary                | Analysis `summary`, stored apart from the author's abstract (`abstract.generated_summary` and `abstract.original_abstract`) |
| Analyze source                  | `analysis/`: `llm` (Claude) or `heuristic` engine, same output schema |
| Store JSON                      | `project.json`, `sources.json`, `analysis/<id>.json`, validated by the files in `schemas/` |
| Output: bibliographic reference | `references/abnt.py`: book, article and website structures from the specification, with ABNT placeholders |

Also included because they were cheap and needed for real use: the researcher
validation workflow, the literature matrix, the reference list, per-source reports,
JSON export, tags, notes, duplicate detection by exact file hash, a **web
interface** (`acam web`), and **multi-tenancy**: user accounts, each with a
private workspace that holds any number of projects.

## 2. Architecture

```text
cli.py ─┐
web/  ──┴► pipeline.py ──► conversion/  (pdf, docx, html, txt, md → Markdown)
                      ├──► validation.py
                      ├──► extraction/metadata.py
                      ├──► analysis/   (llm.py | heuristic.py, schema.py)
                      ├──► references/abnt.py
                      └──► storage.py  (file-based project repository)
artifacts/  ◄── reads only the JSON catalog + analyses (never the originals)
```

Each stage is a separate module with its own tests, as the specification asks
("each processing stage should be independently testable"). Analysis code only
ever receives Markdown.

### Key design decisions

1. **Provenance-wrapped metadata.** Every metadata field is stored as
   `{value, source, confidence, validated}`. Machine output is always
   `validated: false`. `acam confirm` validates an extracted value, and
   `acam set` stores a researcher value (`source: "researcher"`). The LLM
   engine can fill empty or low-confidence fields but never overwrites validated
   ones or a source type the researcher set.
2. **No fabrication.** Extractors return `null`/`"unknown"` instead of guessing.
   References use ABNT placeholders (`[s.l.]`, `[s.n.]`, `[s.d.]`) and list the
   missing fields.
3. **Traceability.** The PDF converter writes `<!-- page: N -->` markers. Findings,
   limitations, contributions and gaps are evidence items with
   `{text, section, page, quote}`. The heuristic engine only emits verbatim quotes.
4. **Reproducibility.** Every analysis records `processed_at`, `processor_version`,
   `analysis_model`, `prompt_version` and token usage. Each source keeps an
   append-only `history` of events.
5. **Plain files, Git-friendly.** Projects are directories of JSON and Markdown.
   There is no database and no server.
6. **LLM integration.** One Claude call per source (`claude-opus-5-5`, adaptive
   thinking, `effort: medium`) using structured outputs (`output_config.format`
   with a JSON schema). Server-side refusal fallback (`fallbacks: "default"`) is on.
   The whole document is sent; documents above ~2M characters are refused, never
   silently truncated.
7. **Offline mode.** The heuristic engine keeps the tool usable, and fully
   testable, without an API key.
8. **Web interface.** Flask with server-rendered templates and plain CSS/JS: no
   build step and no external assets, so it works offline. It is a thin layer over
   the same pipeline functions as the CLI. Analyses run in a background thread pool
   and the page polls a small JSON endpoint. Catalog writes go through one lock,
   and analysis re-reads the record before saving, so researcher edits made during
   an analysis are not lost.
9. **Multi-tenancy.** Each account gets its own workspace directory,
   `<root>/users/<username>/`, containing that user's projects. Isolation comes from
   the filesystem layout: every web request resolves projects only inside the
   logged-in user's directory, and usernames and project ids are validated against
   strict patterns, so a crafted id such as `../bob/x` can't escape. Background jobs
   are owned by a user and filtered by owner. Accounts are stored in `users.json`
   (scrypt hashes, mode 600). The first account becomes administrator, and further
   accounts are created by an admin or through optional self-service sign-up. The CLI
   targets a user's space with `--user`, and `acam user adopt` migrates
   single-user data. File-based tenancy fits the project's "plain files,
   Git-friendly" principle and needs no database. A database becomes worthwhile
   only for many concurrent users or cross-user features such as shared projects.

## 3. Status lifecycle

`imported → converted → extracted → analyzed → under_review → validated → included`,
with `rejected` possible from review. Import sets `converted` and then `extracted`.
If validation fails, the source stays `converted` and has no metadata. Analysis sets
`analyzed`. All later states are set by the researcher with `acam status`.

## 4. Testing strategy

- Fixtures are built at test time from `examples/sample-article.md` as PDF (a small
  built-in PDF writer), DOCX (python-docx), TXT and HTML, so there are no binary
  files in the repository.
- Reference tests reproduce the specification's three examples exactly.
- The Claude call is exercised with a fake client. The tests check the request
  shape (model, JSON-schema output, fallbacks, project context), the recorded
  provenance, the metadata merge rules and refusal handling.
- Every stored record and analysis is validated against `schemas/*.schema.json`.
- The CLI is tested end to end, from `init` to `export`.
- Every web route is tested with Flask's test client. Background jobs run inline
  in tests.

## 5. Known limitations of 0.1.0

- **Scanned PDFs** are detected (warning, failed validation) but not OCR'd.
- **PDF structure** comes from heuristics: only recognized section names become
  headings. Tables and multi-column layouts come out as plain text.
- **Metadata heuristics** are best-effort, especially author detection. That is why
  confidence scores and the confirm/set workflow exist.
- **References** cover the specification's book, article and website structures. Other
  types fall back to a generic form.
- **Duplicate detection** only catches identical files (same hash).
- The **LLM engine was verified with a fake client only**. Run it once against the
  real API with your key before relying on it.
- No cross-source synthesis yet, apart from the matrix.
- Multi-tenancy has no project sharing yet (each project belongs to exactly one
  user), no login rate limiting, and no email-based password reset. An admin resets
  a password with `acam user passwd`. All users share the server's Anthropic
  API key.
- Concurrency is limited to one host. File locks and the SQLite queue need a
  local filesystem ([ADR-010](../architecture/decisions/ADR-010-multi-process-concurrency.md)).

## 6. Next iterations (from the specification roadmap)

1. **Phase 5: synthesis.** A cross-source LLM pass over the validated analyses
   (themes, methodology comparison, consistent/contradictory findings, gap report),
   written as artifacts that separate source evidence, generated synthesis and
   researcher interpretation.
2. **Batch analysis** through the Message Batches API (50% cost) for large imports.
3. **Better conversion:** OCR for scanned PDFs, EPUB input, table extraction.
4. **Duplicate detection** by DOI or normalized title+year+author.
5. **Artifact templates:** literature review draft, research gap analysis,
   theoretical framework draft.
6. **PRISMA tracking:** identification, screening and eligibility counts from
   statuses and criteria.
7. **Web UI v2:** side-by-side view of the original PDF and the extracted
   evidence (jump to page), and cross-source synthesis pages.
8. **Collaboration:** share a project with other users (read-only or editor),
   per-user API keys or usage quotas, login rate limiting, and password reset by
   email.
