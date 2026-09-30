import os

import pytest

from acam import accounts, container
from acam.web import create_app


def test_env_configures_app(workspace, monkeypatch):
    monkeypatch.setenv("ACAM_ALLOW_SIGNUP", "true")
    monkeypatch.setenv("ACAM_SECURE_COOKIES", "1")
    app = create_app(workspace)
    assert app.config["ALLOW_SIGNUP"] is True
    assert app.config["SESSION_COOKIE_SECURE"] is True
    # Explicit arguments win over the environment.
    app = create_app(workspace, allow_signup=False, secure_cookies=False)
    assert app.config["ALLOW_SIGNUP"] is False and app.config["SESSION_COOKIE_SECURE"] is False


@pytest.mark.parametrize("value,expected", [("", False), ("false", False), ("0", False),
                                            ("yes", True), ("ON", True)])
def test_env_flag_parsing(workspace, monkeypatch, value, expected):
    monkeypatch.setenv("ACAM_ALLOW_SIGNUP", value)
    assert create_app(workspace).config["ALLOW_SIGNUP"] is expected


def test_healthz_is_public(workspace):
    client = create_app(workspace).test_client()
    r = client.get("/healthz")
    assert r.status_code == 200 and r.get_json()["status"] == "ok"
    assert not (workspace / ".healthz").exists()


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                    reason="root ignores directory permissions")
def test_healthz_reports_unwritable_data_root(workspace):
    app = create_app(workspace)
    workspace.chmod(0o500)
    try:
        r = app.test_client().get("/healthz")
    finally:
        workspace.chmod(0o700)
    assert r.status_code == 503 and r.get_json()["status"] == "error"


def test_bootstrap_creates_admin_once(workspace, monkeypatch, tmp_path):
    assert "first visitor" in container.bootstrap(workspace)
    secret = tmp_path / "admin_password"
    secret.write_text("s3cret-password\n")
    monkeypatch.setenv("ACAM_ADMIN_USER", "admin")
    monkeypatch.setenv("ACAM_ADMIN_NAME", "Lab Admin")
    monkeypatch.setenv("ACAM_ADMIN_PASSWORD_FILE", str(secret))
    assert container.bootstrap(workspace) == "created administrator 'admin'"
    user = accounts.authenticate(workspace, "admin", "s3cret-password")  # newline stripped
    assert user["is_admin"] and user["display_name"] == "Lab Admin"
    assert "already exists" in container.bootstrap(workspace)


def test_bootstrap_requires_a_password(workspace, monkeypatch):
    monkeypatch.setenv("ACAM_ADMIN_USER", "admin")
    monkeypatch.delenv("ACAM_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("ACAM_ADMIN_PASSWORD_FILE", raising=False)
    with pytest.raises(accounts.AccountError, match="no ACAM_ADMIN_PASSWORD"):
        container.bootstrap(workspace)
    monkeypatch.setenv("ACAM_ADMIN_PASSWORD", "short")
    with pytest.raises(accounts.AccountError, match="at least 8"):
        container.bootstrap(workspace)


def test_wsgi_module_builds_app_from_env(workspace, monkeypatch):
    import importlib

    monkeypatch.setenv("ACAM_HOME", str(workspace))
    import acam.web.wsgi as wsgi
    wsgi = importlib.reload(wsgi)
    assert wsgi.app.config["ROOT"] == workspace.resolve()
