"""Load secrets from files (Docker/Kubernetes secrets, systemd credentials).

For each supported variable, ``<NAME>_FILE`` may point to a file holding the
value. This keeps secrets out of the process environment shown by
``docker inspect``/``docker compose config`` and out of shell history. An
explicitly set ``<NAME>`` takes precedence.
"""

from __future__ import annotations

import os
from pathlib import Path

SUPPORTED = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


class SecretFileError(ValueError):
    pass


def load_secret_files(environ: dict | None = None) -> list[str]:
    """Populate ``NAME`` from ``NAME_FILE`` where needed; returns the names loaded."""
    env = os.environ if environ is None else environ
    loaded = []
    for name in SUPPORTED:
        path = env.get(f"{name}_FILE")
        if not path or env.get(name):
            continue
        try:
            value = Path(path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SecretFileError(f"cannot read {name}_FILE ({path}): {exc.strerror}") from None
        if not value:
            raise SecretFileError(f"{name}_FILE ({path}) is empty")
        env[name] = value
        loaded.append(name)
    return loaded
