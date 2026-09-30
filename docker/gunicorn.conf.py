"""gunicorn settings for the ACAM Assistant container.

Catalog writes use inter-process file locks and analyses go through the SQLite
job queue (ADR-010), so any number of worker processes is safe on one host.
Analyses normally run in the separate `worker` service
(ACAM_EMBEDDED_WORKER=false for the web service).
"""

import os

bind = os.environ.get("ACAM_BIND", "0.0.0.0:8000")
workers = int(os.environ.get("ACAM_WORKERS", "2"))
worker_class = "gthread"
threads = int(os.environ.get("ACAM_THREADS", "4"))
timeout = int(os.environ.get("ACAM_TIMEOUT", "120"))  # large uploads; analyses run in background
graceful_timeout = 30
keepalive = 5
worker_tmp_dir = "/dev/shm"  # heartbeat file off the (possibly read-only) disk
control_socket_disable = True  # gunicorn >= 26 control socket; unused and needs a writable home

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("ACAM_LOG_LEVEL", "info")
# Proxy IPs allowed to set X-Forwarded-* headers (the compose network by default).
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1")

# Do not preload: each worker process builds its own app (and embedded worker, if enabled).
preload_app = False
