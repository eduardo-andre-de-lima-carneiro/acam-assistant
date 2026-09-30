"""Container start-up tasks, run by the image entrypoint before the web server.

Creates the first administrator from the environment so a fresh deployment is
usable without opening the first-run page:

    ACAM_ADMIN_USER             username to create if it does not exist
    ACAM_ADMIN_PASSWORD_FILE    file holding the password (Docker/K8s secret) — preferred
    ACAM_ADMIN_PASSWORD         password in plain env (fallback)

Nothing happens when ``ACAM_ADMIN_USER`` is unset or the user already
exists, so the task is safe to run on every start.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import accounts, storage


def _password() -> str | None:
    path = os.environ.get("ACAM_ADMIN_PASSWORD_FILE")
    if path:
        try:
            return Path(path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise accounts.AccountError(f"cannot read ACAM_ADMIN_PASSWORD_FILE: {exc.strerror}")
    return os.environ.get("ACAM_ADMIN_PASSWORD") or None


def bootstrap(root: Path | None = None) -> str:
    root = (root or storage.default_workspace()).resolve()
    root.mkdir(parents=True, exist_ok=True)
    username = (os.environ.get("ACAM_ADMIN_USER") or "").strip()
    if not username:
        if not accounts.has_users(root):
            return "no accounts yet: the first visitor to the web page creates the administrator"
        return "accounts present"
    if accounts.get_user(root, username):
        return f"administrator '{username}' already exists"
    password = _password()
    if not password:
        raise accounts.AccountError(
            "ACAM_ADMIN_USER is set but no ACAM_ADMIN_PASSWORD_FILE or "
            "ACAM_ADMIN_PASSWORD was provided")
    accounts.create_user(root, username, password, os.environ.get("ACAM_ADMIN_NAME", ""),
                         is_admin=True)
    return f"created administrator '{username}'"


def main() -> None:
    try:
        message = bootstrap()
    except accounts.AccountError as exc:
        print(f"acam bootstrap: error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"acam bootstrap: {message}", flush=True)


if __name__ == "__main__":
    main()
