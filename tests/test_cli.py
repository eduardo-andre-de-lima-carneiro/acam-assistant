import json

import pytest

from acam.cli import main


def run(workspace, *args):
    main(["--workspace", str(workspace), *args])


def test_end_to_end_cli(workspace, sample_md, sample_pdf, sample_html, capsys):
    run(workspace, "init", "AI in Software Engineering", "--id", "ai-se",
        "-q", "How is AI applied to code review?", "--include", "peer-reviewed")
    run(workspace, "import", "ai-se", str(sample_md), str(sample_pdf), "--tag", "llm")
    run(workspace, "import", "ai-se", str(sample_html), "--type", "website")
    run(workspace, "analyze", "ai-se", "--engine", "heuristic")
    run(workspace, "set", "ai-se", "source-003", "title", "Cidades")
    run(workspace, "status", "ai-se", "source-002", "rejected", "--note", "duplicate of source-001")
    run(workspace, "matrix", "ai-se")
    run(workspace, "matrix", "ai-se", "--csv")
    run(workspace, "references", "ai-se")
    run(workspace, "report", "ai-se", "source-001")
    run(workspace, "export", "ai-se")
    run(workspace, "list", "ai-se")
    out = capsys.readouterr().out

    assert "source-001" in out and "source-003" in out
    root = workspace / "ai-se"
    info = json.loads((root / "project.json").read_text())
    assert info["inclusion_criteria"] == ["peer-reviewed"]

    matrix = (root / "artifacts" / "literature-matrix.md").read_text()
    assert "| source-001 | Maria Fernanda Souza et al. | 2025 | journal_article |" in matrix
    assert "source-002" not in matrix  # rejected sources are excluded by default
    assert "case_study" in matrix

    refs = (root / "artifacts" / "references.md").read_text()
    assert "SOUZA, M. F.; MILLER, J. P." in refs
    assert "Disponível em:" in refs  # website reference
    assert refs.index("INSTITUTO") < refs.index("SOUZA")  # alphabetical order

    report = (root / "artifacts" / "source-001-analysis.md").read_text()
    assert "Generated summary (machine-generated" in report
    assert "Original abstract (author)" in report

    catalog = json.loads((root / "artifacts" / "catalog.json").read_text())
    assert catalog["project"]["id"] == "ai-se"
    assert len(catalog["sources"]) == 3
    assert catalog["sources"][0]["analysis_result"]["engine"] == "heuristic"


def test_cli_reports_errors(workspace, capsys, tmp_path):
    run(workspace, "init", "P", "--id", "p")
    bad = tmp_path / "x.pptx"
    bad.write_bytes(b"x")
    with pytest.raises(SystemExit) as exc:
        run(workspace, "import", "p", str(bad))
    assert exc.value.code == 1
    assert "Unsupported format" in capsys.readouterr().err

    with pytest.raises(SystemExit) as exc:
        run(workspace, "show", "p", "source-404")
    assert exc.value.code == 2

    with pytest.raises(SystemExit):
        run(workspace, "init", "P", "--id", "p")  # already exists


def test_queue_worker_and_jobs_commands(workspace, sample_md, capsys):
    run(workspace, "init", "Q", "--id", "q")
    run(workspace, "import", "q", str(sample_md))
    run(workspace, "analyze", "q", "--queue", "--engine", "heuristic")
    run(workspace, "analyze", "q", "--queue", "--engine", "heuristic")  # deduplicated
    run(workspace, "jobs")
    out = capsys.readouterr().out
    assert "queued source-001 as job 1 (queued)" in out
    assert out.count("as job 1") == 2
    assert "jobs: queued=1, running=0, done=0, failed=0" in out and "live workers: 0" in out

    with pytest.raises(SystemExit) as exc:
        run(workspace, "worker", "--health")
    assert exc.value.code == 1
    run(workspace, "worker", "--drain")
    run(workspace, "jobs", "--purge", "0", "--recover", "600")
    out = capsys.readouterr().out
    assert "processed 1 job(s)" in out
    assert "purged 1 finished job(s)" in out and "recovered 0 stalled job(s)" in out


def test_web_command_starts_server(workspace, monkeypatch):
    calls = {}
    monkeypatch.setattr("flask.Flask.run", lambda self, **kw: calls.update(kw))
    run(workspace, "web", "--port", "9999", "--allow-signup")
    assert calls["port"] == 9999 and calls["threaded"] is True
