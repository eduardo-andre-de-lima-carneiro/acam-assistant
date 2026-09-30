# Local Installation

For one researcher on their own computer (macOS, Linux or Windows with Python).

## Requirements

- Python **3.10 or newer** (`python3 --version`)
- About 100 MB of disk for the environment, plus space for your sources
- Optional: an Anthropic API key for the LLM analysis engine

## Install

```bash
cd acam-s2
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .                   # add ".[dev]" to also install the test tools
acam --version
```

## Run the web interface

```bash
acam web                           # http://127.0.0.1:8000
```

1. The first visit asks you to create the administrator account (your account).
2. Create a project and import files.

Data is stored in `./projects` (relative to where you ran the command). To keep
it elsewhere:

```bash
export ACAM_HOME="$HOME/Research/acam-data"
acam web
# or: acam --workspace ~/Research/acam-data web --port 8080
```

The server only listens on `127.0.0.1`, so other computers cannot reach it.
Stop it with `Ctrl+C`.

## Enable Claude analysis (optional)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
acam web
```

The header shows `engine: llm` when a key is detected. Without a key, analysis
uses the offline heuristic engine. See [Claude API integration](../integration/claude-api.md)
for costs and privacy.

## Use only the command line

Without `--user`, CLI commands work directly in the data root, which is a
single-user workspace separate from the web accounts:

```bash
acam init "My review" --id my-review
acam import my-review ~/Downloads/*.pdf --analyze
```

To work on the same projects you see in the web interface, add `--user <your-username>`:

```bash
acam --user eduardo projects
```

To move CLI-created projects into your web account:

```bash
acam user adopt eduardo
```

## Back up

Copy the data root folder (`./projects` or `$ACAM_HOME`) while the server is
stopped. Keep `users.json` and `.secret_key` out of any public repository.

## Uninstall

Delete the `.venv` folder. Your data stays in the data root until you delete it.

## Troubleshooting

| Symptom | Fix |
| ------- | --- |
| `acam: command not found` | activate the environment: `source .venv/bin/activate` |
| `Address already in use` | `acam web --port 8080` |
| "Invalid or missing CSRF token" | the page was open before a server key change; reload it |
| PDF import: "no extractable text (OCR)" | the PDF is scanned; run OCR first (e.g. `ocrmypdf in.pdf out.pdf`) and import the result |
| Analysis failed: authentication error | check `ANTHROPIC_API_KEY`, or choose the heuristic engine |
| I forgot my password | `acam user passwd <username>` |
