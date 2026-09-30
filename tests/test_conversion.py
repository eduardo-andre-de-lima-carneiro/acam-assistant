import pytest

from acam import conversion
from acam.markdown_doc import parse_sections
from acam.validation import validate_markdown


@pytest.mark.parametrize("fixture", ["sample_md", "sample_txt", "sample_pdf", "sample_docx"])
def test_every_format_converts_to_structured_markdown(fixture, request):
    result = conversion.convert(request.getfixturevalue(fixture))
    keys = [s.key for s in parse_sections(result.markdown) if s.level]
    for expected in ("abstract", "introduction", "methodology", "results", "conclusion", "references"):
        assert expected in keys, f"{expected} missing from {fixture}: {keys}"
    report = validate_markdown(result.markdown, result.page_count)
    assert report["passed"]
    assert report["status"] == "passed"


def test_pdf_keeps_page_markers_and_embedded_metadata(sample_pdf):
    result = conversion.convert(sample_pdf)
    assert result.page_count == 2
    assert "<!-- page: 1 -->" in result.markdown and "<!-- page: 2 -->" in result.markdown
    assert result.embedded_metadata["title"].startswith("Large Language Models")
    # Page numbers flow through to sections for traceability.
    results = next(s for s in parse_sections(result.markdown) if s.key == "results")
    assert results.page in (1, 2)


def test_docx_preserves_title_headings_and_tables(sample_docx):
    md = conversion.convert(sample_docx).markdown
    assert md.startswith("# Large Language Models as Code Review Assistants")
    assert "## 3. Methodology" in md
    assert "| Metric | Value |" in md and "| Review time reduction | 23% |" in md


def test_html_drops_boilerplate_and_keeps_structure(sample_html):
    result = conversion.convert(sample_html)
    md = result.markdown
    assert "# Cidades e Estados" in md
    assert "var x" not in md and "Menu Home" not in md
    assert "[the portal](https://cidades.ibge.gov.br)" in md
    assert "| Recife | 1,488,920 |" in md
    assert result.embedded_metadata["title"] == "Cidades"


def test_unsupported_format_is_rejected(tmp_path):
    f = tmp_path / "slides.pptx"
    f.write_bytes(b"x")
    with pytest.raises(conversion.ConversionError, match="Unsupported format"):
        conversion.convert(f)


def test_empty_document_fails_validation(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("   \n\n", encoding="utf-8")
    report = validate_markdown(conversion.convert(f).markdown)
    assert not report["passed"]
    assert report["status"] == "failed"


def test_scanned_pdf_warns_about_missing_text(tmp_path):
    from pdfgen import make_pdf

    f = tmp_path / "scan.pdf"
    f.write_bytes(make_pdf([[], []]))
    result = conversion.convert(f)
    assert any("OCR" in w for w in result.warnings)
    assert not validate_markdown(result.markdown, result.page_count)["passed"]


def test_latin1_text_is_decoded_with_warning(tmp_path):
    f = tmp_path / "legacy.txt"
    f.write_bytes("Introdução à pesquisa científica.".encode("latin-1"))
    result = conversion.convert(f)
    assert "Introdução" in result.markdown
    assert result.warnings
