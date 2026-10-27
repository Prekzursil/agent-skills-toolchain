"""Extra branch-coverage tests for scholarly_access.logic (loop if-false paths,
doi-only candidate gathering, second allowlisted candidate)."""

from __future__ import annotations

from scholarly_access import logic
from scholarly_access import sources as S

CROSSREF_MSG = {
    "title": ["Attention Is All You Need"],
    "author": [{"given": "Ashish", "family": "Vaswani"}],
    "issued": {"date-parts": [[2017]]},
    "container-title": ["NeurIPS"],
    "DOI": "10.1/X",
    "type": "journal-article",
}


def patch(monkeypatch, **funcs):
    for name, fn in funcs.items():
        monkeypatch.setattr(S, name, fn)


def test_resolve_title_loop_worse_items(monkeypatch):
    # exact crossref match first; a worse 2nd item exercises `if sim > best_sim`
    # False; a worse openalex item does the same in its loop.
    patch(
        monkeypatch,
        classify_identifier=lambda s: ("title", "Attention Is All You Need"),
        crossref_search=lambda t, rows=5: [CROSSREF_MSG, {"title": ["unrelated zzz"]}],
        openalex_search=lambda t, per_page=5: [
            {"title": "unrelated qqq", "publication_year": 1, "doi": None}
        ],
    )
    out = logic.resolve("Attention Is All You Need")
    assert out["sources_used"] == ["crossref"]


def test_fetch_metadata_arxiv_lookup_none(monkeypatch):
    monkeypatch.setattr(
        logic,
        "resolve",
        lambda i: {"resolved": True, "identifiers": {"arxiv": "a"}, "sources_used": []},
    )
    patch(
        monkeypatch,
        pubmed_efetch=lambda p: None,
        arxiv_lookup=lambda **k: None,
        semanticscholar=lambda **k: None,
    )
    assert logic.fetch_metadata("x")["abstract"] == ""


def test_candidates_doi_only_openalex_none(monkeypatch):
    # arxiv falsy -> skip arxiv block; openalex None -> skip openalex block.
    patch(
        monkeypatch,
        unpaywall=lambda d: None,
        openalex_by_doi=lambda d: None,
        semanticscholar=lambda **k: None,
        core_search=lambda **k: None,
        doaj_by_doi=lambda d: None,
    )
    assert logic._candidates("10.1/x", arxiv="") == []


def test_find_oa_pdf_second_allowlisted_kept(monkeypatch):
    monkeypatch.setattr(
        logic,
        "_candidates",
        lambda doi, arxiv="": [
            {"url": "https://arxiv.org/pdf/a", "source": "arxiv", "license": "arXiv"},
            {
                "url": "https://zenodo.org/record/1/files/b.pdf",
                "source": "zenodo",
                "license": None,
            },
        ],
    )
    out = logic.find_oa_pdf(doi="10.1/x")
    assert out["oa_pdf_url"] == "https://arxiv.org/pdf/a"
    assert sum(1 for e in out["evidence"] if "allowlisted" in e["verdict"]) == 2
