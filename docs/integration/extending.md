# Extending ACAM Assistant

Recipes for the most common extensions. Every change should come with tests (see
[Technology stack → Testing](../technology/stack.md#testing-strategy)) and an update
to the document that owns the topic.

## Add an input format

Example: EPUB.

1. Create `src/acam/conversion/epub_converter.py` with
   `convert(path: Path) -> ConversionResult`. Return Markdown that uses `#`
   headings, and put any embedded title/author into `embedded_metadata`. For text
   without structure, reuse `conversion.structure.structure_text`.
2. Register the extension in `_converters()` in `conversion/__init__.py`.
3. Add the extension to the upload `accept` list. This happens automatically,
   because the template uses `supported_formats()`.
4. Tests: build a fixture at test time in `tests/conftest.py` and add it to the
   parametrized cases in `test_conversion.py` and `test_pipeline.py`.
5. Docs: the format table in [Processing pipeline](../design/processing-pipeline.md#2-convert).

Rules: never invent headings or a title; raise or let exceptions propagate
(they become `ConversionError`); add warnings for partial extraction.

## Add an analysis engine

Example: a local model.

1. Create `src/acam/analysis/<name>.py` with
   `analyze(markdown, record, project_info, **kwargs) -> dict` returning the shape
   described in [Data model → Analysis](../design/data-model.md#analysis-analysissource-idjson):
   include `source_id`, `engine`, `processing` (with `processed_at`,
   `processor_version`, `analysis_model`, `prompt_version`), and
   `requires_validation: true`.
2. Add a branch for it in `analysis.analyze()` and the engine choices in `cli.py`
   and `web/templates/_macros.html` (`engine_select`).
3. Add the engine name to the `engine` enum in `schemas/analysis.schema.json`.
4. Test it against the schema (see `test_heuristic_analysis`).

## Add a metadata field

1. Add it to `METADATA_FIELDS` (and `LIST_FIELDS` if it holds a list) in `models.py`.
2. Add it to `schemas/source.schema.json` (`metadata.properties` and `required`).
3. If the LLM should extract it, add it to `metadata_candidates` in
   `analysis/schema.py` and bump `PROMPT_VERSION`.
4. Use it in `references/abnt.py` if it belongs in references.
5. The web metadata table and CLI `set` pick it up automatically.

## Add a reference style

Example: APA.

1. Create `src/acam/references/apa.py` with
   `build_reference(record) -> Reference` (reuse the `Reference` dataclass;
   set `style="apa"` and report `missing` fields).
2. Choose the style per project: add a `reference_style` key to `project.json`
   (and its schema), and use it in `pipeline.refresh_reference`.
3. Add tests with published examples of the style, as `test_references.py` does
   for ABNT.

## Add an artifact

Example: a research-gap report.

1. Add a function to `src/acam/artifacts/__init__.py` that **reads only** the
   catalog and analyses and returns text. Start it with `_header(...)` so the
   "machine-generated" notice is included.
2. CLI: add a subcommand in `cli.py` that writes it with `_write_artifact`.
3. Web: add a name to `DOWNLOADS` in `web/__init__.py` (and optionally a page and
   a button in `project.html`).
4. Keep source evidence, generated synthesis and researcher interpretation
   clearly separated in the output (a specification requirement).

## Add a web page or action

- Put state changes in a `pipeline` function (under `project.lock()`, with a
  history event), not in the route. Keep the locked part to in-memory
  read-modify-write; do slow work before taking the lock and re-read the record
  inside it.
- Long-running work belongs in the job queue (`JobQueue.submit`) and the worker,
  not in the request.
- Resolve projects with `project_or_404(pid)`, which is scoped to the logged-in
  user. Never build paths from request data.
- Every `<form method="post">` needs
  `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`.
- Add the route to [HTTP interface](http-interface.md) and a test to
  `tests/test_web.py`. For anything that touches data, also add a cross-user
  test to `tests/test_tenancy.py`.

## Add an account feature

Keep `users.json` handling inside `accounts.py`. Never return `password_hash`
from public functions (use `_public`). Validate usernames with `check_username`.
Document it in [Security](../security/security.md).
