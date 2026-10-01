# Server Deployment

How to host ACAM Assistant for a research group on a Linux server. The same app runs
locally with `acam web`. For a server, use a production WSGI server behind
an HTTPS reverse proxy.

```text
Users ──HTTPS──► nginx (TLS, rate limit, body size) ──HTTP──► gunicorn (1 worker, N threads)
                                                                  │
                                                     /srv/acam/data (data root)
```

## Processes

ACAM Assistant runs as two kinds of process sharing the data root
([ADR-010](../architecture/decisions/ADR-010-multi-process-concurrency.md)):

| Process | Command | Scale with |
| ------- | ------- | ---------- |
| web | `gunicorn … acam.web.wsgi:app` | `-w` (processes, uses more CPU cores) and `--threads` |
| analysis worker | `acam worker` | `--threads`, or more worker processes |

Both use file locks and a SQLite queue, so any number of them is safe **on one
host**. The data root must be on a local filesystem, not NFS or SMB. Set
`ACAM_EMBEDDED_WORKER=false` for the web process when a separate worker
runs. That way web restarts never interrupt analyses.

## 1. Prepare the host

```bash
sudo useradd --system --create-home --home-dir /srv/acam acam
sudo -u acam python3 -m venv /srv/acam/venv
sudo -u acam /srv/acam/venv/bin/pip install "/path/to/acam-s2[server]"                  # includes gunicorn
sudo -u acam mkdir -p /srv/acam/data
sudo chmod 700 /srv/acam/data
```

## 2. Configure

`/srv/acam/acam.env` (mode 600, owned by `acam`):

```bash
ACAM_HOME=/srv/acam/data
ACAM_EMBEDDED_WORKER=false            # analyses run in acam-worker.service
ANTHROPIC_API_KEY=sk-ant-...          # optional: enables the LLM engine
# or keep it in a root-only file:  ANTHROPIC_API_KEY_FILE=/etc/acam/anthropic_api_key
# ACAM_MODEL=claude-opus-5-5     # optional override
```

The application options (`allow_signup`, `secure_cookies`) are passed to the app
factory in the gunicorn command. See [Configuration](configuration.md).

## 3. Run with gunicorn

```bash
cd /srv/acam
set -a; . ./acam.env; set +a
venv/bin/gunicorn -w 2 --threads 4 -b 127.0.0.1:8000 --timeout 120 \
  "acam.web:create_app(secure_cookies=True)"
# equivalent, configured only by environment variables:
# ACAM_SECURE_COOKIES=true venv/bin/gunicorn -w 2 --threads 4 -b 127.0.0.1:8000 acam.web.wsgi:app

# in another terminal / service: the analysis worker
venv/bin/acam worker --threads 2
```

- `secure_cookies=True`: required when users connect over HTTPS.
- Add `allow_signup=True` inside the parentheses to allow self-registration.
- `--timeout 120` covers large uploads. Analyses run in background threads and
  are not limited by the request timeout.

Then create the administrator: open the site and use the first-run page, or run

```bash
sudo -u acam env ACAM_HOME=/srv/acam/data \
  /srv/acam/venv/bin/acam user add admin --admin
```

## 4. systemd service

`/etc/systemd/system/acam.service`:

```ini
[Unit]
Description=ACAM Assistant (Academic Management Assistant) web
After=network.target

[Service]
User=acam
Group=acam
WorkingDirectory=/srv/acam
EnvironmentFile=/srv/acam/acam.env
ExecStart=/srv/acam/venv/bin/gunicorn -w 2 --threads 4 -b 127.0.0.1:8000 --timeout 120 \
  "acam.web:create_app(secure_cookies=True)"
# equivalent, configured only by environment variables:
# ACAM_SECURE_COOKIES=true venv/bin/gunicorn -w 2 --threads 4 -b 127.0.0.1:8000 acam.web.wsgi:app
Restart=on-failure
# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/srv/acam/data
UMask=0077

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/acam-worker.service`:

```ini
[Unit]
Description=ACAM Assistant analysis worker
After=network.target

[Service]
User=acam
Group=acam
WorkingDirectory=/srv/acam
EnvironmentFile=/srv/acam/acam.env
ExecStart=/srv/acam/venv/bin/acam worker --threads 2
Restart=on-failure
# Let running analyses finish on stop; if killed they are re-queued automatically.
TimeoutStopSec=180
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/srv/acam/data
UMask=0077

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now acam acam-worker
journalctl -u acam -u acam-worker -f
sudo -u acam env ACAM_HOME=/srv/acam/data /srv/acam/venv/bin/acam jobs
```

Uploads are staged in the system temporary directory, which `PrivateTmp`
isolates per service.

## 5. nginx reverse proxy (TLS)

```nginx
limit_req_zone $binary_remote_addr zone=acam_login:10m rate=10r/m;

server {
    listen 443 ssl http2;
    server_name review.example.org;

    ssl_certificate     /etc/letsencrypt/live/review.example.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/review.example.org/privkey.pem;

    client_max_body_size 200m;             # matches the app's upload limit

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Referrer-Policy same-origin always;
    add_header Content-Security-Policy "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; form-action 'self'; frame-ancestors 'none'" always;

    location = /login {                    # slow down password guessing
        limit_req zone=acam_login burst=5 nodelay;
        proxy_pass http://127.0.0.1:8000;
        include /etc/nginx/proxy_params;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;       # required: CSRF origin check compares with Host
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}

server {
    listen 80;
    server_name review.example.org;
    return 301 https://$host$request_uri;
}
```

`proxy_params` (Debian/Ubuntu) sets `Host` and the forwarding headers. On other
systems, copy the three `proxy_set_header` lines into the `/login` block. The
Content-Security-Policy above works because ACAM Assistant loads no external or inline
scripts or styles. The only inline asset is the favicon, a `data:` image.

## 6. Containers (alternative)

The repository includes a tested `Dockerfile`, `docker-compose.yml` and an
optional Caddy HTTPS proxy. See [Container deployment](container.md).

## Operations

### Health check

`GET /healthz` returns `200 {"status":"ok","version":…}` when the app is up and
the data root is writable, and `503` otherwise. It needs no login. Use it for
uptime monitoring and load-balancer probes.

### Logs

gunicorn writes access and error logs to stdout/stderr (journald or `docker logs`).
Failed analyses are shown to the user and kept in the job queue
(`acam jobs` shows counts; `acam jobs --purge 30` removes finished jobs
older than 30 days). Put nginx access logs somewhere persistent for auditing.

### Backup and restore

Everything is in the data root. Back up the whole directory, including
`users.json` and `.secret_key`:

```bash
# consistent copy: stop, copy, start (a few seconds of downtime)
sudo systemctl stop acam
sudo tar -C /srv/acam -czf /backup/acam-$(date +%F).tar.gz data
sudo systemctl start acam
```

A filesystem snapshot (LVM/ZFS/cloud disk) taken while the app runs is also
consistent enough: JSON files are replaced atomically. Restoring means putting
the directory back while the service is stopped. Encrypt backups, because they
contain password hashes and research data.

### Upgrading

```bash
sudo -u acam /srv/acam/venv/bin/pip install --upgrade /path/to/new/acam-s2
sudo systemctl restart acam
```

Restarting the web service doesn't affect analyses. Restarting the worker lets
running analyses finish (up to `TimeoutStopSec`); anything interrupted is
re-queued automatically. Saved data is not affected. Read the changelog or
decision records for data-format changes. The 0.1.0 formats are described in
[Data model](../design/data-model.md).

### Migrating from single-user to accounts

Projects created with the CLI before accounts existed live directly in the data
root. Move them into an account with:

```bash
acam user adopt <username>
```

### Managing users

```bash
acam user list
acam user add maria --name "Maria Silva"
acam user passwd maria
acam user remove maria                      # keeps her workspace on disk
acam user remove maria --delete-data        # also deletes her projects
```

Run these as the service user with the same `ACAM_HOME`.

## Hardening checklist

- [ ] HTTPS only, HSTS enabled, app started with `secure_cookies=True`
- [ ] gunicorn bound to `127.0.0.1` (or a private network)
- [ ] Data root on a local filesystem or block volume (not NFS/SMB)
- [ ] Self-service sign-up disabled unless needed (`allow_signup` not set)
- [ ] Rate limit on `/login` at the proxy
- [ ] Data root owned by the service user, mode 700; `UMask=0077`
- [ ] Data volume encrypted at rest; backups encrypted
- [ ] `ANTHROPIC_API_KEY` in an environment file with mode 600, spend limit set in the Anthropic console
- [ ] Users informed which engine is active and what the LLM engine sends to Anthropic ([Security](../security/security.md#data-sent-to-third-parties))
- [ ] OS and Python dependencies patched regularly (`pip list --outdated`)
- [ ] Disk usage monitored (no per-user quotas in the app)
