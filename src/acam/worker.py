"""Analysis worker: takes jobs from the SQLite queue and runs them.

Run standalone (``acam worker``) so analyses are independent of the web
server, or embedded in the web process (the default for ``acam web``).
Any number of workers, in any number of processes, can share one queue.
"""

from __future__ import annotations

import threading
from pathlib import Path

from . import pipeline, storage
from .jobs import JobQueue, worker_identity

HEARTBEAT_EVERY = 15.0   # seconds between heartbeats of a running job
STALE_AFTER = 120.0      # a running job without heartbeat for this long is re-queued
POLL_INTERVAL = 1.0      # idle wait between claims


class Worker:
    def __init__(self, queue: JobQueue, threads: int = 2, poll_interval: float = POLL_INTERVAL,
                 heartbeat_every: float = HEARTBEAT_EVERY, stale_after: float = STALE_AFTER,
                 identity: str | None = None, client=None):
        self.queue = queue
        self.threads = max(1, threads)
        self.poll_interval = poll_interval
        self.heartbeat_every = heartbeat_every
        self.stale_after = stale_after
        self.identity = identity or worker_identity()
        self.client = client  # injected Claude client (tests)
        self.stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

    # --- one job ------------------------------------------------------------------------

    def process(self, job: dict) -> bool:
        """Run one claimed job; returns True on success. Never raises."""
        done = threading.Event()

        def beat():
            while not done.wait(self.heartbeat_every):
                try:
                    self.queue.register_worker(self.identity, self.threads)
                    if not self.queue.heartbeat(job["id"], self.identity):
                        return
                except Exception:  # transient database error: try again next beat
                    continue

        beater = threading.Thread(target=beat, name=f"heartbeat-{job['id']}", daemon=True)
        beater.start()
        error = None
        try:
            project = storage.open_project(Path(job["workspace"]), job["project"])
            pipeline.analyze_source(project, job["source"], job["engine"], client=self.client,
                                    model=job.get("model"))
        except Exception as exc:  # reported on the job
            error = str(exc) or exc.__class__.__name__
        finally:
            done.set()
            beater.join()
        self.queue.finish(job["id"], self.identity, error)
        return error is None

    def run_once(self) -> bool:
        """Recover stale jobs, then claim and run one job. False if the queue was empty."""
        self.queue.requeue_stale(self.stale_after)
        job = self.queue.claim(self.identity)
        if job is None:
            return False
        self.process(job)
        return True

    def drain(self) -> int:
        """Process jobs until the queue is empty; returns how many ran."""
        count = 0
        while self.run_once():
            count += 1
        return count

    # --- long-running -------------------------------------------------------------------

    def _loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.queue.register_worker(self.identity, self.threads)
                worked = self.run_once()
            except Exception:  # database busy/unavailable: back off and retry
                worked = False
            if not worked:
                self.stop_event.wait(self.poll_interval)

    def start(self) -> "Worker":
        self.queue.register_worker(self.identity, self.threads)
        for i in range(self.threads):
            t = threading.Thread(target=self._loop, name=f"acam-worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)
        return self

    def stop(self, timeout: float | None = None) -> None:
        """Stop claiming new jobs and wait for running ones to finish."""
        self.stop_event.set()
        for t in self._threads:
            t.join(timeout)
        self._threads.clear()
        self.queue.unregister_worker(self.identity)

    def serve_forever(self) -> None:  # pragma: no cover - exercised by the process tests
        import signal

        def _stop(signum, frame):
            self.stop_event.set()

        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)
        self.start()
        print(f"acam worker {self.identity}: {self.threads} thread(s), queue {self.queue.db_path}",
              flush=True)
        while not self.stop_event.wait(1.0):
            pass
        print("acam worker: stopping; waiting for running analyses…", flush=True)
        self.stop()


def queue_for(root: Path) -> JobQueue:
    return JobQueue(Path(root) / "jobs.db")
