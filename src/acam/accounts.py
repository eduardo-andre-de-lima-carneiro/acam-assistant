"""User accounts and per-user workspaces (multi-tenancy).

Layout under the root directory (``$ACAM_HOME`` or ``./projects``)::

    <root>/
        users.json               accounts (password hashes, never plain text)
        users/<username>/        one isolated workspace per user
            <project-id>/        that user's projects (see storage.py)

Projects created before accounts existed live directly in ``<root>/`` and can be
moved into a user's space with :func:`adopt_legacy_projects`.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from . import models, storage
from .locks import InterProcessLock, lock_for

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,31}$")
MIN_PASSWORD = 8



def _lock(root: Path) -> InterProcessLock:
    """Serializes changes to users.json across threads and processes."""
    return lock_for(root / "users.json.lock")


class AccountError(ValueError):
    pass


def _users_file(root: Path) -> Path:
    return root / "users.json"


def _load(root: Path) -> list[dict]:
    f = _users_file(root)
    if not f.exists():
        return []
    return json.loads(f.read_text(encoding="utf-8"))["users"]


def _save(root: Path, users: list[dict]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    f = _users_file(root)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps({"users": users}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(f)


def _public(user: dict) -> dict:
    return {k: v for k, v in user.items() if k != "password_hash"}


def check_username(username: str) -> str:
    username = (username or "").strip().lower()
    if not USERNAME_RE.fullmatch(username):
        raise AccountError("Username must be 3-32 characters: lowercase letters, digits, '-' or '_', "
                           "starting with a letter or digit")
    return username


def _check_password(password: str) -> None:
    if len(password or "") < MIN_PASSWORD:
        raise AccountError(f"Password must have at least {MIN_PASSWORD} characters")


def user_workspace(root: Path, username: str) -> Path:
    return root / "users" / check_username(username)


def list_users(root: Path) -> list[dict]:
    return [_public(u) for u in _load(root)]


def get_user(root: Path, username: str) -> dict | None:
    username = (username or "").strip().lower()
    return next((_public(u) for u in _load(root) if u["username"] == username), None)


def has_users(root: Path) -> bool:
    return bool(_load(root))


def create_user(root: Path, username: str, password: str, display_name: str = "",
                is_admin: bool = False) -> dict:
    username = check_username(username)
    _check_password(password)
    with _lock(root):
        users = _load(root)
        if any(u["username"] == username for u in users):
            raise AccountError(f"User '{username}' already exists")
        user = {
            "username": username,
            "display_name": display_name.strip() or username,
            "is_admin": is_admin or not users,  # the first account administers the instance
            "password_hash": generate_password_hash(password),
            "created_at": models.now_iso(),
        }
        users.append(user)
        _save(root, users)
    user_workspace(root, username).mkdir(parents=True, exist_ok=True)
    return _public(user)


def authenticate(root: Path, username: str, password: str) -> dict | None:
    username = (username or "").strip().lower()
    for u in _load(root):
        if u["username"] == username:
            return _public(u) if check_password_hash(u["password_hash"], password or "") else None
    # Hash anyway so unknown usernames take as long as wrong passwords.
    check_password_hash(generate_password_hash("x"), password or "")
    return None


def set_password(root: Path, username: str, password: str) -> None:
    _check_password(password)
    with _lock(root):
        users = _load(root)
        for u in users:
            if u["username"] == username:
                u["password_hash"] = generate_password_hash(password)
                _save(root, users)
                return
    raise AccountError(f"No such user '{username}'")


def delete_user(root: Path, username: str, delete_data: bool = False) -> None:
    with _lock(root):
        users = _load(root)
        remaining = [u for u in users if u["username"] != username]
        if len(remaining) == len(users):
            raise AccountError(f"No such user '{username}'")
        _save(root, remaining)
    if delete_data:
        shutil.rmtree(user_workspace(root, username), ignore_errors=True)


def adopt_legacy_projects(root: Path, username: str) -> list[str]:
    """Move projects stored directly under ``root`` into ``username``'s space."""
    if not get_user(root, username):
        raise AccountError(f"No such user '{username}'")
    target = user_workspace(root, username)
    target.mkdir(parents=True, exist_ok=True)
    moved = []
    with _lock(root):
        for project in storage.list_projects(root):
            dest = target / project.id
            if dest.exists():
                raise AccountError(f"{username} already has a project '{project.id}'")
            with project.lock():
                shutil.move(str(project.root), str(dest))
            moved.append(project.id)
    return moved
