# CLI Reference

```text
acam [--workspace PATH] [--user NAME] <command> [options]
```

- `--workspace PATH`: data root (default `$ACAM_HOME` or `./projects`).
- `--user NAME`: operate inside that account's workspace.
- Exit codes: `0` success; `1` one or more files failed to import or analyses
  failed; `2` usage or user error (unknown project/source, invalid value).

## Projects

| Command | Description |
| ------- | ----------- |
| `init TITLE [--id ID] [--description TEXT] [-q QUESTION]… [--include CRIT]… [--exclude CRIT]…` | create a project |
| `projects` | list projects with their source counts |

## Sources

| Command | Description |
| ------- | ----------- |
| `import PROJECT FILE… [--type TYPE] [--tag TAG]… [--analyze] [--engine auto\|llm\|heuristic] [--model ID] [--allow-duplicate]` | import, convert, validate and extract metadata; optionally analyze |
| `analyze PROJECT [SOURCE…] [--all] [--engine …] [--model ID] [--queue]` | analyze the given sources, or every source not yet analyzed (`--all` re-analyzes everything). `--queue` hands them to the background worker instead of running now; with `--user`, they show up in that user's web interface |
| `list PROJECT [--status STATUS] [--tag TAG]` | table of sources |
| `show PROJECT SOURCE [--json]` | readable report, or the raw record + analysis as JSON |

## Researcher validation

| Command | Description |
| ------- | ----------- |
| `set PROJECT SOURCE FIELD VALUE` | set a metadata field (validated, origin `researcher`). `FIELD=type` sets the source type. Lists (`authors`, `keywords`) use `;` as separator |
| `confirm PROJECT SOURCE FIELD…` | mark extracted values as validated |
| `status PROJECT SOURCE STATUS [--note TEXT]` | change the status: `imported converted extracted analyzed under_review rejected validated included` |
| `note PROJECT SOURCE TEXT` | append a researcher note |
| `tag PROJECT SOURCE [--add TAG]… [--remove TAG]…` | edit tags |

## Artifacts

Written to `<project>/artifacts/`.

| Command | Output |
| ------- | ------ |
| `matrix PROJECT [--csv] [--include-rejected]` | `literature-matrix.md` or `.csv` |
| `references PROJECT [--include-rejected]` | `references.md` |
| `report PROJECT [SOURCE…]` | `<source>-analysis.md` for each source (default: all) |
| `export PROJECT` | `catalog.json` |

## Accounts

| Command | Description |
| ------- | ----------- |
| `user add USERNAME [--name NAME] [--admin] [--password-stdin]` | create an account (prompts twice for the password unless `--password-stdin`) |
| `user list` | accounts, roles and project counts |
| `user passwd USERNAME [--password-stdin]` | set a password |
| `user remove USERNAME [--delete-data]` | delete an account; its workspace is kept unless `--delete-data` |
| `user adopt USERNAME` | move projects stored directly in the data root into the user's workspace |

## Background analysis

| Command | Description |
| ------- | ----------- |
| `worker [--threads N] [--poll S]` | run the analysis worker until SIGTERM/SIGINT; finishes running jobs before exiting |
| `worker --drain` | process every queued job, then exit (cron, one-off catch-up) |
| `worker --health [--max-age S]` | exit 0 if a worker on this host checked in within S seconds (default 60) |
| `jobs [--purge DAYS] [--recover SECONDS]` | queue counts and live workers; delete finished jobs older than DAYS; re-queue running jobs silent for SECONDS |

## Server and help

| Command | Description |
| ------- | ----------- |
| `web [--host H] [--port P] [--allow-signup] [--secure-cookies] [--debug]` | start the web interface ([Configuration](../deployment/configuration.md#acam-web-options)) |
| `formats` | list supported formats, source types, statuses and metadata fields |

## Scripting examples

```bash
# Import a folder for a user and analyze offline
acam --user maria import ai-se ~/papers/*.pdf --analyze --engine heuristic

# Non-interactive account creation (e.g. provisioning)
printf '%s\n' "$INITIAL_PASSWORD" | acam user add joao --name "João" --password-stdin

# Export every project of a user
for p in $(acam --user maria projects | awk '{print $1}'); do
  acam --user maria export "$p"
done

# Machine-readable source record
acam show ai-se source-001 --json | jq '.source.metadata.doi.value'
```
