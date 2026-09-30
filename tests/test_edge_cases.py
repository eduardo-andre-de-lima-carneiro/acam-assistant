"""Error paths of the LLM engine, container bootstrap and PDF conversion."""

import json

import pytest
from pypdf import PdfReader, PdfWriter

from acam import container, conversion, pipeline
from acam.analysis import llm
from test_pipeline import LLM_OUTPUT, FakeClient


@pytest.fixture
def md_source(project, sample_md):
    return project, pipeline.import_source(project, sample_md)["id"]


def _analyze(project, sid, client):
    return pipeline.analyze_source(project, sid, engine="llm", client=client)


def test_llm_refuses_oversized_documents(md_source, monkeypatch):
    project, sid = md_source
    monkeypatch.setattr(llm, "MAX_CHARS", 100)
    client = FakeClient()
    with pytest.raises(llm.LLMAnalysisError, match="Split the document"):
        _analyze(project, sid, client)
    assert client.calls == []  # never sent, never truncated


@pytest.mark.parametrize("stop_reason,content,match", [
    ("max_tokens", json.dumps(LLM_OUTPUT), "cut off"),
    ("end_turn", None, "no analysis text"),
    ("end_turn", "{not json", "Could not parse"),
])
def test_llm_bad_responses_store_nothing(md_source, stop_reason, content, match):
    project, sid = md_source
    client = FakeClient(stop_reason=stop_reason)
    if content is None:
        client.response.content = [c for c in client.response.content if c.type != "text"]
    else:
        client.response.content[-1].text = content
    with pytest.raises(llm.LLMAnalysisError, match=match):
        _analyze(project, sid, client)
    assert project.read_analysis(sid) is None


def test_llm_default_client_and_model_from_env(md_source, monkeypatch):
    project, sid = md_source
    fake = FakeClient()
    monkeypatch.setattr("anthropic.Anthropic", lambda: fake)
    monkeypatch.setenv("ACAM_MODEL", "claude-sonnet-5-5")
    _analyze(project, sid, None)
    assert fake.calls[0]["model"] == "claude-sonnet-5-5"


def test_unknown_engine_is_rejected(md_source):
    project, sid = md_source
    with pytest.raises(ValueError, match="Unknown analysis engine"):
        pipeline.analyze_source(project, sid, engine="magic")


def test_auto_engine_uses_llm_with_credentials(monkeypatch):
    from acam.analysis import resolve_engine

    assert resolve_engine("auto") == "heuristic"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert resolve_engine("auto") == "llm"


def test_container_main_reports_errors(monkeypatch, workspace, capsys, tmp_path):
    monkeypatch.setenv("ACAM_HOME", str(workspace))
    container.main()
    assert "first visitor" in capsys.readouterr().out

    monkeypatch.setenv("ACAM_ADMIN_USER", "admin")
    monkeypatch.setenv("ACAM_ADMIN_PASSWORD_FILE", str(tmp_path / "missing"))
    with pytest.raises(SystemExit) as exc:
        container.main()
    assert exc.value.code == 1
    assert "cannot read ACAM_ADMIN_PASSWORD_FILE" in capsys.readouterr().err

    monkeypatch.delenv("ACAM_ADMIN_PASSWORD_FILE")
    monkeypatch.setenv("ACAM_ADMIN_PASSWORD", "long-enough-pw")
    container.main()
    monkeypatch.delenv("ACAM_ADMIN_USER")
    container.main()
    assert "accounts present" in capsys.readouterr().out


def _encrypted_copy(src, dst, user_password):
    writer = PdfWriter()
    for page in PdfReader(str(src)).pages:
        writer.add_page(page)
    writer.encrypt(user_password=user_password, owner_password="owner", algorithm="RC4-128")
    with open(dst, "wb") as fh:
        writer.write(fh)
    return dst


def test_pdf_with_empty_user_password_is_converted(sample_pdf, tmp_path):
    pdf = _encrypted_copy(sample_pdf, tmp_path / "open.pdf", "")
    assert "## Abstract" in conversion.convert(pdf).markdown


def test_password_protected_pdf_is_reported(sample_pdf, tmp_path):
    pdf = _encrypted_copy(sample_pdf, tmp_path / "locked.pdf", "secret")
    with pytest.raises(conversion.ConversionError):
        conversion.convert(pdf)


def test_converter_crash_becomes_conversion_error(tmp_path):
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"%PDF-1.4 this is not really a pdf")
    with pytest.raises(conversion.ConversionError, match="Failed to convert broken.pdf"):
        conversion.convert(bad)
