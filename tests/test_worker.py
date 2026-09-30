import time

import pytest

from acam import pipeline, worker as worker_mod
from acam.worker import Worker, queue_for
from test_pipeline import FakeClient


@pytest.fixture
def setup(project, sample_md, workspace):
    sid = pipeline.import_source(project, sample_md)["id"]
    return project, sid, queue_for(workspace)


def test_process_success_records_analysis(setup, workspace):
    project, sid, queue = setup
    queue.submit("", workspace, project.id, sid, "heuristic")
    w = Worker(queue, identity="w:1")
    assert w.drain() == 1
    job = queue.latest_for_source("", project.id, sid)
    assert job["state"] == "done" and job["worker"] == "w:1" and job["attempts"] == 1
    assert project.get_source(sid)["status"] == "analyzed"
    assert w.drain() == 0


def test_process_failure_is_recorded_not_raised(setup, workspace):
    project, sid, queue = setup
    queue.submit("", workspace, project.id, "source-404", "heuristic")
    Worker(queue, identity="w:1").drain()
    job = queue.latest_for_source("", project.id, "source-404")
    assert job["state"] == "failed" and "source-404" in job["error"]


def test_llm_jobs_use_injected_client_and_model(setup, workspace):
    project, sid, queue = setup
    queue.submit("", workspace, project.id, sid, "llm", model="claude-sonnet-5-5")
    client = FakeClient()
    Worker(queue, identity="w:1", client=client).drain()
    assert client.calls[0]["model"] == "claude-sonnet-5-5"
    assert queue.latest_for_source("", project.id, sid)["state"] == "done"


def test_heartbeats_while_running(setup, workspace, monkeypatch):
    project, sid, queue = setup
    real = pipeline.analyze_source

    def slow(*a, **k):
        time.sleep(0.35)
        return real(*a, **k)

    monkeypatch.setattr(worker_mod.pipeline, "analyze_source", slow)
    beats = []
    original = queue.heartbeat
    monkeypatch.setattr(queue, "heartbeat", lambda *a: beats.append(a) or original(*a))
    queue.submit("", workspace, project.id, sid, "heuristic")
    Worker(queue, identity="w:1", heartbeat_every=0.05).drain()
    assert len(beats) >= 3
    assert queue.live_workers(host="w")  # registered while busy


def test_heartbeat_errors_do_not_break_the_job(setup, workspace, monkeypatch):
    project, sid, queue = setup
    real = pipeline.analyze_source
    monkeypatch.setattr(worker_mod.pipeline, "analyze_source",
                        lambda *a, **k: (time.sleep(0.2), real(*a, **k))[1])

    def broken(*a):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(queue, "register_worker", broken)
    queue.submit("", workspace, project.id, sid, "heuristic")
    w = Worker(queue, identity="w:1", heartbeat_every=0.05)
    assert w.run_once()
    assert queue.latest_for_source("", project.id, sid)["state"] == "done"


def test_heartbeat_stops_when_job_taken_away(setup, workspace, monkeypatch):
    project, sid, queue = setup
    real = pipeline.analyze_source
    monkeypatch.setattr(worker_mod.pipeline, "analyze_source",
                        lambda *a, **k: (time.sleep(0.2), real(*a, **k))[1])
    monkeypatch.setattr(queue, "heartbeat", lambda *a: False)
    queue.submit("", workspace, project.id, sid, "heuristic")
    assert Worker(queue, identity="w:1", heartbeat_every=0.02).run_once()


def test_stale_job_from_dead_worker_is_recovered(setup, workspace):
    project, sid, queue = setup
    queue.submit("", workspace, project.id, sid, "heuristic")
    queue.claim("crashed:99")  # a worker took it and died
    w = Worker(queue, identity="w:1", stale_after=-1)
    assert w.drain() == 1
    job = queue.latest_for_source("", project.id, sid)
    assert job["state"] == "done" and job["attempts"] == 2 and job["worker"] == "w:1"


def test_background_threads_process_and_stop(setup, workspace):
    project, sid, queue = setup
    w = Worker(queue, threads=2, poll_interval=0.02, identity="bg:1").start()
    assert [x["id"] for x in queue.live_workers()] == ["bg:1"]
    queue.submit("", workspace, project.id, sid, "heuristic")
    deadline = time.time() + 10
    while queue.latest_for_source("", project.id, sid)["state"] != "done":
        assert time.time() < deadline, "background worker did not process the job"
        time.sleep(0.02)
    w.stop(timeout=5)
    assert queue.live_workers() == []


def test_loop_survives_database_errors(setup, monkeypatch):
    _, _, queue = setup
    calls = []

    def flaky(*a):
        calls.append(1)
        raise RuntimeError("disk I/O error")

    w = Worker(queue, threads=1, poll_interval=0.01, identity="f:1")
    monkeypatch.setattr(queue, "register_worker", flaky)
    w.stop_event.clear()
    import threading
    t = threading.Thread(target=w._loop)
    t.start()
    time.sleep(0.1)
    w.stop_event.set()
    t.join(2)
    assert not t.is_alive() and len(calls) > 1
