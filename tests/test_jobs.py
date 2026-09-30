import threading
import time

import pytest

from acam import jobs as jobs_mod
from acam.jobs import JobQueue


@pytest.fixture
def queue(tmp_path):
    return JobQueue(tmp_path / "jobs.db")


def test_submit_deduplicates_active_jobs(queue, tmp_path):
    a = queue.submit("alice", tmp_path, "p1", "source-001", "heuristic")
    b = queue.submit("alice", tmp_path, "p1", "source-001", "llm")
    assert a["id"] == b["id"] and b["engine"] == "heuristic" and a["state"] == "queued"
    c = queue.submit("alice", tmp_path, "p1", "source-002")
    assert c["id"] != a["id"]
    assert "workspace" not in a  # internal paths are not exposed


def test_claim_is_fifo_and_exclusive(queue, tmp_path):
    ids = [queue.submit("u", tmp_path, "p", f"s{i}")["id"] for i in range(3)]
    first = queue.claim("w1")
    assert first["id"] == ids[0] and first["state"] == "running" and first["attempts"] == 1
    assert first["workspace"] == str(tmp_path.resolve())
    assert queue.claim("w2")["id"] == ids[1]
    assert queue.claim("w3")["id"] == ids[2]
    assert queue.claim("w4") is None


def test_concurrent_claims_never_share_a_job(queue, tmp_path):
    for i in range(40):
        queue.submit("u", tmp_path, "p", f"s{i}")
    claimed, lock = [], threading.Lock()

    def grab(name):
        while (job := queue.claim(name)) is not None:
            with lock:
                claimed.append(job["id"])

    threads = [threading.Thread(target=grab, args=(f"w{i}",)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(claimed) == sorted(set(claimed)) and len(claimed) == 40


def test_heartbeat_and_finish_require_ownership(queue, tmp_path):
    job = queue.submit("u", tmp_path, "p", "s")
    claimed = queue.claim("w1")
    assert queue.heartbeat(claimed["id"], "w1")
    assert not queue.heartbeat(claimed["id"], "intruder")
    queue.finish(claimed["id"], "intruder")
    assert queue.latest_for_source("u", "p", "s")["state"] == "running"
    queue.finish(claimed["id"], "w1", error="boom")
    done = queue.latest_for_source("u", "p", "s")
    assert done["state"] == "failed" and done["error"] == "boom" and done["finished_at"]
    assert not queue.heartbeat(job["id"], "w1")  # no longer running
    # A finished source can be queued again.
    assert queue.submit("u", tmp_path, "p", "s")["id"] != job["id"]


def test_stale_jobs_are_requeued_then_failed(queue, tmp_path, monkeypatch):
    monkeypatch.setattr(jobs_mod, "MAX_ATTEMPTS", 2)
    queue.submit("u", tmp_path, "p", "s")
    queue.claim("dead-1")
    assert queue.requeue_stale(stale_after=60) == 0  # heartbeat is fresh
    assert queue.requeue_stale(stale_after=-1) == 1
    job = queue.latest_for_source("u", "p", "s")
    assert job["state"] == "queued" and job["worker"] is None
    queue.claim("dead-2")  # attempts = 2 = MAX_ATTEMPTS
    assert queue.requeue_stale(stale_after=-1) == 1
    job = queue.latest_for_source("u", "p", "s")
    assert job["state"] == "failed" and "after 2 attempts" in job["error"]


def test_queries_are_scoped_by_owner(queue, tmp_path):
    queue.submit("alice", tmp_path / "a", "p", "s1")
    queue.submit("bob", tmp_path / "b", "p", "s1")
    assert [j["owner"] for j in queue.for_project("alice", "p")] == ["alice"]
    assert queue.active_for("alice", "p")["owner"] == "alice"
    assert queue.active_for("alice", "p", "s9") is None
    assert queue.active_for("carol", "p") is None
    assert queue.latest_for_source("carol", "p", "s1") is None
    assert queue.counts() == {"queued": 2}


def test_worker_registry(queue):
    queue.register_worker("host-a:1", 2)
    queue.register_worker("host-b:2", 4)
    queue.register_worker("host-a:1", 3)  # upsert
    live = queue.live_workers()
    assert [(w["id"], w["threads"]) for w in live] == [("host-a:1", 3), ("host-b:2", 4)]
    assert [w["id"] for w in queue.live_workers(host="host-b")] == ["host-b:2"]
    assert queue.live_workers(max_age=-1) == []
    queue.unregister_worker("host-a:1")
    assert [w["id"] for w in queue.live_workers()] == ["host-b:2"]
    assert ":" in jobs_mod.worker_identity()


def test_purge_removes_only_old_finished_jobs(queue, tmp_path):
    queue.submit("u", tmp_path, "p", "old")
    old = queue.claim("w")
    queue.finish(old["id"], "w")
    queue.submit("u", tmp_path, "p", "queued")
    assert queue.purge(older_than_days=1) == 0
    time.sleep(0.01)
    assert queue.purge(older_than_days=0) == 1
    assert queue.counts() == {"queued": 1}


def test_failed_transaction_rolls_back(queue, tmp_path):
    with pytest.raises(RuntimeError):
        with queue._transaction() as db:
            db.execute("INSERT INTO workers (id, host, pid, threads, seen_ts) VALUES ('x', 'h', 1, 1, 0)")
            raise RuntimeError("boom")
    assert queue.live_workers(max_age=1e12) == []
