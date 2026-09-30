# Architecture Decision Records

Each record explains one significant decision: context, decision, consequences and
alternatives. Add a new record (next number) when a decision changes, and mark the
old one *Superseded*.

| ADR | Decision | Status |
| --- | -------- | ------ |
| [ADR-001](ADR-001-markdown-canonical-format.md) | Markdown as the canonical analytical format | Accepted |
| [ADR-002](ADR-002-file-based-storage.md) | File-based JSON and Markdown storage | Accepted |
| [ADR-003](ADR-003-provenance-and-validation.md) | Provenance-wrapped metadata and researcher validation | Accepted |
| [ADR-004](ADR-004-dual-analysis-engines.md) | Two analysis engines with one output schema | Accepted |
| [ADR-005](ADR-005-claude-structured-outputs.md) | One Claude call per source with structured outputs | Accepted |
| [ADR-006](ADR-006-server-rendered-web-ui.md) | Server-rendered Flask web interface without a build step | Accepted |
| [ADR-007](ADR-007-filesystem-multi-tenancy.md) | Filesystem-based multi-tenancy | Accepted |
| [ADR-008](ADR-008-in-process-jobs-single-process.md) | In-process background jobs and single-process deployment | Superseded by ADR-010 |
| [ADR-009](ADR-009-container-packaging.md) | Container image and Compose as the reference deployment | Accepted |
| [ADR-010](ADR-010-multi-process-concurrency.md) | Multi-process concurrency with file locks and a SQLite job queue | Accepted |
