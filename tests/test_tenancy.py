import io
import json
import stat

import pytest

from acam import accounts, storage
from acam.cli import main
from acam.web import create_app
from test_web import Browser, udir


@pytest.fixture
def app(workspace):
    app = create_app(workspace, inline_jobs=True)
    app.config["TESTING"] = True
    return app


def _project(browser, pid="ai-se", title="AI in SE"):
    return browser.post("/projects", {"title": title, "id": pid})


# --- accounts module --------------------------------------------------------------

def test_accounts_store_only_password_hashes(workspace):
    user = accounts.create_user(workspace, "alice", "correct-horse", "Alice")
    assert user["is_admin"]  # first account administers the instance
    assert "password_hash" not in user
    raw = (workspace / "users.json").read_text()
    assert "correct-horse" not in raw
    assert stat.S_IMODE((workspace / "users.json").stat().st_mode) == 0o600
    assert accounts.authenticate(workspace, "alice", "correct-horse")["username"] == "alice"
    assert accounts.authenticate(workspace, "ALICE ", "correct-horse")  # normalized
    assert accounts.authenticate(workspace, "alice", "wrong") is None
    assert accounts.authenticate(workspace, "nobody", "correct-horse") is None
    assert not accounts.create_user(workspace, "bob", "another-pass")["is_admin"]


@pytest.mark.parametrize("name", ["ab", "../evil", "a/b", "Alice!", "-lead", "x" * 33])
def test_invalid_usernames_are_rejected(workspace, name):
    with pytest.raises(accounts.AccountError):
        accounts.create_user(workspace, name, "correct-horse")


def test_weak_password_and_duplicates(workspace):
    with pytest.raises(accounts.AccountError, match="at least 8"):
        accounts.create_user(workspace, "alice", "short")
    accounts.create_user(workspace, "alice", "correct-horse")
    with pytest.raises(accounts.AccountError, match="already exists"):
        accounts.create_user(workspace, "alice", "correct-horse")


@pytest.mark.parametrize("pid", ["..", "../users/bob/x", "a/b", "", "UPPER"])
def test_project_ids_cannot_escape_workspace(workspace, pid):
    with pytest.raises(storage.StorageError, match="Invalid project id"):
        storage.open_project(workspace, pid)
    if pid:  # an empty id on create falls back to a slug of the title
        with pytest.raises(storage.StorageError, match="Invalid project id"):
            storage.create_project(workspace, "T", project_id=pid)


def test_adopt_legacy_projects(workspace):
    storage.create_project(workspace, "Old review", project_id="old")
    accounts.create_user(workspace, "alice", "correct-horse")
    assert accounts.adopt_legacy_projects(workspace, "alice") == ["old"]
    assert not (workspace / "old").exists()
    assert storage.open_project(udir(workspace), "old").info()["title"] == "Old review"


# --- web: authentication ---------------------------------------------------------------

def test_first_visit_leads_to_admin_signup(app):
    b = Browser(app)
    r = b.get("/")
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    r = b.get("/login")
    assert r.status_code == 302 and r.headers["Location"].endswith("/signup")
    assert "administrator" in b.get("/signup").get_data(as_text=True)
    r = b.signup("alice", display_name="Alice")
    assert r.status_code == 302
    page = b.get("/").get_data(as_text=True)
    assert "My projects" in page and "Alice" in page


def test_login_required_everywhere(app):
    Browser(app).signup("alice")
    anon = Browser(app)
    for url in ("/", "/p/ai-se", "/account", "/p/ai-se/matrix", "/p/ai-se/download/catalog.json"):
        r = anon.get(url)
        assert r.status_code == 302 and "/login" in r.headers["Location"], url
    assert anon.get("/api/p/ai-se/jobs").status_code == 401
    assert anon.post("/projects", {"title": "x"}).status_code == 302
    assert storage.list_projects(udir(app.config["ROOT"])) == []  # nothing was created


def test_login_logout_and_bad_credentials(app):
    b = Browser(app)
    b.signup("alice")
    b.logout()
    assert b.get("/").status_code == 302
    r = b.login("alice", "wrong-password")
    assert r.status_code == 200 and "Invalid username or password" in r.get_data(as_text=True)
    assert b.get("/").status_code == 302
    r = b.post("/login?next=/account", {"username": "alice", "password": "correct-horse"})
    assert r.headers["Location"].endswith("/account")
    b.logout()
    r = b.post("/login?next=//evil.example/x", {"username": "alice", "password": "correct-horse"})
    assert r.headers["Location"] == "/"  # no open redirect


def test_signup_closed_after_first_account_unless_enabled(workspace):
    app = create_app(workspace, inline_jobs=True)
    Browser(app).signup("alice")
    other = Browser(app)
    r = other.signup("bob")
    assert r.status_code == 302 and r.headers["Location"].endswith("/login")
    assert accounts.get_user(workspace, "bob") is None

    open_app = create_app(workspace, inline_jobs=True, allow_signup=True)
    Browser(open_app).signup("bob")
    assert accounts.get_user(workspace, "bob")["is_admin"] is False


def test_sessions_survive_restart(workspace):
    b = Browser(create_app(workspace, inline_jobs=True))
    b.signup("alice")
    cookie = b.c.get_cookie("session")
    b2 = Browser(create_app(workspace, inline_jobs=True))
    b2.c.set_cookie("session", cookie.value)
    assert b2.get("/").status_code == 200


def test_password_change(app):
    b = Browser(app)
    b.signup("alice")
    b.post("/account", {"current": "wrong", "password": "new-password1", "confirm": "new-password1"})
    assert accounts.authenticate(app.config["ROOT"], "alice", "correct-horse")
    b.post("/account", {"current": "correct-horse", "password": "new-password1",
                        "confirm": "new-password1"})
    assert accounts.authenticate(app.config["ROOT"], "alice", "new-password1")


def test_admin_creates_users_non_admin_cannot(app):
    admin = Browser(app)
    admin.signup("alice")
    admin.post("/admin/users", {"username": "bob", "password": "bob-password"})
    assert accounts.get_user(app.config["ROOT"], "bob")
    assert "bob" in admin.get("/account").get_data(as_text=True)

    bob = Browser(app)
    bob.login("bob", "bob-password")
    assert bob.post("/admin/users", {"username": "eve", "password": "eve-password"}).status_code == 403
    assert "Create user" not in bob.get("/account").get_data(as_text=True)


# --- web: isolation between tenants -------------------------------------------------

def test_users_are_isolated(app, sample_md):
    root = app.config["ROOT"]
    alice = Browser(app)
    alice.signup("alice")
    alice.post("/admin/users", {"username": "bob", "password": "bob-password"})
    bob = Browser(app)
    bob.login("bob", "bob-password")

    _project(alice, "ai-se", "Alice's review")
    alice.post("/p/ai-se/upload", {"files": (io.BytesIO(sample_md.read_bytes()), "a.md"),
                                   "engine": "heuristic", "analyze": "1"},
               content_type="multipart/form-data")

    # Bob sees nothing of Alice's and cannot reach it by URL.
    assert "Alice&#39;s review" not in bob.get("/").get_data(as_text=True)
    for url in ("/p/ai-se", "/p/ai-se/s/source-001", "/p/ai-se/s/source-001/original",
                "/p/ai-se/matrix", "/p/ai-se/download/catalog.json", "/api/p/ai-se/jobs"):
        assert bob.get(url).status_code == 404, url
    assert bob.post("/p/ai-se/delete", {"confirm_id": "ai-se"}).status_code == 404

    # The same project id can exist independently in both spaces.
    _project(bob, "ai-se", "Bob's review")
    assert "Bob&#39;s review" in bob.get("/p/ai-se").get_data(as_text=True)
    assert bob.get("/api/p/ai-se/jobs").get_json() == []
    assert len(alice.get("/api/p/ai-se/jobs").get_json()) == 1
    assert storage.open_project(udir(root, "alice"), "ai-se").info()["title"] == "Alice's review"
    assert storage.open_project(udir(root, "bob"), "ai-se").sources() == []


# --- web: multiple projects per user --------------------------------------------------

def test_multiple_projects_and_deletion(app):
    b = Browser(app)
    b.signup("alice")
    for pid, title in (("review-a", "Review A"), ("review-b", "Review B"), ("review-c", "Review C")):
        _project(b, pid, title)
    page = b.get("/").get_data(as_text=True)
    assert all(t in page for t in ("Review A", "Review B", "Review C"))

    r = b.post("/projects", {"title": "Dup", "id": "review-a"}, follow_redirects=True)
    assert "already exists" in r.get_data(as_text=True)
    r = b.post("/projects", {"title": "Bad", "id": "../escape"}, follow_redirects=True)
    assert "Invalid project id" in r.get_data(as_text=True)

    # Deletion needs the id typed back.
    r = b.post("/p/review-b/delete", {"confirm_id": "wrong"}, follow_redirects=True)
    assert "to confirm deletion" in r.get_data(as_text=True)
    assert b.get("/p/review-b").status_code == 200
    b.post("/p/review-b/delete", {"confirm_id": "review-b"})
    assert b.get("/p/review-b").status_code == 404
    assert [p.id for p in storage.list_projects(udir(app.config["ROOT"]))] == ["review-a", "review-c"]


# --- CLI -------------------------------------------------------------------------------

def test_cli_user_management_and_scoping(workspace, sample_md, monkeypatch, capsys):
    def run(*args, stdin=None):
        if stdin is not None:
            monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
        main(["--workspace", str(workspace), *args])

    storage.create_project(workspace, "Legacy", project_id="legacy")
    run("user", "add", "alice", "--name", "Alice", "--password-stdin", stdin="correct-horse\n")
    run("user", "add", "bob", "--password-stdin", stdin="bob-password\n")
    run("user", "adopt", "alice")
    run("--user", "bob", "init", "Bob review", "--id", "bob-review")
    run("--user", "bob", "import", "bob-review", str(sample_md))
    run("user", "list")
    out = capsys.readouterr().out
    assert "Created administrator 'alice'" in out and "Created researcher 'bob'" in out
    assert "Moved 1 project(s) into alice's workspace: legacy" in out
    assert "alice" in out and "bob" in out

    assert [p.id for p in storage.list_projects(udir(workspace, "alice"))] == ["legacy"]
    assert [p.id for p in storage.list_projects(udir(workspace, "bob"))] == ["bob-review"]
    assert storage.list_projects(workspace) == []

    run("user", "passwd", "bob", "--password-stdin", stdin="new-password\n")
    assert accounts.authenticate(workspace, "bob", "new-password")

    with pytest.raises(SystemExit):
        run("--user", "nobody", "projects")
    run("user", "remove", "bob", "--delete-data")
    assert not udir(workspace, "bob").exists()
    assert json.loads((workspace / "users.json").read_text())["users"][0]["username"] == "alice"
