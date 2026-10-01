# Design Overview & Principles

## Purpose

**ACAM Assistant** (ACAM = *Academic Management*) is a research assistant for
managing academic work. Version 0.1.0 focuses on literature reviews. The full
original vision is in the [product specification](specification.md); this
document summarizes it and states what 0.1.0 implements.

ACAM Assistant reduces the repetitive work of a literature review: collecting sources,
converting them to text, cataloging bibliographic data, extracting objectives,
methods, findings, limitations and gaps, and producing matrices and reference
lists. The researcher keeps full control over interpretation and every
academic decision.

> The goal is not to automate the researcher's thinking. The goal is to remove
> repetitive work so researchers can spend more time thinking.

## Users

| User | Needs |
| ---- | ----- |
| Students (TCC, master's, PhD) | organize sources, get structured summaries, produce ABNT references and a literature matrix |
| Researchers and professors | run several reviews in parallel, keep an auditable, reproducible record |
| Research groups | each member works in a private space on the same server |
| Administrators | create accounts, operate and back up the server |

## Scope of version 0.1.0

In scope:

- Multi-user web application and command-line tool over the same core.
- Private workspace per user, with any number of projects.
- Import of PDF, DOCX, TXT, Markdown and HTML.
- Conversion to canonical Markdown and validation of the conversion.
- Candidate metadata extraction and ABNT-style reference generation.
- Per-source analysis by Claude (LLM engine) or offline rules (heuristic engine).
- Researcher validation workflow and status lifecycle.
- Artifacts: literature matrix (Markdown/CSV), reference list, per-source reports,
  full JSON export.

Not in scope yet: cross-source synthesis, OCR, EPUB, project sharing between
users, PRISMA tracking. See [the MVP plan](../planning/mvp-plan.md#6-next-iterations-from-the-specification-roadmap).

## Design principles

These principles come from the product specification and are enforced in code.
Each links to where it is implemented.

### 1. Markdown is the canonical analytical representation

Every source is converted to Markdown before any analysis. Analysis code never
reads PDFs or DOCX files. The original file is kept unchanged, as the
authoritative source.

```text
Original file (immutable, authoritative)
      │  conversion/
      ▼
Canonical Markdown (what analysis reads)
      │  extraction/, analysis/
      ▼
Structured JSON (derived data, with provenance and validation status)
      │  artifacts/
      ▼
Academic artifacts (always regenerated from JSON)
```

Implemented in `src/acam/conversion/` and `pipeline.import_source`.
Rationale: [ADR-001](../architecture/decisions/ADR-001-markdown-canonical-format.md).

### 2. No fabrication

The system never invents authors, titles, dates, DOIs, citations, findings,
methods, statistics or quotes. Missing values stay `null` or `"unknown"`, and
references use ABNT placeholders (`[s.l.]`, `[s.n.]`, `[s.d.]`) and list what is
missing. The LLM prompt forbids outside knowledge and requires `"unknown"` when
the text does not say something.

### 3. Researcher in the loop

Machine output is *candidate* data until a human validates it:

- metadata fields carry `validated: false` until confirmed or set by the researcher;
- analyses carry `requires_validation: true`;
- status changes (`validated`, `included`, `rejected`) are only made by people;
- values the researcher validated are never overwritten by later analysis runs.

See [Data model → provenance fields](data-model.md#provenance-fields).
Rationale: [ADR-003](../architecture/decisions/ADR-003-provenance-and-validation.md).

### 4. Traceability

PDF conversion inserts `<!-- page: N -->` markers. Findings, limitations,
contributions and gaps are *evidence items* holding the section, the page and a
verbatim quote. Each source keeps an append-only `history` of events.

### 5. Reproducibility

Every analysis records the engine, model, prompt version, processor version,
timestamp and token usage. Originals, Markdown and JSON are all kept, so a
dataset can be rebuilt and audited.

### 6. Transparency

AI-generated content is labelled everywhere: "machine-generated" badges in the web
interface, a notice at the top of each generated artifact, and separate fields
for the author's abstract and the generated summary.

### 7. Plain files, modular components

All data is JSON and Markdown on disk. This works with Git and backups and is
easy to inspect. Conversion, extraction, analysis, references and artifacts are
separate modules with their own tests.
Rationale: [ADR-002](../architecture/decisions/ADR-002-file-based-storage.md).

### 8. Private by default

Each account gets an isolated workspace, and nothing is shared between users.
Rationale: [ADR-007](../architecture/decisions/ADR-007-filesystem-multi-tenancy.md).

## Quality attributes

| Attribute | How it is achieved |
| --------- | ------------------ |
| Reliability | extraction fails safe (unknown instead of guesses); conversion validation blocks extraction from empty or garbled text |
| Traceability | page markers, evidence items, event history |
| Reproducibility | processing metadata on every analysis; immutable originals |
| Maintainability | independent modules; 75 automated tests; JSON schemas |
| Extensibility | converter registry, engine switch, reference builder per type ([Extending](../integration/extending.md)) |
| Portability | a project is a folder; `catalog.json` export |
| Security | authentication, CSRF protection, per-user isolation, strict identifiers ([Security](../security/security.md)) |
| Usability | web interface that works on phones; drag-and-drop import; background analysis |

## Explicit limitations (by design)

ACAM Assistant does not decide whether a study is valid, whether evidence is
sufficient, whether a gap really exists, or whether a source belongs in a
systematic review. Those decisions stay with the researcher. Detected research
gaps are labelled as *hypotheses*.
