#!/bin/sh
# ACAM Assistant container entrypoint.
#   serve (default)   bootstrap, then run gunicorn as PID 1
#   worker            run the background analysis worker as PID 1
#   <anything else>   run that command, e.g. `acam user list`
set -eu

case "${1:-serve}" in
  serve)
    mkdir -p "${TMPDIR:-/data/.tmp}"
    # Leftovers from an interrupted upload.
    find "${TMPDIR:-/data/.tmp}" -mindepth 1 -mmin +60 -delete 2>/dev/null || true
    python -m acam.container
    exec gunicorn --config /etc/acam/gunicorn.conf.py acam.web.wsgi:app
    ;;
  worker)
    mkdir -p "${TMPDIR:-/data/.tmp}"
    exec acam worker --threads "${ACAM_WORKER_THREADS:-2}"
    ;;
  *)
    exec "$@"
    ;;
esac
