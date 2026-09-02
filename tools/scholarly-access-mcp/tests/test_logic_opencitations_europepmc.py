"""Unit tests for the keyless per-source tools in scholarly_access.logic:
citations_for_doi / references_for_doi (OpenCitations) and europepmc_fulltext /
europepmc_annotations (Europe PMC). The ``sources`` clients are replaced with
deterministic fakes; no real network. Targets 100% line+branch coverage."""

from __future__ import annotations

import pytest

from scholarly_access import logic
from scholarly_access import sources as S


def upstream(status, url="https://api.example/x"):
    return S.UpstreamError(f"upstream returned HTTP {status}", status=status, url=url)


def raising(err):
    def fn(*a, **k):
        raise err

    return fn


# --------------------------------------------------------------------------- helpers
def test_fold_strips_diacritics_and_case():
    assert logic._fold("Müller") == "muller"
    assert logic._fold("MÜLLER ") == "muller"
    assert logic._fold("García-Márquez") == "garcia-marquez"


def test_first_surname_parses_meta_author_field():
    field = "Vaswani, Ashish [orcid:0000 omid:ra/1]; Shazeer, Noam [omid:ra/2]"
    assert logic._first_surname(field) == "vaswani"
    assert logic._first_surname("") == ""
    assert logic._first_surname("Plato [omid:ra/3]") == "plato"


def test_doi_in_picks_doi_token_lowercased():
    assert logic._doi_in("omid:br/1 doi:10.1000/ABC pmid:123") == "10.1000/abc"
    assert logic._doi_in("omid:br/1 pmid:123") is None
    assert logic._doi_in("") is None


def test_clamp():
    assert logic._clamp(0, 1, 100) == 1
    assert logic._clamp(1000, 1, 100) == 100
    assert logic._clamp(42, 1, 100) == 42


# --------------------------------------------------------------------------- _meta_lookup
def test_meta_lookup_batches_and_skips_rows_without_doi(monkeypatch):
    calls = []

    def fake_meta(dois):
        calls.append(list(dois))
        return [
            {
                "id": "doi:10.1000/a omid:br/1",
                "title": "A",
                "author": "Doe, J",
                "pub_date": "2001",
            },
            {"id": "omid:br/2", "title": "no doi id"},  # skipped
            {
                "id": "doi:10.1000/b",
                "title": "",
                "author": "",
                "pub_date": "",
            },  # -> None
        ]

    monkeypatch.setattr(S, "opencitations_meta", fake_meta)
    warnings = []
    dois = [f"10.1000/{i}" for i in range(26)] + [
        "10.1000/a",
        "10.1000/a",
    ]  # dedup + 2 batches
    out = logic._meta_lookup(dois, warnings)
    assert len(calls) == 2 and len(calls[0]) == 25 and len(calls[1]) == 2
    assert out["10.1000/a"] == {"title": "A", "date": "2001", "surname": "doe"}
    assert out["10.1000/b"] == {"title": None, "date": None, "surname": ""}
    assert warnings == []


def test_meta_lookup_failed_batch_becomes_warning_with_status(monkeypatch):
    monkeypatch.setattr(S, "opencitations_meta", raising(upstream(503)))
    warnings = []
    assert logic._meta_lookup(["10.1000/a"], warnings) == {}
    assert warnings == [
        {
            "stage": "opencitations-meta",
            "error": "upstream returned HTTP 503",
            "upstream_status": 503,
            "url": "https://api.example/x",
        }
    ]


# --------------------------------------------------------------------------- citations_for_doi
INDEX_ROWS = [
    {
        "oci": "oci-1",
        "citing": "omid:br/11 doi:10.2000/self pmid:1",
        "cited": "omid:br/1 doi:10.1000/x",
        "creation": "2021-05-01",
        "timespan": "P4Y",
        "journal_sc": "no",
        "author_sc": "yes",
    },
    {
        "oci": "oci-2",
        "citing": "omid:br/12 doi:10.2000/other",
        "cited": "omid:br/1 doi:10.1000/x",
        "creation": "2020-01-01",
        "timespan": "",
        "journal_sc": "yes",
        "author_sc": "no",
    },
    {
        "oci": "oci-3",
        "citing": "omid:br/13",  # no DOI at all -> no Meta enrichment possible
        "cited": "omid:br/1 doi:10.1000/x",
        "creation": "2019-01-01",
    },
    {
        "oci": "oci-4",
        "citing": "omid:br/14 doi:10.2000/unknown-to-meta",
        "cited": "omid:br/1 doi:10.1000/x",
        "creation": "2018-01-01",
    },
]

META_ROWS = [
    {
        "id": "doi:10.1000/x omid:br/1",
        "title": "Mine",
        "author": "Doe, Jane [omid:ra/1]",
        "pub_date": "2017",
    },
    {
        "id": "doi:10.2000/self",
        "title": "Self",
        "author": "DOE, John; Roe, R",
        "pub_date": "2021-05-01",
    },
    {
        "id": "doi:10.2000/other",
        "title": "Other",
        "author": "Müller, K",
        "pub_date": "2020-01-01",
    },
]


def test_citations_for_doi_full(monkeypatch):
    monkeypatch.setattr(S, "opencitations_index", lambda kind, doi: INDEX_ROWS)
    monkeypatch.setattr(S, "opencitations_meta", lambda dois: META_ROWS)
    out = logic.citations_for_doi("https://doi.org/10.1000/X")
    assert out["ok"] is True and out["source"] == "opencitations"
    assert out["doi"] == "10.1000/x"
    assert out["work"] == {
        "doi": "10.1000/x",
        "title": "Mine",
        "date": "2017",
        "first_author_surname": "doe",
    }
    assert out["count"] == 4 and out["total_upstream"] == 4
    assert out["truncated"] is False
    assert out["license"] == "CC0-1.0" and "HEURISTIC" in out["note"]
    assert out["warnings"] == []
    rows = out["citations"]
    assert rows[0] == {
        "citing_doi": "10.2000/self",
        "title": "Self",
        "date": "2021-05-01",  # citations: `creation` is the citing work's date
        "timespan": "P4Y",
        "oci": "oci-1",
        "first_author_surname": "doe",
        "self_citation_suspect": True,
        "opencitations_author_sc": True,
        "opencitations_journal_sc": False,
    }
    assert rows[1]["self_citation_suspect"] is False
    assert rows[1]["first_author_surname"] == "muller"
    assert rows[1]["timespan"] is None
    assert rows[1]["opencitations_journal_sc"] is True
    # no citing DOI -> nothing to look up -> unknown, never a false accusation
    assert rows[2]["citing_doi"] is None
    assert rows[2]["self_citation_suspect"] is None
    assert rows[2]["title"] is None
    # DOI present but unknown to Meta -> also None
    assert rows[3]["citing_doi"] == "10.2000/unknown-to-meta"
    assert rows[3]["self_citation_suspect"] is None


def test_references_for_doi_uses_meta_date_of_cited_work(monkeypatch):
    seen = {}

    def fake_index(kind, doi):
        seen["kind"], seen["doi"] = kind, doi
        return [
            {
                "oci": "oci-9",
                "citing": "omid:br/1 doi:10.1000/x",
                "cited": "omid:br/21 doi:10.2000/other",
                "creation": "2017-06-12",  # citing work's date, NOT the cited one's
                "timespan": "P3Y",
                "journal_sc": "no",
                "author_sc": "no",
            }
        ]

    monkeypatch.setattr(S, "opencitations_index", fake_index)
    monkeypatch.setattr(S, "opencitations_meta", lambda dois: META_ROWS)
    out = logic.references_for_doi("10.1000/x")
    assert seen == {"kind": "references", "doi": "10.1000/x"}
    assert out["ok"] is True
    ref = out["references"][0]
    assert ref["cited_doi"] == "10.2000/other"
    assert ref["date"] == "2020-01-01"  # from Meta, not `creation`
    assert ref["self_citation_suspect"] is False


def test_citations_limit_is_clamped_and_truncation_flagged(monkeypatch):
    rows = [
        {
            "oci": f"o{i}",
            "citing": f"doi:10.2000/c{i}",
            "cited": "doi:10.1000/x",
            "creation": "2020",
        }
        for i in range(150)
    ]
    monkeypatch.setattr(S, "opencitations_index", lambda kind, doi: rows)
    monkeypatch.setattr(S, "opencitations_meta", lambda dois: [])
    out = logic.citations_for_doi("10.1000/x", limit=1000)
    assert out["count"] == 100 and out["total_upstream"] == 150
    assert out["truncated"] is True
    out = logic.citations_for_doi("10.1000/x", limit=0)
    assert out["count"] == 1 and out["truncated"] is True
    # Meta knew nothing -> the input work's own metadata is truthfully None
    assert out["work"] == {
        "doi": "10.1000/x",
        "title": None,
        "date": None,
        "first_author_surname": None,
    }


def test_citations_meta_failure_degrades_to_warning_not_error(monkeypatch):
    monkeypatch.setattr(S, "opencitations_index", lambda kind, doi: INDEX_ROWS[:1])
    monkeypatch.setattr(S, "opencitations_meta", raising(upstream(429)))
    out = logic.citations_for_doi("10.1000/x")
    assert out["ok"] is True and out["count"] == 1
    assert out["warnings"][0]["upstream_status"] == 429
    assert out["citations"][0]["self_citation_suspect"] is None
    assert out["citations"][0]["opencitations_author_sc"] is True  # Index flag survives


def test_citations_index_failure_is_truthful_error(monkeypatch):
    monkeypatch.setattr(
        S,
        "opencitations_index",
        raising(
            upstream(
                500, "https://api.opencitations.net/index/v2/citations/doi:10.1000/x"
            )
        ),
    )
    out = logic.citations_for_doi("10.1000/x")
    assert out == {
        "ok": False,
        "source": "opencitations",
        "doi": "10.1000/x",
        "error": "upstream returned HTTP 500",
        "upstream_status": 500,
        "url": "https://api.opencitations.net/index/v2/citations/doi:10.1000/x",
    }


def test_citations_timeout_reports_status_none(monkeypatch):
    err = S.UpstreamError("request failed: ConnectTimeout", status=None, url="u")
    monkeypatch.setattr(S, "opencitations_index", raising(err))
    out = logic.references_for_doi("10.1000/x")
    assert out["ok"] is False and out["upstream_status"] is None
    assert out["error"] == "request failed: ConnectTimeout"


@pytest.mark.parametrize("bad", ["", "not a doi", "12345678", "arxiv:1706.03762"])
def test_citations_rejects_non_doi_without_network(monkeypatch, bad):
    monkeypatch.setattr(S, "opencitations_index", raising(AssertionError("no network")))
    out = logic.citations_for_doi(bad)
    assert out["ok"] is False and out["doi"] is None
    assert out["upstream_status"] is None and "not a DOI" in out["error"]


# --------------------------------------------------------------------------- Europe PMC ids
@pytest.mark.parametrize(
    "raw,norm",
    [
        ("PMC1182327", "PMC1182327"),
        ("pmc1182327", "PMC1182327"),
        (" PMC7 ", "PMC7"),
        ("1182327", None),  # bare digits are a PMID, never silently prefixed
        ("PMC", None),
        ("PMC1234567890", None),
        ("", None),
    ],
)
def test_norm_pmcid(raw, norm):
    assert logic._norm_pmcid(raw) == norm


@pytest.mark.parametrize(
    "raw,ident",
    [
        ("PMC1182327", "PMC:PMC1182327"),
        ("pmc12", "PMC:PMC12"),
        ("16060722", "MED:16060722"),
        (" 7 ", "MED:7"),
        ("10.1000/x", None),
        ("", None),
    ],
)
def test_classify_epmc_id(raw, ident):
    assert logic._classify_epmc_id(raw) == ident


# --------------------------------------------------------------------------- europepmc_fulltext
JATS = """<article xmlns:xlink="http://www.w3.org/1999/xlink">
<front><article-meta>
<title-group><article-title> The <italic>Title</italic> </article-title></title-group>
<permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/">
<license-p>Open access
   under CC BY.</license-p></license></permissions>
<abstract><p>First   sentence.</p><p>Second <b>bold</b> sentence.</p></abstract>
</article-meta></front>
<body>
<sec><title>Introduction</title><p>Intro para <xref>1</xref>.</p>
<sec><title>Sub</title><p>Nested para.</p></sec></sec>
<sec><p>No heading here.</p></sec>
</body></article>"""


def test_fulltext_success_sections_license_title(monkeypatch):
    monkeypatch.setattr(S, "europepmc_fulltext_xml", lambda pmcid: JATS)
    out = logic.europepmc_fulltext("pmc1182327")
    assert out["ok"] is True and out["source"] == "europepmc"
    assert out["pmcid"] == "PMC1182327"
    assert out["url"] == S.europepmc_fulltext_url("PMC1182327")
    assert out["title"] == "The Title"
    assert out["license"] == {
        "text": "Open access under CC BY.",
        "url": "https://creativecommons.org/licenses/by/4.0/",
    }
    assert [s["title"] for s in out["sections"]] == [
        "Abstract",
        "Introduction",
        "(untitled section)",
    ]
    assert out["sections"][0]["text"] == "First sentence. Second bold sentence."
    assert out["sections"][1]["text"] == "Intro para 1. Nested para."
    assert out["section_count"] == 3
    assert out["chars"] == sum(s["chars"] for s in out["sections"])
    assert out["truncated"] is False
    assert out["max_chars"] == logic.FULLTEXT_DEFAULT_CHARS


def test_fulltext_no_abstract_no_license_no_title(monkeypatch):
    monkeypatch.setattr(
        S,
        "europepmc_fulltext_xml",
        lambda pmcid: (
            "<article><front/><body><sec><title>A</title><p>x</p></sec></body></article>"
        ),
    )
    out = logic.europepmc_fulltext("PMC1")
    assert out["title"] is None and out["license"] is None
    assert out["sections"] == [{"title": "A", "text": "x", "chars": 1}]


def test_fulltext_bare_abstract_and_markup_in_section_title(monkeypatch):
    xml = (
        "<article><front><abstract>Plain abstract, no paragraphs.</abstract></front>"
        "<body><sec><title>Results <italic>in vivo</italic></title><p>r</p></sec>"
        "<sec><title>Empty</title></sec>"
        "<sec><title>Bare</title>Text <italic>in</italic> a section <p></p></sec>"
        "</body></article>"
    )
    monkeypatch.setattr(S, "europepmc_fulltext_xml", lambda pmcid: xml)
    out = logic.europepmc_fulltext("PMC1")
    assert out["sections"] == [
        {"title": "Abstract", "text": "Plain abstract, no paragraphs.", "chars": 30},
        {"title": "Results in vivo", "text": "r", "chars": 1},
        {"title": "Empty", "text": "", "chars": 0},  # heading is not echoed as body
        {"title": "Bare", "text": "Text in a section", "chars": 17},
    ]


def test_fulltext_truncates_at_max_chars(monkeypatch):
    big = "word " * 400  # 2000 chars
    xml = (
        "<article><front><abstract><p>ABSTRACT</p></abstract></front><body>"
        f"<sec><title>Body</title><p>{big}</p></sec>"
        "<sec><title>Never reached</title><p>tail</p></sec>"
        "</body></article>"
    )
    monkeypatch.setattr(S, "europepmc_fulltext_xml", lambda pmcid: xml)
    out = logic.europepmc_fulltext("PMC1", max_chars=1)  # clamped up to 1_000
    assert out["max_chars"] == 1_000
    assert out["truncated"] is True
    assert out["chars"] == 1_000
    assert [s["title"] for s in out["sections"]] == ["Abstract", "Body"]
    assert out["sections"][1]["chars"] == 1_000 - len("ABSTRACT")


def test_fulltext_room_exhausted_exactly_breaks_before_next_section(monkeypatch):
    # First section fills the budget to the byte; the next one hits `room <= 0`.
    xml = (
        "<article><body>"
        f"<sec><title>A</title><p>{'a' * 1_000}</p></sec>"
        "<sec><title>B</title><p>b</p></sec>"
        "</body></article>"
    )
    monkeypatch.setattr(S, "europepmc_fulltext_xml", lambda pmcid: xml)
    out = logic.europepmc_fulltext("PMC1", max_chars=1_000)
    assert [s["title"] for s in out["sections"]] == ["A"]
    assert out["sections"][0]["chars"] == 1_000
    assert out["truncated"] is True


def test_fulltext_max_chars_clamped_high(monkeypatch):
    monkeypatch.setattr(S, "europepmc_fulltext_xml", lambda pmcid: "<article/>")
    out = logic.europepmc_fulltext("PMC1", max_chars=10**9)
    assert out["max_chars"] == logic.FULLTEXT_MAX_CHARS
    assert out["sections"] == [] and out["chars"] == 0


def test_fulltext_404_is_truthful_with_reason(monkeypatch):
    url = S.europepmc_fulltext_url("PMC999")
    monkeypatch.setattr(S, "europepmc_fulltext_xml", raising(upstream(404, url)))
    out = logic.europepmc_fulltext("PMC999")
    assert out["ok"] is False and out["source"] == "europepmc"
    assert out["pmcid"] == "PMC999"
    assert out["upstream_status"] == 404 and out["url"] == url
    assert "open-access subset" in out["reason"]


def test_fulltext_other_status_has_no_oa_reason(monkeypatch):
    monkeypatch.setattr(S, "europepmc_fulltext_xml", raising(upstream(503)))
    out = logic.europepmc_fulltext("PMC1")
    assert out["ok"] is False and out["upstream_status"] == 503
    assert "reason" not in out


def test_fulltext_unparseable_xml(monkeypatch):
    monkeypatch.setattr(S, "europepmc_fulltext_xml", lambda pmcid: "<article><sec>")
    out = logic.europepmc_fulltext("PMC1")
    assert out["ok"] is False and out["upstream_status"] is None
    assert out["error"] == "upstream returned unparseable XML"
    assert out["url"] == S.europepmc_fulltext_url("PMC1")


@pytest.mark.parametrize("bad", ["", "1182327", "10.1000/x", "PMCX"])
def test_fulltext_rejects_non_pmcid_without_network(monkeypatch, bad):
    monkeypatch.setattr(
        S, "europepmc_fulltext_xml", raising(AssertionError("no network"))
    )
    out = logic.europepmc_fulltext(bad)
    assert out["ok"] is False and out["pmcid"] is None
    assert out["upstream_status"] is None and "not a PMCID" in out["error"]


def test_fulltext_url_is_policy_checked(monkeypatch):
    # The fetch URL goes through assert_lawful; a denied host must never be fetched.
    monkeypatch.setattr(
        S, "europepmc_fulltext_url", lambda pmcid: "https://sci-hub.se/x"
    )
    monkeypatch.setattr(
        S, "europepmc_fulltext_xml", raising(AssertionError("fetched!"))
    )
    with pytest.raises(PermissionError):
        logic.europepmc_fulltext("PMC1")


# --------------------------------------------------------------------------- europepmc_annotations
ANN_ROWS = [
    {
        "source": "PMC",
        "extId": "PMC1182327",
        "pmcid": "PMC1182327",
        "annotations": [
            {
                "type": "Gene_Proteins",
                "exact": "p53",
                "prefix": "the ",
                "postfix": " protein",
                "section": "Abstract",
                "provider": "Europe PMC",
                "tags": [
                    {"name": "TP53", "uri": "http://purl.uniprot.org/uniprot/P04637"}
                ],
            },
            {"type": "Diseases", "exact": "cancer", "tags": None},
            {"type": "Diseases", "exact": "tumour", "tags": []},
        ],
    }
]


def test_annotations_success(monkeypatch):
    seen = {}

    def fake(article_id, type_=""):
        seen["id"], seen["type"] = article_id, type_
        return ANN_ROWS

    monkeypatch.setattr(S, "europepmc_annotations", fake)
    out = logic.europepmc_annotations("pmc1182327")
    assert seen == {"id": "PMC:PMC1182327", "type": ""}
    assert out["ok"] is True and out["source"] == "europepmc"
    assert out["article_id"] == "PMC:PMC1182327" and out["type_filter"] is None
    assert out["article"] == {
        "source": "PMC",
        "ext_id": "PMC1182327",
        "pmcid": "PMC1182327",
    }
    assert out["types"] == ["Diseases", "Gene_Proteins"]
    assert (
        out["count"] == 3 and out["total_upstream"] == 3 and out["truncated"] is False
    )
    assert out["annotations"][0] == {
        "type": "Gene_Proteins",
        "exact": "p53",
        "prefix": "the ",
        "postfix": " protein",
        "section": "Abstract",
        "provider": "Europe PMC",
        "tags": [{"name": "TP53", "uri": "http://purl.uniprot.org/uniprot/P04637"}],
    }
    assert (
        out["annotations"][1]["tags"] == [] and out["annotations"][1]["section"] is None
    )
    assert "not proof of absence" in out["note"]


def test_annotations_pmid_type_filter_and_limit(monkeypatch):
    seen = {}

    def fake(article_id, type_=""):
        seen["id"], seen["type"] = article_id, type_
        return ANN_ROWS

    monkeypatch.setattr(S, "europepmc_annotations", fake)
    out = logic.europepmc_annotations("16060722", type="Diseases", limit=2)
    assert seen == {"id": "MED:16060722", "type": "Diseases"}
    assert out["article_id"] == "MED:16060722" and out["type_filter"] == "Diseases"
    assert out["count"] == 2 and out["total_upstream"] == 3 and out["truncated"] is True


def test_annotations_limit_clamped(monkeypatch):
    monkeypatch.setattr(S, "europepmc_annotations", lambda a, t="": ANN_ROWS)
    assert logic.europepmc_annotations("1", limit=0)["count"] == 1
    assert logic.europepmc_annotations("1", limit=10**6)["count"] == 3


def test_annotations_empty_upstream_list(monkeypatch):
    # Europe PMC answers 200 + [] for an id it does not know.
    monkeypatch.setattr(S, "europepmc_annotations", lambda a, t="": [])
    out = logic.europepmc_annotations("PMC1")
    assert out["ok"] is True and out["article"] is None
    assert out["annotations"] == [] and out["types"] == [] and out["count"] == 0


def test_annotations_unknown_type_is_article_with_empty_list(monkeypatch):
    # ...and for an unknown type name (probed 2026-09-02) the article object with
    # annotations: [] — truthfully passed through, never turned into an error.
    row = {
        "source": "MED",
        "extId": "16060722",
        "pmcid": "PMC1182327",
        "annotations": [],
    }
    monkeypatch.setattr(S, "europepmc_annotations", lambda a, t="": [row])
    out = logic.europepmc_annotations("16060722", type="NoSuchType")
    assert out["ok"] is True and out["type_filter"] == "NoSuchType"
    assert out["article"] == {
        "source": "MED",
        "ext_id": "16060722",
        "pmcid": "PMC1182327",
    }
    assert out["annotations"] == [] and out["count"] == 0
    assert "not proof of absence" in out["note"]


def test_annotations_upstream_error(monkeypatch):
    monkeypatch.setattr(S, "europepmc_annotations", raising(upstream(500)))
    out = logic.europepmc_annotations("PMC1")
    assert out == {
        "ok": False,
        "source": "europepmc",
        "article_id": "PMC:PMC1",
        "error": "upstream returned HTTP 500",
        "upstream_status": 500,
        "url": "https://api.example/x",
    }


@pytest.mark.parametrize("bad", ["", "10.1000/x", "PMC", "MED:1"])
def test_annotations_rejects_bad_id_without_network(monkeypatch, bad):
    monkeypatch.setattr(
        S, "europepmc_annotations", raising(AssertionError("no network"))
    )
    out = logic.europepmc_annotations(bad)
    assert out["ok"] is False and out["article_id"] is None
    assert out["upstream_status"] is None and "not a PMCID" in out["error"]
