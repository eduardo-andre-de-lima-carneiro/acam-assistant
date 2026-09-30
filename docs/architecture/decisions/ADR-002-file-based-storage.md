# ADR-002: File-based JSON and Markdown storage

- **Status:** Accepted
- **Date:** 2026-09-30

## Context

The data per project is small (tens to hundreds of sources). The specification
values portability, versioning with Git, transparency and reproducibility, and
researchers should be able to open and back up their data without tools.

## Decision

Store everything as files: `project.json`, `sources.json`, `analysis/*.json`,
`markdown/*.md`, `original/*`, `artifacts/*`. Writes go to a temporary file that
then atomically replaces the target. A process-wide lock serializes
read-modify-write cycles. JSON Schemas in `schemas/` document the formats and are
checked in tests.

## Consequences

- No database to install or operate. A project is a folder that can be copied,
  zipped or committed.
- Backups are a file copy.
- Data can be inspected with any editor.
- Concurrency relies on file locks (`flock`), so the data root must be on a local
  filesystem (see ADR-010).
- Cross-project queries (for example "all sources by author X") require scanning
  files. That is acceptable at the intended scale.

## Alternatives considered

- *SQLite:* robust concurrency, but binary and harder to diff or version.
  Worth reconsidering if cross-project search or project sharing is added.
- *Server database (PostgreSQL):* adds a service to operate; not justified yet.
