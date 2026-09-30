"""Command-line interface: ``acam <command> ...``"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

from . import __version__, accounts, artifacts, conversion, models, pipeline, storage
from .analysis import resolve_engine


def _project(args) -> storage.Project:
    return storage.open_project(args.workspace, args.project)


def _write_artifact(project: storage.Project, name: str, content: str) -> Path:
    path = project.path("artifacts", name)
    path.write_text(content, encoding="utf-8")
    return path


def _print_record_line(r: dict) -> None:
    title = models.value_of(r["metadata"], "title", r["original_file"]["name"])
    year = models.value_of(r["metadata"], "publication_year", "")
    print(f"{r['id']:<11} {r['status']:<13} {r['type']:<17} {str(year):<5} {title[:70]}")


# --- commands -------------------------------------------------------------------

def cmd_init(args) -> None:
    p = storage.create_project(args.workspace, args.title, args.id, args.description or "",
                               args.question)
    if args.include or args.exclude:
        info = p.info()
        info["inclusion_criteria"] = args.include or []
        info["exclusion_criteria"] = args.exclude or []
        p.save_info(info)
    print(f"Created project '{p.id}' at {p.root}")


def cmd_projects(args) -> None:
    projects = storage.list_projects(args.workspace)
    if not projects:
        print(f"No projects in {args.workspace}")
    for p in projects:
        info = p.info()
        print(f"{p.id:<30} {len(p.sources()):>3} sources  {info['title']}")


def cmd_import(args) -> None:
    project = _project(args)
    failures = 0
    for f in args.files:
        try:
            r = pipeline.import_source(project, Path(f), args.type, args.tag, args.allow_duplicate)
        except (storage.StorageError, conversion.ConversionError, ValueError) as exc:
            failures += 1
            print(f"✗ {f}: {exc}", file=sys.stderr)
            continue
        v = r["conversion"]["validation"]
        print(f"✓ {f} -> {r['id']} [{r['status']}] conversion: {v['status']} "
              f"({v['words']} words, sections: {', '.join(v['recognized_sections']) or 'none'})")
        for w in r["conversion"]["warnings"]:
            print(f"    warning: {w}")
        for c in v["checks"]:
            if not c["passed"]:
                print(f"    {c['severity']}: {c['check']} — {c['detail']}")
        if args.analyze and r["status"] == "extracted":
            _analyze_one(project, r["id"], args.engine, args.model)
    if failures:
        sys.exit(1)


def _analyze_one(project, source_id: str, engine: str, model: str | None) -> bool:
    chosen = resolve_engine(engine)
    print(f"  analyzing {source_id} with {chosen} engine…", flush=True)
    try:
        r = pipeline.analyze_source(project, source_id, chosen, model=model)
    except Exception as exc:  # report and continue with the next source
        print(f"✗ {source_id}: analysis failed: {exc}", file=sys.stderr)
        return False
    a = r["analysis"]
    print(f"✓ {source_id} analyzed (engine={a['engine']}, model={a['model'] or 'n/a'}, "
          f"confidence={a['confidence']})")
    return True


def cmd_analyze(args) -> None:
    project = _project(args)
    ids = args.sources or [s["id"] for s in project.sources()
                           if args.all or s["status"] in ("extracted", "converted")]
    if not ids:
        print("Nothing to analyze (use --all to re-analyze analyzed sources).")
        return
    if args.queue:
        from .worker import queue_for

        queue = queue_for(args.root)
        for sid in ids:
            job = queue.submit(args.user or "", args.workspace, project.id, sid,
                               engine=resolve_engine(args.engine), model=args.model)
            print(f"queued {sid} as job {job['id']} ({job['state']})")
        return
    ok = [_analyze_one(project, sid, args.engine, args.model) for sid in ids]
    if not all(ok):
        sys.exit(1)


def cmd_list(args) -> None:
    project = _project(args)
    sources = project.sources()
    if args.status:
        sources = [s for s in sources if s["status"] == args.status]
    if args.tag:
        sources = [s for s in sources if args.tag in s.get("tags", [])]
    print(f"{'ID':<11} {'STATUS':<13} {'TYPE':<17} {'YEAR':<5} TITLE")
    for r in sources:
        _print_record_line(r)


def cmd_show(args) -> None:
    project = _project(args)
    if args.json:
        record = project.get_source(args.source)
        print(json.dumps({"source": record, "analysis": project.read_analysis(args.source)},
                         ensure_ascii=False, indent=2))
    else:
        print(artifacts.source_report(project, args.source))


def cmd_set(args) -> None:
    r = pipeline.set_metadata(_project(args), args.source, args.field, args.value)
    print(f"{args.source}.{args.field} set (researcher, validated)")
    print(f"Reference: {r['bibliographic_reference']['text']}")


def cmd_confirm(args) -> None:
    pipeline.confirm_metadata(_project(args), args.source, args.fields)
    print(f"Confirmed {', '.join(args.fields)} for {args.source}")


def cmd_status(args) -> None:
    pipeline.set_status(_project(args), args.source, args.status, args.note)
    print(f"{args.source} -> {args.status}")


def cmd_note(args) -> None:
    pipeline.add_note(_project(args), args.source, args.text)
    print(f"Note added to {args.source}")


def cmd_tag(args) -> None:
    r = pipeline.set_tags(_project(args), args.source, args.add or [], args.remove or [])
    print(f"{args.source} tags: {', '.join(r['tags']) or '(none)'}")


def cmd_matrix(args) -> None:
    project = _project(args)
    if args.csv:
        path = _write_artifact(project, "literature-matrix.csv",
                               artifacts.literature_matrix_csv(project, args.include_rejected))
    else:
        path = _write_artifact(project, "literature-matrix.md",
                               artifacts.literature_matrix(project, args.include_rejected))
    print(f"Wrote {path}")


def cmd_references(args) -> None:
    project = _project(args)
    path = _write_artifact(project, "references.md",
                           artifacts.references_list(project, args.include_rejected))
    print(f"Wrote {path}")


def cmd_report(args) -> None:
    project = _project(args)
    ids = args.sources or [s["id"] for s in project.sources()]
    for sid in ids:
        path = _write_artifact(project, f"{sid}-analysis.md", artifacts.source_report(project, sid))
        print(f"Wrote {path}")


def cmd_export(args) -> None:
    project = _project(args)
    path = _write_artifact(project, "catalog.json", artifacts.export_catalog(project))
    print(f"Wrote {path}")


def cmd_web(args) -> None:
    from .web import run

    # Flags only turn options on; otherwise the environment decides (see create_app).
    run(host=args.host, port=args.port, workspace=args.root, debug=args.debug,
        allow_signup=args.allow_signup or None, secure_cookies=args.secure_cookies or None)


def cmd_worker(args) -> None:
    from .worker import Worker, queue_for

    queue = queue_for(args.root)
    if args.health:
        import socket

        alive = queue.live_workers(args.max_age, host=socket.gethostname())
        print("healthy" if alive else "no live worker on this host")
        sys.exit(0 if alive else 1)
    worker = Worker(queue, threads=args.threads, poll_interval=args.poll)
    if args.drain:
        print(f"processed {worker.drain()} job(s)")
        return
    worker.serve_forever()  # pragma: no cover - long-running; covered by process tests


def cmd_jobs(args) -> None:
    from .worker import queue_for

    queue = queue_for(args.root)
    if args.purge is not None:
        print(f"purged {queue.purge(args.purge)} finished job(s)")
    if args.recover:
        print(f"recovered {queue.requeue_stale(args.recover)} stalled job(s)")
    counts = queue.counts()
    print("jobs: " + ", ".join(f"{k}={counts.get(k, 0)}" for k in ("queued", "running", "done", "failed")))
    workers = queue.live_workers(60)
    print(f"live workers: {len(workers)}"
          + "".join(f"\n  {w['id']} ({w['threads']} threads)" for w in workers))


def _read_password(args, prompt: str = "Password: ") -> str:
    if args.password_stdin:
        return sys.stdin.readline().rstrip("\n")
    first = getpass.getpass(prompt)
    if getpass.getpass("Repeat password: ") != first:
        raise accounts.AccountError("Passwords do not match")
    return first


def cmd_user_add(args) -> None:
    user = accounts.create_user(args.root, args.username, _read_password(args),
                                args.name or "", args.admin)
    role = "administrator" if user["is_admin"] else "researcher"
    print(f"Created {role} '{user['username']}' "
          f"(workspace: {accounts.user_workspace(args.root, user['username'])})")


def cmd_user_list(args) -> None:
    users = accounts.list_users(args.root)
    if not users:
        print("No users. Create one with: acam user add <username>")
    for u in users:
        n = len(storage.list_projects(accounts.user_workspace(args.root, u["username"])))
        print(f"{u['username']:<24} {'admin' if u['is_admin'] else 'user':<6} {n:>3} projects  "
              f"{u['display_name']}")


def cmd_user_passwd(args) -> None:
    accounts.set_password(args.root, args.username, _read_password(args, "New password: "))
    print(f"Password changed for '{args.username}'")


def cmd_user_remove(args) -> None:
    accounts.delete_user(args.root, args.username, args.delete_data)
    kept = "" if args.delete_data else " (workspace kept on disk)"
    print(f"Removed user '{args.username}'{kept}")


def cmd_user_adopt(args) -> None:
    moved = accounts.adopt_legacy_projects(args.root, args.username)
    print(f"Moved {len(moved)} project(s) into {args.username}'s workspace: {', '.join(moved) or '-'}")


def cmd_formats(args) -> None:
    print("Supported input formats: " + ", ".join(conversion.supported_formats()))
    print("Source types: " + ", ".join(models.SOURCE_TYPES))
    print("Statuses: " + ", ".join(models.STATUSES))
    print("Metadata fields: " + ", ".join(models.METADATA_FIELDS))


# --- parser ------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="acam",
                                     description="ACAM Assistant — Academic Management Assistant (MVP)")
    parser.add_argument("--version", action="version", version=f"ACAM Assistant {__version__}")
    parser.add_argument("--workspace", type=Path, default=None,
                        help="data root directory (default: $ACAM_HOME or ./projects)")
    parser.add_argument("--user", "-u", default=None,
                        help="work inside this user's private workspace (multi-user setups)")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, func, help_, project=True, source=False):
        p = sub.add_parser(name, help=help_)
        if project:
            p.add_argument("project", help="project id")
        if source:
            p.add_argument("source", help="source id, e.g. source-001")
        p.set_defaults(func=func)
        return p

    p = add("init", cmd_init, "create a research project", project=False)
    p.add_argument("title")
    p.add_argument("--id", help="project id (default: slug of the title)")
    p.add_argument("--description")
    p.add_argument("--question", "-q", action="append", help="research question (repeatable)")
    p.add_argument("--include", action="append", help="inclusion criterion (repeatable)")
    p.add_argument("--exclude", action="append", help="exclusion criterion (repeatable)")

    add("projects", cmd_projects, "list projects", project=False)

    p = add("import", cmd_import, "import, convert, validate and extract metadata")
    p.add_argument("files", nargs="+")
    p.add_argument("--type", choices=models.SOURCE_TYPES, help="source type (skip auto-detection)")
    p.add_argument("--tag", action="append", help="tag (repeatable)")
    p.add_argument("--analyze", action="store_true", help="run analysis right after import")
    p.add_argument("--engine", default="auto", choices=("auto", "llm", "heuristic"))
    p.add_argument("--model", help="Claude model id (default: claude-opus-5-5)")
    p.add_argument("--allow-duplicate", action="store_true")

    p = add("analyze", cmd_analyze, "analyze sources (default: all not yet analyzed)")
    p.add_argument("sources", nargs="*")
    p.add_argument("--all", action="store_true", help="include already-analyzed sources")
    p.add_argument("--queue", action="store_true",
                   help="queue for the background worker instead of analyzing now")
    p.add_argument("--engine", default="auto", choices=("auto", "llm", "heuristic"))
    p.add_argument("--model")

    p = add("list", cmd_list, "list sources in a project")
    p.add_argument("--status", choices=models.STATUSES)
    p.add_argument("--tag")

    p = add("show", cmd_show, "show a source record and analysis", source=True)
    p.add_argument("--json", action="store_true")

    p = add("set", cmd_set, "set a metadata field (researcher-validated); 'type' sets source type",
            source=True)
    p.add_argument("field")
    p.add_argument("value", help="lists (authors, keywords) are separated by ';'")

    p = add("confirm", cmd_confirm, "mark extracted metadata fields as validated", source=True)
    p.add_argument("fields", nargs="+")

    p = add("status", cmd_status, "change a source's review status", source=True)
    p.add_argument("status", choices=models.STATUSES)
    p.add_argument("--note")

    p = add("note", cmd_note, "append a researcher note", source=True)
    p.add_argument("text")

    p = add("tag", cmd_tag, "add/remove tags", source=True)
    p.add_argument("--add", action="append")
    p.add_argument("--remove", action="append")

    p = add("matrix", cmd_matrix, "generate the literature matrix artifact")
    p.add_argument("--csv", action="store_true")
    p.add_argument("--include-rejected", action="store_true")

    p = add("references", cmd_references, "generate the reference list artifact")
    p.add_argument("--include-rejected", action="store_true")

    p = add("report", cmd_report, "generate per-source analysis reports")
    p.add_argument("sources", nargs="*")

    add("export", cmd_export, "export project + catalog + analyses as one JSON")
    add("formats", cmd_formats, "list supported formats and vocabularies", project=False)

    p = add("web", cmd_web, "start the local web interface", project=False)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--debug", action="store_true")
    p.add_argument("--allow-signup", action="store_true",
                   help="let anyone create an account (the first account can always be created)")
    p.add_argument("--secure-cookies", action="store_true",
                   help="mark session cookies Secure (use when served over HTTPS)")

    p = add("worker", cmd_worker, "run the background analysis worker", project=False)
    p.add_argument("--threads", type=int, default=int(os.environ.get("ACAM_WORKER_THREADS", "2")),
                   help="concurrent analyses (default: $ACAM_WORKER_THREADS or 2)")
    p.add_argument("--poll", type=float, default=1.0, help="seconds between queue checks when idle")
    p.add_argument("--drain", action="store_true", help="process queued jobs, then exit")
    p.add_argument("--health", action="store_true",
                   help="exit 0 if a worker on this host is alive (container health check)")
    p.add_argument("--max-age", type=float, default=60.0, help="liveness window for --health")

    p = add("jobs", cmd_jobs, "show the analysis queue; purge or recover jobs", project=False)
    p.add_argument("--purge", type=float, metavar="DAYS", help="delete finished jobs older than DAYS")
    p.add_argument("--recover", type=float, metavar="SECONDS",
                   help="re-queue running jobs without heartbeat for SECONDS")

    users = sub.add_parser("user", help="manage user accounts").add_subparsers(
        dest="user_command", required=True)
    u = users.add_parser("add", help="create an account")
    u.add_argument("username")
    u.add_argument("--name", help="display name")
    u.add_argument("--admin", action="store_true")
    u.add_argument("--password-stdin", action="store_true", help="read the password from stdin")
    u.set_defaults(func=cmd_user_add)
    u = users.add_parser("list", help="list accounts")
    u.set_defaults(func=cmd_user_list)
    u = users.add_parser("passwd", help="set a user's password")
    u.add_argument("username")
    u.add_argument("--password-stdin", action="store_true")
    u.set_defaults(func=cmd_user_passwd)
    u = users.add_parser("remove", help="delete an account")
    u.add_argument("username")
    u.add_argument("--delete-data", action="store_true", help="also delete the user's workspace")
    u.set_defaults(func=cmd_user_remove)
    u = users.add_parser("adopt", help="move projects created before accounts existed into a user's space")
    u.add_argument("username")
    u.set_defaults(func=cmd_user_adopt)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.root = (args.workspace or storage.default_workspace()).resolve()
    args.workspace = args.root
    try:
        if args.user:
            if not accounts.get_user(args.root, args.user):
                raise accounts.AccountError(f"No such user '{args.user}'")
            args.workspace = accounts.user_workspace(args.root, args.user)
    except accounts.AccountError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    try:
        args.func(args)
    except (storage.StorageError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
