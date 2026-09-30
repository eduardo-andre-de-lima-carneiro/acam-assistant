# ACAM Assistant Documentation

Technical documentation for **ACAM Assistant** (ACAM = *Academic Management*), a
research assistant for managing academic work, currently focused on literature reviews.
The repository's top-level [README](../README.md) is the product specification and
quick start. This folder explains how the system is designed, built, secured,
deployed and integrated.

| Area | Document | Read it when you want to… |
| ---- | -------- | ------------------------- |
| **Design** | [Overview & principles](design/overview.md) | understand what the system does, for whom, and the rules it never breaks |
| | [Data model](design/data-model.md) | read or write `project.json`, `sources.json`, analysis files, provenance fields |
| | [Processing pipeline](design/processing-pipeline.md) | know exactly what happens from import to analysis |
| | [User experience](design/user-experience.md) | see the web and CLI workflows |
| **Architecture** | [Architecture overview](architecture/overview.md) | find your way around the modules, runtime behaviour and storage layout |
| | [Decision records](architecture/decisions/README.md) | understand *why* things are built the way they are |
| **Technology** | [Technology stack](technology/stack.md) | set up a dev environment, run the tests, add a dependency |
| **Security** | [Security](security/security.md) | review the threat model, controls, data flows to third parties and known gaps |
| **Deployment** | [Local installation](deployment/local.md) | run ACAM Assistant on your own computer |
| | [Container deployment](deployment/container.md) | run it with Docker / Compose (recommended for servers), with optional automatic HTTPS |
| | [Server deployment](deployment/server.md) | host it without containers (gunicorn, nginx, systemd, backups) |
| | [Configuration reference](deployment/configuration.md) | look up every environment variable, flag and file |
| **Integration** | [Claude API integration](integration/claude-api.md) | understand or change the LLM analysis engine |
| | [CLI reference](integration/cli-reference.md) | script ACAM Assistant from the shell |
| | [HTTP interface](integration/http-interface.md) | call the web routes or the JSON job endpoint |
| | [Data exchange](integration/data-exchange.md) | consume exports (JSON, CSV, Markdown) or feed data from other tools |
| | [Extending ACAM Assistant](integration/extending.md) | add a format, analysis engine, reference style or artifact |
| **Planning** | [MVP plan](planning/mvp-plan.md) | see the MVP scope, what was delivered and what comes next |

## Conventions used in these documents

- Paths such as `src/acam/pipeline.py` are relative to the repository root.
- *Data root* is the directory given by `--workspace` or `$ACAM_HOME`
  (default `./projects`). A *workspace* is the directory that holds a set of
  projects: the data root itself in single-user CLI use, or
  `<data root>/users/<username>/` for an account.
- "Researcher" means a human user; "system" means ACAM Assistant.

## Version

These documents describe ACAM Assistant **0.1.0**. When behaviour changes, update the
document that owns the topic (see the table above) in the same change as the code.
