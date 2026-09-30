# Academic Literature Review Assistant

> A structured research assistant for organizing, cataloging, analyzing, and synthesizing academic literature while reducing the manual effort involved in systematic literature reviews.

## Overview

The **Academic Literature Review Assistant** is a research-oriented project designed to reduce the time and cognitive effort required to perform literature reviews and related academic research activities.

Literature reviews are often labor-intensive because researchers must manually:

- Find relevant academic sources;
- Download and organize documents;
- Read and extract relevant information;
- Identify authors, publication dates, methodologies, and research objectives;
- Catalog references;
- Compare studies;
- Identify similarities, differences, and research gaps;
- Maintain consistent bibliographic information;
- Create summaries and analytical notes;
- Produce academic artifacts based on the collected evidence.

This project aims to support these activities through a structured and reproducible workflow.

The system should help **students, researchers, professors, and academic professionals** organize information from:

- Academic papers;
- Journal articles;
- Books;
- Theses and dissertations;
- Conference papers;
- Technical and scientific reports;
- Websites and online academic resources;
- Other relevant documentary sources.

The central principle of the project is:

> **Documents should be converted into a standardized Markdown representation before any analytical processing takes place.**

This creates a common intermediate format that can be processed consistently regardless of the original document type.

---

# Project Goals

## Primary Goal

Develop a system capable of supporting the literature review process by transforming heterogeneous academic sources into structured, searchable, analyzable, and reusable research information.

The system should reduce the amount of repetitive manual work required from researchers while preserving researcher control over interpretation and academic decisions.

## Secondary Goals

The system should help researchers:

1. Import academic documents;
2. Convert supported files into Markdown;
3. Preserve relevant document structure;
4. Extract bibliographic metadata;
5. Generate an abstract or structured summary;
6. Catalog academic sources;
7. Organize sources by research project;
8. Analyze individual documents;
9. Compare multiple sources;
10. Identify recurring concepts and themes;
11. Identify methodological approaches;
12. Identify research gaps;
13. Track relevant findings;
14. Maintain structured references;
15. Generate academic artifacts;
16. Reuse previously cataloged sources;
17. Maintain reproducibility of the literature review process.

---

# Core Principle

The system follows a document-processing pipeline:

````text
Original Source
      │
      ▼
Document Import
      │
      ▼
Format Conversion
      │
      ▼
Markdown Representation
      │
      ▼
Content Validation
      │
      ▼
Metadata Extraction
      │
      ▼
Content Analysis
      │
      ▼
Structured JSON Catalog
      │
      ├──────────────┐
      ▼              ▼
Individual Analysis  Cross-source Analysis
      │              │
      └───────┬──────┘
              ▼
       Research Synthesis
              │
              ▼
      Academic Artifacts

The **Markdown document is the canonical analytical representation** of the original source.

The original file should be preserved whenever possible, but analytical operations must operate on the generated Markdown representation.


# Main Features

## 1. Document Import

The system should allow researchers to provide documents from different sources and formats.

Potential supported formats include:

* PDF
* DOCX
* EPUB
* TXT
* HTML
* Markdown
* Other formats that can be reliably converted to Markdown

The system should preserve the original document whenever possible.

### Requirements

For each imported document, the system should:

* Generate a unique identifier;
* Record the original filename;
* Record the original file type;
* Record the import date;
* Store the original source;
* Convert the document to Markdown;
* Store the generated Markdown;
* Associate the document with a research project.

---

# 2. Mandatory Markdown Conversion

## Principle

All documents must be converted into Markdown **before analysis**.

The analytical engine must never depend directly on the original PDF, DOCX, EPUB, or other source format.

```text
PDF ──────┐
DOCX ─────┤
EPUB ─────┤
HTML ─────┤
TXT ──────┤
          ▼
    Markdown Converter
          │
          ▼
   Canonical Markdown
          │
          ▼
       Analysis
````

This design provides a standardized representation for downstream processing.

## Why Markdown?

Markdown provides several advantages:

- Human-readable representation;
- Easy version control;
- Simple text processing;
- Compatibility with LLM-based analysis;
- Easy transformation into HTML, PDF, DOCX, and other formats;
- Preservation of headings and logical structure;
- Reduced dependency on proprietary document formats;
- Easier debugging;
- Easier comparison between processing stages.

---

# 3. Document Structure Preservation

The conversion process should attempt to preserve the logical structure of the original document.

For example:

```markdown
# Article Title

## Abstract

...

## 1. Introduction

...

## 2. Theoretical Framework

...

## 3. Methodology

...

## 4. Results

...

## 5. Discussion

...

## 6. Conclusion

...

## References

...
```

When possible, the system should preserve:

- Title;
- Authors;
- Abstract;
- Keywords;
- Headings;
- Subheadings;
- Paragraphs;
- Tables;
- Figures descriptions;
- Citations;
- Footnotes;
- References;
- Appendices.

The system should not invent missing content.

If information cannot be reliably extracted, the field should be marked as unknown or requiring validation.

---

# 4. Academic Source Catalog

Each source should be cataloged in a structured JSON representation.

The JSON catalog is the **machine-readable research record** for each project.

The catalog should contain information about:

- Source identification;
- Bibliographic metadata;
- Source type;
- Authors;
- Publication information;
- Abstract;
- Keywords;
- Research objective;
- Methodology;
- Main findings;
- Contributions;
- Limitations;
- Relevant concepts;
- Research questions;
- References;
- Researcher's notes;
- Analysis status.

---

# Project-Based Organization

Each literature review should be treated as an independent research project.

Example:

```text
projects/
│
├── project-001/
│   ├── project.json
│   ├── sources.json
│   │
│   ├── original/
│   │   ├── paper-001.pdf
│   │   ├── paper-002.pdf
│   │   └── book-001.epub
│   │
│   ├── markdown/
│   │   ├── paper-001.md
│   │   ├── paper-002.md
│   │   └── book-001.md
│   │
│   ├── analysis/
│   │   ├── paper-001.json
│   │   ├── paper-002.json
│   │   └── book-001.json
│   │
│   └── artifacts/
│       ├── literature-review.md
│       ├── synthesis.md
│       └── references.md
│
└── project-002/
    └── ...
```

The exact directory structure may evolve as implementation decisions are made.

---

# Structured JSON Model

Each project should maintain a structured JSON file containing the relevant information extracted from its sources.

Example:

```json
{
  "project": {
    "id": "project-001",
    "title": "Artificial Intelligence in Software Engineering",
    "description": "Systematic literature review about the application of AI in software engineering.",
    "created_at": "2026-09-29",
    "updated_at": "2026-09-29"
  },
  "sources": [
    {
      "id": "source-001",
      "type": "journal_article",

      "original_file": {
        "name": "article.pdf",
        "format": "pdf"
      },

      "markdown_file": "markdown/source-001.md",

      "bibliographic_reference": "AUTHOR, First Name. Article title. Journal Name, v. 10, n. 2, p. 10-20, 2025.",

      "metadata": {
        "authors": [],
        "title": "",
        "publication_year": null,
        "publisher": "",
        "journal": "",
        "volume": "",
        "issue": "",
        "pages": "",
        "doi": "",
        "url": "",
        "access_date": ""
      },

      "abstract": "",

      "keywords": [],

      "research_objective": "",

      "research_questions": [],

      "methodology": "",

      "main_findings": [],

      "main_contributions": [],

      "limitations": [],

      "relevant_concepts": [],

      "research_gaps": [],

      "researcher_notes": "",

      "analysis": {
        "status": "pending",
        "analyzed_at": null,
        "confidence": null
      }
    }
  ]
}
```

---

# Source Analysis

The system should support structured analysis of each source.

The analysis should not be limited to generating a generic summary.

The goal is to extract information that can later support academic reasoning and synthesis.

## Minimum Analysis Fields

Each source should attempt to identify:

### Bibliographic Information

- Authors;
- Title;
- Publication year;
- Publisher;
- Journal;
- Volume;
- Issue;
- Pages;
- DOI;
- URL;
- Edition;
- Publication location;
- Access date when applicable.

### Content Information

- Abstract;
- Keywords;
- Research problem;
- Research objective;
- Research questions;
- Hypotheses, when applicable;
- Theoretical framework;
- Methodology;
- Population/sample, when applicable;
- Data collection method;
- Analysis method;
- Main findings;
- Conclusions;
- Limitations;
- Contributions;
- Future research recommendations.

### Literature Review Information

The system should also identify:

- Concepts relevant to the research project;
- Definitions proposed by the authors;
- Important theories;
- Frequently cited authors;
- Important references;
- Agreements with other studies;
- Contradictions with other studies;
- Evidence supporting specific claims;
- Research gaps;
- Potential relevance to the research project.

---

# Abstract Generation

Every imported source should have an abstract or structured summary associated with it.

Important distinction:

> A generated abstract is a machine-generated research aid and must not automatically be treated as the author's original abstract.

The system should preserve the original abstract separately when available.

Recommended structure:

```json
{
  "original_abstract": "",
  "generated_summary": "",
  "summary_type": "structured",
  "generated_at": "",
  "requires_validation": true
}
```

The system should never fabricate an abstract when the source cannot be reliably analyzed.

---

# Systematic Literature Review Support

The system should support the major activities involved in a systematic literature review.

Potential workflow:

```text
Research Question
       │
       ▼
Search Strategy
       │
       ▼
Source Collection
       │
       ▼
Deduplication
       │
       ▼
Screening
       │
       ▼
Eligibility Criteria
       │
       ▼
Included Sources
       │
       ▼
Markdown Conversion
       │
       ▼
Structured Extraction
       │
       ▼
Quality Assessment
       │
       ▼
Evidence Synthesis
       │
       ▼
Academic Artifact
```

The system should support researcher-defined criteria rather than automatically deciding whether a paper belongs in the review.

---

# Source Classification

Each source should have a controlled source type.

Recommended initial taxonomy:

```text
book
book_chapter
journal_article
conference_paper
thesis
dissertation
technical_report
website
online_article
preprint
other
```

Example:

```json
{
  "type": "journal_article"
}
```

---

# Bibliographic Reference Standards

The system should generate bibliographic references according to the source type.

The initial reference model is based on the following structures.

---

## 1. Books

### Structure

```text
LAST NAME, First Name. Book title: subtitle. Edition number (if not the first). City of publication: Publisher, Year.
```

### Example

```text
SILVA, J. A. Direito ambiental constitucional. 4. ed. São Paulo: Malheiros, 2002.
```

The book title and subtitle should be represented as required by the project's formatting rules.

---

## 2. Journal Articles

### Structure

```text
LAST NAME, First Name. Article title. Journal Name, City of publication, volume, issue, page range, month and year.
```

### Example

```text
SWELLER, J. Cognitive load during problem solving: A reinterpretation. Cognitive Science, v. 12, n. 2, p. 257-285, 1988.
```

---

## 3. Websites and Online Pages

### Structure

```text
LAST NAME, First Name. Title of the page/article. Website Name, Year of publication (if available). Disponível em: [URL]. Acesso em: date of access.
```

### Example

```text
INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA (IBGE). Cidades. 2021. Disponível em: ibge.gov.br. Acesso em: 15 out. 2026.
```

---

# Bibliographic Validation

Bibliographic information extracted automatically should be considered **candidate metadata** until validated.

The system should distinguish between:

```text
Extracted
      │
      ▼
Normalized
      │
      ▼
Validated
```

For example:

```json
{
  "title": {
    "value": "Example Article",
    "source": "extracted",
    "confidence": 0.97,
    "validated": false
  }
}
```

This prevents automatically generated metadata from being treated as authoritative academic information.

---

# Research Tags

Sources should support tags for organization and filtering.

Example:

```json
{
  "tags": [
    "artificial-intelligence",
    "software-engineering",
    "large-language-models",
    "devsecops"
  ]
}
```

Tags can be used to:

- Group related sources;
- Filter the literature;
- Identify research themes;
- Support synthesis;
- Generate thematic reports.

---

# Relationships Between Sources

The system should eventually support relationships between sources.

Examples:

```text
Source A
   │
   ├── cites ─────────► Source B
   │
   ├── contradicts ───► Source C
   │
   ├── extends ───────► Source D
   │
   └── replicates ────► Source E
```

Potential relationship types:

```text
cites
cited_by
supports
contradicts
extends
replicates
uses_methodology_from
builds_on
similar_to
```

These relationships can later support knowledge graphs and evidence mapping.

---

# Literature Synthesis

Once multiple sources have been analyzed, the system should support cross-source analysis.

Possible synthesis dimensions include:

## Thematic Analysis

Identify:

- Recurring themes;
- Emerging themes;
- Dominant concepts;
- Underexplored concepts.

## Methodological Analysis

Compare:

- Research methodologies;
- Data collection approaches;
- Sample characteristics;
- Analytical techniques;
- Experimental approaches.

## Findings Comparison

Identify:

- Consistent findings;
- Divergent findings;
- Contradictory results;
- Complementary findings.

## Research Gaps

Identify areas where:

- Evidence is limited;
- Findings are contradictory;
- Specific populations are underrepresented;
- Methodologies are insufficiently explored;
- Questions remain unanswered.

Important:

> Automatically identified gaps are hypotheses for researcher validation, not definitive statements about the literature.

---

# Researcher-in-the-Loop Principle

The system is intended to **assist research**, not replace academic judgment.

The researcher remains responsible for:

- Defining research questions;
- Establishing inclusion/exclusion criteria;
- Validating sources;
- Validating extracted metadata;
- Evaluating methodological quality;
- Interpreting evidence;
- Confirming research gaps;
- Approving generated academic artifacts.

The system should make its provenance visible whenever possible.

---

# Academic Artifact Templates

The project should provide reusable templates for academic work.

Potential templates include:

```text
literature-review
systematic-literature-review
research-proposal
research-question
research-objective
theoretical-framework
methodology
article-analysis
book-analysis
thesis-analysis
critical-review
literature-matrix
research-gap-analysis
bibliographic-reference
academic-summary
```

---

# Literature Review Matrix

A structured literature matrix can be generated from the catalog.

Example:

| ID   | Author   | Year | Source  | Objective | Methodology  | Main Findings | Research Gap |
| ---- | -------- | ---: | ------- | --------- | ------------ | ------------- | ------------ |
| S001 | Author A | 2024 | Article | ...       | Qualitative  | ...           | ...          |
| S002 | Author B | 2023 | Article | ...       | Quantitative | ...           | ...          |
| S003 | Author C | 2022 | Book    | ...       | Theoretical  | ...           | ...          |

The matrix should be generated from the structured JSON data rather than manually maintained whenever possible.

---

# Architecture

A modular architecture is recommended.

```text
┌──────────────────────────────┐
│          User Interface      │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│       Project Management     │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│      Document Ingestion      │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│     Format Conversion        │
│      → Markdown              │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│     Metadata Extraction      │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│       Content Analysis       │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│       JSON Repository        │
└──────────────┬───────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
┌──────────────┐  ┌───────────────┐
│ Source       │  │ Cross-source  │
│ Analysis     │  │ Synthesis     │
└──────┬───────┘  └───────┬───────┘
       │                  │
       └────────┬─────────┘
                ▼
       ┌──────────────────┐
       │ Academic Artifact│
       │ Generation       │
       └──────────────────┘
```

---

# Repository Structure

```text
academic-literature-review/
│
├── README.md
│
├── docs/
│   ├── architecture.md
│   ├── data-model.md
│   ├── workflow.md
│   ├── research-methodology.md
│   └── decisions/
│
├── projects/
│   └── <project-id>/
│       │
│       ├── project.json
│       ├── sources.json
│       │
│       ├── original/
│       │
│       ├── markdown/
│       │
│       ├── analysis/
│       │
│       ├── artifacts/
│       │
│       └── references/
│
├── templates/
│   ├── source-analysis.json
│   ├── book-analysis.md
│   ├── article-analysis.md
│   ├── thesis-analysis.md
│   ├── literature-matrix.md
│   ├── systematic-review.md
│   └── bibliographic-reference.md
│
├── schemas/
│   ├── project.schema.json
│   ├── source.schema.json
│   └── analysis.schema.json
│
├── src/
│   ├── ingestion/
│   ├── conversion/
│   ├── extraction/
│   ├── analysis/
│   ├── synthesis/
│   ├── references/
│   └── artifacts/
│
├── tests/
│   ├── conversion/
│   ├── extraction/
│   ├── analysis/
│   └── references/
│
└── scripts/
    ├── import-source
    ├── convert-to-markdown
    ├── analyze-source
    └── generate-artifact
```

---

# End-to-End Workflow

## Step 1 — Create a Research Project

The researcher defines:

- Project title;
- Research problem;
- Research questions;
- Objectives;
- Scope;
- Inclusion criteria;
- Exclusion criteria.

Example:

```json
{
  "id": "project-001",
  "title": "AI Applications in Software Engineering",
  "research_questions": ["How is AI being applied to software engineering?"],
  "inclusion_criteria": [],
  "exclusion_criteria": []
}
```

---

## Step 2 — Import Sources

The researcher adds:

```text
paper.pdf
book.epub
article.docx
website.html
```

The system registers each source.

---

## Step 3 — Convert Sources

Each source is converted into Markdown.

```text
paper.pdf
    ↓
paper.md
```

The Markdown file becomes the canonical analysis input.

---

## Step 4 — Validate Conversion

The system should verify:

- File was successfully converted;
- Text is not empty;
- Headings are present when expected;
- Major sections were preserved;
- Encoding is valid;
- No obvious extraction failure occurred.

---

## Step 5 — Extract Metadata

The system identifies candidate metadata:

```text
Author
Title
Year
Publisher
Journal
DOI
Pages
URL
Abstract
Keywords
```

---

## Step 6 — Analyze Content

The system analyzes the Markdown representation and generates structured information.

```text
Markdown
   │
   ├── Metadata
   ├── Abstract
   ├── Objective
   ├── Research Questions
   ├── Methodology
   ├── Findings
   ├── Contributions
   ├── Limitations
   └── Research Gaps
```

---

## Step 7 — Store Results

The extracted information is persisted in the project's structured JSON catalog.

---

## Step 8 — Researcher Validation

The researcher reviews the extracted information.

Possible statuses:

```text
pending
reviewing
validated
rejected
needs_revision
```

---

## Step 9 — Cross-Source Analysis

Once multiple sources are validated, the system can compare them.

---

## Step 10 — Generate Academic Artifacts

The researcher can generate:

- Literature matrices;
- Summaries;
- Literature review sections;
- Research gap reports;
- Bibliographic references;
- Theoretical framework drafts;
- Methodological comparison;
- Other academic artifacts.

Generated artifacts should clearly distinguish:

```text
Source evidence
Generated synthesis
Researcher interpretation
```

---

# AI Usage Principles

If AI or Large Language Models are used, the system should follow several principles.

## 1. Evidence First

AI-generated conclusions should be grounded in the Markdown source.

```text
Source
  ↓
Markdown
  ↓
Evidence
  ↓
Analysis
```

The model should not rely on unsupported external knowledge when analyzing a specific source.

---

## 2. No Fabrication

The system must never invent:

- Authors;
- Titles;
- Citations;
- Publication dates;
- DOI numbers;
- Findings;
- Research methods;
- Statistics;
- Quotes.

If information is unavailable:

```text
unknown
```

or:

```text
requires_validation
```

should be used.

---

## 3. Traceability

Where technically feasible, extracted claims should maintain a relationship with the source location.

Example:

```json
{
  "finding": "The study identified a reduction in processing time.",
  "evidence": {
    "source_id": "source-001",
    "section": "Results",
    "page": 12
  }
}
```

This makes the system more useful for academic verification.

---

# Data Integrity

Academic research requires reproducibility.

The system should therefore preserve:

- Original documents;
- Converted Markdown;
- Extracted metadata;
- Analysis results;
- Model/version information;
- Processing date;
- Researcher validation;
- Generated artifacts.

A recommended record is:

```json
{
  "processing": {
    "processed_at": "2026-09-29T20:00:00Z",
    "processor_version": "0.1.0",
    "analysis_model": "model-name",
    "prompt_version": "v1",
    "status": "validated"
  }
}
```

---

# Quality Control

Each processing stage should be independently testable.

## Conversion Tests

Verify:

- PDF → Markdown;
- DOCX → Markdown;
- EPUB → Markdown;
- HTML → Markdown.

## Extraction Tests

Verify:

- Author extraction;
- Title extraction;
- Publication date;
- DOI;
- Abstract;
- Keywords.

## Analysis Tests

Verify:

- Objective extraction;
- Methodology extraction;
- Findings;
- Limitations;
- Research gaps.

## Reference Tests

Verify:

- Book reference format;
- Journal article format;
- Website reference format.

---

# Future Features

The architecture should allow future expansion.

Potential features include:

## Semantic Search

Allow researchers to ask:

```text
Which papers discuss context engineering?
```

or:

```text
Which studies identified limitations related to dataset size?
```

---

## Research Knowledge Graph

Represent relationships between:

```text
Authors
Papers
Concepts
Methods
Findings
Research Questions
References
```

---

## Citation Network

Visualize:

```text
Paper A
 ├── cites → Paper B
 ├── cites → Paper C
 └── extends → Paper D
```

---

## Duplicate Detection

Identify potentially duplicated documents using:

- DOI;
- Title;
- Authors;
- Publication year;
- Similarity analysis.

---

## Evidence Matrix

Generate structured evidence tables for systematic reviews.

---

## PRISMA Support

The project may eventually support structured tracking of:

- Identification;
- Screening;
- Eligibility;
- Inclusion.

The researcher should remain responsible for the final methodological decisions and reporting.

---

# Source Status Lifecycle

```text
IMPORTED
    │
    ▼
CONVERTED
    │
    ▼
EXTRACTED
    │
    ▼
ANALYZED
    │
    ▼
UNDER_REVIEW
    │
    ├──► REJECTED
    │
    ▼
VALIDATED
    │
    ▼
INCLUDED
```

---

# Design Principles

The project should follow these principles.

### 1. Reproducibility

The same source and processing configuration should produce traceable results.

### 2. Transparency

Researchers should be able to understand how information was generated.

### 3. Human Validation

AI-generated information should remain subject to researcher verification.

### 4. Source Traceability

Important claims should be traceable to their original source.

### 5. Format Independence

Analysis should operate on Markdown rather than proprietary document formats.

### 6. Structured Data

Research information should be stored in machine-readable structures.

### 7. Modularity

Document conversion, extraction, analysis, synthesis, and artifact generation should remain independent components.

### 8. Extensibility

New source types, analysis models, academic standards, and artifact templates should be easy to add.

---

# Initial MVP Scope

The first version should focus on a small but reliable workflow.

## MVP

### Input

- PDF
- DOCX
- Markdown
- TXT

### Processing

```text
Import
  ↓
Convert
  ↓
Validate Markdown
  ↓
Extract Metadata
  ↓
Generate Summary
  ↓
Analyze Source
  ↓
Store JSON
```

### Output

- Markdown representation;
- Structured JSON;
- Bibliographic reference;
- Source summary;
- Source analysis.

---

# Development Roadmap

## Phase 1 — Foundation

- [ ] Define project structure
- [ ] Define JSON schemas
- [ ] Implement project creation
- [ ] Implement source registration
- [ ] Implement document storage

## Phase 2 — Conversion

- [ ] PDF → Markdown
- [ ] DOCX → Markdown
- [ ] TXT → Markdown
- [ ] HTML → Markdown
- [ ] Add conversion validation

## Phase 3 — Metadata

- [ ] Extract title
- [ ] Extract authors
- [ ] Extract publication date
- [ ] Extract abstract
- [ ] Extract keywords
- [ ] Extract DOI
- [ ] Generate bibliographic references

## Phase 4 — Analysis

- [ ] Source summarization
- [ ] Research objective extraction
- [ ] Methodology extraction
- [ ] Findings extraction
- [ ] Limitations extraction
- [ ] Research gap identification
- [ ] Structured analysis JSON

## Phase 5 — Research Synthesis

- [ ] Literature matrix
- [ ] Cross-source comparison
- [ ] Theme identification
- [ ] Methodology comparison
- [ ] Evidence mapping
- [ ] Research gap analysis

## Phase 6 — Academic Artifacts

- [ ] Literature review template
- [ ] Research proposal template
- [ ] Theoretical framework template
- [ ] Methodology template
- [ ] Academic summary template
- [ ] Reference generation

## Phase 7 — Advanced Research Features

- [ ] Semantic search
- [ ] Citation graph
- [ ] Knowledge graph
- [ ] Duplicate detection
- [ ] Evidence traceability
- [ ] PRISMA workflow support

---

# Non-Functional Requirements

The system should prioritize:

| Requirement     | Description                                                  |
| --------------- | ------------------------------------------------------------ |
| Reproducibility | Processing should be repeatable and traceable                |
| Reliability     | Extraction should fail safely rather than invent information |
| Traceability    | Claims should be linked to their sources                     |
| Maintainability | Components should remain modular                             |
| Extensibility   | New source formats should be easy to add                     |
| Portability     | Research projects should be exportable                       |
| Versionability  | Markdown and JSON should work well with Git                  |
| Transparency    | AI-generated content should be identifiable                  |
| Validation      | Researchers must be able to review extracted information     |

---

# Important Limitations

This system is an **academic research support tool**, not an autonomous researcher.

It should not automatically determine:

- Whether a study is scientifically valid;
- Whether evidence is sufficient;
- Whether a research gap definitively exists;
- Whether a source should be included in a systematic review;
- Whether a methodological decision is academically appropriate.

Those decisions require researcher judgment.

AI-generated analysis should therefore be treated as:

> **structured research assistance that requires verification.**

---

# Research Reproducibility

Each project should ideally be reproducible from:

```text
Original Documents
       +
Processing Configuration
       +
Prompt/Analysis Version
       +
Software Version
       +
Structured JSON
       =
Reproducible Research Dataset
```

This is particularly important when the system uses generative AI because model behavior may change over time.

---

# Example Research Project

```text
Project:
Systematic Literature Review on AI-Assisted Software Engineering

Research Question:
How are artificial intelligence techniques being applied
to improve software engineering activities?

Sources:

S001
├── Type: Journal Article
├── Author: Author A
├── Year: 2024
├── Methodology: Systematic Review
└── Status: Validated

S002
├── Type: Conference Paper
├── Author: Author B
├── Year: 2023
├── Methodology: Experimental
└── Status: Validated

S003
├── Type: Book
├── Author: Author C
├── Year: 2022
├── Type: Theoretical
└── Status: Validated
```

The system can then generate:

```text
                    Research Question
                           │
                           ▼
                 ┌───────────────────┐
                 │   Source Catalog   │
                 └─────────┬─────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
        S001 Article   S002 Paper     S003 Book
            │              │              │
            └──────────────┼──────────────┘
                           ▼
                  Cross-Source Analysis
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
          Themes       Methods        Findings
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                    Research Gaps
                           │
                           ▼
                  Academic Synthesis
```

---

# Researcher + AI Collaboration Model

The intended relationship is:

```text
                 RESEARCHER
                     │
          Defines questions
                     │
                     ▼
               AI ASSISTANT
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼             ▼
    Organize      Extract       Analyze
       │             │             │
       └─────────────┼─────────────┘
                     ▼
                Researcher
                 validates
                     │
                     ▼
                 Synthesis
                     │
                     ▼
              Academic Artifact
```

The system should therefore optimize for **researcher productivity without obscuring researcher responsibility**.

---

# Guiding Principle

The project is based on a simple idea:

> **The goal is not to automate researcher's thinking. The goal is to remove repetitive work so researchers can spend more time thinking.**

Document conversion, metadata extraction, cataloging, organization, comparison, and artifact preparation are activities that can be partially automated.

Critical interpretation, methodological judgment, and scientific reasoning should remain under researcher control.

---

# License

MIT License.

---

# Project Status

**Status:** Initial design / specification

**Version:** 0.1.0

**Primary purpose:** Academic literature organization, analysis, and systematic literature review support.

**Canonical analytical format:** Markdown

**Structured research format:** JSON

**Primary users:** Students, researchers, professors, and academic professionals.

---

# Next Step

The next implementation step should be to transform this specification into a formal technical design containing:

1. `project.schema.json`
2. `source.schema.json`
3. `analysis.schema.json`
4. Markdown document specification
5. Processing pipeline specification
6. Prompt templates for each analysis stage
7. Source-type-specific extraction rules
8. Academic reference-generation rules
9. Validation workflow
10. Initial MVP architecture

These specifications should be defined **before implementing the AI analysis layer**, so that the system's data model and provenance requirements remain independent from any particular AI model.

````

### Recommended architectural decision

One point I would make explicit before implementation is the distinction between **three representations of the same source**:

```text
Original Artifact
      │
      │ immutable
      ▼
Markdown Artifact
      │
      │ canonical analytical representation
      ▼
Structured Research Data
      │
      │ machine-readable
      ▼
Academic Artifacts
````

This is important because it prevents a common problem in AI-assisted research systems: the model's interpretation gradually becoming the "source of truth." The **original document remains authoritative**, Markdown becomes the canonical processing layer, and JSON stores **extracted/derived information with provenance and validation status**.
