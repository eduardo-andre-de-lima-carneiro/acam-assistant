import subprocess
import sys
import textwrap
import threading
import time

import pytest

from acam import locks, storage


def test_lock_for_returns_one_object_per_path(tmp_path):
    a = locks.lock_for(tmp_path / "x.lock")
    assert locks.lock_for(tmp_path / "sub" / ".." / "x.lock") is a
    assert locks.lock_for(tmp_path / "y.lock") is not a


def test_lock_is_reentrant_within_a_thread(tmp_path):
    lock = locks.lock_for(tmp_path / "r.lock")
    with lock:
        with lock:  # would deadlock if flock were taken twice
            assert lock._depth == 2
        assert lock._fd is not None
    assert lock._depth == 0 and lock._fd is None


def test_lock_excludes_other_threads(tmp_path):
    lock = locks.lock_for(tmp_path / "t.lock")
    inside, order = threading.Event(), []

    def holder():
        with lock:
            inside.set()
            time.sleep(0.2)
            order.append("holder-done")

    t = threading.Thread(target=holder)
    t.start()
    inside.wait()
    with lock:
        order.append("second")
    t.join()
    assert order == ["holder-done", "second"]


def test_thread_lock_timeout(tmp_path):
    lock = locks.InterProcessLock(tmp_path / "tt.lock")
    ready, release = threading.Event(), threading.Event()

    def holder():
        with lock:
            ready.set()
            release.wait()

    t = threading.Thread(target=holder)
    t.start()
    ready.wait()
    with pytest.raises(locks.LockTimeout):
        lock.acquire(timeout=0.1)
    release.set()
    t.join()


def test_lock_excludes_other_processes_and_times_out(tmp_path):
    path = tmp_path / "p.lock"
    holder = subprocess.Popen([sys.executable, "-c", textwrap.dedent(f"""
        import sys, time
        from acam.locks import lock_for
        with lock_for({str(path)!r}):
            print("locked", flush=True)
            time.sleep(1.0)
        """)], stdout=subprocess.PIPE, text=True)
    assert holder.stdout.readline().strip() == "locked"
    lock = locks.InterProcessLock(path)
    with pytest.raises(locks.LockTimeout):
        lock.acquire(timeout=0.2)
    start = time.monotonic()
    lock.acquire(timeout=5)  # granted once the other process releases it
    assert time.monotonic() - start > 0.3
    lock.release()
    holder.wait(5)


def test_project_lock_and_update_info(project):
    assert project.lock() is project.lock()
    info = project.update_info({"scope": "industry"})
    assert info["scope"] == "industry" and project.info()["scope"] == "industry"
    assert (project.root / storage.LOCK_FILE).exists()


def test_json_writes_leave_no_temp_files(project):
    for i in range(5):
        project.update_info({"scope": str(i)})
    assert not list(project.root.glob(".*.tmp"))
