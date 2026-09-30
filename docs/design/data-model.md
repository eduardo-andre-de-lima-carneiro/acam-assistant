# Data Model

All persistent data is JSON and Markdown on the filesystem. Formal JSON Schemas
live in [`schemas/`](../../schemas) and every stored record is validated against
them in the test suite.

| File | Schema | Content |
| ---- | ------ | ------- |
| `<project>/project.json` | [`project.schema.json`](../../schemas/project.schema.json) | research project definition |
| `<project>/sources.json` | [`source.schema.json`](../../schemas/source.schema.json) (one per entry) | the catalog: one record per source |
| `<project>/analysis/<source-id>.json` | [`analysis.schema.json`](../../schemas/analysis.schema.json) | structured analysis of one source |
| `<data root>/users.json` | none (internal) | user accounts |

## Storage layout

```text
<data root>/                          $ACAM_HOME or --workspace (default ./projects)
├── users.json                        accounts: username, display name, role, scrypt hash (mode 600)
├── users.json.lock                   flock target for account changes
├── .secret_key                       32-byte session signing key (mode 600)
├── jobs.db                           SQLite job queue + worker registry (operational state)
├── <project-id>/                     single-user (CLI without --user) projects
└── users/
    └── <username>/                   one private workspace per account
        └── <project-id>/
            ├── .lock                          flock target for this project's writes
            ├── project.json
            ├── sources.json
            ├── original/<source-id>.<ext>     immutable copy of the imported file
            ├── markdown/<source-id>.md        canonical Markdown
            ├── analysis/<source-id>.json      latest analysis
            └── artifacts/                     generated files (matrix, references, reports, catalog.json)
```

Identifiers:

| Identifier | Pattern | Example |
| ---------- | ------- | ------- |
| username | `^[a-z0-9][a-z0-9_-]{2,31}$` | `eduardo` |
| project id | `^[a-z0-9][a-z0-9_-]{0,63}$`, derived from the title if not given | `ai-se` |
| source id | `source-NNN`, sequential per project | `source-007` |

Timestamps are ISO 8601 UTC strings with a `Z` suffix, e.g. `2026-09-30T18:11:52Z`.

## Project (`project.json`)

```json
{
  "id": "ai-se",
  "title": "AI in Software Engineering",
  "description": "",
  "research_problem": "",
  "research_questions": ["How is AI applied to code review?"],
  "objectives": [],
  "scope": "",
  "inclusion_criteria": ["peer-reviewed"],
  "exclusion_criteria": [],
  "created_at": "2026-09-30T18:00:00Z",
  "updated_at": "2026-09-30T18:05:00Z"
}
```

The research questions are sent to the LLM engine so it can assess each source's
relevance to the project.

## Source record (entry of `sources.json`)

```json
{
  "id": "source-001",
  "type": "journal_article",
  "type_provenance": {"source": "extracted", "confidence": 0.5},
  "status": "analyzed",
  "original_file": {
    "name": "sample-article.pdf",
    "format": "pdf",
    "stored_as": "original/source-001.pdf",
    "sha256": "9f2c…"
  },
  "imported_at": "2026-09-30T18:01:00Z",
  "markdown_file": "markdown/source-001.md",
  "analysis_file": "analysis/source-001.json",
  "conversion": { "status": "passed", "converter": "pypdf", "page_count": 2, "warnings": [], "validation": { … } },
  "metadata": { "title": { … }, "authors": { … }, … },
  "abstract": {
    "original_abstract": "This study investigates…",
    "generated_summary": "An exploratory case study…",
    "summary_type": "structured",
    "generated_at": "2026-09-30T18:02:00Z",
    "requires_validation": true
  },
  "bibliographic_reference": {
    "style": "abnt",
    "text": "SOUZA, M. F.; MILLER, J. P. Large Language Models… **Journal of…**, v. 14, n. 2, p. 45-67, 2025.",
    "missing_fields": [],
    "requires_validation": true
  },
  "analysis": { "status": "pending_review", "engine": "llm", "model": "claude-opus-5-5",
                "analyzed_at": "2026-09-30T18:02:00Z", "confidence": 0.9 },
  "tags": ["llm"],
  "researcher_notes": "Key paper for RQ1",
  "history": [
    {"at": "2026-09-30T18:01:00Z", "event": "imported"},
    {"at": "2026-09-30T18:01:00Z", "event": "converted", "converter": "pypdf", "validation": "passed"},
    {"at": "2026-09-30T18:01:00Z", "event": "metadata_extracted"},
    {"at": "2026-09-30T18:02:00Z", "event": "analyzed", "engine": "llm", "metadata_updated": ["title"]}
  ]
}
```

### Provenance fields

Each metadata field is wrapped so machine output is never mistaken for
validated data:

```json
"title": {
  "value": "Large Language Models as Code Review Assistants",
  "source": "extracted",        // extracted | generated | researcher | unknown
  "confidence": 0.85,           // 0–1, null for researcher values
  "validated": false,           // true only after a researcher confirms or sets it
  "extractor": "llm"            // optional: which engine produced the value
}
```

| Researcher action | Effect |
| ----------------- | ------ |
| **Confirm** (`confirm`, web "Confirm") | `validated: true`, `source` unchanged (keeps who found it) |
| **Set** (`set`, web "Save") | `value` replaced, `source: "researcher"`, `confidence: null`, `validated: true` |

Metadata fields: `title`, `authors` (list), `publication_year` (integer),
`publisher`, `journal`, `volume`, `issue`, `pages`, `doi`, `url`, `edition`,
`publication_place`, `access_date` (ISO date), `keywords` (list).

The source **type** has its own `type_provenance` with the same meaning. Types:
`book`, `book_chapter`, `journal_article`, `conference_paper`, `thesis`,
`dissertation`, `technical_report`, `website`, `online_article`, `preprint`,
`other`.

### Merge rule for LLM metadata

When an analysis returns `metadata_candidates`, a field is updated only if:

1. it is **not** validated, **and**
2. it is empty **or** its current confidence is below **0.8**.

Updated fields get `source: "extracted"`, `confidence: 0.8`, `extractor: "llm"`.
The type is updated unless the researcher set it. So a regex-found DOI
(confidence 0.95) is kept, while a weak title guess (0.5) gets replaced.

### Status lifecycle

```text
imported ─► converted ─► extracted ─► analyzed ─► under_review ─► validated ─► included
                │                                      │
                └─ (validation failed: stays here)     └─► rejected
```

| Status | Set by |
| ------ | ------ |
| `imported`, `converted`, `extracted` | import pipeline |
| `analyzed` | analysis (only from an earlier automatic state) |
| `under_review`, `validated`, `rejected`, `included` | the researcher |

Re-analyzing a source the researcher already moved to `validated` does **not**
change its status. Rejected sources are left out of the matrix and reference list
unless explicitly included.

### Conversion report

`conversion.validation` holds the result of the checks described in
[Processing pipeline → Validate](processing-pipeline.md#3-validate):
`passed`, `status` (`passed` / `passed_with_warnings` / `failed`), `characters`,
`words`, `headings`, `recognized_sections` and the list of `checks`.

## Analysis (`analysis/<source-id>.json`)

The same shape comes from both engines:

| Field | Type | Notes |
| ----- | ---- | ----- |
| `source_id`, `engine` | string | `engine` is `llm` or `heuristic` |
| `processing` | object | `processed_at`, `processor_version`, `analysis_model` (null for heuristic), `prompt_version`, and for LLM `input_tokens`, `output_tokens` |
| `requires_validation` | `true` | always |
| `metadata_candidates` | object or null | bibliographic data found by the LLM; null for heuristic |
| `summary` | string | generated summary (heuristic: extractive, `summary_type: "extractive"`) |
| `research_problem`, `research_objective`, `theoretical_framework`, `conclusions`, `relevance_to_project` | string | `"unknown"` when not stated |
| `research_questions`, `hypotheses`, `future_research`, `relevant_concepts`, `theories`, `frequently_cited_authors`, `warnings` | string[] | |
| `methodology` | object | `approach` (enum below), `description`, `population_sample`, `data_collection`, `analysis_method` |
| `main_findings`, `limitations`, `contributions`, `research_gaps` | evidence[] | see below |
| `definitions` | `{term, definition, page}[]` | |
| `confidence` | number 0–1 | heuristic always 0.3 |

Methodology approaches: `qualitative`, `quantitative`, `mixed_methods`,
`systematic_review`, `literature_review`, `experimental`, `quasi_experimental`,
`case_study`, `survey`, `design_science`, `theoretical`, `other`, `unknown`.

Evidence item:

```json
{ "text": "Median review time fell 23%.", "section": "4. Results", "page": 3,
  "quote": "a reduction of 23%" }
```

Only the latest analysis per source is kept (`analysis/<id>.json` is
overwritten when a source is re-analyzed). Earlier runs remain in the source's
`history` as events.

## Accounts (`users.json`)

```json
{ "users": [
  { "username": "eduardo", "display_name": "Eduardo", "is_admin": true,
    "password_hash": "scrypt:32768:8:1$…", "created_at": "2026-09-30T18:39:55Z" }
] }
```

Plain-text passwords are never stored. The file is written with mode `600`.
See [Security](../security/security.md#authentication).

## Generated artifacts

| File | Produced by | Content |
| ---- | ----------- | ------- |
| `literature-matrix.md` / `.csv` | `matrix`, web download | ID, author, year, type, title, objective, methodology, findings, gaps, status |
| `references.md` | `references` | ABNT references in alphabetical order, with HTML comments flagging missing/unvalidated data |
| `<source-id>-analysis.md` | `report` | human-readable report separating source evidence from generated content |
| `catalog.json` | `export` | `{project, sources[]}` with each source's `analysis_result` embedded |

Artifacts are always regenerated from the JSON and never edited by hand. See
[Data exchange](../integration/data-exchange.md) for formats.
