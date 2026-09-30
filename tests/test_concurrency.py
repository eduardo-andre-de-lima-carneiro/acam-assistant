"""Real multi-process tests: several OS processes work on the same data root."""

import json
import os
import signal
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from acam import storage
from acam.worker import queue_for

ENV = {**os.environ, "ACAM_EMBEDDED_WORKER": "false"}
for _var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
    ENV.pop(_var, None)


def cli(workspace, *args, check=True):
    return subprocess.run([sys.executable, "-m", "acam.cli", "--workspace", str(workspace), *args],
                          env=ENV, capture_output=True, text=True, check=check, timeout=120)


def parallel(n, fn):
    with ThreadPoolExecutor(n) as pool:
        return list(pool.map(fn, range(n)))


def _variant(sample_md, tmp_path, i):
    p = tmp_path / f"paper-{i}.md"
    p.write_text(sample_md.read_text() + f"\n\nVariant {i}.\n")  # distinct content -> distinct hash
    return p


def test_parallel_imports_get_unique_ids_and_complete_records(workspace, sample_md, tmp_path):
    cli(workspace, "init", "Concurrency", "--id", "cc")
    files = [_variant(sample_md, tmp_path, i) for i in range(8)]
    results = parallel(8, lambda i: cli(workspace, "import", "cc", str(files[i])))
    assert all(r.returncode == 0 for r in results)

    project = storage.open_project(workspace, "cc")
    sources = project.sources()
    ids = [s["id"] for s in sources]
    assert len(ids) == 8 and len(set(ids)) == 8
    assert sorted(s["original_file"]["name"] for s in sources) == sorted(f.name for f in files)
    for s in sources:  # every record went through the whole import, none half-written
        assert s["status"] == "extracted" and s["markdown_file"]
        assert project.path(s["original_file"]["stored_as"]).stat().st_size > 0
    json.loads(project.path("sources.json").read_text())  # still valid JSON


def test_parallel_duplicate_imports_keep_one_copy(workspace, sample_md):
    cli(workspace, "init", "Dups", "--id", "dups")
    results = parallel(6, lambda i: cli(workspace, "import", "dups", str(sample_md), check=False))
    assert sum(r.returncode == 0 for r in results) == 1
    assert sum("already imported" in r.stderr for r in results) == 5
    assert len(storage.open_project(workspace, "dups").sources()) == 1


def test_parallel_edits_on_one_source_lose_nothing(workspace, sample_md):
    cli(workspace, "init", "Edits", "--id", "ed")
    cli(workspace, "import", "ed", str(sample_md))
    parallel(20, lambda i: cli(workspace, "note", "ed", "source-001", f"note-{i}"))
    parallel(10, lambda i: cli(workspace, "tag", "ed", "source-001", "--add", f"t{i}"))
    record = storage.open_project(workspace, "ed").get_source("source-001")
    notes = record["researcher_notes"].splitlines()
    assert sorted(notes) == sorted(f"note-{i}" for i in range(20))
    assert sorted(record["tags"]) == sorted(f"t{i}" for i in range(10))
    assert sum(h["event"] == "note_added" for h in record["history"]) == 20


def test_parallel_workers_run_each_job_exactly_once(workspace, sample_md, tmp_path):
    cli(workspace, "init", "Workers", "--id", "wk")
    for i in range(9):
        cli(workspace, "import", "wk", str(_variant(sample_md, tmp_path, i)))
    out = cli(workspace, "analyze", "wk", "--queue", "--engine", "heuristic").stdout
    assert out.count("queued source-") == 9

    parallel(3, lambda i: cli(workspace, "worker", "--drain", "--threads", "1"))

    queue = queue_for(workspace)
    jobs = queue.for_project("", "wk")
    assert len(jobs) == 9 and all(j["state"] == "done" and j["attempts"] == 1 for j in jobs)
    assert len({j["worker"] for j in jobs}) >= 1
    project = storage.open_project(workspace, "wk")
    assert all(s["status"] == "analyzed" for s in project.sources())
    assert all(project.read_analysis(s["id"]) for s in project.sources())


def test_worker_process_recovers_crashed_job_and_stops_gracefully(workspace, sample_md):
    cli(workspace, "init", "Recover", "--id", "rc")
    cli(workspace, "import", "rc", str(sample_md))
    queue = queue_for(workspace)
    queue.submit("", workspace, "rc", "source-001", "heuristic")
    queue.claim("crashed-host:1")  # simulate a worker that died mid-job
    with queue._connect() as db:
        db.execute("UPDATE jobs SET heartbeat_ts = 0")

    proc = subprocess.Popen([sys.executable, "-m", "acam.cli", "--workspace", str(workspace),
                             "worker", "--threads", "2", "--poll", "0.1"],
                            env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        deadline = time.time() + 30
        while queue.latest_for_source("", "rc", "source-001")["state"] != "done":
            assert time.time() < deadline, "worker did not recover the stale job"
            time.sleep(0.1)
        health = cli(workspace, "worker", "--health", check=False)
        assert health.returncode == 0 and "healthy" in health.stdout
    finally:
        proc.send_signal(signal.SIGTERM)
        output = proc.communicate(timeout=30)[0]
    assert proc.returncode == 0
    assert "stopping" in output
    assert queue.live_workers(host=socket.gethostname()) == []
    job = queue.latest_for_source("", "rc", "source-001")
    assert job["attempts"] == 2 and job["worker"] != "crashed-host:1"


@pytest.mark.skipif(subprocess.run([sys.executable, "-c", "import gunicorn"]).returncode != 0,
                    reason="gunicorn not installed")
def test_multi_process_web_server_keeps_every_edit(workspace, sample_md, tmp_path):
    """gunicorn with 3 worker processes + 1 analysis worker, hammered over HTTP."""
    import re
    import urllib.parse
    import urllib.request
    from http.cookiejar import CookieJar

    from acam import accounts, pipeline

    accounts.create_user(workspace, "alice", "correct-horse")
    project = storage.create_project(accounts.user_workspace(workspace, "alice"), "Web", "web")
    pipeline.import_source(project, sample_md)

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**ENV, "ACAM_HOME": str(workspace), "ACAM_EMBEDDED_WORKER": "false"}
    server = subprocess.Popen([sys.executable, "-m", "gunicorn", "-w", "3", "--threads", "4",
                               "-b", f"127.0.0.1:{port}", "--no-control-socket",
                               "acam.web.wsgi:app"],
                              env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    worker = subprocess.Popen([sys.executable, "-m", "acam.cli", "--workspace", str(workspace),
                               "worker", "--poll", "0.1"], env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(base + "/healthz", timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        jar = CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

        def token():
            html = opener.open(base + "/login").read().decode()
            return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

        def post(path, data):
            body = urllib.parse.urlencode({**data, "csrf_token": csrf}).encode()
            return opener.open(base + path, body).status

        csrf = token()
        post("/login", {"username": "alice", "password": "correct-horse"})
        csrf = token()
        statuses = parallel(24, lambda i: post("/p/web/s/source-001/note", {"note": f"n{i}"}))
        assert all(s == 200 for s in statuses)
        post("/p/web/analyze", {"source": "source-001", "engine": "heuristic"})

        record = project.get_source("source-001")
        assert sorted(record["researcher_notes"].splitlines()) == sorted(f"n{i}" for i in range(24))
        deadline = time.time() + 30
        while True:
            jobs = json.loads(opener.open(f"{base}/api/p/web/jobs").read())
            if jobs and jobs[0]["state"] == "done":
                break
            assert time.time() < deadline, f"analysis not finished: {jobs}"
            time.sleep(0.2)
        assert project.get_source("source-001")["status"] == "analyzed"
    finally:
        for p in (server, worker):
            p.terminate()
            p.wait(30)
