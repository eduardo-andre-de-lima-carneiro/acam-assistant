import pytest

from acam import models
from acam.references.abnt import build_reference, format_access_date, format_author


def _record(kind, **values):
    meta = models.empty_metadata()
    for k, v in values.items():
        meta[k] = models.field(v, "researcher", None, True)
    return {"type": kind, "metadata": meta}


@pytest.mark.parametrize("name,expected", [
    ("José Afonso da Silva", "SILVA, J. A."),
    ("Silva, José Afonso", "SILVA, J. A."),
    ("John Sweller", "SWELLER, J."),
    ("Carlos Alberto Souza Filho", "SOUZA FILHO, C. A."),
    ("Instituto Brasileiro de Geografia e Estatística (IBGE)",
     "INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA (IBGE)"),
])
def test_author_formatting(name, expected):
    assert format_author(name) == expected


def test_book_reference_matches_readme_example():
    ref = build_reference(_record("book", authors=["José Afonso da Silva"],
                                  title="Direito ambiental constitucional", edition="4",
                                  publication_place="São Paulo", publisher="Malheiros",
                                  publication_year=2002))
    assert ref.text == "SILVA, J. A. **Direito ambiental constitucional**. 4. ed. São Paulo: Malheiros, 2002."
    assert ref.complete


def test_journal_article_reference_matches_readme_example():
    ref = build_reference(_record("journal_article", authors=["John Sweller"],
                                  title="Cognitive load during problem solving: A reinterpretation",
                                  journal="Cognitive Science", volume="12", issue="2",
                                  pages="257-285", publication_year=1988))
    assert ref.text == ("SWELLER, J. Cognitive load during problem solving: A reinterpretation. "
                        "**Cognitive Science**, v. 12, n. 2, p. 257-285, 1988.")


def test_website_reference_matches_readme_example():
    ref = build_reference(_record("website",
                                  authors=["Instituto Brasileiro de Geografia e Estatística (IBGE)"],
                                  title="Cidades", publication_year=2021, url="ibge.gov.br",
                                  access_date="2026-10-15"))
    assert ref.text == ("INSTITUTO BRASILEIRO DE GEOGRAFIA E ESTATÍSTICA (IBGE). Cidades. 2021. "
                        "Disponível em: ibge.gov.br. Acesso em: 15 out. 2026.")


def test_missing_fields_use_abnt_placeholders_and_are_reported():
    ref = build_reference(_record("book", title="Obra sem dados"))
    assert "[s.l.]: [s.n.], [s.d.]." in ref.text
    assert set(ref.missing) >= {"authors", "publication_year", "publisher", "publication_place"}
    assert not ref.complete


def test_many_authors_use_et_al():
    ref = build_reference(_record("journal_article", authors=["Ana Lima", "Bruno Costa",
                                  "Carla Dias", "Davi Rocha"], title="T", journal="J",
                                  volume="1", pages="1-2", publication_year=2020))
    assert ref.text.startswith("LIMA, A. et al. T.")


def test_access_date_format():
    assert format_access_date("2026-05-03T10:00:00Z") == "3 maio 2026"
