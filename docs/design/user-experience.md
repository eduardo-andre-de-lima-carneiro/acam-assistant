# User Experience

ACAM Assistant has two interfaces over the same core: a **web interface** for
day-to-day research work and a **CLI** for scripting and administration.

## Web interface

### Page map

```text
/login ─┬─ /signup (first account, or when sign-up is enabled)
        ▼
/  "My projects"  ──────────────► /account  (password; admins: user list + create user)
  │  new project form
  ▼
/p/<project>  project dashboard
  │  sources table (filter, bulk analyze) · import panel · jobs · project definition · delete
  ├─► /p/<project>/matrix        literature matrix (+ .md / .csv)
  ├─► /p/<project>/references    ABNT reference list (+ copy, .md)
  └─► /p/<project>/s/<source>    source page
        ├─► …/markdown           canonical Markdown
        └─► …/original           original file
```

### Main workflow

1. **Set up:** the first visit creates the administrator account. Other users get
   accounts from the admin (Account page) or through sign-up if it is enabled.
2. **Create a project:** title, optional id, description and research questions.
3. **Define the review** (Project definition panel): research problem, questions,
   objectives, scope, inclusion and exclusion criteria.
4. **Import:** drag and drop files. You can optionally set the source type, tags,
   and "Analyze after import". Each file gets a message showing the conversion
   result (passed / passed with warnings / failed) and the word count.
5. **Analyze:** runs in the background. The sources table shows *analyzing*, and
   the page reloads when jobs finish. Several sources can be selected and
   analyzed at once.
6. **Review each source:**
   - the author's abstract and the generated summary side by side, clearly labelled;
   - a metadata table with a provenance badge per field
     (`extracted · 85%`, `llm · 80%`, `✓ confirmed`, `✓ researcher`, `missing`),
     Confirm / Save per field, and Confirm all;
   - the analysis, where each finding, limitation and gap shows its section, page
     and quote;
   - conversion checks, event history, links to the Markdown and the original.
7. **Decide:** set the status (under review, validated, rejected, included) with an
   optional note; add tags and notes.
8. **Produce artifacts:** matrix and reference pages, plus downloads.

### Interaction conventions

- **Colour meaning:** green = validated or passed; amber = machine-generated or
  needs attention; red = failed, rejected or missing. Labels always include text,
  so meaning never depends on colour alone.
- **Feedback:** every action shows a flash message; errors are shown on the
  page, never as a stack trace.
- **Destructive actions** (deleting a project) require typing the project id.
- **Responsive:** single column below 960 px; on phones the metadata table stacks
  and less important columns are hidden.
- **Light/dark mode** follows the operating system.
- **Offline:** no external fonts, scripts or CDNs.

## Command line

The CLI covers the same workflow plus administration. Typical session:

```bash
acam init "AI in SE" --id ai-se -q "How is AI applied to code review?"
acam import ai-se papers/*.pdf --tag llm --analyze
acam list ai-se
acam show ai-se source-001
acam confirm ai-se source-001 title authors
acam status ai-se source-001 validated --note "meets criteria"
acam matrix ai-se && acam references ai-se
```

In multi-user setups, add `--user <name>` to any command to work in that user's
workspace. The full command list is in the [CLI reference](../integration/cli-reference.md).

## Accessibility notes

- Form fields have labels; icon-only elements have `title` or `aria-label`.
- Status and provenance use text as well as colour.
- The spinner respects `prefers-reduced-motion`.
- Known gap: no formal WCAG audit has been done yet.
