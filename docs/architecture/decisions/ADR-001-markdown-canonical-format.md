# ADR-001: Markdown as the canonical analytical format

- **Status:** Accepted
- **Date:** 2026-09-30

## Context

Sources arrive as PDF, DOCX, HTML, TXT or Markdown. If analysis code read every
format directly, each extractor and engine would need format-specific logic,
results would be hard to compare, and debugging an analysis would require the
original binary file. The specification requires one intermediate representation.

## Decision

Every source is converted to Markdown at import (`markdown/<id>.md`) and all
downstream processing (validation, metadata extraction, both analysis engines)
reads only that Markdown. PDF conversion adds `<!-- page: N -->` markers so page
numbers survive. The original file is kept unchanged in `original/`.

## Consequences

- Adding a format means writing one converter. Nothing downstream changes.
- Researchers can read and diff exactly what the analysis saw (web: "Markdown").
- LLM input is compact text rather than binary documents.
- Some layout information (multi-column order, complex tables, figures) is lost.
  This is accepted for the MVP and flagged by conversion validation.

## Alternatives considered

- *Send PDFs directly to the LLM (native PDF input):* the heuristic engine
  and metadata extraction could not use it; ties analysis to one provider.
- *HTML or JSON document model:* richer, but less readable and diffable.
