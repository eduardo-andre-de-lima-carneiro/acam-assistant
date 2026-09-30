# ADR-006: Server-rendered Flask web interface without a build step

- **Status:** Accepted
- **Date:** 2026-09-30

## Context

Researchers need a web interface, but the project has no front-end toolchain.
It must work offline and be easy to maintain for a small team.

## Decision

Use Flask with Jinja2 templates, one hand-written CSS file and a small vanilla JS
file (drag and drop, table filtering, job polling, copy button). No external
assets. The web layer is a thin adapter over the same `pipeline`, `artifacts`
and `accounts` functions the CLI uses.

## Consequences

- No node/npm, no bundler; `pip install` is the whole setup.
- Works offline, loads fast, and follows the OS light/dark mode.
- Behaviour is identical to the CLI because the same functions run.
- Rich client interactions (inline editing without reloads, live collaboration)
  would need more JavaScript or a front-end framework later.

## Alternatives considered

- *FastAPI + SPA (React/Vue):* more flexible, but adds a build and two codebases.
- *Streamlit-style frameworks:* quick to start, but limited control over
  authentication, routing and layout.
