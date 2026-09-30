# ADR-008: In-process background jobs and single-process deployment

- **Status:** Superseded by [ADR-010](ADR-010-multi-process-concurrency.md)
- **Date:** 2026-09-30

## Context

LLM analyses take from seconds to minutes. Web requests must not block for that
long, and the MVP should not need extra infrastructure such as Redis or Celery.

## Decision

Run analyses in a `ThreadPoolExecutor` (2 workers) inside the web process. Jobs
are kept in memory, and the browser polls `GET /api/p/<pid>/jobs`. Catalog writes
use a process-wide lock. The application therefore runs as **one process**, with
any number of threads (for example `gunicorn -w 1 --threads 8`).

## Consequences

- No broker or worker service to deploy.
- Job history is lost on restart, and an analysis running during a restart is
  dropped. Saved results are not affected, and the researcher can analyze again.
- Throughput is limited to one machine and one process. That is enough for a
  research group; scaling out would need a shared lock (file lock or database)
  and a shared job queue.

## Alternatives considered

- *Celery/RQ with Redis:* persistent jobs and horizontal scaling, but more services to run.
- *Synchronous analysis in the request:* long-hanging requests and proxy timeouts.
