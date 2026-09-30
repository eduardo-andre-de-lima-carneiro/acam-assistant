# Claude API Integration

The LLM analysis engine (`src/acam/analysis/llm.py`) uses Anthropic's Claude
through the official Python SDK (`anthropic`).
Design rationale: [ADR-005](../architecture/decisions/ADR-005-claude-structured-outputs.md).

## When it is used

| Engine option | Behaviour |
| ------------- | --------- |
| `auto` (default) | LLM if `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` or `ANTHROPIC_PROFILE` is set; otherwise heuristic |
| `llm` | always LLM (fails if no credentials) |
| `heuristic` | never calls the API |

## The request

One streamed Messages API request per source:

```python
client.beta.messages.stream(
    model="claude-opus-5-5",                     # or $ACAM_MODEL
    max_tokens=32000,
    system=SYSTEM_PROMPT,                        # static rules (below)
    messages=[{"role": "user", "content": "<project>…</project>\n\n<source …>MARKDOWN</source>\n\nExtract…"}],
    output_config={
        "effort": "medium",
        "format": {"type": "json_schema", "schema": ANALYSIS_OUTPUT_SCHEMA},
    },
    betas=["server-side-fallback-2026-07-01"],
    fallbacks="default",
)
```

| Choice | Reason |
| ------ | ------ |
| `claude-opus-5-5` | strongest general model for careful reading and extraction |
| **Structured outputs** (`output_config.format`) | the response is valid JSON matching `analysis/schema.py`, so no text parsing |
| **Streaming** + `get_final_message()` | long documents and outputs; avoids HTTP timeouts |
| `effort: "medium"` | set explicitly (it is also the model's default); good balance of depth and cost for extraction. Raise it to `high` for dense theoretical texts |
| Adaptive thinking (model default) | the model decides how much to reason; not configured explicitly |
| `fallbacks: "default"` | if a safety classifier declines, the API retries on Anthropic's recommended fallback model server-side instead of failing |
| Static system prompt; document in the user turn | the system prompt stays identical across calls |

### System prompt rules (summary)

- Ground every statement in the document; no outside knowledge about the work.
- Never invent authors, titles, dates, DOIs, citations, statistics, findings,
  methods or quotes. Use `"unknown"`, `null` or `[]` when the text doesn't say.
- Quotes must be verbatim; give the section heading and the page from the
  nearest `<!-- page: N -->` marker.
- The summary is separate from the author's abstract and must not copy it.
- Research gaps are hypotheses; say whether each was stated by the authors or
  implied by their limitations.
- Report problems (garbled text, missing sections) in `warnings`.

### Output schema

`ANALYSIS_OUTPUT_SCHEMA` in `analysis/schema.py`: bibliographic
`metadata_candidates`, `summary`, problem, objective, questions, hypotheses,
framework, `methodology` (with an enum `approach`), evidence lists (findings,
limitations, contributions, gaps), conclusions, future research, concepts,
definitions, theories, cited authors, relevance to the project, confidence and
warnings. All properties are required and `additionalProperties` is false (a
structured-outputs requirement). Absent values are expressed as `null`,
`"unknown"` or empty lists.

## Handling the response

| Condition | Result |
| --------- | ------ |
| `stop_reason == "refusal"` (after fallback) | `LLMAnalysisError("The model declined…")`; nothing stored |
| `stop_reason == "max_tokens"` | `LLMAnalysisError("…cut off")`; nothing stored |
| no text block / invalid JSON | `LLMAnalysisError`; nothing stored |
| input longer than 2,000,000 characters | refused before calling (the document is never truncated silently) |
| network / API errors | SDK exception (the SDK already retries 408/409/429/5xx twice); job marked failed with the message |
| success | analysis saved with `processing.analysis_model` = the model that actually answered (`response.model`), `prompt_version`, `input_tokens`, `output_tokens` |

Then [the merge rule](../design/data-model.md#merge-rule-for-llm-metadata) applies
the metadata candidates to non-validated, low-confidence fields.

## Cost

Token usage is recorded in every analysis (`processing.input_tokens`,
`output_tokens`), so the actual cost of a project can be summed from its
`analysis/*.json` files.

Rough estimate: a 10–15 page article is about 10–20k input tokens, and the
structured output plus reasoning is a few thousand output tokens. At Claude Opus
5.5 list prices ($4 / M input, $20 / M output as of September 2026) that is
roughly **$0.10–0.20 per article**. Check current pricing on Anthropic's site.

To reduce cost:

- analyze only included sources (select them in the web interface), or
- set `ACAM_MODEL=claude-sonnet-5-5` (cheaper, still strong), or
- lower `effort` to `low` in `analysis/llm.py` for simple documents.

Planned: batch analysis through the Message Batches API (about 50% cheaper) for
large imports.

## Privacy

The request contains the full Markdown of the source, the project title and
research questions, the source id and the original file name. See
[Security → Data sent to third parties](../security/security.md#data-sent-to-third-parties).

## Changing the integration

| Change | Where | Also do |
| ------ | ----- | ------- |
| Different default model | `DEFAULT_MODEL` in `analysis/llm.py` (or `ACAM_MODEL`) | check the model supports structured outputs and `effort`; run one real analysis |
| Prompt wording | `SYSTEM_PROMPT` | bump `PROMPT_VERSION` in `analysis/schema.py` |
| New analysis field | `ANALYSIS_OUTPUT_SCHEMA` (+ heuristic engine + `schemas/analysis.schema.json` + templates/reports) | bump `PROMPT_VERSION`; update tests |
| Another provider | add an engine module with the same output shape ([Extending](extending.md#add-an-analysis-engine)) | keep `processing` provenance fields |

## Testing

`tests/test_pipeline.py` injects a fake client through
`analyze_source(..., client=FakeClient())` and checks the model, the JSON-schema
format, `fallbacks`, that the project context is in the user message, the
provenance fields, the merge rules and refusal handling. The live API is **not**
called in tests. Run one real analysis after any change to the request.
