# ADR-004: Two analysis engines with one output schema

- **Status:** Accepted
- **Date:** 2026-09-30

## Context

LLM analysis gives the best results but needs an API key, costs money and needs
network access. The tool must also work offline, in classrooms, and in automated
tests.

## Decision

Provide two engines producing the same JSON shape (`analysis/schema.py`):
`llm` (Claude) and `heuristic` (offline, extractive, verbatim sentences only).
`auto` chooses `llm` when Anthropic credentials are configured. Each analysis
records which engine and model produced it.

## Consequences

- The whole application, including the web interface and every test, works
  without an API key.
- The heuristic engine has low recall; its output is labelled with confidence 0.3
  and a warning.
- Anything that consumes analyses (reports, matrix, web pages) is engine-agnostic.

## Alternatives considered

- *LLM only:* simpler, but unusable offline and hard to test.
- *Local LLM:* heavy install, inconsistent quality; could be added later as a third engine.
