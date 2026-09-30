"""Web interface for ACAM Assistant (Flask, server-rendered, no build step).

Multi-tenant: every user logs in and works only inside their own workspace
(``<root>/users/<username>/``), where they can keep any number of projects.
Start with ``acam web`` and open http://127.0.0.1:8000.
"""

from __future__ import annotations

import functools
import hmac
import os
import re
import secrets
import tempfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from flask import (Flask, Response, abort, flash, g, jsonify, redirect, render_template, request,
                   send_file, session, url_for)
from markupsafe import Markup, escape
from werkzeug.utils import secure_filename

from .. import __version__, accounts, artifacts, conversion, models, pipeline, storage
from ..analysis import resolve_engine
from ..locks import LockTimeout
from ..worker import Worker, queue_for


def _lines(text: str | None) -> list[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def _secret_key(root: Path) -> bytes:
    """Persist the session key so logins survive server restarts."""
    f = root / ".secret_key"
    if not f.exists():
        f.write_bytes(secrets.token_bytes(32))
        f.chmod(0o600)
    return f.read_bytes()


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def create_app(workspace: Path | None = None, inline_jobs: bool = False,
               allow_signup: bool | None = None, secure_cookies: bool | None = None,
               embedded_worker: bool | None = None) -> Flask:
    """App factory. Options not passed explicitly are read from the environment
    (``ACAM_ALLOW_SIGNUP``, ``ACAM_SECURE_COOKIES``,
    ``ACAM_EMBEDDED_WORKER``), which is how the container image is configured.

    Analyses go through the durable SQLite queue (``<root>/jobs.db``). By default
    this process also runs an embedded worker; with ``embedded_worker=False`` a
    separate ``acam worker`` process must run. ``inline_jobs`` processes
    queued jobs synchronously within the request (tests)."""
    app = Flask(__name__)
    if allow_signup is None:
        allow_signup = env_flag("ACAM_ALLOW_SIGNUP")
    if secure_cookies is None:
        secure_cookies = env_flag("ACAM_SECURE_COOKIES")
    if embedded_worker is None:
        embedded_worker = env_flag("ACAM_EMBEDDED_WORKER", default=True)
    root = (workspace or storage.default_workspace()).resolve()
    root.mkdir(parents=True, exist_ok=True)
    app.config.update(
        SECRET_KEY=_secret_key(root),
        MAX_CONTENT_LENGTH=200 * 1024 * 1024,
        ROOT=root,
        ALLOW_SIGNUP=allow_signup,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=secure_cookies,
    )
    jobs = queue_for(root)
    worker = Worker(jobs, threads=int(os.environ.get("ACAM_WORKER_THREADS", "2")))
    app.extensions["acam_jobs"] = jobs
    app.extensions["acam_worker"] = worker
    if embedded_worker and not inline_jobs:
        worker.start()

    def enqueue(pid: str, sid: str, engine: str) -> dict:
        job = jobs.submit(owner(), ws(), pid, sid, engine=resolve_engine(engine))
        if inline_jobs:
            worker.drain()
        return job

    # --- authentication -------------------------------------------------------------

    PUBLIC_ENDPOINTS = {"login", "signup", "static", "healthz"}

    def signup_open() -> bool:
        # The first account can always be created; later ones only if enabled.
        return app.config["ALLOW_SIGNUP"] or not accounts.has_users(root)

    @app.before_request
    def load_user():
        g.user = None
        username = session.get("user")
        if username:
            g.user = accounts.get_user(root, username)
            if g.user is None:  # account deleted
                session.clear()
        if g.user is None and request.endpoint not in PUBLIC_ENDPOINTS and request.endpoint:
            if request.path.startswith("/api/"):
                abort(401)
            return redirect(url_for("login", next=request.full_path))

    @app.get("/healthz")
    def healthz():
        """Liveness/readiness probe: the data root must be writable."""
        try:
            probe = root / ".healthz"
            probe.write_text(models.now_iso(), encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            return jsonify(status="error", detail=f"data root not writable: {exc.strerror}"), 503
        return jsonify(status="ok", version=__version__)

    def csrf_token() -> str:
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]

    @app.before_request
    def check_csrf():
        if request.method != "POST":
            return
        # Defence in depth: browsers flag cross-site requests.
        if request.headers.get("Sec-Fetch-Site") == "cross-site":
            abort(403)
        origin = request.headers.get("Origin")
        if origin and urlparse(origin).netloc != request.host:
            abort(403)
        sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
        if not hmac.compare_digest(sent, session.get("csrf", "")):
            abort(400, "Invalid or missing CSRF token — reload the page and try again.")

    def _safe_next(target: str | None) -> str:
        if target and target.startswith("/") and not target.startswith("//"):
            return target
        return url_for("index")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            user = accounts.authenticate(root, request.form.get("username", ""),
                                         request.form.get("password", ""))
            if user:
                session.clear()  # prevent session fixation
                session["user"] = user["username"]
                return redirect(_safe_next(request.args.get("next")))
            flash("Invalid username or password", "error")
        if not accounts.has_users(root):
            return redirect(url_for("signup"))
        return render_template("login.html", signup_open=signup_open())

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if not signup_open():
            flash("Sign-up is disabled. Ask an administrator for an account.", "warn")
            return redirect(url_for("login"))
        first = not accounts.has_users(root)
        if request.method == "POST":
            if request.form.get("password") != request.form.get("confirm"):
                flash("Passwords do not match", "error")
            else:
                try:
                    user = accounts.create_user(root, request.form.get("username", ""),
                                                request.form.get("password", ""),
                                                request.form.get("display_name", ""))
                except accounts.AccountError as exc:
                    flash(str(exc), "error")
                else:
                    session.clear()
                    session["user"] = user["username"]
                    flash(f"Welcome, {user['display_name']}! This is your private workspace.", "ok")
                    return redirect(url_for("index"))
        return render_template("signup.html", first=first)

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/account", methods=["GET", "POST"])
    def account():
        if request.method == "POST":
            if not accounts.authenticate(root, g.user["username"], request.form.get("current", "")):
                flash("Current password is incorrect", "error")
            elif request.form.get("password") != request.form.get("confirm"):
                flash("New passwords do not match", "error")
            else:
                accounts.set_password(root, g.user["username"], request.form.get("password", ""))
                flash("Password changed", "ok")
            return redirect(url_for("account"))
        users = accounts.list_users(root) if g.user.get("is_admin") else None
        return render_template("account.html", users=users,
                               projects=len(storage.list_projects(ws())))

    @app.post("/admin/users")
    def admin_create_user():
        if not g.user.get("is_admin"):
            abort(403)
        user = accounts.create_user(root, request.form.get("username", ""),
                                    request.form.get("password", ""),
                                    request.form.get("display_name", ""),
                                    is_admin=bool(request.form.get("is_admin")))
        flash(f"User {user['username']} created", "ok")
        return redirect(url_for("account"))

    # --- helpers ------------------------------------------------------------------

    def ws() -> Path:
        """The logged-in user's private workspace."""
        path = accounts.user_workspace(root, g.user["username"])
        path.mkdir(parents=True, exist_ok=True)
        return path

    def owner() -> str:
        return g.user["username"]

    def project_or_404(pid: str) -> storage.Project:
        try:
            return storage.open_project(ws(), pid)
        except storage.StorageError:
            abort(404)

    def source_or_404(project: storage.Project, sid: str) -> dict:
        try:
            return project.get_source(sid)
        except storage.StorageError:
            abort(404)

    @app.errorhandler(LockTimeout)
    def busy(exc):
        flash("The project is busy with another change; please try again.", "warn")
        return redirect(request.referrer or url_for("index"))

    @app.errorhandler(storage.StorageError)
    @app.errorhandler(accounts.AccountError)
    @app.errorhandler(ValueError)
    def user_error(exc):
        flash(str(exc), "error")
        return redirect(request.referrer or url_for("index"))

    @app.context_processor
    def globals_():
        return {
            "version": __version__,
            "SOURCE_TYPES": models.SOURCE_TYPES,
            "STATUSES": models.STATUSES,
            "METADATA_FIELDS": models.METADATA_FIELDS,
            "LIST_FIELDS": models.LIST_FIELDS,
            "default_engine": resolve_engine("auto"),
            "formats": conversion.supported_formats(),
            "value_of": models.value_of,
            "csrf_token": csrf_token,
            "current_user": g.get("user"),
        }

    @app.template_filter("mdbold")
    def mdbold(text: str) -> Markup:
        return Markup(re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", str(escape(text or ""))))

    @app.template_filter("fieldtext")
    def fieldtext(value) -> str:
        if value in (None, "", []):
            return ""
        return "; ".join(map(str, value)) if isinstance(value, list) else str(value)

    @app.template_filter("when")
    def when(ts: str | None) -> str:
        return (ts or "").replace("T", " ").replace("Z", " UTC")

    # --- projects -----------------------------------------------------------------

    @app.get("/")
    def index():
        projects = []
        for p in storage.list_projects(ws()):
            sources = p.sources()
            projects.append({"id": p.id, "info": p.info(), "count": len(sources),
                             "statuses": Counter(s["status"] for s in sources)})
        return render_template("index.html", projects=projects)

    @app.post("/projects")
    def create_project():
        title = request.form.get("title", "").strip()
        if not title:
            raise ValueError("A project title is required")
        p = storage.create_project(ws(), title, request.form.get("id", "").strip() or None,
                                   request.form.get("description", "").strip(),
                                   _lines(request.form.get("questions")))
        flash(f"Project “{title}” created", "ok")
        return redirect(url_for("project_view", pid=p.id))

    @app.get("/p/<pid>")
    def project_view(pid):
        project = project_or_404(pid)
        sources = project.sources()
        return render_template(
            "project.html", project=project, info=project.info(), sources=sources,
            statuses=Counter(s["status"] for s in sources),
            tags=sorted({t for s in sources for t in s.get("tags", [])}),
            jobs=jobs.for_project(owner(), pid, limit=10),
            no_worker=(not inline_jobs and jobs.active_for(owner(), pid) is not None
                       and not jobs.live_workers()),
            active={j["source"] for j in jobs.for_project(owner(), pid) if j["state"] in ("queued", "running")},
        )

    @app.post("/p/<pid>/settings")
    def project_settings(pid):
        project = project_or_404(pid)
        changes = {key: request.form.get(key, "").strip()
                   for key in ("description", "research_problem", "scope")}
        title = request.form.get("title", "").strip()
        if title:
            changes["title"] = title
        for key, form_key in (("research_questions", "questions"), ("objectives", "objectives"),
                              ("inclusion_criteria", "inclusion"), ("exclusion_criteria", "exclusion")):
            changes[key] = _lines(request.form.get(form_key))
        project.update_info(changes)
        flash("Project definition saved", "ok")
        return redirect(url_for("project_view", pid=pid))

    @app.post("/p/<pid>/delete")
    def delete_project(pid):
        project = project_or_404(pid)
        if request.form.get("confirm_id") != pid:
            raise ValueError(f"Type the project id “{pid}” to confirm deletion")
        if jobs.active_for(owner(), pid):
            raise ValueError("Wait for running analyses to finish before deleting this project")
        title = project.info()["title"]
        storage.delete_project(ws(), pid)
        flash(f"Project “{title}” deleted", "ok")
        return redirect(url_for("index"))

    @app.post("/p/<pid>/upload")
    def upload(pid):
        project = project_or_404(pid)
        files = [f for f in request.files.getlist("files") if f and f.filename]
        if not files:
            raise ValueError("Choose at least one file to import")
        source_type = request.form.get("type") or None
        tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]
        analyze_after = bool(request.form.get("analyze"))
        engine = request.form.get("engine", "auto")
        with tempfile.TemporaryDirectory() as tmp:
            for f in files:
                safe = secure_filename(f.filename) or "upload"
                path = Path(tmp) / safe
                f.save(path)
                try:
                    r = pipeline.import_source(project, path, source_type, tags,
                                               original_name=f.filename)
                except (storage.StorageError, conversion.ConversionError, ValueError) as exc:
                    flash(f"{f.filename}: {exc}", "error")
                    continue
                v = r["conversion"]["validation"]
                level = "ok" if v["status"] == "passed" else ("warn" if v["passed"] else "error")
                flash(f"{f.filename} → {r['id']}: conversion {v['status'].replace('_', ' ')} "
                      f"({v['words']} words)", level)
                if analyze_after and r["status"] == "extracted":
                    enqueue(pid, r["id"], engine)
        return redirect(url_for("project_view", pid=pid))

    @app.post("/p/<pid>/analyze")
    def analyze(pid):
        project = project_or_404(pid)
        engine = request.form.get("engine", "auto")
        ids = request.form.getlist("source")
        if not ids:
            ids = [s["id"] for s in project.sources() if s["status"] in ("extracted", "converted")
                   and (s.get("conversion") or {}).get("status") != "failed"]
        if not ids:
            flash("Nothing pending analysis", "warn")
        for sid in ids:
            enqueue(pid, sid, engine)
        if ids:
            flash(f"Analysis started for {len(ids)} source(s) with the "
                  f"{resolve_engine(engine)} engine", "ok")
        return redirect(request.referrer or url_for("project_view", pid=pid))

    @app.get("/api/p/<pid>/jobs")
    def jobs_api(pid):
        project_or_404(pid)
        return jsonify(jobs.for_project(owner(), pid))

    # --- sources ------------------------------------------------------------------

    @app.get("/p/<pid>/s/<sid>")
    def source_view(pid, sid):
        project = project_or_404(pid)
        record = source_or_404(project, sid)
        return render_template("source.html", project=project, info=project.info(), s=record,
                               a=project.read_analysis(sid),
                               job=jobs.latest_for_source(owner(), pid, sid))

    @app.post("/p/<pid>/s/<sid>/metadata")
    def set_metadata(pid, sid):
        project = project_or_404(pid)
        name, value = request.form["field"], request.form.get("value", "").strip()
        if request.form.get("action") == "confirm":
            pipeline.confirm_metadata(project, sid, [name])
            flash(f"{name} confirmed", "ok")
        else:
            pipeline.set_metadata(project, sid, name, value)
            flash(f"{name} saved as researcher-validated", "ok")
        return redirect(url_for("source_view", pid=pid, sid=sid) + "#metadata")

    @app.post("/p/<pid>/s/<sid>/confirm-all")
    def confirm_all(pid, sid):
        project = project_or_404(pid)
        record = source_or_404(project, sid)
        names = [n for n, e in record["metadata"].items()
                 if e.get("value") not in (None, "", []) and not e.get("validated")]
        if names:
            pipeline.confirm_metadata(project, sid, names)
        flash(f"Confirmed {len(names)} field(s)", "ok")
        return redirect(url_for("source_view", pid=pid, sid=sid) + "#metadata")

    @app.post("/p/<pid>/s/<sid>/status")
    def set_status(pid, sid):
        project = project_or_404(pid)
        pipeline.set_status(project, sid, request.form["status"],
                            request.form.get("note", "").strip() or None)
        flash(f"Status changed to {request.form['status']}", "ok")
        return redirect(url_for("source_view", pid=pid, sid=sid))

    @app.post("/p/<pid>/s/<sid>/note")
    def add_note(pid, sid):
        text = request.form.get("note", "").strip()
        if text:
            pipeline.add_note(project_or_404(pid), sid, text)
            flash("Note added", "ok")
        return redirect(url_for("source_view", pid=pid, sid=sid) + "#notes")

    @app.post("/p/<pid>/s/<sid>/tags")
    def set_tags(pid, sid):
        project = project_or_404(pid)
        record = source_or_404(project, sid)
        wanted = {t.strip() for t in request.form.get("tags", "").split(",") if t.strip()}
        current = set(record.get("tags", []))
        pipeline.set_tags(project, sid, sorted(wanted - current), sorted(current - wanted))
        flash("Tags saved", "ok")
        return redirect(url_for("source_view", pid=pid, sid=sid))

    @app.get("/p/<pid>/s/<sid>/markdown")
    def markdown_view(pid, sid):
        project = project_or_404(pid)
        record = source_or_404(project, sid)
        return render_template("markdown.html", project=project, info=project.info(), s=record,
                               markdown=project.read_markdown(record))

    @app.get("/p/<pid>/s/<sid>/original")
    def original(pid, sid):
        project = project_or_404(pid)
        record = source_or_404(project, sid)
        return send_file(project.path(record["original_file"]["stored_as"]),
                         download_name=record["original_file"]["name"], as_attachment=False)

    # --- artifacts ------------------------------------------------------------------

    @app.get("/p/<pid>/matrix")
    def matrix(pid):
        project = project_or_404(pid)
        include = bool(request.args.get("rejected"))
        return render_template("matrix.html", project=project, info=project.info(),
                               rows=artifacts.matrix_rows(project, include), include=include)

    @app.get("/p/<pid>/references")
    def references(pid):
        project = project_or_404(pid)
        include = bool(request.args.get("rejected"))
        return render_template("references.html", project=project, info=project.info(),
                               entries=artifacts.reference_entries(project, include),
                               include=include)

    DOWNLOADS = {
        "literature-matrix.md": ("text/markdown", lambda p, inc: artifacts.literature_matrix(p, inc)),
        "literature-matrix.csv": ("text/csv", lambda p, inc: artifacts.literature_matrix_csv(p, inc)),
        "references.md": ("text/markdown", lambda p, inc: artifacts.references_list(p, inc)),
        "catalog.json": ("application/json", lambda p, inc: artifacts.export_catalog(p)),
    }

    @app.get("/p/<pid>/download/<name>")
    def download(pid, name):
        project = project_or_404(pid)
        include = bool(request.args.get("rejected"))
        if name in DOWNLOADS:
            mime, build = DOWNLOADS[name]
            content = build(project, include)
        elif m := re.fullmatch(r"(source-\d+)-analysis\.md", name):
            source_or_404(project, m.group(1))
            mime, content = "text/markdown", artifacts.source_report(project, m.group(1))
        else:
            abort(404)
        # Keep the artifacts folder in sync with what the CLI would produce.
        project.path("artifacts", name).write_text(content, encoding="utf-8")
        return Response(content, mimetype=f"{mime}; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{pid}-{name}"'})

    return app


def run(host: str = "127.0.0.1", port: int = 8000, workspace: Path | None = None,
        debug: bool = False, allow_signup: bool | None = None,
        secure_cookies: bool | None = None) -> None:
    app = create_app(workspace, allow_signup=allow_signup, secure_cookies=secure_cookies)
    root = app.config["ROOT"]
    print(f"ACAM Assistant web UI on http://{host}:{port}  (data root: {root})")
    if not accounts.has_users(root):
        print("No accounts yet: open the page to create the first (administrator) account.")
    print(f"Self-service sign-up: "
          f"{'enabled' if app.config['ALLOW_SIGNUP'] else 'disabled (first account only)'}")
    app.run(host=host, port=port, debug=debug, threaded=True, use_reloader=False)
