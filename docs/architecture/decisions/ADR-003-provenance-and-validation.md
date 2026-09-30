# ADR-003: Provenance-wrapped metadata and researcher validation

- **Status:** Accepted
- **Date:** 2026-09-30

## Context

Machine-extracted bibliographic data and AI analyses can be wrong. The
specification requires that generated information never be treated as
authoritative, and that the researcher stays responsible for validation.

## Decision

Every metadata field is stored as `{value, source, confidence, validated}`.
Machine values are `validated: false`. The researcher either **confirms** a
value (validated, origin kept) or **sets** it (origin `researcher`). Later
analysis runs never overwrite validated fields or a researcher-set type. They
only fill empty or low-confidence (< 0.8) fields. Analyses always carry
`requires_validation: true`. Status changes past `analyzed` are manual.

## Consequences

- The interfaces can show where each value came from (badges) and how
  confident the system is.
- References and reports can flag unvalidated data.
- Records are more verbose than plain key/value metadata.

## Alternatives considered

- *Plain values plus a per-record "verified" flag:* too coarse; you could not
  tell which field was checked.
- *Separate "extracted" and "validated" copies of the metadata:* duplication and
  merge complexity.
