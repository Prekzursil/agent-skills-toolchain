"""Unit tests for scholarly_access.logic — the ``sources`` clients are replaced
with deterministic fakes; no real network. Targets 100% line+branch coverage."""

from __future__ import annotations

import pytest
import requests

from scholarly_access import logic
from scholarly_access import policy
from scholarly_access import sources as S


def patch(monkeypatch, **funcs):
    """Replace sources.<name> with the given callables/values."""
    for name, fn in funcs.items():
        monkeypatch.setattr(
            S, name, fn if callable(fn) else (lambda *a, _v=fn, **k: _v)
        )


CROSSREF_MSG = {
    "title": ["Attention Is All You Need"],
    "author": [{"given": "Ashish", "family": "Vaswani"}],
    "issued": {"date-parts": [[2017]]},
    "container-title": ["NeurIPS"],
    "DOI": "10.1/X",
    "type": "journal-article",
}


# --------------------------------------------------------------------------- _canonical_from_crossref
def test_canonical_minimal():
    out = logic._canonical_from_crossref({})
    assert out["title"] == ""
    assert out["doi"] is None
    assert out["year"] == ""


def test_canonical_full():
    out = logic._canonical_from_crossref(CROSSREF_MSG)
    assert out["title"] == "Attention Is All You Need"
    assert out["authors"] == ["Ashish Vaswani"]
    assert out["year"] == "2017"
    assert out["doi"] == "10.1/x"


# --------------------------------------------------------------------------- resolve: doi
def test_resolve_doi_all_sources(monkeypatch):
    patch(
        monkeypatch,
        classify_identifier=lambda s: ("doi", "10.1/x"),
        crossref_by_doi=lambda d: CROSSREF_MSG,
        openalex_by_doi=lambda d: {
            "id": "W1",
            "title": "t",
            "publication_year": 2017,
            "authorships": [],
        },
        pubmed_pmid_for_doi=lambda d: "999",
    )
    out = logic.resolve("10.1/x")
    assert out["resolved"] is True
    assert "crossref" in out["sources_used"] and "openalex" in out["sources_used"]
    assert out["identifiers"]["openalex"] == "W1"
    assert out["identifiers"]["pmid"] == "999"


def test_resolve_doi_openalex_only(monkeypatch):
    patch(
        monkeypatch,
        classify_identifier=lambda s: ("doi", "10.1/x"),
        crossref_by_doi=lambda d: None,
        openalex_by_doi=lambda d: {
            "id": "W1",
            "title": "t",
            "publication_year": 2018,
            "authorships": [{"author": {"display_name": "A B"}}],
        },
        pubmed_pmid_for_doi=lambda d: None,
    )
    out = logic.resolve("10.1/x")
    assert out["resolved"] is True
    assert out["metadata"]["authors"] == ["A B"]


def test_resolve_doi_unresolved(monkeypatch):
    patch(
        monkeypatch,
        classify_identifier=lambda s: ("doi", "10.1/x"),
        crossref_by_doi=lambda d: None,
        openalex_by_doi=lambda d: None,
        pubmed_pmid_for_doi=lambda d: None,
    )
    out = logic.resolve("10.1/x")
    assert out["resolved"] is False
    assert out["confidence"] == 0.0


# --------------------------------------------------------------------------- openalex_authenticated flag
KEY = "oa-test-key-never-echoed"


@pytest.mark.parametrize("keyed", [True, False])
def test_resolve_doi_reports_openalex_authenticated(monkeypatch, keyed):
    if keyed:
        monkeypatch.setenv("OPENALEX_API_KEY", KEY)
    else:
        monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    patch(
        monkeypatch,
        classify_identifier=lambda s: ("doi", "10.1/x"),
        crossref_by_doi=lambda d: None,
        openalex_by_doi=lambda d: None,
        pubmed_pmid_for_doi=lambda d: None,
    )
    out = logic.resolve("10.1/x")
    assert out["openalex_authenticated"] is keyed
    assert KEY not in repr(out)  # the flag is a bool; the key is never echoed


def test_resolve_title_reports_openalex_authenticated(monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", KEY)
    patch(
        monkeypatch,
        classify_identifier=lambda s: ("title", "q"),
        crossref_search=lambda t, rows=5: [],
        openalex_search=lambda t, per_page=5: [],
    )
    assert logic.resolve("q")["openalex_authenticated"] is True


def test_resolve_pmid_and_arxiv_do_not_consult_openalex(monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", KEY)
    patch(
        monkeypatch,
        classify_identifier=lambda s: ("pmid", "999"),
        pubmed_efetch=lambda p: None,
    )
    assert "openalex_authenticated" not in logic.resolve("999")
    patch(
        monkeypatch,
        classify_identifier=lambda s: ("arxiv", "x"),
        arxiv_lookup=lambda **k: None,
    )
    assert "openalex_authenticated" not in logic.resolve("x")


# --------------------------------------------------------------------------- resolve: pmid
def test_resolve_pmid_with_doi(monkeypatch):
    patch(
        monkeypatch,
        classify_identifier=lambda s: ("pmid", "999"),
        pubmed_efetch=lambda p: {
            "title": "T",
            "authors": ["A"],
            "year": "2000",
            "journal": "J",
            "doi": "10.2/Y",
        },
    )
    out = logic.resolve("999")
    assert out["identifiers"]["doi"] == "10.2/y"
    assert out["resolved"] is True


def test_resolve_pmid_no_doi_none(monkeypatch):
    patch(
        monkeypatch,
        classify_identifier=lambda s: ("pmid", "999"),
        pubmed_efetch=lambda p: {
            "title": "T",
            "authors": ["A"],
            "year": "2000",
            "journal": "J",
            "doi": None,
        },
    )
    out = logic.resolve("999")
    assert "doi" not in out["identifiers"]


def test_resolve_pmid_unresolved(monkeypatch):
    patch(
        monkeypatch,
        classify_identifier=lambda s: ("pmid", "999"),
        pubmed_efetch=lambda p: None,
    )
    assert logic.resolve("999")["resolved"] is False


# --------------------------------------------------------------------------- resolve: arxiv
def test_resolve_arxiv(monkeypatch):
    patch(
        monkeypatch,
        classify_identifier=lambda s: ("arxiv", "1706.03762"),
        arxiv_lookup=lambda **k: {"title": "T", "authors": ["A"], "published": "2017"},
    )
    out = logic.resolve("1706.03762")
    assert out["metadata"]["journal"] == "arXiv"


def test_resolve_arxiv_none(monkeypatch):
    patch(
        monkeypatch,
        classify_identifier=lambda s: ("arxiv", "x"),
        arxiv_lookup=lambda **k: None,
    )
    assert logic.resolve("x")["resolved"] is False


# --------------------------------------------------------------------------- resolve: title
def test_resolve_title_crossref_accept(monkeypatch):
    patch(
        monkeypatch,
        classify_identifier=lambda s: ("title", "Attention Is All You Need"),
        crossref_search=lambda t, rows=5: [CROSSREF_MSG],
        openalex_search=lambda t, per_page=5: [],
    )
    out = logic.resolve("Attention Is All You Need")
    assert out["resolved"] is True
    assert out["identifiers"]["doi"] == "10.1/x"
    assert "title_match_similarity" in out


def test_resolve_title_openalex_better(monkeypatch):
    patch(
        monkeypatch,
        classify_identifier=lambda s: ("title", "Attention Is All You Need"),
        crossref_search=lambda t, rows=5: [{"title": ["totally unrelated"]}],
        openalex_search=lambda t, per_page=5: [
            {
                "title": "Attention Is All You Need",
                "publication_year": 2017,
                "doi": "https://doi.org/10.9/z",
            }
        ],
    )
    out = logic.resolve("Attention Is All You Need")
    assert out["sources_used"] == ["openalex"]
    assert out["identifiers"]["doi"] == "10.9/z"


def test_resolve_title_below_threshold(monkeypatch):
    patch(
        monkeypatch,
        classify_identifier=lambda s: ("title", "abcdefg hijklmn"),
        crossref_search=lambda t, rows=5: [{"title": ["zzz qqq wholly different"]}],
        openalex_search=lambda t, per_page=5: [],
    )
    out = logic.resolve("abcdefg hijklmn")
    assert out["resolved"] is False
    assert "best_rejected_match" in out


def test_resolve_title_no_candidates(monkeypatch):
    patch(
        monkeypatch,
        classify_identifier=lambda s: ("title", "q"),
        crossref_search=lambda t, rows=5: [],
        openalex_search=lambda t, per_page=5: [],
    )
    out = logic.resolve("q")
    assert out["resolved"] is False
    assert "best_rejected_match" not in out


def test_resolve_title_accept_no_doi(monkeypatch):
    # openalex candidate with no doi -> accepted but identifiers has no doi
    patch(
        monkeypatch,
        classify_identifier=lambda s: ("title", "Attention Is All You Need"),
        crossref_search=lambda t, rows=5: [],
        openalex_search=lambda t, per_page=5: [
            {
                "title": "Attention Is All You Need",
                "publication_year": 2017,
                "doi": None,
            }
        ],
    )
    out = logic.resolve("Attention Is All You Need")
    assert out["resolved"] is True
    assert "doi" not in out["identifiers"]


# --------------------------------------------------------------------------- fetch_metadata
def test_fetch_metadata_unresolved(monkeypatch):
    monkeypatch.setattr(
        logic, "resolve", lambda i: {"resolved": False, "identifiers": {}}
    )
    assert logic.fetch_metadata("x")["resolved"] is False


def test_fetch_metadata_full(monkeypatch):
    monkeypatch.setattr(
        logic,
        "resolve",
        lambda i: {
            "resolved": True,
            "identifiers": {"doi": "10.1/x", "pmid": "9", "arxiv": "a"},
            "sources_used": [],
        },
    )
    patch(
        monkeypatch,
        pubmed_efetch=lambda p: {"abstract": "ABS"},
        arxiv_lookup=lambda **k: {"summary": "SUM"},
        semanticscholar=lambda **k: {
            "abstract": "S2",
            "references": [{"title": "R1"}, {"title": None}],
        },
    )
    out = logic.fetch_metadata("x")
    assert out["abstract"] == "ABS"  # pubmed wins
    assert out["references"] == ["R1"]


def test_fetch_metadata_arxiv_abstract(monkeypatch):
    monkeypatch.setattr(
        logic,
        "resolve",
        lambda i: {"resolved": True, "identifiers": {"arxiv": "a"}, "sources_used": []},
    )
    patch(
        monkeypatch,
        pubmed_efetch=lambda p: None,
        arxiv_lookup=lambda **k: {"summary": "SUM"},
        semanticscholar=lambda **k: None,
    )
    out = logic.fetch_metadata("x")
    assert out["abstract"] == "SUM"
    assert out["references"] == []


def test_fetch_metadata_pmid_none(monkeypatch):
    monkeypatch.setattr(
        logic,
        "resolve",
        lambda i: {
            "resolved": True,
            "identifiers": {"doi": "10.1/x", "pmid": "9"},
            "sources_used": [],
        },
    )
    patch(
        monkeypatch,
        pubmed_efetch=lambda p: None,
        arxiv_lookup=lambda **k: None,
        semanticscholar=lambda **k: {"abstract": "S2", "references": []},
    )
    assert logic.fetch_metadata("x")["abstract"] == "S2"


# --------------------------------------------------------------------------- _candidates
def test_candidates_all_sources(monkeypatch):
    patch(
        monkeypatch,
        arxiv_lookup=lambda **k: {"pdf_url": "http://arxiv.org/pdf/x"},
        unpaywall=lambda d: {
            "best_oa_location": {"url_for_pdf": "http://u/p.pdf", "license": "cc"},
            "oa_locations": [None, {"url_for_pdf": "http://u2/p.pdf"}, {}],
        },
        openalex_by_doi=lambda d: {"best_oa_location": {"pdf_url": "http://oa/p.pdf"}},
        semanticscholar=lambda **k: {"openAccessPdf": {"url": "http://s2/p.pdf"}},
        core_search=lambda **k: {"downloadUrl": "http://core/p.pdf"},
        doaj_by_doi=lambda d: {
            "bibjson": {
                "link": [
                    {"type": "fulltext", "url": "http://doaj/p"},
                    {"type": "homepage", "url": "x"},
                ]
            }
        },
    )
    cands = logic._candidates("10.1/x", arxiv="1706.03762")
    srcs = {c["source"] for c in cands}
    assert {"arxiv", "unpaywall", "openalex", "semanticscholar", "core", "doaj"} <= srcs


def test_candidates_empty(monkeypatch):
    patch(
        monkeypatch,
        arxiv_lookup=lambda **k: None,
        unpaywall=lambda d: None,
        openalex_by_doi=lambda d: {"best_oa_location": {}},
        semanticscholar=lambda **k: {"openAccessPdf": None},
        core_search=lambda **k: None,
        doaj_by_doi=lambda d: None,
    )
    assert logic._candidates("10.1/x", arxiv="a") == []


def test_candidates_arxiv_no_pdf(monkeypatch):
    patch(monkeypatch, arxiv_lookup=lambda **k: {"pdf_url": None})
    assert logic._candidates("", arxiv="a") == []


# --------------------------------------------------------------------------- find_oa_pdf
def test_find_oa_pdf_chosen_and_denied(monkeypatch):
    monkeypatch.setattr(
        logic,
        "_candidates",
        lambda doi, arxiv="": [
            {"url": "https://sci-hub.se/10.1/x", "source": "x", "license": None},
            {"url": "https://researchgate.net/p.pdf", "source": "rg", "license": None},
            {"url": "https://arxiv.org/pdf/x", "source": "arxiv", "license": "arXiv"},
        ],
    )
    out = logic.find_oa_pdf(doi="10.1/x")
    assert out["oa_pdf_url"] == "https://arxiv.org/pdf/x"
    verdicts = [e["verdict"] for e in out["evidence"]]
    assert any("DENIED" in v for v in verdicts)
    assert any("off-allowlist" in v for v in verdicts)


def test_find_oa_pdf_resolve_path(monkeypatch):
    monkeypatch.setattr(
        logic, "resolve", lambda i: {"identifiers": {"doi": "10.1/x", "arxiv": "a"}}
    )
    monkeypatch.setattr(logic, "_candidates", lambda doi, arxiv="": [])
    out = logic.find_oa_pdf(identifier="something")
    assert out["oa_pdf_url"] is None


# --------------------------------------------------------------------------- access_status
def test_access_status_oa(monkeypatch):
    monkeypatch.setattr(
        logic,
        "find_oa_pdf",
        lambda **k: {
            "oa_pdf_url": "https://arxiv.org/pdf/x",
            "license": "arXiv",
            "source": "arxiv",
            "evidence": [],
        },
    )
    assert logic.access_status(doi="10.1/x")["status"] == policy.OA_PDF


def test_access_status_unresolved_unknown(monkeypatch):
    monkeypatch.setattr(
        logic, "resolve", lambda i: {"resolved": False, "identifiers": {}}
    )
    out = logic.access_status(identifier="nope")
    assert out["status"] == policy.UNKNOWN


def test_access_status_free_not_redist(monkeypatch):
    monkeypatch.setattr(
        logic, "find_oa_pdf", lambda **k: {"oa_pdf_url": None, "evidence": []}
    )
    patch(
        monkeypatch,
        unpaywall=lambda d: {
            "is_oa": True,
            "oa_status": "green",
            "best_oa_location": {"url": "http://land"},
        },
    )
    out = logic.access_status(doi="10.1/x")
    assert out["status"] == policy.FREE_NOT_REDIST


def test_access_status_subscription(monkeypatch):
    monkeypatch.setattr(
        logic, "find_oa_pdf", lambda **k: {"oa_pdf_url": None, "evidence": []}
    )
    patch(monkeypatch, unpaywall=lambda d: {"is_oa": False})
    assert logic.access_status(doi="10.1/x")["status"] == policy.SUBSCRIPTION


def test_access_status_arxiv_unavailable(monkeypatch):
    monkeypatch.setattr(
        logic, "find_oa_pdf", lambda **k: {"oa_pdf_url": None, "evidence": []}
    )
    patch(monkeypatch, unpaywall=lambda d: None)
    out = logic.access_status(arxiv="a")
    assert out["status"] == policy.UNAVAILABLE


def test_access_status_doi_unavailable(monkeypatch):
    monkeypatch.setattr(
        logic, "find_oa_pdf", lambda **k: {"oa_pdf_url": None, "evidence": []}
    )
    patch(monkeypatch, unpaywall=lambda d: None)
    out = logic.access_status(doi="10.1/x")
    assert out["status"] == policy.UNAVAILABLE


def test_access_status_resolve_with_doi(monkeypatch):
    monkeypatch.setattr(
        logic, "resolve", lambda i: {"resolved": True, "identifiers": {"doi": "10.1/x"}}
    )
    monkeypatch.setattr(
        logic,
        "find_oa_pdf",
        lambda **k: {
            "oa_pdf_url": "https://arxiv.org/pdf/x",
            "license": None,
            "source": "arxiv",
            "evidence": [],
        },
    )
    assert logic.access_status(identifier="paper")["status"] == policy.OA_PDF


# --------------------------------------------------------------------------- citation_graph
def test_citation_graph_s2(monkeypatch):
    patch(
        monkeypatch,
        semanticscholar=lambda **k: {
            "references": [{"title": "R", "externalIds": {"DOI": "10.r/1"}}],
            "citations": [{"title": "C", "externalIds": None}],
        },
    )
    out = logic.citation_graph(doi="10.1/x")
    assert out["source"] == "semanticscholar"
    assert out["counts"]["references"] == 1


def test_citation_graph_openalex(monkeypatch):
    patch(
        monkeypatch,
        semanticscholar=lambda **k: None,
        openalex_by_doi=lambda d: {"referenced_works": ["W1", "W2"]},
    )
    out = logic.citation_graph(doi="10.1/x")
    assert out["source"] == "openalex"
    assert out["counts"]["references"] == 2


def test_citation_graph_resolve_no_doi(monkeypatch):
    monkeypatch.setattr(logic, "resolve", lambda i: {"identifiers": {}})
    out = logic.citation_graph(identifier="x")
    assert out["source"] is None


def test_citation_graph_openalex_none(monkeypatch):
    patch(monkeypatch, semanticscholar=lambda **k: None, openalex_by_doi=lambda d: None)
    out = logic.citation_graph(doi="10.1/x")
    assert out["references"] == []


def test_citation_graph_flag_only_when_openalex_consulted(monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", KEY)
    patch(monkeypatch, semanticscholar=lambda **k: {"references": [], "citations": []})
    assert "openalex_authenticated" not in logic.citation_graph(doi="10.1/x")
    patch(monkeypatch, semanticscholar=lambda **k: None, openalex_by_doi=lambda d: None)
    assert logic.citation_graph(doi="10.1/x")["openalex_authenticated"] is True
    monkeypatch.delenv("OPENALEX_API_KEY")
    assert logic.citation_graph(doi="10.1/x")["openalex_authenticated"] is False


# --------------------------------------------------------------------------- download_oa_pdf
class FakeResp:
    def __init__(self, status=200, content=b"%PDF-1.7 data"):
        self.status_code = status
        self.content = content


def test_download_denied():
    with pytest.raises(PermissionError):
        logic.download_oa_pdf("https://sci-hub.se/10.1/x")


def test_download_off_allowlist():
    with pytest.raises(PermissionError):
        logic.download_oa_pdf("https://evil.example.com/p.pdf")


def test_download_ok(monkeypatch, tmp_path):
    monkeypatch.setattr(logic.requests, "get", lambda *a, **k: FakeResp())
    out = logic.download_oa_pdf(
        "https://arxiv.org/pdf/x",
        dest_dir=str(tmp_path),
        license="arXiv",
        source="arxiv",
    )
    assert out["ok"] is True
    assert out["path"].endswith(".pdf")
    assert out["sha256"]


def test_download_ok_named(monkeypatch, tmp_path):
    monkeypatch.setattr(logic.requests, "get", lambda *a, **k: FakeResp())
    out = logic.download_oa_pdf(
        "https://arxiv.org/pdf/x", dest_dir=str(tmp_path), filename="my.pdf"
    )
    assert out["path"].endswith("my.pdf")


def test_download_fetch_error(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise requests.RequestException("net")

    monkeypatch.setattr(logic.requests, "get", boom)
    out = logic.download_oa_pdf("https://arxiv.org/pdf/x", dest_dir=str(tmp_path))
    assert out["ok"] is False and "fetch failed" in out["error"]


def test_download_not_pdf(monkeypatch, tmp_path):
    monkeypatch.setattr(
        logic.requests, "get", lambda *a, **k: FakeResp(content=b"<html>")
    )
    out = logic.download_oa_pdf("https://arxiv.org/pdf/x", dest_dir=str(tmp_path))
    assert out["ok"] is False and "not a PDF" in out["error"]


# --------------------------------------------------------------------------- summarize
def test_summarize_unresolved(monkeypatch):
    monkeypatch.setattr(logic, "fetch_metadata", lambda i: {"resolved": False})
    assert logic.summarize("x")["resolved"] is False


def test_summarize_full(monkeypatch):
    monkeypatch.setattr(
        logic,
        "fetch_metadata",
        lambda i: {
            "resolved": True,
            "metadata": {
                "title": "T",
                "authors": ["A"] * 10,
                "year": "2017",
                "journal": "J",
                "doi": "10.1/x",
            },
            "identifiers": {"doi": "10.1/x", "arxiv": ""},
            "abstract": "",
            "references": ["r1", "r2"],
        },
    )
    monkeypatch.setattr(logic, "access_status", lambda **k: {"status": policy.OA_PDF})
    out = logic.summarize(doi="10.1/x")
    assert out["access_status"] == policy.OA_PDF
    assert len(out["authors"]) == 8  # capped at 8
    assert out["abstract"].startswith("(no abstract")


# --------------------------------------------------------------------------- batch_resolve
def test_batch_resolve(monkeypatch):
    def fake_resolve(ident):
        if ident == "bad":
            return {"resolved": False, "identifiers": {}}
        return {
            "resolved": True,
            "identifiers": {"doi": "10.1/x", "arxiv": ""},
            "metadata": {"title": "T", "year": "2017"},
        }

    monkeypatch.setattr(logic, "resolve", fake_resolve)
    monkeypatch.setattr(
        logic, "access_status", lambda **k: {"status": policy.OA_PDF, "oa_pdf_url": "u"}
    )
    out = logic.batch_resolve(["good", "bad"])
    assert out["count"] == 2 and out["resolved"] == 1
    assert out["unresolved"] == ["bad"]
