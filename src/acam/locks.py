"""Locks that serialize writers across threads *and* processes.

ACAM Assistant's data is plain files, and several processes may write to the same
data root (web workers, analysis workers, CLI). Each read-modify-write of a
shared file (a project's ``sources.json``, ``users.json``) runs under an
:class:`InterProcessLock`: a thread lock plus ``flock`` on a lock file.

``flock`` is reliable on local filesystems and block volumes (ext4, xfs, APFS,
Docker named volumes, Kubernetes ReadWriteOnce volumes); it is **not** reliable
on NFS/SMB shares, so the data root must not live on a network share.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows: thread-level locking only
    fcntl = None

DEFAULT_TIMEOUT = 30.0
_POLL = 0.01


class LockTimeout(Exception):
    pass


class InterProcessLock:
    """Re-entrant (per thread) exclusive lock backed by ``flock`` on ``path``."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._thread_lock = threading.RLock()
        self._depth = 0
        self._fd: int | None = None

    def acquire(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        if not self._thread_lock.acquire(timeout=timeout):
            raise LockTimeout(f"timed out waiting for {self.path}")
        try:
            if self._depth == 0:
                self._fd = self._lock_file(timeout)
            self._depth += 1
        except BaseException:
            self._thread_lock.release()
            raise

    def _lock_file(self, timeout: float) -> int | None:
        if fcntl is None:  # pragma: no cover
            return None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fd
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    os.close(fd)
                    raise LockTimeout(f"timed out waiting for {self.path}")
                time.sleep(_POLL)

    def release(self) -> None:
        self._depth -= 1
        if self._depth == 0 and self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None
        self._thread_lock.release()

    def __enter__(self) -> "InterProcessLock":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


_registry: dict[str, InterProcessLock] = {}
_registry_lock = threading.Lock()


def lock_for(path: Path) -> InterProcessLock:
    """One lock object per path and process, so re-entrancy works across callers."""
    key = str(Path(path).resolve())
    with _registry_lock:
        lock = _registry.get(key)
        if lock is None:
            lock = _registry[key] = InterProcessLock(Path(key))
        return lock
