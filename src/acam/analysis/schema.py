"""JSON schema the LLM must fill (structured outputs), shared with the heuristic engine."""

from __future__ import annotations

PROMPT_VERSION = "source-analysis/v1"

_NULLABLE_STR = {"anyOf": [{"type": "string"}, {"type": "null"}]}
_NULLABLE_INT = {"anyOf": [{"type": "integer"}, {"type": "null"}]}

EVIDENCE_ITEM = {
    "type": "object",
    "properties": {
        "text": {"type": "string", "description": "The claim, in your own concise words."},
        "section": {**_NULLABLE_STR, "description": "Heading of the section the claim comes from."},
        "page": {**_NULLABLE_INT, "description": "Page number from the nearest preceding <!-- page: N --> marker."},
        "quote": {**_NULLABLE_STR, "description": "Short verbatim excerpt (max ~40 words) supporting the claim."},
    },
    "required": ["text", "section", "page", "quote"],
    "additionalProperties": False,
}

_STR_LIST = {"type": "array", "items": {"type": "string"}}
_EVIDENCE_LIST = {"type": "array", "items": EVIDENCE_ITEM}

METHODOLOGY_APPROACHES = [
    "qualitative", "quantitative", "mixed_methods", "systematic_review", "literature_review",
    "experimental", "quasi_experimental", "case_study", "survey", "design_science",
    "theoretical", "other", "unknown",
]

ANALYSIS_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "metadata_candidates": {
            "type": "object",
            "description": "Bibliographic data explicitly printed in the document. null when absent.",
            "properties": {
                "title": _NULLABLE_STR,
                "authors": _STR_LIST,
                "publication_year": _NULLABLE_INT,
                "journal": _NULLABLE_STR,
                "publisher": _NULLABLE_STR,
                "volume": _NULLABLE_STR,
                "issue": _NULLABLE_STR,
                "pages": _NULLABLE_STR,
                "doi": _NULLABLE_STR,
                "edition": _NULLABLE_STR,
                "publication_place": _NULLABLE_STR,
                "keywords": _STR_LIST,
                "source_type": {"type": "string", "enum": [
                    "book", "book_chapter", "journal_article", "conference_paper", "thesis",
                    "dissertation", "technical_report", "website", "online_article",
                    "preprint", "other"]},
            },
            "required": ["title", "authors", "publication_year", "journal", "publisher", "volume",
                         "issue", "pages", "doi", "edition", "publication_place", "keywords",
                         "source_type"],
            "additionalProperties": False,
        },
        "summary": {"type": "string", "description": "Structured summary (150-250 words): problem, objective, method, main findings, conclusion."},
        "research_problem": {"type": "string"},
        "research_objective": {"type": "string"},
        "research_questions": _STR_LIST,
        "hypotheses": _STR_LIST,
        "theoretical_framework": {"type": "string"},
        "methodology": {
            "type": "object",
            "properties": {
                "approach": {"type": "string", "enum": METHODOLOGY_APPROACHES},
                "description": {"type": "string"},
                "population_sample": {"type": "string"},
                "data_collection": {"type": "string"},
                "analysis_method": {"type": "string"},
            },
            "required": ["approach", "description", "population_sample", "data_collection",
                         "analysis_method"],
            "additionalProperties": False,
        },
        "main_findings": _EVIDENCE_LIST,
        "conclusions": {"type": "string"},
        "limitations": _EVIDENCE_LIST,
        "contributions": _EVIDENCE_LIST,
        "future_research": _STR_LIST,
        "relevant_concepts": _STR_LIST,
        "definitions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"term": {"type": "string"}, "definition": {"type": "string"},
                               "page": _NULLABLE_INT},
                "required": ["term", "definition", "page"],
                "additionalProperties": False,
            },
        },
        "theories": _STR_LIST,
        "frequently_cited_authors": _STR_LIST,
        "research_gaps": _EVIDENCE_LIST,
        "relevance_to_project": {"type": "string", "description": "How the source relates to the project's research questions. 'unknown' if no project questions are given."},
        "confidence": {"type": "number", "description": "0-1: how completely the document could be analyzed."},
        "warnings": _STR_LIST,
    },
    "required": ["metadata_candidates", "summary", "research_problem", "research_objective",
                 "research_questions", "hypotheses", "theoretical_framework", "methodology",
                 "main_findings", "conclusions", "limitations", "contributions", "future_research",
                 "relevant_concepts", "definitions", "theories", "frequently_cited_authors",
                 "research_gaps", "relevance_to_project", "confidence", "warnings"],
    "additionalProperties": False,
}
