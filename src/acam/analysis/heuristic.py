"""Offline, rule-based extractive analysis.

Selects sentences by section and cue phrases. It never paraphrases, so every
item is a verbatim quote with its section and page. Recall is limited; the
LLM engine is recommended when credentials are available.
"""

from __future__ import annotations

import re

from .. import __version__, models
from ..markdown_doc import Section, find_section, parse_sections
from . import UNKNOWN

PROMPT_VERSION = "heuristic/v1"

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý\"“(])")

CUES = {
    "objective": r"\b(this (paper|study|article|work|research|thesis|dissertation)|we|the aim|the purpose|the goal|the objective|objetivo)\b.{0,60}\b(aim|aims|propose|proposes|investigate|investigates|present|presents|examine|examines|analy[sz]es?|explore|explores|evaluate|evaluates|purpose|goal|objective|objetiva|busca)\b",
    "problem": r"\b(problem|challenge|issue|problema|desafio)\b",
    "finding": r"\b(found|find|show|shows|showed|indicate|indicates|reveal|reveals|demonstrate|demonstrates|suggest|suggests|results?|evidence|significant|identified|observed|decreased|increased|reduced|improved|reduction|resultados?|mostram?|indicam?)\b",
    "limitation": r"\b(limitation|limitations|limited|constraint|caveat|shortcoming|limitaç)",
    "contribution": r"\b(contribut|we propose|novel|this paper provides|contribui)",
    "future": r"\b(future (work|research|studies)|further research|trabalhos futuros|pesquisas futuras)\b",
    "gap": r"\b(gap|little is known|few studies|remains? unclear|under-?explored|lack of|scarce|not yet been|lacuna|pouco se sabe)\b",
    "theory": r"\b(theory|theoretical framework|model of|teoria)\b",
}

APPROACHES = [
    ("systematic_review", r"\bsystematic (literature )?review|revisão sistemática|prisma\b"),
    ("mixed_methods", r"\bmixed[- ]methods?\b|métodos mistos"),
    ("experimental", r"\b(controlled )?experiment(s|al)?\b|randomi[sz]ed"),
    ("case_study", r"\bcase stud(y|ies)\b|estudo de caso"),
    ("survey", r"\bsurvey|questionnaire|questionário"),
    ("design_science", r"\bdesign science\b"),
    ("qualitative", r"\bqualitative|interviews?|thematic analysis|grounded theory|qualitativ"),
    ("quantitative", r"\bquantitative|regression|statistical|quantitativ"),
    ("literature_review", r"\bliterature review|revisão (de|da) literatura|bibliographic"),
]


def _sentences(section: Section) -> list[str]:
    out = []
    for para in section.paragraphs:
        if para.startswith(("|", "<!--")):
            continue
        out.extend(s.strip() for s in _SENT_SPLIT.split(para) if 25 <= len(s.strip()) <= 600)
    return out


def _evidence(sentence: str, section: Section) -> dict:
    return {"text": sentence, "section": section.title or None, "page": section.page,
            "quote": sentence}


def _collect(sections: list[Section], cue: str, prefer: tuple[str, ...] = (), limit: int = 5,
             exclude: tuple[str, ...] = ("references", "referências", "bibliography")) -> list[dict]:
    pattern = re.compile(CUES[cue], re.I)
    ordered = ([s for s in sections if any(p in s.key for p in prefer)] +
               [s for s in sections if not any(p in s.key for p in prefer)])
    seen, found = set(), []
    for s in ordered:
        if any(e in s.key for e in exclude):
            continue
        for sent in _sentences(s):
            if sent not in seen and pattern.search(sent):
                seen.add(sent)
                found.append(_evidence(sent, s))
                if len(found) >= limit:
                    return found
    return found


def _first(items: list[dict]) -> str:
    return items[0]["text"] if items else UNKNOWN


def analyze(markdown: str, record: dict, project_info: dict) -> dict:
    sections = [s for s in parse_sections(markdown) if s.text]
    body = [s for s in sections if not any(k in s.key for k in ("references", "referências"))]
    full = "\n".join(s.text for s in body)

    objective = _collect(body, "objective", ("abstract", "introduction", "resumo", "introdução"), 1)
    problem = _collect(body, "problem", ("introduction", "introdução", "abstract"), 1)
    findings = _collect(body, "finding", ("results", "findings", "discussion", "conclusion", "resultados"), 5)
    limitations = _collect(body, "limitation", ("limitation", "discussion", "conclusion"), 4)
    contributions = _collect(body, "contribution", ("introduction", "conclusion"), 3)
    future = _collect(body, "future", ("conclusion", "future", "discussion"), 3)
    gaps = _collect(body, "gap", ("introduction", "related", "literature", "discussion"), 4)
    theories = _collect(body, "theory", ("theoretical", "framework", "background"), 3)

    method_section = find_section(body, "methodology", "methods", "method", "materials and methods",
                                  "metodologia", "research design")
    approach = "unknown"
    method_text = method_section.text if method_section else ""
    for name, pattern in APPROACHES:
        if re.search(pattern, method_text or full, re.I):
            approach = name
            break
    method_desc = method_section.paragraphs[0] if method_section and method_section.paragraphs else UNKNOWN

    questions = []
    for s in body:
        for sent in _sentences(s):
            if sent.endswith("?") or re.match(r"^\(?RQ\s?\d", sent):
                questions.append(sent)
    conclusion = find_section(body, "conclusion", "conclusions", "conclusão", "considerações finais",
                              "final remarks")

    method_first = _SENT_SPLIT.split(method_desc)[0] if method_desc != UNKNOWN else None
    summary_parts = [_first(objective), method_first,
                     _first(findings), conclusion.paragraphs[0] if conclusion and conclusion.paragraphs else None]
    summary = " ".join(p for p in summary_parts if p and p != UNKNOWN) or UNKNOWN

    keywords = models.value_of(record.get("metadata", {}), "keywords", [])
    warnings = ["Heuristic engine: extractive sentence selection only; verify every field."]
    if not method_section:
        warnings.append("No methodology section recognized.")
    if not sections:
        warnings.append("No text available for analysis.")

    return {
        "source_id": record["id"],
        "engine": "heuristic",
        "processing": {
            "processed_at": models.now_iso(),
            "processor_version": __version__,
            "analysis_model": None,
            "prompt_version": PROMPT_VERSION,
        },
        "requires_validation": True,
        "metadata_candidates": None,
        "summary": summary,
        "summary_type": "extractive",
        "research_problem": _first(problem),
        "research_objective": _first(objective),
        "research_questions": questions[:5],
        "hypotheses": [],
        "theoretical_framework": _first(theories),
        "methodology": {
            "approach": approach,
            "description": method_desc,
            "population_sample": UNKNOWN,
            "data_collection": UNKNOWN,
            "analysis_method": UNKNOWN,
        },
        "main_findings": findings,
        "conclusions": conclusion.paragraphs[0] if conclusion and conclusion.paragraphs else UNKNOWN,
        "limitations": limitations,
        "contributions": contributions,
        "future_research": [f["text"] for f in future],
        "relevant_concepts": list(keywords),
        "definitions": [],
        "theories": [t["text"] for t in theories],
        "frequently_cited_authors": [],
        "research_gaps": gaps,
        "relevance_to_project": UNKNOWN,
        "confidence": 0.3,
        "warnings": warnings,
    }
