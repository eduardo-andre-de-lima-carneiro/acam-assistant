# Container Deployment

ACAM Assistant ships as an OCI image built from the repository's `Dockerfile`, with a
`docker-compose.yml` for single-host deployments. This is the recommended way to
run it on a server.

Verified with Docker 28 / Compose v2: image build; the full test suite and the
per-file coverage gate inside the image (Python 3.12); health checks of both
services; admin bootstrap; upload and analysis processed by the worker container;
30 parallel edits across 2 web processes with none lost; the "no worker" warning
and automatic catch-up when the worker returns; `--scale worker=2` sharing the
queue; persistence across restarts; and the HTTPS profile (Caddy), including login
and CSRF through the proxy.

## Files

| File | Purpose |
| ---- | ------- |
| `Dockerfile` | multi-stage build: `build` (wheels), `test` (runs pytest as non-root), `runtime` (final image) |
| `docker/gunicorn.conf.py` | gunicorn settings (`ACAM_WORKERS` processes × `ACAM_THREADS` threads) |
| `docker/entrypoint.sh` | `serve` (default): bootstrap, then `exec gunicorn`; `worker`: `exec acam worker`; any other command is run as given |
| `docker/Caddyfile` | HTTPS reverse proxy for the `tls` profile |
| `docker-compose.yml` | `acam` (web) and `worker` services with hardening, plus an optional `caddy` service (`--profile tls`) |
| `.env.example` | every setting, documented; copy it to `.env` |
| `.dockerignore` | keeps `.git`, `.venv`, `.env`, `secrets/`, local `projects/` and docs out of the build |

## Image

| Property | Value |
| -------- | ----- |
| Base | `python:3.12-slim` (build argument `PYTHON_VERSION`) |
| Size | about 180 MB |
| User | `app`, uid/gid **10001**, no shell, no home |
| Process | `gunicorn` as PID 1 (via `exec`): `ACAM_WORKERS` (2) processes × `ACAM_THREADS` (4) threads; or `acam worker` with the `worker` command |
| Port | 8000 |
| Volume | `/data`: the data root (accounts, secret key, all workspaces) |
| Temporary files | `TMPDIR=/data/.tmp`. Uploads are staged on the volume, not in memory, so the root filesystem can be read-only |
| Health check | web: `GET /healthz` (data root writable); worker service: `acam worker --health` (the worker on this host is registered and alive) |
| Logs | access and error logs on stdout/stderr |

## Quick start

```bash
cp .env.example .env              # set ANTHROPIC_API_KEY, admin user, etc.
docker compose up -d --build
docker compose ps                 # wait for "healthy"
open http://127.0.0.1:8000        # or xdg-open
```

If `ACAM_ADMIN_USER` and a password are set, that administrator is created
at first start. Otherwise the first visitor creates the administrator on the
setup page. **Do this immediately** after exposing the service.

## Configuration

All settings are environment variables, usually in `.env`. The full list is in
[Configuration](configuration.md#container-variables). The most important ones:

| Variable | Typical value |
| -------- | ------------- |
| `ANTHROPIC_API_KEY` | your key (empty = offline heuristic engine) |
| `ACAM_ADMIN_USER` / `ACAM_ADMIN_PASSWORD_FILE` | first administrator, created once |
| `ACAM_SECURE_COOKIES` | `true` whenever users connect over HTTPS |
| `ACAM_ALLOW_SIGNUP` | `false` unless open registration is wanted |
| `ACAM_DOMAIN` | public domain for the `tls` profile |
| `ACAM_WORKERS` / `ACAM_THREADS` | web processes (default 2) and threads per process (default 4) |
| `ACAM_WORKER_THREADS` | concurrent analyses per worker container (default 2) |

### Admin password as a secret

Prefer a file secret to a plain variable:

```bash
mkdir -p secrets && chmod 700 secrets
printf '%s' 'a-long-random-password' > secrets/admin_password.txt
```

In `docker-compose.yml`, uncomment the two `secrets:` blocks. In `.env`, set:

```bash
ACAM_ADMIN_USER=admin
ACAM_ADMIN_PASSWORD_FILE=/run/secrets/admin_password
ACAM_ADMIN_PASSWORD=
```

`secrets/` is git- and docker-ignored. After the first start the account exists,
and the secret is no longer read (the bootstrap skips existing users).

## HTTPS with the `tls` profile

For a server with a public DNS name pointing at it and ports 80 and 443 open:

```bash
# .env
ACAM_DOMAIN=review.example.org
ACAM_SECURE_COOKIES=true
FORWARDED_ALLOW_IPS=*

docker compose --profile tls up -d --build
```

Caddy gets and renews a Let's Encrypt certificate, redirects HTTP to HTTPS, and
adds HSTS, CSP, `X-Frame-Options`, `nosniff` and `Referrer-Policy` headers. It
limits request bodies to 200 MB and forwards the original `Host` header, which
ACAM Assistant's CSRF origin check needs. The app itself stays bound to `127.0.0.1`.

With `ACAM_DOMAIN=localhost`, Caddy uses its internal CA, which is useful
for testing. To use your own proxy (nginx, Traefik, a cloud load balancer)
instead, see [Server deployment](server.md#5-nginx-reverse-proxy-tls): keep the
`Host` header and set `ACAM_SECURE_COOKIES=true`.

## Hardening applied by the compose file

| Setting | Effect |
| ------- | ------ |
| `read_only: true` | root filesystem is immutable; only `/data` (volume) and `/tmp` (64 MB tmpfs) are writable |
| `cap_drop: [ALL]` | no Linux capabilities |
| `security_opt: no-new-privileges` | no privilege escalation through setuid binaries |
| non-root user 10001 | set in the image |
| port bound to `127.0.0.1` | not reachable from the network without the proxy |
| gunicorn control socket disabled | no extra socket, no writable home needed |

## Operations

### Administration commands

`docker compose exec` runs commands in the running container as the app user:

```bash
docker compose exec acam acam user list
docker compose exec acam acam user add maria --name "Maria Silva"             # prompts for the password
docker compose exec acam acam user passwd maria
docker compose exec acam acam --user maria projects
```

### Logs and health

```bash
docker compose logs -f acam
docker compose ps                     # STATUS shows (healthy)
curl -s http://127.0.0.1:8000/healthz # {"status":"ok","version":"0.1.0"}
```

### Backup and restore

All state is in the `acam-data` volume:

```bash
# backup (stop briefly for a fully consistent copy)
docker compose stop acam
docker run --rm -v acam_acam-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/acam-$(date +%F).tar.gz -C /data .
docker compose start acam

# restore into an empty volume
docker compose down
docker run --rm -v acam_acam-data:/data -v "$PWD":/backup alpine \
  sh -c 'tar xzf /backup/acam-YYYY-MM-DD.tar.gz -C /data && chown -R 10001:10001 /data'
docker compose up -d
```

The volume name is `<compose project>_acam-data`; check it with
`docker volume ls`. Backups contain password hashes, the session key and research
data, so encrypt them.

### Upgrade

```bash
git pull
docker compose build --pull
docker compose up -d
```

Sessions survive because the key is on the volume. The worker gets 3 minutes
(`stop_grace_period`) to finish running analyses; anything interrupted is
re-queued and picked up by the new worker.

### Using a host directory instead of a named volume

```yaml
    volumes:
      - /srv/acam/data:/data
```

The directory must be writable by uid 10001:
`sudo install -d -o 10001 -g 10001 -m 700 /srv/acam/data`.

### Migrating existing data into the container

Copy an existing data root (the folder with `users.json` and `users/`) into the
volume with the restore command above. Projects created before accounts existed
can then be adopted with
`docker compose exec acam acam user adopt <username>`.

## Scaling and limits

| Need | Do |
| ---- | -- |
| more concurrent page loads / uploads | raise `ACAM_WORKERS` (processes, one per CPU core is a good start) or `ACAM_THREADS` |
| more concurrent analyses | raise `ACAM_WORKER_THREADS`, or `docker compose up -d --scale worker=N` |
| analyses independent of web deploys | already the default: the web service has `ACAM_EMBEDDED_WORKER=false` |

All containers must run on **one host** and share the `acam-data` volume.
File locks and SQLite need a local filesystem, so don't put the data root on NFS
or SMB, and don't spread replicas across hosts
([ADR-010](../architecture/decisions/ADR-010-multi-process-concurrency.md)).
The practical ceiling for analyses is your Anthropic rate limit, not ACAM Assistant.

Watch the queue with `docker compose exec acam acam jobs`. If jobs are
queued and no worker is alive, the project page shows a warning.

Kubernetes works with the same constraints:
- put the web `Deployment` and the worker `Deployment` on the same node
  (pod affinity) with a `ReadWriteOnce` volume at `/data`;
- use `/healthz` as the web probe and `acam worker --health` as the worker
  probe;
- run with `runAsUser: 10001` and `readOnlyRootFilesystem: true`.

No manifests are provided yet.

## Building and testing the image

```bash
docker build --target test .           # runs the test suite + per-file coverage gate (≥ 85%) as a non-root user
docker build -t acam:0.1.0 .           # runtime image
docker build --build-arg PYTHON_VERSION=3.11 -t acam:py311 .
```
