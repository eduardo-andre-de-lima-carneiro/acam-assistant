# ADR-005: One Claude call per source with structured outputs

- **Status:** Accepted
- **Date:** 2026-09-30

## Context

The LLM engine must return machine-readable data that conforms to the analysis
schema, keep each claim tied to the source, and be reproducible.

## Decision

For each source, make **one** streamed Messages API request to
`claude-opus-5-5` with:
- a static system prompt stating the no-fabrication and evidence rules;
- the project context and the full canonical Markdown in the user turn;
- `output_config.format` = JSON schema of the analysis (structured outputs), and
  `effort: "medium"`;
- server-side refusal fallback (`fallbacks: "default"`).

Inputs above 2,000,000 characters are refused rather than truncated.
The model id and a prompt version are recorded in each analysis.

## Consequences

- The output always parses against the schema. No fragile text parsing.
- One call per source keeps cost predictable and traceable.
- Very long books may exceed the size limit and need to be split.
- The model can be changed with `ACAM_MODEL`. The prompt version must be bumped when
  the prompt or schema changes.

## Alternatives considered

- *Multiple calls per field:* more cost and latency, and fields may contradict each other.
- *Free-text output parsed with regexes:* brittle.
- *Tool use to force JSON:* structured outputs is the direct mechanism.
