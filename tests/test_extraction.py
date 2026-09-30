from acam import conversion
from acam.extraction.metadata import extract_metadata, guess_source_type
from acam.models import value_of


def _meta(path):
    r = conversion.convert(path)
    return extract_metadata(r.markdown, r.embedded_metadata)


def test_extracts_bibliographic_metadata(sample_md):
    meta, abstract = _meta(sample_md)
    assert value_of(meta, "title") == ("Large Language Models as Code Review Assistants: "
                                       "An Exploratory Case Study")
    assert value_of(meta, "authors") == ["Maria Fernanda Souza", "John Peter Miller"]
    assert value_of(meta, "publication_year") == 2025
    assert value_of(meta, "doi") == "10.1234/jser.2025.0042"
    assert value_of(meta, "journal") == "Journal of Software Engineering Research"
    assert (value_of(meta, "volume"), value_of(meta, "issue"), value_of(meta, "pages")) == ("14", "2", "45-67")
    assert value_of(meta, "keywords") == ["large language models", "code review",
                                          "software engineering", "case study"]
    assert abstract["original_abstract"].startswith("This study investigates")
    assert "Keywords" not in abstract["original_abstract"]


def test_extracted_values_are_candidates_not_validated(sample_md):
    meta, _ = _meta(sample_md)
    for entry in meta.values():
        assert entry["validated"] is False
        if entry["value"] not in (None, []):
            assert entry["source"] == "extracted"
            assert 0 < entry["confidence"] <= 1


def test_never_invents_missing_metadata(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("some lowercase notes without any bibliographic information at all\n" * 5,
                 encoding="utf-8")
    meta, abstract = _meta(f)
    for name in ("authors", "publication_year", "doi", "journal", "keywords", "publisher"):
        assert value_of(meta, name) is None, name
    assert abstract["original_abstract"] is None


def test_pdf_and_docx_metadata_match(sample_pdf, sample_docx):
    for path in (sample_pdf, sample_docx):
        meta, _ = _meta(path)
        assert value_of(meta, "title").startswith("Large Language Models")
        assert value_of(meta, "authors") == ["Maria Fernanda Souza", "John Peter Miller"]
        assert value_of(meta, "doi") == "10.1234/jser.2025.0042"


def test_source_type_guess_is_conservative(sample_md):
    md = sample_md.read_text()
    assert guess_source_type(md, "md")[0] == "journal_article"
    assert guess_source_type("plain notes", "txt") == ("other", 0.0)
    assert guess_source_type("<p>x</p>", "html")[0] == "website"
