# Configuration Reference

ACAM Assistant is configured through environment variables, command-line flags and
app-factory arguments. It has no configuration file.

## Environment variables

| Variable | Default | Used by | Purpose |
| -------- | ------- | ------- | ------- |
| `ACAM_HOME` | `./projects` (resolved against the working directory) | CLI, web | data root |
| `ACAM_MODEL` | `claude-opus-5-5` | LLM engine | Claude model id |
| `ANTHROPIC_API_KEY` | — | LLM engine | API key. Setting it makes `auto` choose the LLM engine |
| `ANTHROPIC_API_KEY_FILE` | — | CLI, web, worker | file holding the API key (Docker/K8s secret); used when `ANTHROPIC_API_KEY` is not set. Recommended for servers |
| `ANTHROPIC_AUTH_TOKEN_FILE` | — | CLI, web, worker | same for `ANTHROPIC_AUTH_TOKEN` |
| `ANTHROPIC_AUTH_TOKEN` | — | LLM engine | alternative credential (OAuth token); also makes `auto` choose LLM |
| `ANTHROPIC_PROFILE` | — | LLM engine | named Anthropic CLI profile; also makes `auto` choose LLM |
| `ACAM_ALLOW_SIGNUP` | `false` | web | `true`/`1`/`yes`/`on` enables self-service sign-up (flag `--allow-signup` or factory argument wins) |
| `ACAM_SECURE_COOKIES` | `false` | web | session cookie only over HTTPS (flag `--secure-cookies` or factory argument wins) |
| `ACAM_EMBEDDED_WORKER` | `true` | web | run an analysis worker inside each web process; set `false` when a separate `acam worker` runs |
| `ACAM_WORKER_THREADS` | `2` | web (embedded), `acam worker` | concurrent analyses per worker |

The `auto` engine only looks at the three `ANTHROPIC_*` variables above. If your
credentials come from somewhere else (for example the default profile of
`ant auth login`), the SDK can still authenticate, but `auto` falls back to the
heuristic engine. Select `--engine llm` explicitly in that case.

### Container variables

Read by the image's entrypoint and gunicorn config (`docker/`). See
[Container deployment](container.md).

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `ACAM_ADMIN_USER` | — | administrator created at start-up if it doesn't exist |
| `ACAM_ADMIN_NAME` | username | display name for that administrator |
| `ACAM_ADMIN_PASSWORD_FILE` | — | file with the admin password (Docker/K8s secret), preferred |
| `ACAM_ADMIN_PASSWORD` | — | admin password as plain variable (fallback) |
| `ACAM_BIND` | `0.0.0.0:8000` | gunicorn bind address inside the container |
| `ACAM_WORKERS` | `2` | gunicorn worker processes |
| `ACAM_THREADS` | `4` | gunicorn threads per process |
| `ACAM_TIMEOUT` | `120` | gunicorn request timeout in seconds |
| `ACAM_LOG_LEVEL` | `info` | gunicorn log level |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` in the image; `*` in `.env.example` | proxies trusted for `X-Forwarded-*` headers |
| `TMPDIR` | `/data/.tmp` | where uploads are staged |
| `ACAM_PORT` | `8000` | compose only: host port (bound to 127.0.0.1) |
| `ACAM_DOMAIN` | — | compose `tls` profile: public domain for Caddy |
| `ACAM_IMAGE_TAG` | `0.1.0` | compose only: image tag |

## Global CLI options

| Option | Meaning |
| ------ | ------- |
| `--workspace PATH` | data root (overrides `ACAM_HOME`) |
| `--user NAME`, `-u NAME` | run the command inside that account's workspace; the account must exist |
| `--version` | print the version |

## `acam web` options

| Option | Default | Meaning |
| ------ | ------- | ------- |
| `--host` | `127.0.0.1` | interface to bind. Only change it behind a firewall or proxy |
| `--port` | `8000` | TCP port |
| `--allow-signup` | off | anyone can create an account (the first account can always be created) |
| `--secure-cookies` | off | session cookie sent only over HTTPS |
| `--debug` | off | Flask debug mode. Refused unless `--host` is a loopback address; never use in production |

`acam web` uses Flask's development server, which is fine on your own
machine. For servers, use the app factory with gunicorn:

```python
acam.web.create_app(
    workspace=None,          # Path; default: ACAM_HOME or ./projects
    inline_jobs=False,       # True runs analyses synchronously (tests)
    allow_signup=None,       # None: read ACAM_ALLOW_SIGNUP
    secure_cookies=None,     # None: read ACAM_SECURE_COOKIES
    embedded_worker=None,    # None: read ACAM_EMBEDDED_WORKER (default true)
)
```

```bash
gunicorn -w 2 --threads 4 "acam.web:create_app(allow_signup=True, secure_cookies=True)"
gunicorn -w 2 --threads 4 acam.web.wsgi:app            # everything from the environment
acam worker --threads 2                                 # separate analysis worker
```

## Files in the data root

| Path | Created | Notes |
| ---- | ------- | ----- |
| `users.json` | first account | mode 600; see [Data model](../design/data-model.md#accounts-usersjson) |
| `.secret_key` | first web start | mode 600; delete it to invalidate every session |
| `.tmp/` | container start | staged uploads (`TMPDIR` in the image); safe to empty while stopped |
| `jobs.db` (+ `-wal`, `-shm`) | first web/worker start | SQLite job queue and worker registry; operational state only. Deleting it while everything is stopped only loses job history |
| `users.json.lock`, `<project>/.lock` | first write | empty lock files used with `flock`; safe to leave |
| `users/<username>/` | account creation | the user's workspace |
| `<project-id>/` | CLI without `--user` | single-user projects; move them with `user adopt` |

## Built-in limits

These are constants in the code. Change them there if needed.

| Limit | Value | Location |
| ----- | ----- | -------- |
| Upload request size | 200 MB | `web/__init__.py` `MAX_CONTENT_LENGTH` |
| Analysis threads per worker | 2 | `ACAM_WORKER_THREADS` / `acam worker --threads` |
| Job heartbeat / stale timeout / max attempts | 15 s / 120 s / 3 | `worker.py` `HEARTBEAT_EVERY`, `STALE_AFTER`; `jobs.py` `MAX_ATTEMPTS` |
| Lock wait timeout | 30 s | `locks.py` `DEFAULT_TIMEOUT` |
| Job polling interval (browser) | 2.5 s | `web/static/app.js` |
| LLM input size | 2,000,000 characters | `analysis/llm.py` `MAX_CHARS` |
| LLM `max_tokens` / effort | 32,000 / `medium` | `analysis/llm.py` |
| Minimum converted text | 200 characters | `validation.py` `MIN_CHARS` |
| Password length | ≥ 8 characters | `accounts.py` `MIN_PASSWORD` |
| Username pattern | `^[a-z0-9][a-z0-9_-]{2,31}$` | `accounts.py` |
| Project id pattern | `^[a-z0-9][a-z0-9_-]{0,63}$` | `storage.py` |
