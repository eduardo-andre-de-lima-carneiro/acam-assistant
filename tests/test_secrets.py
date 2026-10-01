"""Handling of secrets: session key, account file, API key files, debug mode."""

import os
import stat
import subprocess
import sys
import textwrap

import pytest

from acam import accounts, secretfiles
from acam.cli import main
from acam.web import _secret_key, create_app, run


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_session_key_is_private_from_creation(tmp_path):
    old = os.umask(0o000)  # most permissive umask: the file must still be 600
    try:
        key = _secret_key(tmp_path)
    finally:
        os.umask(old)
    assert len(key) == 32 and _mode(tmp_path / ".secret_key") == 0o600
    assert _secret_key(tmp_path) == key  # stable across restarts


def test_concurrent_processes_agree_on_one_session_key(tmp_path):
    script = textwrap.dedent(f"""
        import pathlib
        from acam.web import _secret_key
        print(_secret_key(pathlib.Path({str(tmp_path)!r})).hex())
    """)
    procs = [subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, text=True)
             for _ in range(8)]
    keys = {p.communicate(timeout=60)[0].strip() for p in procs}
    assert len(keys) == 1 and len(keys.pop()) == 64


def test_incomplete_session_key_is_reported(tmp_path, monkeypatch):
    (tmp_path / ".secret_key").write_bytes(b"short")
    monkeypatch.setattr("acam.web.time.sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="incomplete"):
        _secret_key(tmp_path)


def test_users_file_is_private_and_leaves_no_temp_files(workspace):
    old = os.umask(0o000)
    try:
        accounts.create_user(workspace, "alice", "correct-horse")
        accounts.set_password(workspace, "alice", "another-pass")
    finally:
        os.umask(old)
    assert _mode(workspace / "users.json") == 0o600
    assert not list(workspace.glob(".users.json.*.tmp"))
    assert "another-pass" not in (workspace / "users.json").read_text()


def test_api_key_file_is_loaded(tmp_path):
    secret = tmp_path / "key"
    secret.write_text("sk-ant-test-123\n")
    env = {"ANTHROPIC_API_KEY_FILE": str(secret)}
    assert secretfiles.load_secret_files(env) == ["ANTHROPIC_API_KEY"]
    assert env["ANTHROPIC_API_KEY"] == "sk-ant-test-123"
    # An explicit value wins over the file.
    env = {"ANTHROPIC_API_KEY": "explicit", "ANTHROPIC_API_KEY_FILE": str(secret)}
    assert secretfiles.load_secret_files(env) == [] and env["ANTHROPIC_API_KEY"] == "explicit"


@pytest.mark.parametrize("content,match", [(None, "cannot read"), ("  \n", "is empty")])
def test_bad_api_key_files_fail_clearly(tmp_path, content, match):
    path = tmp_path / "key"
    if content is not None:
        path.write_text(content)
    with pytest.raises(secretfiles.SecretFileError, match=match):
        secretfiles.load_secret_files({"ANTHROPIC_API_KEY_FILE": str(path)})


def test_cli_and_app_load_key_files(tmp_path, workspace, monkeypatch, capsys):
    secret = tmp_path / "key"
    secret.write_text("sk-ant-from-file")
    monkeypatch.setenv("ANTHROPIC_API_KEY_FILE", str(secret))
    create_app(workspace)
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-from-file"
    header = create_app(workspace).test_client().get("/signup").get_data(as_text=True)
    assert "engine: <strong>llm</strong>" in header
    assert "sk-ant-from-file" not in header  # the key itself is never rendered

    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.setenv("ANTHROPIC_API_KEY_FILE", str(tmp_path / "missing"))
    with pytest.raises(SystemExit) as exc:
        main(["--workspace", str(workspace), "projects"])
    assert exc.value.code == 2 and "cannot read ANTHROPIC_API_KEY_FILE" in capsys.readouterr().err


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10", "::", "example.org"])
def test_debug_mode_refused_on_non_loopback_hosts(host, workspace):
    with pytest.raises(ValueError, match="only allowed when listening on localhost"):
        run(host=host, workspace=workspace, debug=True)


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_debug_mode_allowed_on_loopback(host, workspace, monkeypatch):
    calls = {}
    monkeypatch.setattr("flask.Flask.run", lambda self, **kw: calls.update(kw))
    run(host=host, workspace=workspace, debug=True)
    assert calls["debug"] is True and calls["host"] == host


def test_cli_refuses_public_debug(workspace, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--workspace", str(workspace), "web", "--host", "0.0.0.0", "--debug"])
    assert exc.value.code == 2 and "--debug is only allowed" in capsys.readouterr().err


def test_password_never_appears_in_responses_or_logs(workspace, caplog):
    from test_web import Browser

    app = create_app(workspace, inline_jobs=True)
    b = Browser(app)
    r = b.signup("alice", password="s3cret-Passw0rd")
    pages = [b.get(u).get_data(as_text=True) for u in ("/", "/account")]
    r = b.post("/login", {"username": "alice", "password": "wrong-s3cret"}, follow_redirects=True)
    pages.append(r.get_data(as_text=True))
    for text in pages + [caplog.text]:
        assert "s3cret-Passw0rd" not in text and "wrong-s3cret" not in text
