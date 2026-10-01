# Security

This document describes what ACAM Assistant protects, against whom, how, and what it
does **not** protect yet. Deployment hardening is in
[Server deployment](../deployment/server.md#hardening-checklist).

## Assets

| Asset | Where | Sensitivity |
| ----- | ----- | ----------- |
| Research data: originals, Markdown, analyses, notes | `<root>/users/<user>/…` | confidential to its owner (may include unpublished manuscripts) |
| Account credentials | `<root>/users.json` (scrypt hashes) | high |
| Session signing key | `<root>/.secret_key` | high: anyone who has it can forge sessions |
| Anthropic API key | environment of the server process | high: billing and data access |

## Trust boundaries and threat model

```text
 Internet / LAN ──► [reverse proxy, HTTPS] ──► acam process ──► data root (filesystem)
      untrusted                                     │
                                                    └──► Anthropic API (third party)
```

| Threat | Actor | Mitigation |
| ------ | ----- | ---------- |
| Reading or changing another user's projects | authenticated user | per-user workspace resolved from the session; strict ids; 404 for other users' data; job queries filtered by owner |
| Path traversal (`../`, absolute paths) via project id, username, file name or download name | any user | regex validation of usernames and project ids before path building; uploads saved under `secure_filename` in a temporary directory; downloads limited to a fixed list of names or `source-NNN-analysis.md` |
| Cross-site request forgery | malicious website | per-session CSRF token on every POST form (constant-time compare); `Origin` must match the host; `Sec-Fetch-Site: cross-site` refused; `SameSite=Lax` cookies |
| Session theft or forgery | network attacker, XSS | signed session cookies (`HttpOnly`, `SameSite=Lax`, optional `Secure`); key stored with mode 600; session cleared on login (prevents fixation) |
| Credential compromise | attacker with a copy of `users.json` | scrypt hashes (Werkzeug default); plain passwords never stored or logged; minimum length 8 |
| Username enumeration | anonymous | same error message for unknown user and wrong password; hashing also runs for unknown users so response times match |
| Cross-site scripting | author of a malicious source document | Jinja2 autoescaping everywhere; the only markup filter (`mdbold`) escapes first, then adds `<strong>`; Markdown is shown as escaped text; HTML sources are converted to text, never rendered |
| Open redirect after login | phishing | `next` must be a local path (`/…`, not `//…`) |
| Privilege escalation | authenticated user | admin routes check `is_admin`; admins cannot open other users' projects in the web interface |
| Resource exhaustion by upload | authenticated user | 200 MB request limit; LLM input refused above 2 M characters |
| Data corruption from concurrent writers | any two users/processes | per-project `flock` locks; atomic fsynced JSON writes; SQLite transactions for jobs ([ADR-010](../architecture/decisions/ADR-010-multi-process-concurrency.md)) |
| Malicious document exploiting a parser | author of a source | pure-Python parsers (pypdf, python-docx, html.parser), no macros or scripts run; see *Known limitations* |

## Controls in detail

### Authentication

- Accounts in `users.json`. Passwords are hashed with
  `werkzeug.security.generate_password_hash` (scrypt) and checked with
  `check_password_hash`.
- Usernames: `^[a-z0-9][a-z0-9_-]{2,31}$`, stored lower-case. Passwords: ≥ 8 characters.
- The **first** account is created from the web page and becomes administrator.
  After that, sign-up is **closed** unless the server runs with `--allow-signup`.
  Admins create accounts on the Account page or with `acam user add`.
- Users change their own password (the current password is required).
  Admins reset passwords with `acam user passwd`.

### Sessions

- Flask signed-cookie sessions. The key is 32 random bytes in `<root>/.secret_key`,
  created on first start with mode 600, so sessions survive restarts.
- Cookie flags: `HttpOnly`, `SameSite=Lax`, and `Secure` when started with
  `--secure-cookies` (or `create_app(secure_cookies=True)`). Use that whenever
  the site is served over HTTPS.
- To **log out all users**, stop the server, delete `.secret_key`, and start it again.
- A deleted account's session stops working on its next request.

### Authorization and tenant isolation

- Every route except `login`, `signup` and `static` requires a logged-in user.
  Pages redirect to login; `/api/*` returns 401.
- All project access goes through the logged-in user's workspace. No parameter
  selects another user.
- Missing and foreign resources both return **404**, so their existence isn't revealed.
- Deleting a project requires typing its id and is refused while analyses are running.

### Input handling

- Uploads: the extension must be one of `pdf docx txt md markdown html htm`.
  Files are written to a temporary directory under a sanitized name, then copied
  to `original/<source-id>.<ext>`. The user's original file name is stored as
  data only and never used as a path.
- Downloads: an allow-list of artifact names, or `source-\d+-analysis.md` after
  checking that the source exists.
- `original/` files are served with `send_file` from a path built from the
  record, never from the request.

### Data sent to third parties

With the **LLM engine**, each analysis sends to Anthropic:

- the **full canonical Markdown** of the source;
- the **project title and research questions**;
- the original file name and source id.

Nothing else is sent: no notes, other sources, account data or file bytes.
Researchers handling confidential or unpublished material should:

- use the **heuristic engine** (`--engine heuristic`, or run the server without
  Anthropic credentials), or
- check that their Anthropic organization's data-retention terms fit their
  institution's policy.

The engine used for each analysis is recorded, so it is auditable which sources
left the server.

### Secrets

- **API key:** `ANTHROPIC_API_KEY` is read from the environment and never written
  to disk, logs or pages.
  - Prefer **`ANTHROPIC_API_KEY_FILE`**: a path to a file (Docker or Kubernetes
    secret) holding the key, so it doesn't show in `docker inspect` or
    `docker compose config`. The same works for `ANTHROPIC_AUTH_TOKEN_FILE`.
  - An empty or unreadable file stops start-up with a clear error.
- **First administrator:** the password can come from `ACAM_ADMIN_PASSWORD_FILE`
  in the same way.
- **Session key (`.secret_key`):** created atomically with mode 600, so it is
  never readable by other users, even briefly. It is created exactly once:
  several processes starting at the same time all use the same key.
- **`users.json`:** written through a temporary file created with mode 600.
  Password hashes are never readable by other users.
- **Git:** `.secret_key`, `users.json`, `.env`, `secrets/`, and the runtime files
  (`jobs.db*`, lock files) are git- and docker-ignored. Never commit a data root
  that contains them.
- **Debug mode:** `acam web --debug` refuses to start unless the server listens
  only on this machine (`127.0.0.1`, `::1`, `localhost`), because the Flask
  debugger can run arbitrary code.
- Every user of a server shares its API key: usage is billed to one account and
  there are no per-user quotas.

### Integrity and audit

- Originals are immutable and SHA-256 hashed at import.
- Every change to a source is added to its `history` (who: implicit, the
  workspace owner; what; when). There is no global audit log of logins or admin
  actions yet.

### Container hardening

The image runs as non-root uid 10001 with gunicorn as PID 1. The compose file
adds a read-only root filesystem, drops all Linux capabilities, sets
`no-new-privileges`, and publishes the port on `127.0.0.1` only. The first
admin's password can come from a secret file (`ACAM_ADMIN_PASSWORD_FILE`)
instead of an environment variable. `.env` and `secrets/` are excluded from git
and from the Docker build context. Details: [Container deployment](../deployment/container.md#hardening-applied-by-the-compose-file).

## Known limitations

| Gap | Risk | Suggested mitigation |
| --- | ---- | -------------------- |
| No login rate limiting or lockout | password guessing | put the app behind a proxy with rate limiting (see server guide); use strong passwords |
| No MFA, no email password reset | account recovery goes through the admin | admin resets with `acam user passwd` |
| Data at rest isn't encrypted; server admins can read all workspaces | insider access, stolen disk | encrypted volume; restricted OS accounts; see hardening checklist |
| File type is checked by extension, not content | a crafted file can reach a parser | parsers are pure Python and run no scripts; keep dependencies updated; optionally run in a container |
| Parsing runs inside the web process | a parser crash or hang affects that web process | upload size limit; several gunicorn processes and a restart policy (systemd/Docker); a future version could parse in a subprocess with a timeout |
| Data root on a network share (NFS/SMB) | `flock`/SQLite can silently fail, causing lost updates | keep the data root on a local filesystem or block volume (documented in deployment guides) |
| `jobs.db` reveals owners, project ids and workspace paths | local information disclosure | same protection as the rest of the data root (mode 700 directory, service user) |
| No per-user storage quotas | disk exhaustion | monitor disk; OS quotas on the data volume |
| One shared Anthropic key | cost abuse by a user | monitor usage in the Anthropic console; set spend limits there |
| Flask's built-in server | not hardened | use gunicorn behind a reverse proxy, or the container image, for anything beyond localhost |
| No global audit log | limited forensics | proxy access logs; future: structured audit events |

## Secret-exposure audit (2026-10-01)

| Check | Result |
| ----- | ------ |
| Pattern scan of the working tree (API keys, private keys, tokens, password hashes) | no secrets; only placeholders (`sk-ant-...`) and a truncated example hash in the data-model doc |
| [gitleaks](https://github.com/gitleaks/gitleaks) over all commits and the working tree | **no leaks found** |
| Every path ever committed | no `.env`, keys, `users.json`, `.secret_key` or `jobs.db` |
| Ignore rules (`git check-ignore`) | `.env*`, `secrets/`, `.secret_key`, `users.json`, `jobs.db*`, lock files, coverage files and `*.egg-info/` are ignored |
| Docker image (environment, files, layer history) | no secrets; `/data` empty; only public CA certificates and Python's public GPG key fingerprint |
| Running stack with key and admin password as Docker secrets | not present in `docker inspect`, `docker compose config`, logs or pages |
| Tests (`tests/test_secrets.py`) | session key private and identical across 8 concurrent processes; `users.json` mode 600 under a permissive umask; key files; debug guard; passwords never appear in responses or logs |

Not secrets, but reported in the same audit: the public repository contained a
committed research project (`projects/ai-se`), including a publisher's PDF, the
`src/acam_assistant.egg-info/` build folder, and 44 compiled `__pycache__/*.pyc`
files that embed absolute local paths. `.gitignore` now covers all of them, but
files already committed have to be removed from the index explicitly. Research data and third-party
PDFs should not be committed; keep the data root outside the repository or
git-ignored.

## Reporting a vulnerability

Report security issues privately to the maintainers (repository owner) rather
than in a public issue. Include the version (`acam --version`), steps to
reproduce and the impact.
