# Processing Pipeline

```text
Import ─► Convert ─► Validate ─► Extract metadata ─► Build reference ─► (Analyze ─► Merge) ─► Store
  │          │           │              │                                   │
original/  markdown/   conversion     metadata{…}                      analysis/<id>.json
```

Orchestration lives in `src/acam/pipeline.py`. Import runs synchronously.
Analysis runs synchronously in the CLI (`analyze`), or through the durable job
queue and a worker (web interface, `analyze --queue`). Everything is safe to run
concurrently from several threads and processes
([ADR-010](../architecture/decisions/ADR-010-multi-process-concurrency.md)).

## 1. Import

`pipeline.import_source(project, file, source_type=None, tags=None, allow_duplicate=False)`

1. Check that the extension is supported (`pdf`, `docx`, `txt`, `md`/`markdown`, `html`/`htm`)
   and compute the file's SHA-256 (no lock).
2. **Under the project lock** (milliseconds):
   - if another source has the same hash, raise `DuplicateSourceError`, unless
     `allow_duplicate` is set;
   - allocate the next `source-NNN` (counting both records and files in `original/`);
   - create an empty `original/<id>.<ext>`;
   - save a placeholder record with status `imported`.
3. Copy the file, then convert, validate and extract (next steps), **without the lock**.
4. **Under the lock again:** re-read the record, apply the results, rebuild the
   reference, and save.

Concurrent imports into one project therefore get distinct ids, duplicates are
caught even when uploaded at the same moment, and a long conversion never blocks
other users. If the process dies during step 3, the source stays `imported`, and
its id is never reused.

## 2. Convert

`conversion.convert(path)` picks a converter by extension. Every converter
returns Markdown plus any metadata embedded in the file, which is used only as
candidate metadata.

| Format | Converter | Structure preserved | Embedded metadata |
| ------ | --------- | ------------------- | ----------------- |
| PDF | `pypdf`, page by page | `<!-- page: N -->` before each page; recognized section names become headings; paragraphs rebuilt; hyphenated line breaks joined | document info Title, Author |
| DOCX | `python-docx`, body order | `Title` style → `#`; `Heading N` → `#` × (N+1); lists; tables → Markdown tables | core properties title, author |
| HTML | stdlib `html.parser` | `h1`–`h6`, paragraphs, lists, links, bold/italic, tables; drops `script`, `style`, `nav`, `header`, `footer`, `aside`, `form`, `svg`, `noscript` | `citation_title`/`og:title`/`<title>`, `citation_author`/`author`, `citation_doi` |
| TXT | built-in | same heading and paragraph heuristics as PDF; UTF-8, with Latin-1 fallback and a warning | — |
| Markdown | pass-through | as written | — |

Heading detection for unstructured text (PDF, TXT, and DOCX paragraphs without
heading styles) only promotes **known academic section names** in English,
Portuguese and Spanish (Abstract/Resumo, Introduction/Introdução, Methodology/
Metodologia, Results/Resultados, Conclusion/Conclusão, References/Referências…),
optionally numbered (`2.`, `2.1`, `IV.`). It never invents a title or headings.
In the front matter (the lines before the first recognized heading, capped at 25),
each line stays on its own so the title, authors and journal line don't merge.

Output is normalized: `\n` line endings, trailing spaces removed, at most one
blank line in a row.

Scanned PDFs (pages without extractable text) produce a warning recommending OCR.

## 3. Validate

`validation.validate_markdown(markdown, page_count)`

| Check | Severity | Passes when |
| ----- | -------- | ----------- |
| `not_empty` | error | any text was extracted |
| `minimum_length` | error | ≥ 200 characters |
| `encoding` | error | < 1% replacement (`�`) or control characters |
| `headings_present` | warning | at least one heading |
| `academic_sections` | warning | ≥ 2 of abstract, introduction, method, results, conclusion, references |
| `text_density` | warning | PDFs: ≥ 50 words per page |

If any **error** fails, the conversion status is `failed`, the source stays
`converted`, and metadata extraction and analysis are skipped. The files are
kept so the researcher can inspect them.

## 4. Extract metadata

`extraction.metadata.extract_metadata(markdown, embedded)` is rule-based. Each
value gets a confidence score:

| Field | Rule | Confidence |
| ----- | ---- | ---------- |
| title | first `#` heading | 0.85 |
| | first substantive line (0.8 if it matches embedded title) | 0.5 / 0.8 |
| | embedded title only | 0.6 |
| authors | embedded author property | 0.75 (institutions kept whole: 0.6) |
| | name list on the lines after the title | 0.45 |
| doi | `10.xxxx/…` anywhere, or embedded | 0.95 |
| publication_year | first 1950–2049 year in the first 80 lines | 0.5 |
| keywords | `Keywords:` / `Palavras-chave:` line | 0.85 |
| journal, volume | `Journal Name, v. 14` pattern in front matter | 0.5, 0.6 |
| issue, pages | `n. 2`, `p. 45-67` in front matter | 0.5 |
| url | first non-DOI URL in front matter | 0.5 |
| original abstract | body of the Abstract/Resumo section (keywords line removed) | — |

The source type is guessed conservatively from keywords (`dissertation`,
`thesis`, `proceedings`, `arXiv`, `journal`/`vol.`, `ISBN`; HTML → `website`),
with confidence ≤ 0.5. A type given at import is recorded as the researcher's.

## 5. Build the reference

`references.abnt.build_reference(record)` uses the specification's ABNT-based structures:

| Types | Pattern |
| ----- | ------- |
| book, thesis, dissertation, technical_report | `AUTHOR. **Title**: subtitle. N. ed. Place: Publisher, Year.` |
| journal_article, conference_paper, preprint, book_chapter | `AUTHOR. Title. **Journal**, Place, v. X, n. Y, p. a-b, Year. DOI: …` |
| website, online_article, other | `AUTHOR. Title. Site, Year. Disponível em: URL. Acesso em: D mmm. YYYY.` |

- Authors: `SURNAME, I. I.`, joined with `; `. More than three authors are shown as
  first author + `et al.`. Name suffixes (Filho, Júnior, Neto…) and particles
  (da, de, dos…) are handled. Institutions (`Instituto…`, `University…`,
  acronyms in parentheses, all-caps) are written in full capitals.
- Missing data uses `[s.l.]`, `[s.n.]`, `[s.d.]` and is listed in `missing_fields`.
- The access date defaults to the import date.
- `requires_validation` stays true until both title and authors are validated.

The reference is rebuilt after every metadata change.

## 6. Analyze

`pipeline.analyze_source(project, source_id, engine)` accepts engine `auto`,
`llm` or `heuristic`. `auto` picks `llm` when Anthropic credentials are
configured, otherwise `heuristic`.

### LLM engine (`analysis/llm.py`)

Sends the canonical Markdown and the project title and research questions to
Claude in one request, with a JSON-schema output format. Full details:
[Claude API integration](../integration/claude-api.md).

### Heuristic engine (`analysis/heuristic.py`)

Offline and extractive: it selects **verbatim sentences**, never paraphrases.

- Splits each section into sentences and matches cue patterns per field
  (objective: "this study aims/investigates…"; findings: "found, show, indicate,
  reduced…"; limitations; contributions; future work; gaps: "few studies, little
  is known, lack of…"; theories).
- Looks in the most likely sections first (for example findings in
  Results/Discussion/Conclusion), and never in References.
- Detects the methodology approach from keywords in the methods section
  (systematic review, mixed methods, experiment, case study, survey, design
  science, qualitative, quantitative).
- Research questions: sentences ending in `?` or starting with `RQn`.
- Summary: objective + first method sentence + first finding + first conclusion
  paragraph (`summary_type: "extractive"`).
- Confidence is fixed at 0.3, with a warning saying every field needs checking.

### Merge and store

The analysis is written to `analysis/<id>.json`. The source record is then
**re-read under the write lock**, so edits the researcher made while the
analysis ran are kept. After that:

- metadata candidates are merged ([rule](data-model.md#merge-rule-for-llm-metadata));
- `abstract.generated_summary` is updated (the original abstract is never touched);
- the status moves to `analyzed` only if it was still automatic;
- the reference is rebuilt and an `analyzed` history event is added.

If the analysis fails (refusal, truncation, network error), nothing is stored and
the error is reported: CLI exit code 1, or a failed job in the web interface.

## 7. Researcher operations

| Operation | Function | Web | CLI |
| --------- | -------- | --- | --- |
| Confirm field(s) | `confirm_metadata` | Confirm / Confirm all | `confirm` |
| Set field / type | `set_metadata` | Save | `set` |
| Change status | `set_status` | Review status | `status` |
| Add note | `add_note` | Researcher notes | `note` |
| Tags | `set_tags` | Tags | `tag` |

All of them are serialized by the catalog write lock and recorded in `history`.

## 8. Artifacts

`artifacts/__init__.py` builds the matrix, reference list, reports and export
from the JSON only. Every generated Markdown file starts with a notice giving the
version and time and saying machine-extracted content needs validation.
