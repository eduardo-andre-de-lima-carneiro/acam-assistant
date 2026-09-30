import json
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import pytest

from acam import pipeline
from acam.analysis.llm import LLMAnalysisError
from acam.models import value_of
from acam.storage import StorageError

SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"


def _schema(name):
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text())


# --- fake Claude client -------------------------------------------------------------

LLM_OUTPUT = {
    "metadata_candidates": {
        "title": "Large Language Models as Code Review Assistants: An Exploratory Case Study",
        "authors": ["Maria Fernanda Souza", "John Peter Miller"],
        "publication_year": 2025, "journal": "Journal of Software Engineering Research",
        "publisher": None, "volume": "14", "issue": "2", "pages": "45-67",
        "doi": "10.1234/jser.2025.0042", "edition": None, "publication_place": None,
        "keywords": ["LLM", "code review"], "source_type": "journal_article",
    },
    "summary": "An exploratory case study of LLM-assisted code review in two teams.",
    "research_problem": "Code review is time-consuming.",
    "research_objective": "Explore how LLM assistance affects review time and quality.",
    "research_questions": ["How does LLM assistance affect code review time?"],
    "hypotheses": [],
    "theoretical_framework": "Distributed cognition",
    "methodology": {"approach": "case_study", "description": "Exploratory case study.",
                    "population_sample": "18 developers in two teams",
                    "data_collection": "Repository mining and interviews",
                    "analysis_method": "Descriptive statistics, Mann-Whitney U, thematic analysis"},
    "main_findings": [{"text": "Median review time fell 23%.", "section": "4. Results", "page": None,
                       "quote": "a reduction of 23%"}],
    "conclusions": "Useful for routine checks.",
    "limitations": [{"text": "Two teams from one company.", "section": "5. Discussion",
                     "page": None, "quote": None}],
    "contributions": [],
    "future_research": ["Replicate across organizations."],
    "relevant_concepts": ["code review"],
    "definitions": [],
    "theories": ["Distributed cognition"],
    "frequently_cited_authors": ["Bacchelli"],
    "research_gaps": [{"text": "Few industrial studies (stated by authors).", "section": "1. Introduction",
                       "page": None, "quote": "Few studies have examined"}],
    "relevance_to_project": "Directly addresses AI in code review.",
    "confidence": 0.9,
    "warnings": [],
}


class FakeClient:
    def __init__(self, output=LLM_OUTPUT, stop_reason="end_turn"):
        self.calls = []
        self.response = SimpleNamespace(
            stop_reason=stop_reason, model="claude-opus-5-5",
            content=[SimpleNamespace(type="thinking", thinking=""),
                     SimpleNamespace(type="text", text=json.dumps(output))],
            usage=SimpleNamespace(input_tokens=1200, output_tokens=800))
        outer = self

        class _Stream:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get_final_message(self):
                return outer.response

        class _Messages:
            def stream(self, **kwargs):
                outer.calls.append(kwargs)
                return _Stream()

        self.beta = SimpleNamespace(messages=_Messages())


# --- tests -----------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["sample_md", "sample_txt", "sample_pdf", "sample_docx", "sample_html"])
def test_import_stores_original_markdown_and_catalog(project, fixture, request):
    path = request.getfixturevalue(fixture)
    record = pipeline.import_source(project, path)
    assert record["status"] == "extracted"
    assert project.path(record["original_file"]["stored_as"]).read_bytes() == path.read_bytes()
    assert project.path(record["markdown_file"]).read_text().strip()
    assert record["bibliographic_reference"]["text"]
    jsonschema.validate(record, _schema("source"))
    jsonschema.validate(project.info(), _schema("project"))


def test_duplicate_import_is_refused(project, sample_md):
    pipeline.import_source(project, sample_md)
    with pytest.raises(pipeline.DuplicateSourceError):
        pipeline.import_source(project, sample_md)
    assert pipeline.import_source(project, sample_md, allow_duplicate=True)["id"] == "source-002"


def test_failed_conversion_is_recorded_not_extracted(project, tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("\n", encoding="utf-8")
    record = pipeline.import_source(project, f)
    assert record["status"] == "converted"
    assert record["conversion"]["status"] == "failed"
    assert value_of(record["metadata"], "title") is None


def test_heuristic_analysis(project, sample_md):
    sid = pipeline.import_source(project, sample_md)["id"]
    record = pipeline.analyze_source(project, sid, engine="heuristic")
    analysis = project.read_analysis(sid)
    jsonschema.validate(analysis, _schema("analysis"))
    jsonschema.validate(record, _schema("source"))
    assert record["status"] == "analyzed"
    assert analysis["methodology"]["approach"] == "case_study"
    assert any("23%" in f["text"] for f in analysis["main_findings"])
    assert any("Few studies" in g["text"] for g in analysis["research_gaps"])
    assert analysis["limitations"]
    # Every heuristic item is a verbatim quote with its location.
    md = project.read_markdown(record)
    for item in analysis["main_findings"]:
        assert item["quote"] in md and item["section"]
    assert record["abstract"]["generated_summary"]
    assert record["abstract"]["generated_summary"] != record["abstract"]["original_abstract"]


def test_llm_analysis_with_fake_client(project, sample_txt):
    sid = pipeline.import_source(project, sample_txt)["id"]
    client = FakeClient()
    record = pipeline.analyze_source(project, sid, engine="llm", client=client)
    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["fallbacks"] == "default"
    # The document goes in the user turn; the system prompt stays static.
    assert "Few studies have examined" in call["messages"][0]["content"]
    assert "Few studies have examined" not in call["system"]
    assert "How is AI applied to code review?" in call["messages"][0]["content"]

    analysis = project.read_analysis(sid)
    jsonschema.validate(analysis, _schema("analysis"))
    assert analysis["processing"]["analysis_model"] == "claude-opus-5-5"
    assert analysis["processing"]["prompt_version"] == "source-analysis/v1"
    assert record["analysis"]["engine"] == "llm"
    # Low-confidence heuristic title (TXT, 0.5) is upgraded by the LLM candidate.
    assert record["metadata"]["title"]["extractor"] == "llm"
    # High-confidence DOI from regex is kept.
    assert "extractor" not in record["metadata"]["doi"]


def test_llm_never_overrides_researcher_validated_values(project, sample_md):
    sid = pipeline.import_source(project, sample_md)["id"]
    pipeline.set_metadata(project, sid, "title", "Researcher Title")
    pipeline.set_metadata(project, sid, "type", "conference_paper")
    record = pipeline.analyze_source(project, sid, engine="llm", client=FakeClient())
    assert value_of(record["metadata"], "title") == "Researcher Title"
    assert record["type"] == "conference_paper"


def test_llm_refusal_raises(project, sample_md):
    sid = pipeline.import_source(project, sample_md)["id"]
    with pytest.raises(LLMAnalysisError, match="declined"):
        pipeline.analyze_source(project, sid, engine="llm", client=FakeClient(stop_reason="refusal"))
    assert project.read_analysis(sid) is None


def test_researcher_validation_workflow(project, sample_md):
    sid = pipeline.import_source(project, sample_md)["id"]
    record = pipeline.confirm_metadata(project, sid, ["title", "authors"])
    assert record["metadata"]["title"]["validated"]
    assert record["metadata"]["title"]["source"] == "extracted"
    assert record["bibliographic_reference"]["requires_validation"] is False

    record = pipeline.set_metadata(project, sid, "authors", "Souza, Maria Fernanda; Miller, John")
    assert value_of(record["metadata"], "authors") == ["Souza, Maria Fernanda", "Miller, John"]
    assert record["metadata"]["authors"]["source"] == "researcher"

    with pytest.raises(ValueError):
        pipeline.confirm_metadata(project, sid, ["publisher"])  # empty -> must be set, not confirmed
    with pytest.raises(ValueError):
        pipeline.set_status(project, sid, "approved")

    pipeline.set_status(project, sid, "validated", note="checked against PDF")
    pipeline.add_note(project, sid, "Key paper for RQ1")
    record = pipeline.set_tags(project, sid, ["llm", "code-review"], [])
    assert record["status"] == "validated"
    assert record["tags"] == ["code-review", "llm"]
    assert record["researcher_notes"] == "Key paper for RQ1"
    events = [h["event"] for h in record["history"]]
    assert events[-2:] == ["status_changed", "note_added"]
    assert record["history"][-2]["note"] == "checked against PDF"
    jsonschema.validate(record, _schema("source"))


def test_unknown_source_is_an_error(project):
    with pytest.raises(StorageError):
        pipeline.analyze_source(project, "source-999", engine="heuristic")
