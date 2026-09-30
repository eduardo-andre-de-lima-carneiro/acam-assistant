# HTTP Interface

The web application is server-rendered HTML. Its routes are documented here for
integrators (automation, reverse-proxy rules, monitoring). There is no public REST
API in 0.1.0 apart from the job-status endpoint. For automation, use the
[CLI](cli-reference.md) or [data exports](data-exchange.md).

## Conventions

- **Authentication:** session cookie from `POST /login`. Public routes: `/login`,
  `/signup`, `/healthz`, `/static/*`. Anonymous requests to
  pages are redirected to `/login?next=…`; anonymous requests to `/api/*` get `401`.
- **CSRF:** every `POST` must include the session's token as the form field
  `csrf_token` (or the `X-CSRF-Token` header). Pages embed it in each form.
  A missing or wrong token returns `400`. Cross-site requests (`Origin` not
  matching `Host`, or `Sec-Fetch-Site: cross-site`) get `403`.
- **Responses:** successful POSTs redirect (`302`) with a flash message. User
  errors redirect back with an error message.
- **Scope:** `<pid>` is resolved **inside the logged-in user's workspace**. Other
  users' projects return `404`.

## Routes

### Authentication and accounts

| Method | Path | Purpose | Form fields |
| ------ | ---- | ------- | ----------- |
| GET, POST | `/login` | log in (`?next=/local/path`) | `username`, `password` |
| GET, POST | `/signup` | create an account (first account, or if sign-up is enabled) | `username`, `display_name`, `password`, `confirm` |
| POST | `/logout` | end the session | — |
| GET, POST | `/account` | profile; change password | `current`, `password`, `confirm` |
| POST | `/admin/users` | admin only: create a user | `username`, `display_name`, `password`, `is_admin` |

### Projects

| Method | Path | Purpose | Form fields |
| ------ | ---- | ------- | ----------- |
| GET | `/` | my projects | — |
| POST | `/projects` | create a project | `title`, `id`, `description`, `questions` (one per line) |
| GET | `/p/<pid>` | project dashboard | — |
| POST | `/p/<pid>/settings` | edit the definition | `title`, `description`, `research_problem`, `scope`, `questions`, `objectives`, `inclusion`, `exclusion` (lists: one per line) |
| POST | `/p/<pid>/delete` | delete the project | `confirm_id` (must equal `<pid>`) |
| POST | `/p/<pid>/upload` | import files (multipart) | `files` (repeatable), `type`, `tags` (comma-separated), `analyze`, `engine` |
| POST | `/p/<pid>/analyze` | queue analyses | `source` (repeatable; none = all pending), `engine` |
| GET | `/p/<pid>/matrix` | literature matrix page (`?rejected=1` includes rejected) | — |
| GET | `/p/<pid>/references` | reference list page (`?rejected=1`) | — |
| GET | `/p/<pid>/download/<name>` | download an artifact (`?rejected=1`); also saved to `artifacts/` | `name` ∈ `literature-matrix.md`, `literature-matrix.csv`, `references.md`, `catalog.json`, `source-NNN-analysis.md` |

### Sources

| Method | Path | Purpose | Form fields |
| ------ | ---- | ------- | ----------- |
| GET | `/p/<pid>/s/<sid>` | source page | — |
| GET | `/p/<pid>/s/<sid>/markdown` | canonical Markdown | — |
| GET | `/p/<pid>/s/<sid>/original` | original file (inline) | — |
| POST | `/p/<pid>/s/<sid>/metadata` | set or confirm one field | `field`, `value`, `action` = `set` \| `confirm` |
| POST | `/p/<pid>/s/<sid>/confirm-all` | confirm every filled field | — |
| POST | `/p/<pid>/s/<sid>/status` | change the status | `status`, `note` |
| POST | `/p/<pid>/s/<sid>/note` | add a note | `note` |
| POST | `/p/<pid>/s/<sid>/tags` | replace tags | `tags` (comma-separated) |

### JSON endpoint

`GET /api/p/<pid>/jobs` returns the current user's analysis jobs for the project
(the latest 50, newest first). They come from the durable queue (`jobs.db`), so
they survive restarts and are the same from every web process.

```json
[
  {
    "id": 3, "owner": "eduardo", "project": "ai-se", "source": "source-002",
    "engine": "llm", "state": "running", "error": null, "attempts": 1,
    "worker": "3bd3ee580f51:1", "queued_at": "2026-09-30T18:11:52Z",
    "started_at": "2026-09-30T18:11:53Z", "finished_at": null
  }
]
```

`state` is one of `queued`, `running`, `done`, `failed` (with `error`).
`attempts` above 1 means the job was recovered after a worker stopped.

### Health

`GET /healthz` needs no login. It returns `200 {"status": "ok", "version": "0.1.0"}`,
or `503 {"status": "error", "detail": "data root not writable: …"}`. Used by the
container `HEALTHCHECK` and suitable for load-balancer probes.

### Static assets

`GET /static/style.css`, `GET /static/app.js`. There are no other assets and no
external requests.

## Example: scripted upload with curl

```bash
B=https://review.example.org; J=cookies.txt
token() { curl -s -b $J -c $J "$B$1" | grep -o 'name="csrf_token" value="[^"]*"' | head -1 | cut -d'"' -f4; }

T=$(token /login)
curl -s -b $J -c $J -d "csrf_token=$T&username=maria&password=$PASS" $B/login -o /dev/null
T=$(token /)
curl -s -b $J -c $J -F "csrf_token=$T" -F "files=@paper.pdf" -F analyze=1 -F engine=llm \
     $B/p/ai-se/upload -o /dev/null
curl -s -b $J $B/api/p/ai-se/jobs
```

The HTML routes are not a stable API and may change between versions. Prefer
the CLI on the server for automation.
