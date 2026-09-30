# ADR-009: Container image and Compose as the reference deployment

- **Status:** Accepted (single-worker rule superseded by [ADR-010](ADR-010-multi-process-concurrency.md))
- **Date:** 2026-09-30

## Context

Deploying ACAM Assistant on a server by hand (virtualenv, gunicorn, systemd, nginx)
takes many manual steps, and it is easy to misconfigure the one hard rule: run a
single process ([ADR-008](ADR-008-in-process-jobs-single-process.md)). Research
groups want a deployment that can be reproduced with one command.

## Decision

Provide a multi-stage `Dockerfile` and a `docker-compose.yml` as the reference
deployment:

- **Image:** wheels are built in a `build` stage and installed into a slim
  `runtime` stage. It runs as non-root uid 10001, has `/data` as its single
  volume, and runs gunicorn as PID 1.
- **Test stage:** a `test` stage runs the full suite inside the image's Python.
- **Configuration:** everything comes from environment variables
  (`ACAM_ALLOW_SIGNUP`, `ACAM_SECURE_COOKIES`, …) through `create_app`
  and `acam.web.wsgi:app`.
- **Bootstrap:** an optional first administrator is created at start-up from
  `ACAM_ADMIN_USER` and a secret file (`acam.container`). It does
  nothing on later starts.
- **Single worker:** `docker/gunicorn.conf.py` fixes `workers = 1` and refuses to
  start otherwise.
- **Health:** a public `GET /healthz` checks that the data root is writable and
  backs the image `HEALTHCHECK`.
- **Uploads:** staged in `/data/.tmp` (`TMPDIR`), so the root filesystem can be
  read-only without holding large uploads in memory.
- **Compose hardening:** read-only root, all capabilities dropped,
  `no-new-privileges`, and the port published on localhost only. An opt-in `tls`
  profile adds Caddy for automatic HTTPS.

## Consequences

- One command (`docker compose up -d --build`) gives a hardened, health-checked
  deployment. Adding `--profile tls` gives public HTTPS.
- The single-worker rule is enforced in configuration, not just documented.
- Operators need Docker. The non-container path ([server.md](../../deployment/server.md))
  remains supported.
- The image must still run as a single replica. Horizontal scaling needs the
  changes described in ADR-008.

## Alternatives considered

- *Documentation only (manual install):* error-prone, and it doesn't enforce the
  single-process rule.
- *nginx instead of Caddy in the compose file:* needs certificate management
  (certbot). Caddy handles ACME automatically. nginx remains documented for
  non-container installs.
- *Kubernetes manifests / Helm chart:* premature for the target audience. The
  container guide describes the required settings.
