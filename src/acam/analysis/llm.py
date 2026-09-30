"""Claude-backed source analysis using structured outputs."""

from __future__ import annotations

import json
import os

from .. import __version__, models
from .schema import ANALYSIS_OUTPUT_SCHEMA, PROMPT_VERSION

DEFAULT_MODEL = "claude-opus-5-5"
# The 1M-token context window holds ~3M characters; stay well below it and
# refuse rather than silently truncating a source.
MAX_CHARS = 2_000_000

SYSTEM_PROMPT = """You are a research assistant that extracts structured information from one academic source for a literature review.

The source is given as canonical Markdown converted from the original file. Lines like <!-- page: N --> mark where page N of the original begins.

Rules:
- Ground every statement in the document. Do not use outside knowledge about the work, its authors, or its field.
- Never invent authors, titles, dates, DOIs, citations, statistics, findings, methods, or quotes.
- When the document does not state something, use the string "unknown" for text fields, null for nullable fields, and an empty list for lists.
- Quotes must be verbatim excerpts from the document. For each evidence item give the section heading and page number when the markers allow it; otherwise null.
- The summary is a research aid written by you; keep it separate from, and do not copy, the author's abstract.
- Research gaps are hypotheses for the researcher to validate: report gaps the authors state, and gaps clearly implied by stated limitations, and say which in the text.
- Record in warnings anything that limited the analysis (garbled conversion, missing sections, truncated text, non-academic content)."""


class LLMAnalysisError(Exception):
    pass


def _project_context(project_info: dict) -> str:
    lines = [f"Project title: {project_info.get('title') or 'unknown'}"]
    for q in project_info.get("research_questions") or []:
        lines.append(f"Research question: {q}")
    return "\n".join(lines)


def analyze(markdown: str, record: dict, project_info: dict, client=None,
            model: str | None = None) -> dict:
    if len(markdown) > MAX_CHARS:
        raise LLMAnalysisError(
            f"{record['id']} is {len(markdown):,} characters; above the {MAX_CHARS:,} limit. "
            "Split the document (e.g. by chapter) and import the parts separately.")

    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    model = model or os.environ.get("ACAM_MODEL", DEFAULT_MODEL)

    user = (f"<project>\n{_project_context(project_info)}\n</project>\n\n"
            f"<source id=\"{record['id']}\" original_file=\"{record['original_file']['name']}\">\n"
            f"{markdown}\n</source>\n\n"
            "Extract the structured analysis of this source.")

    with client.beta.messages.stream(
        model=model,
        max_tokens=32000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user}],
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": ANALYSIS_OUTPUT_SCHEMA},
        },
        # On a safety-classifier decline, retry server-side on Anthropic's
        # recommended fallback model instead of failing the analysis.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        response = stream.get_final_message()

    if response.stop_reason == "refusal":
        raise LLMAnalysisError(f"The model declined to analyze {record['id']}.")
    if response.stop_reason == "max_tokens":
        raise LLMAnalysisError(f"Analysis of {record['id']} was cut off (max_tokens).")

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise LLMAnalysisError("The model returned no analysis text.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMAnalysisError(f"Could not parse analysis JSON: {exc}") from exc

    return {
        "source_id": record["id"],
        "engine": "llm",
        "processing": {
            "processed_at": models.now_iso(),
            "processor_version": __version__,
            "analysis_model": response.model,
            "prompt_version": PROMPT_VERSION,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
        "requires_validation": True,
        **data,
    }
