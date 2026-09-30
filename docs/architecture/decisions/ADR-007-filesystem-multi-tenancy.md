# ADR-007: Filesystem-based multi-tenancy

- **Status:** Accepted
- **Date:** 2026-09-30

## Context

Several researchers must be able to use one installation, each with a private
space that holds multiple projects. The system has no database (ADR-002).

## Decision

Each account gets a workspace directory `<root>/users/<username>/` containing
that user's projects. Accounts live in `<root>/users.json` (scrypt hashes, mode
600). The web layer resolves every project through the logged-in user's
workspace; usernames and project ids are validated against strict patterns
before any path is built; background jobs record and filter by owner. The first
account becomes administrator; more accounts are created by an admin, by
`acam user add`, or by self-service sign-up if `--allow-signup` is set. The
CLI selects a workspace with `--user`, and `acam user adopt` migrates
single-user projects.

## Consequences

- Isolation is simple to reason about and to audit: a user's data is a directory.
- Per-user backup, export or deletion is a directory operation.
- Other users' projects answer 404, so their existence is not revealed.
- Project sharing between users isn't possible yet. It would need an access
  list per project (or a database, see ADR-002).
- Anyone with filesystem access (server administrators) can read every workspace.
  Data at rest isn't encrypted.

## Alternatives considered

- *Tenant id column in a shared database:* needs a database, and isolation
  depends on every query remembering the filter.
- *One process or container per user:* strongest isolation, but much heavier to run.
