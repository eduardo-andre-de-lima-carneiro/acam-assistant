"""Source analysis engines.

Two engines produce the same analysis shape (``schemas/analysis.schema.json``):

* ``llm``       — Claude reads the canonical Markdown and returns structured JSON.
* ``heuristic`` — offline, rule-based, extractive. Lower recall, no API needed.
"""

from __future__ import annotations

import os

UNKNOWN = "unknown"


def resolve_engine(engine: str) -> str:
    if engine != "auto":
        return engine
    has_credentials = any(os.environ.get(k) for k in
                          ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"))
    return "llm" if has_credentials else "heuristic"


def analyze(markdown: str, record: dict, project_info: dict, engine: str = "auto",
            client=None, model: str | None = None) -> dict:
    engine = resolve_engine(engine)
    if engine == "llm":
        from .llm import analyze as run
        return run(markdown, record, project_info, client=client, model=model)
    if engine == "heuristic":
        from .heuristic import analyze as run
        return run(markdown, record, project_info)
    raise ValueError(f"Unknown analysis engine: {engine}")
