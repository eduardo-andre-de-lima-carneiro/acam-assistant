import io
import json

import pytest

from acam import accounts, storage
from acam.web import create_app


class Browser:
    """Test client that behaves like a browser form: sends the session's CSRF token."""

    def __init__(self, app):
        self.c = app.test_client()

    def token(self):
        self.c.get("/login")  # any page issues a token
        with self.c.session_transaction() as sess:
            return sess.get("csrf", "")

    def get(self, *a, **k):
        return self.c.get(*a, **k)

    def post(self, url, data=None, csrf=True, **k):
        data = dict(data or {})
        if csrf:
            data.setdefault("csrf_token", self.token())
        return self.c.post(url, data=data, **k)

    def signup(self, username, password="correct-horse", **extra):
        return self.post("/signup", {"username": username, "password": password,
                                     "confirm": password, **extra})

    def login(self, username, password="correct-horse"):
        return self.post("/login", {"username": username, "password": password})

    def logout(self):
        return self.post("/logout")


@pytest.fixture
def app(workspace):
    app = create_app(workspace, inline_jobs=True)  # analysis runs synchronously in tests
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    b = Browser(app)
    b.signup("alice")
    return b


def udir(workspace, user="alice"):
    return accounts.user_workspace(workspace, user)


def _create(client, title="AI in Software Engineering", pid="ai-se"):
    return client.post("/projects", data={"title": title, "id": pid,
                                          "questions": "How is AI applied to code review?\n"})


def _upload(client, path, pid="ai-se", **extra):
    data = {"files": (io.BytesIO(path.read_bytes()), path.name), "engine": "heuristic", **extra}
    return client.post(f"/p/{pid}/upload", data=data, content_type="multipart/form-data",
                       follow_redirects=True)


def test_create_project_and_list(client, workspace):
    r = _create(client)
    assert r.status_code == 302 and r.headers["Location"].endswith("/p/ai-se")
    page = client.get("/").get_data(as_text=True)
    assert "AI in Software Engineering" in page
    assert "How is AI applied to code review?" in page
    assert storage.open_project(udir(workspace), "ai-se").info()["research_questions"] == [
        "How is AI applied to code review?"]


def test_upload_analyze_and_view_source(client, sample_pdf, workspace):
    _create(client)
    page = _upload(client, sample_pdf, analyze="1").get_data(as_text=True)
    assert "sample-article.pdf → source-001" in page

    project = storage.open_project(udir(workspace), "ai-se")
    record = project.get_source("source-001")
    assert record["original_file"]["name"] == "sample-article.pdf"
    assert record["status"] == "analyzed"

    page = client.get("/p/ai-se/s/source-001").get_data(as_text=True)
    assert "Large Language Models as Code Review Assistants" in page
    assert "Original abstract" in page and "Generated summary" in page
    assert "Main findings" in page and "case study" in page
    assert "SOUZA, M. F.; MILLER, J. P." in page

    md = client.get("/p/ai-se/s/source-001/markdown").get_data(as_text=True)
    assert "&lt;!-- page: 1 --&gt;" in md
    original = client.get("/p/ai-se/s/source-001/original")
    assert original.data == sample_pdf.read_bytes()


def test_upload_errors_are_reported(client, sample_md):
    _create(client)
    _upload(client, sample_md)
    page = _upload(client, sample_md).get_data(as_text=True)
    assert "already imported as source-001" in page
    bad = client.post("/p/ai-se/upload", data={"files": (io.BytesIO(b"x"), "deck.pptx")},
                      content_type="multipart/form-data", follow_redirects=True)
    assert "Unsupported format" in bad.get_data(as_text=True)


def test_researcher_edits(client, sample_md, workspace):
    _create(client)
    _upload(client, sample_md)
    client.post("/p/ai-se/s/source-001/metadata", data={"field": "title", "action": "confirm"})
    client.post("/p/ai-se/s/source-001/metadata",
                data={"field": "publisher", "value": "SBC", "action": "set"})
    client.post("/p/ai-se/s/source-001/metadata", data={"field": "type", "value": "conference_paper"})
    client.post("/p/ai-se/s/source-001/status", data={"status": "validated", "note": "ok"})
    client.post("/p/ai-se/s/source-001/note", data={"note": "Key paper"})
    client.post("/p/ai-se/s/source-001/tags", data={"tags": "llm, code-review"})

    r = storage.open_project(udir(workspace), "ai-se").get_source("source-001")
    assert r["metadata"]["title"]["validated"] and r["metadata"]["title"]["source"] == "extracted"
    assert r["metadata"]["publisher"] == {"value": "SBC", "source": "researcher",
                                          "confidence": None, "validated": True}
    assert r["type"] == "conference_paper"
    assert r["status"] == "validated"
    assert r["researcher_notes"] == "Key paper"
    assert r["tags"] == ["code-review", "llm"]

    client.post("/p/ai-se/s/source-001/confirm-all")
    r = storage.open_project(udir(workspace), "ai-se").get_source("source-001")
    filled = [e for e in r["metadata"].values() if e["value"] not in (None, "", [])]
    assert all(e["validated"] for e in filled)

    # Invalid input is reported, not a crash.
    bad = client.post("/p/ai-se/s/source-001/metadata",
                      data={"field": "publication_year", "value": "soon", "action": "set"},
                      headers={"Referer": "/p/ai-se/s/source-001"}, follow_redirects=True)
    assert bad.status_code == 200 and "invalid literal" in bad.get_data(as_text=True)


def test_project_settings(client, workspace):
    _create(client)
    client.post("/p/ai-se/settings", data={"title": "Renamed", "questions": "Q1\nQ2",
                                           "inclusion": "peer-reviewed", "exclusion": ""})
    info = storage.open_project(udir(workspace), "ai-se").info()
    assert info["title"] == "Renamed"
    assert info["research_questions"] == ["Q1", "Q2"]
    assert info["inclusion_criteria"] == ["peer-reviewed"]


def test_bulk_analyze_and_jobs_api(client, sample_md, sample_txt):
    _create(client)
    _upload(client, sample_md)
    _upload(client, sample_txt, **{"type": "journal_article"})
    r = client.post("/p/ai-se/analyze", data={"engine": "heuristic"}, follow_redirects=True)
    assert "Analysis started for 2 source(s)" in r.get_data(as_text=True)
    jobs = client.get("/api/p/ai-se/jobs").get_json()
    assert {j["source"] for j in jobs} == {"source-001", "source-002"}
    assert all(j["state"] == "done" for j in jobs)


def test_failed_job_is_shown(client, sample_md, monkeypatch):
    _create(client)
    _upload(client, sample_md)

    def boom(*a, **k):
        raise RuntimeError("API unavailable")

    monkeypatch.setattr("acam.pipeline.analysis.analyze", boom)
    client.post("/p/ai-se/analyze", data={"source": "source-001", "engine": "heuristic"})
    page = client.get("/p/ai-se/s/source-001").get_data(as_text=True)
    assert "Last analysis failed: API unavailable" in page


def test_artifact_pages_and_downloads(client, sample_md, sample_html, workspace):
    _create(client)
    _upload(client, sample_md, analyze="1")
    _upload(client, sample_html, type="website")

    matrix = client.get("/p/ai-se/matrix").get_data(as_text=True)
    assert "source-001" in matrix and "case study" in matrix
    refs = client.get("/p/ai-se/references").get_data(as_text=True)
    assert "<strong>Journal of Software Engineering Research</strong>" in refs
    assert refs.index("INSTITUTO") < refs.index("SOUZA")

    for name in ("literature-matrix.md", "literature-matrix.csv", "references.md", "catalog.json",
                 "source-001-analysis.md"):
        r = client.get(f"/p/ai-se/download/{name}")
        assert r.status_code == 200, name
        assert "attachment" in r.headers["Content-Disposition"]
        assert (udir(workspace) / "ai-se" / "artifacts" / name).exists()
    catalog = json.loads(client.get("/p/ai-se/download/catalog.json").data)
    assert len(catalog["sources"]) == 2
    assert client.get("/p/ai-se/download/../../etc/passwd").status_code == 404
    assert client.get("/p/ai-se/download/source-999-analysis.md").status_code == 404


def test_not_found_and_cross_site_posts(client):
    assert client.get("/p/nope").status_code == 404
    _create(client)
    assert client.get("/p/ai-se/s/source-404").status_code == 404
    r = client.post("/p/ai-se/settings", data={"title": "x"},
                    headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.post("/p/ai-se/settings", data={"title": "x"}, headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403
    # A POST without the session's CSRF token is refused.
    assert client.post("/p/ai-se/settings", data={"title": "x"}, csrf=False).status_code == 400
    assert client.post("/p/ai-se/settings", data={"title": "x", "csrf_token": "forged"},
                       csrf=False).status_code == 400


# --- job queue integration ---------------------------------------------------------------

def test_queued_jobs_warn_when_no_worker_runs(workspace, sample_md):
    app = create_app(workspace, embedded_worker=False)  # separate worker expected, none running
    b = Browser(app)
    b.signup("alice")
    _create(b)
    _upload(b, sample_md, analyze="1")
    page = b.get("/p/ai-se").get_data(as_text=True)
    assert "no analysis worker is running" in page
    assert b.get("/api/p/ai-se/jobs").get_json()[0]["state"] == "queued"

    from acam.worker import Worker
    Worker(app.extensions["acam_jobs"], identity="w:1").drain()  # a worker shows up
    assert b.get("/api/p/ai-se/jobs").get_json()[0]["state"] == "done"
    assert "no analysis worker is running" not in b.get("/p/ai-se").get_data(as_text=True)


def test_embedded_worker_processes_in_background(workspace, sample_md):
    import time

    app = create_app(workspace, embedded_worker=True)
    worker = app.extensions["acam_worker"]
    worker.poll_interval = 0.05
    try:
        b = Browser(app)
        b.signup("alice")
        _create(b)
        _upload(b, sample_md, analyze="1")
        deadline = time.time() + 15
        while b.get("/api/p/ai-se/jobs").get_json()[0]["state"] != "done":
            assert time.time() < deadline
            time.sleep(0.05)
        assert "no analysis worker is running" not in b.get("/p/ai-se").get_data(as_text=True)
    finally:
        worker.stop(timeout=5)


def test_busy_project_is_reported(client, monkeypatch):
    from acam import locks

    _create(client)

    def busy(self, timeout=0):
        raise locks.LockTimeout("busy")

    monkeypatch.setattr(locks.InterProcessLock, "acquire", busy)
    r = client.post("/p/ai-se/settings", data={"title": "x"}, headers={"Referer": "/p/ai-se"},
                    follow_redirects=True)
    assert "busy with another change" in r.get_data(as_text=True)
