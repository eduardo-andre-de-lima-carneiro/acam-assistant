# Data Exchange

How to get data out of ACAM Assistant and bring data in from other tools.

## Exports

| Export | How | Format | Best for |
| ------ | --- | ------ | -------- |
| `catalog.json` | `acam export P` / "Export JSON" | JSON: `{project, sources[]}`, each source with `analysis_result` | archiving, scripts, other tools |
| `literature-matrix.csv` | `acam matrix P --csv` / matrix page | CSV (UTF-8, header row) | spreadsheets (Excel, LibreOffice, Sheets) |
| `literature-matrix.md` | `acam matrix P` | Markdown table | dissertation drafts, Git |
| `references.md` | `acam references P` | ABNT references, one per paragraph | reference list of a manuscript |
| `<source>-analysis.md` | `acam report P [S]` | Markdown report | reading, sharing with an advisor |
| Raw files | the project folder | JSON + Markdown + originals | full backup or moving a project |

### `catalog.json`

```json
{
  "project": { "id": "ai-se", "title": "…", "research_questions": ["…"], … },
  "sources": [
    {
      "id": "source-001", "type": "journal_article", "status": "validated",
      "metadata": { "title": {"value": "…", "source": "extracted", "confidence": 0.85, "validated": true}, … },
      "bibliographic_reference": { "text": "…", "missing_fields": [] },
      "abstract": { "original_abstract": "…", "generated_summary": "…" },
      "analysis_result": { "engine": "llm", "main_findings": [ {"text": "…", "section": "…", "page": 3, "quote": "…"} ], … },
      …
    }
  ]
}
```

Field definitions: [Data model](../design/data-model.md). Schemas:
[`schemas/`](../../schemas). To read a plain value, use `field["value"]`, and
check `field["validated"]` before treating it as authoritative.

Example: every validated DOI in a project:

```bash
jq -r '.sources[] | select(.metadata.doi.validated) | .metadata.doi.value' catalog.json
```

### CSV columns

`id, author, year, type, title, objective, methodology, findings, gaps, status`.
List cells (findings, gaps) are joined with `; `.

### Reference text

References use Markdown bold (`**Journal**`) for the element ABNT emphasizes.
Paste them into a Markdown-aware editor, or convert with pandoc
(`pandoc references.md -o references.docx`) to keep the bold. Each line ends with
an HTML comment (`<!-- source-001: missing: publisher -->`) that most renderers
hide. Resolve the flagged items before submission.

## Moving a project

A project is a self-contained folder. To move it between installations or users:

```bash
cp -r <root>/users/alice/ai-se <other-root>/users/bob/ai-se
```

The project id is the folder name. Keep it matching `project.json`'s `id`.

## Importing from other tools

ACAM Assistant 0.1.0 imports **documents**, not reference-manager databases. Current
options:

| Source | How |
| ------ | --- |
| Zotero / Mendeley / EndNote | export the attached PDFs (for Zotero: right-click → "Show File", or use the storage folder) and import them. Correct metadata with `set`/Save, or confirm what was extracted |
| Web pages | save as HTML (`.html`) and import; `citation_*` meta tags are used |
| Word manuscripts, reports | import `.docx` directly |
| Scanned PDFs | run OCR first (e.g. `ocrmypdf`), then import |
| BibTeX / RIS | not supported yet; planned. Meanwhile set metadata with a script around `acam set` |

Example: apply metadata from a CSV (`source,field,value`) with the CLI:

```bash
while IFS=, read -r src field value; do
  acam set ai-se "$src" "$field" "$value"
done < corrections.csv
```

## Stability

- The formats of `project.json`, `sources.json`, `analysis/*.json` and
  `catalog.json` are described by the JSON Schemas and are the supported
  integration surface.
- Changes to these formats will be listed in release notes and in the decision
  records.
- The HTML pages and routes are not a stable API ([HTTP interface](http-interface.md)).
