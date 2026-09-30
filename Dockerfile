# syntax=docker/dockerfile:1
#
# ACAM Assistant (Academic Management Assistant) container image.
#
#   docker build -t acam .                       # runtime image
#   docker build --target test -t acam:test .   # runs the test suite in the image's Python
#
# See docs/deployment/container.md.

ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------- build ----
FROM python:${PYTHON_VERSION}-slim AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /src
COPY pyproject.toml README.md ./
COPY src ./src
# Wheels for the app and every runtime dependency (incl. gunicorn).
RUN pip wheel --wheel-dir /wheels ".[server]"

# ----------------------------------------------------------------- test ----
FROM build AS test
COPY schemas ./schemas
COPY examples ./examples
COPY tests ./tests
RUN pip install -e ".[dev,server]" \
 && useradd --create-home tester && chown -R tester /src
USER tester
COPY tools ./tools
RUN python -m pytest -q -p no:cacheprovider && python tools/check_coverage.py --min 85

# -------------------------------------------------------------- runtime ----
FROM python:${PYTHON_VERSION}-slim AS runtime

LABEL org.opencontainers.image.title="ACAM Assistant" \
      org.opencontainers.image.description="Academic Management Assistant: literature review support" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ACAM_HOME=/data \
    TMPDIR=/data/.tmp \
    ACAM_BIND=0.0.0.0:8000 \
    ACAM_EMBEDDED_WORKER=true

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /nonexistent --shell /usr/sbin/nologin app \
 && mkdir -p /data/.tmp && chown -R app:app /data && chmod 700 /data

COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels "acam-assistant[server]" \
 && rm -rf /wheels

COPY docker/gunicorn.conf.py /etc/acam/gunicorn.conf.py
COPY --chmod=0755 docker/entrypoint.sh /usr/local/bin/acam-entrypoint

USER app
WORKDIR /data
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request as u; sys.exit(0 if u.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"]

ENTRYPOINT ["acam-entrypoint"]
CMD ["serve"]
