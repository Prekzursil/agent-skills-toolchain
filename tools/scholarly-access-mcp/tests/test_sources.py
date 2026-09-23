"""Unit tests for scholarly_access.sources — every network call is mocked at
``requests.get``; no real network. Targets 100% line+branch coverage."""

from __future__ import annotations

import pytest
import requests

from scholarly_access import sources as S


class FakeResp:
    def __init__(
        self, status=200, json_data=None, text="", content=b"", raise_json=False
    ):
        self.status_code = status
        self._json = json_data
        self.text = text
        self.content = content
        self._raise_json = raise_json

    def json(self):
        if self._raise_json:
            raise ValueError("no json")
        return self._json


def set_get(monkeypatch, resp=None, *, exc=None):
    """Patch sources.requests.get to return ``resp`` (or raise ``exc``)."""

    def fake_get(url, params=None, headers=None, timeout=None):
        if exc is not None:
            raise exc
        return resp

    monkeypatch.setattr(S.requests, "get", fake_get)


# --------------------------------------------------------------------------- _get / _json
def test_get_success(monkeypatch):
    r = FakeResp(200)
    set_get(monkeypatch, r)
    assert S._get("http://x") is r


def test_get_non_200(monkeypatch):
    set_get(monkeypatch, FakeResp(404))
    assert S._get("http://x") is None


def test_get_exception(monkeypatch):
    set_get(monkeypatch, exc=requests.RequestException("boom"))
    assert S._get("http://x") is None


def test_get_with_headers(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["headers"] = headers
        return FakeResp(200)

    monkeypatch.setattr(S.requests, "get", fake_get)
    S._get("http://x", headers={"Authorization": "Bearer k"})
    assert captured["headers"]["Authorization"] == "Bearer k"


def test_json_none(monkeypatch):
    set_get(monkeypatch, FakeResp(500))
    assert S._json("http://x") is None


def test_json_ok(monkeypatch):
    set_get(monkeypatch, FakeResp(200, json_data={"a": 1}))
    assert S._json("http://x") == {"a": 1}


def test_json_value_error(monkeypatch):
    set_get(monkeypatch, FakeResp(200, raise_json=True))
    assert S._json("http://x") is None


def capture_get(monkeypatch, resp):
    """Patch requests.get to return ``resp`` and record the last call's arguments."""
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured.update(url=url, params=params, headers=headers, timeout=timeout)
        return resp

    monkeypatch.setattr(S.requests, "get", fake_get)
    return captured


def test_json_forwards_headers(monkeypatch):
    cap = capture_get(monkeypatch, FakeResp(200, json_data={}))
    assert S._json("http://x", headers={"Authorization": "Bearer k"}) == {}
    assert cap["headers"]["Authorization"] == "Bearer k"
    assert cap["headers"]["User-Agent"] == S.UA


# --------------------------------------------------------------------------- UpstreamError / _fetch / _fetch_json
def test_upstream_error_envelope():
    e = S.UpstreamError("boom", status=503, url="http://x")
    assert e.envelope() == {"error": "boom", "upstream_status": 503, "url": "http://x"}


def test_fetch_ok(monkeypatch):
    r = FakeResp(200)
    cap = capture_get(monkeypatch, r)
    assert S._fetch("http://x") is r
    assert cap["headers"] == {"User-Agent": S.UA}
    assert cap["timeout"] == S.TIMEOUT  # every request is timeout-bounded


def test_fetch_merges_headers(monkeypatch):
    cap = capture_get(monkeypatch, FakeResp(200))
    S._fetch("http://x", headers={"X-A": "1"})
    assert cap["headers"] == {"User-Agent": S.UA, "X-A": "1"}


def test_fetch_non_200_keeps_status(monkeypatch):
    set_get(monkeypatch, FakeResp(404))
    with pytest.raises(S.UpstreamError) as ei:
        S._fetch("http://x")
    assert ei.value.status == 404
    assert ei.value.url == "http://x"
    assert str(ei.value) == "upstream returned HTTP 404"


def test_fetch_request_exception_never_echoes_exception_text(monkeypatch):
    # The exception text could carry the request URL/query (an email, a key).
    set_get(monkeypatch, exc=requests.ConnectTimeout("http://x?api_key=SECRET"))
    with pytest.raises(S.UpstreamError) as ei:
        S._fetch("http://x")
    assert ei.value.status is None
    assert str(ei.value) == "request failed: ConnectTimeout"
    assert "SECRET" not in str(ei.value)


def test_fetch_json_ok(monkeypatch):
    set_get(monkeypatch, FakeResp(200, json_data=[1]))
    assert S._fetch_json("http://x") == [1]


def test_fetch_json_non_json_body(monkeypatch):
    set_get(monkeypatch, FakeResp(200, raise_json=True))
    with pytest.raises(S.UpstreamError) as ei:
        S._fetch_json("http://x")
    assert ei.value.status == 200
    assert "non-JSON" in str(ei.value)


# --------------------------------------------------------------------------- classify_identifier
@pytest.mark.parametrize(
    "raw,kind,val",
    [
        ("10.1371/journal.pmed.0020124", "doi", "10.1371/journal.pmed.0020124"),
        (
            "https://doi.org/10.1371/journal.pmed.0020124",
            "doi",
            "10.1371/journal.pmed.0020124",
        ),
        ("arxiv:1706.03762", "arxiv", "1706.03762"),
        ("arxiv 1706.03762v2", "arxiv", "1706.03762v2"),
        ("1706.03762", "arxiv", "1706.03762"),
        ("12345678", "pmid", "12345678"),
        ("see ref 10.1234/abc.def here", "doi", "10.1234/abc.def"),
        ("paper /abs/1706.03762 on arxiv", "arxiv", "1706.03762"),
        ("Attention Is All You Need", "title", "Attention Is All You Need"),
    ],
)
def test_classify(raw, kind, val):
    assert S.classify_identifier(raw) == (kind, val)


def test_classify_doi_prefix_no_match():
    # starts with '10.' but not a valid DOI -> falls through to title
    assert S.classify_identifier("10. not a doi") == ("title", "10. not a doi")


def test_classify_arxiv_prefix_no_match():
    assert S.classify_identifier("arxiv: nope") == ("title", "arxiv: nope")


def test_classify_arxiv_re_without_context():
    # contains an arxiv-like number but no 'arxiv'/'abs' context -> title
    assert S.classify_identifier("value 1706.03762 mixed in text x") == (
        "title",
        "value 1706.03762 mixed in text x",
    )


def test_classify_empty():
    assert S.classify_identifier("") == ("title", "")


# --------------------------------------------------------------------------- crossref
def test_crossref_by_doi_ok(monkeypatch):
    set_get(monkeypatch, FakeResp(200, json_data={"message": {"DOI": "x"}}))
    assert S.crossref_by_doi("10.1/x") == {"DOI": "x"}


def test_crossref_by_doi_none(monkeypatch):
    set_get(monkeypatch, FakeResp(500))
    assert S.crossref_by_doi("10.1/x") is None


def test_crossref_search_ok(monkeypatch):
    set_get(monkeypatch, FakeResp(200, json_data={"message": {"items": [{"a": 1}]}}))
    assert S.crossref_search("t") == [{"a": 1}]


def test_crossref_search_empty(monkeypatch):
    set_get(monkeypatch, FakeResp(200, json_data={"message": {}}))
    assert S.crossref_search("t") == []


def test_crossref_search_none(monkeypatch):
    set_get(monkeypatch, FakeResp(500))
    assert S.crossref_search("t") == []


# --------------------------------------------------------------------------- openalex
def test_openalex_by_doi(monkeypatch):
    set_get(monkeypatch, FakeResp(200, json_data={"id": "W1"}))
    assert S.openalex_by_doi("10.1/x") == {"id": "W1"}


def test_openalex_search_ok(monkeypatch):
    set_get(monkeypatch, FakeResp(200, json_data={"results": [{"id": "W1"}]}))
    assert S.openalex_search("t") == [{"id": "W1"}]


def test_openalex_search_none(monkeypatch):
    set_get(monkeypatch, FakeResp(500))
    assert S.openalex_search("t") == []


# --------------------------------------------------------------------------- openalex: OPENALEX_API_KEY
KEY = "oa-test-key-never-echoed"


def test_openalex_authenticated_flag(monkeypatch):
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    assert S.openalex_authenticated() is False
    assert S._openalex_headers() == {}
    monkeypatch.setenv("OPENALEX_API_KEY", KEY)
    assert S.openalex_authenticated() is True
    assert S._openalex_headers() == {"Authorization": f"Bearer {KEY}"}


def test_openalex_by_doi_key_present_sent_as_bearer_mailto_kept(monkeypatch):
    monkeypatch.setenv("OPENALEX_API_KEY", KEY)
    monkeypatch.setenv("UNPAYWALL_EMAIL", "a@b.c")
    cap = capture_get(monkeypatch, FakeResp(200, json_data={"id": "W1"}))
    out = S.openalex_by_doi("10.1/x")
    assert cap["headers"]["Authorization"] == f"Bearer {KEY}"
    assert cap["params"] == {"mailto": "a@b.c"}  # polite-pool id kept, key not in URL
    assert "api_key" not in cap["url"]
    assert KEY not in repr(out)  # never echoed


def test_openalex_by_doi_key_absent_not_sent(monkeypatch):
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    cap = capture_get(monkeypatch, FakeResp(200, json_data={"id": "W1"}))
    S.openalex_by_doi("10.1/x")
    assert "Authorization" not in cap["headers"]
    assert "api_key" not in cap["params"]


def test_openalex_search_key_present_then_absent(monkeypatch):
    cap = capture_get(monkeypatch, FakeResp(200, json_data={"results": []}))
    monkeypatch.setenv("OPENALEX_API_KEY", KEY)
    S.openalex_search("t")
    assert cap["headers"]["Authorization"] == f"Bearer {KEY}"
    assert cap["params"]["search"] == "t"
    monkeypatch.delenv("OPENALEX_API_KEY")
    S.openalex_search("t")
    assert "Authorization" not in cap["headers"]


# --------------------------------------------------------------------------- unpaywall
def test_unpaywall_no_email(monkeypatch):
    monkeypatch.delenv("UNPAYWALL_EMAIL", raising=False)
    assert S.unpaywall("10.1/x") is None


def test_unpaywall_ok(monkeypatch):
    monkeypatch.setenv("UNPAYWALL_EMAIL", "a@b.c")
    set_get(monkeypatch, FakeResp(200, json_data={"is_oa": True}))
    assert S.unpaywall("10.1/x") == {"is_oa": True}


# --------------------------------------------------------------------------- europepmc
def test_europepmc_ok(monkeypatch):
    set_get(
        monkeypatch, FakeResp(200, json_data={"resultList": {"result": [{"id": "1"}]}})
    )
    assert S.europepmc_search("q") == [{"id": "1"}]


def test_europepmc_none(monkeypatch):
    set_get(monkeypatch, FakeResp(500))
    assert S.europepmc_search("q") == []


def test_europepmc_fulltext_url():
    assert S.europepmc_fulltext_url("PMC1182327") == (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC1182327/fullTextXML"
    )


def test_europepmc_fulltext_xml_ok(monkeypatch):
    cap = capture_get(monkeypatch, FakeResp(200, text="<article/>"))
    assert S.europepmc_fulltext_xml("PMC1") == "<article/>"
    assert cap["url"] == S.europepmc_fulltext_url("PMC1")


def test_europepmc_fulltext_xml_404_raises_with_status(monkeypatch):
    set_get(monkeypatch, FakeResp(404))
    with pytest.raises(S.UpstreamError) as ei:
        S.europepmc_fulltext_xml("PMC1")
    assert ei.value.status == 404


def test_europepmc_annotations_params(monkeypatch):
    cap = capture_get(monkeypatch, FakeResp(200, json_data=[{"extId": "1"}]))
    assert S.europepmc_annotations("MED:1") == [{"extId": "1"}]
    assert cap["url"] == S.EUROPEPMC_ANNOTATIONS
    assert cap["params"] == {"articleIds": "MED:1", "format": "JSON"}
    S.europepmc_annotations("PMC:PMC1", "Diseases")
    assert cap["params"] == {
        "articleIds": "PMC:PMC1",
        "format": "JSON",
        "type": "Diseases",
    }


def test_europepmc_annotations_error(monkeypatch):
    set_get(monkeypatch, FakeResp(500))
    with pytest.raises(S.UpstreamError) as ei:
        S.europepmc_annotations("MED:1")
    assert ei.value.status == 500


# --------------------------------------------------------------------------- opencitations
def test_opencitations_index_url_and_sort(monkeypatch):
    cap = capture_get(monkeypatch, FakeResp(200, json_data=[{"oci": "1"}]))
    assert S.opencitations_index("citations", "10.1/x") == [{"oci": "1"}]
    assert cap["url"] == "https://api.opencitations.net/index/v2/citations/doi:10.1/x"
    assert cap["params"] == {"sort": "desc(creation)"}
    S.opencitations_index("references", "10.1/x")
    assert cap["url"] == "https://api.opencitations.net/index/v2/references/doi:10.1/x"


def test_opencitations_index_error_keeps_status(monkeypatch):
    set_get(monkeypatch, FakeResp(429))
    with pytest.raises(S.UpstreamError) as ei:
        S.opencitations_index("citations", "10.1/x")
    assert ei.value.status == 429


def test_opencitations_meta_joins_ids(monkeypatch):
    cap = capture_get(monkeypatch, FakeResp(200, json_data=[]))
    assert S.opencitations_meta(["10.1/a", "10.1/b"]) == []
    assert cap["url"] == (
        "https://api.opencitations.net/meta/v1/metadata/doi:10.1/a__doi:10.1/b"
    )


# --------------------------------------------------------------------------- arxiv
ATOM = """<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
<title>Attention Is All You Need</title>
<summary>We propose the Transformer.</summary>
<id>http://arxiv.org/abs/1706.03762</id>
<author><name>Ashish Vaswani</name></author>
<link title="pdf" href="http://arxiv.org/pdf/1706.03762"/>
<published>2017-06-12T00:00:00Z</published>
</entry>
</feed>"""

ATOM_PDF_BY_TYPE = """<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
<title>T</title>
<link type="application/pdf" href="http://arxiv.org/pdf/x"/>
</entry></feed>"""

ATOM_NO_PDF = """<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>T</title><link title="html" href="h"/></entry></feed>"""

ATOM_EMPTY = """<feed xmlns="http://www.w3.org/2005/Atom"></feed>"""


def test_arxiv_lookup_by_id(monkeypatch):
    set_get(monkeypatch, FakeResp(200, text=ATOM))
    out = S.arxiv_lookup(arxiv_id="1706.03762")
    assert out["title"] == "Attention Is All You Need"
    assert out["pdf_url"] == "http://arxiv.org/pdf/1706.03762"
    assert out["authors"] == ["Ashish Vaswani"]
    assert out["published"] == "2017"


def test_arxiv_lookup_by_title_pdf_type(monkeypatch):
    set_get(monkeypatch, FakeResp(200, text=ATOM_PDF_BY_TYPE))
    out = S.arxiv_lookup(title="T")
    assert out["pdf_url"] == "http://arxiv.org/pdf/x"


def test_arxiv_lookup_no_pdf(monkeypatch):
    set_get(monkeypatch, FakeResp(200, text=ATOM_NO_PDF))
    assert S.arxiv_lookup(arxiv_id="x")["pdf_url"] is None


def test_arxiv_lookup_get_none(monkeypatch):
    set_get(monkeypatch, FakeResp(500))
    assert S.arxiv_lookup(arxiv_id="x") is None


def test_arxiv_lookup_bad_xml(monkeypatch):
    set_get(monkeypatch, FakeResp(200, text="<not><closed>"))
    assert S.arxiv_lookup(arxiv_id="x") is None


def test_arxiv_lookup_no_entry(monkeypatch):
    set_get(monkeypatch, FakeResp(200, text=ATOM_EMPTY))
    assert S.arxiv_lookup(arxiv_id="x") is None


# --------------------------------------------------------------------------- semantic scholar
def test_semanticscholar_doi(monkeypatch):
    set_get(monkeypatch, FakeResp(200, json_data={"title": "T"}))
    assert S.semanticscholar(doi="10.1/x") == {"title": "T"}


def test_semanticscholar_arxiv(monkeypatch):
    set_get(monkeypatch, FakeResp(200, json_data={"title": "A"}))
    assert S.semanticscholar(arxiv="1706.03762") == {"title": "A"}


def test_semanticscholar_no_id():
    assert S.semanticscholar() is None


# --------------------------------------------------------------------------- core
def test_core_no_key(monkeypatch):
    monkeypatch.delenv("CORE_API_KEY", raising=False)
    assert S.core_search(doi="10.1/x") is None


def test_core_ok_doi(monkeypatch):
    monkeypatch.setenv("CORE_API_KEY", "k")
    set_get(monkeypatch, FakeResp(200, json_data={"results": [{"id": 1}]}))
    assert S.core_search(doi="10.1/x") == {"id": 1}


def test_core_ok_title_empty(monkeypatch):
    monkeypatch.setenv("CORE_API_KEY", "k")
    set_get(monkeypatch, FakeResp(200, json_data={"results": []}))
    assert S.core_search(title="t") is None


def test_core_get_none(monkeypatch):
    monkeypatch.setenv("CORE_API_KEY", "k")
    set_get(monkeypatch, FakeResp(500))
    assert S.core_search(doi="10.1/x") is None


def test_core_value_error(monkeypatch):
    monkeypatch.setenv("CORE_API_KEY", "k")
    set_get(monkeypatch, FakeResp(200, raise_json=True))
    assert S.core_search(doi="10.1/x") is None


# --------------------------------------------------------------------------- doaj
def test_doaj_ok(monkeypatch):
    set_get(monkeypatch, FakeResp(200, json_data={"results": [{"id": 1}]}))
    assert S.doaj_by_doi("10.1/x") == {"id": 1}


def test_doaj_empty(monkeypatch):
    set_get(monkeypatch, FakeResp(200, json_data={"results": []}))
    assert S.doaj_by_doi("10.1/x") is None


def test_doaj_none(monkeypatch):
    set_get(monkeypatch, FakeResp(500))
    assert S.doaj_by_doi("10.1/x") is None


# --------------------------------------------------------------------------- pubmed efetch
PM_XML = """<root><PubmedArticle><MedlineCitation><Article>
<ArticleTitle>The Title</ArticleTitle>
<Abstract><AbstractText>Part one.</AbstractText><AbstractText>Part two.</AbstractText></Abstract>
<Journal><Title>J Test</Title></Journal>
<PubDate><Year>2001</Year></PubDate>
<AuthorList><Author><ForeName>Jane</ForeName><LastName>Doe</LastName></Author></AuthorList>
</Article></MedlineCitation>
<PubmedData><ArticleIdList><ArticleId IdType="doi">10.1/x</ArticleId></ArticleIdList></PubmedData>
</PubmedArticle></root>"""

PM_XML_NO_DOI = """<root><PubmedArticle><MedlineCitation><Article>
<ArticleTitle>T</ArticleTitle></Article></MedlineCitation>
<PubmedData><ArticleIdList><ArticleId IdType="pubmed">99</ArticleId></ArticleIdList></PubmedData>
</PubmedArticle></root>"""

PM_XML_NO_ARTICLE = "<root><PubmedArticle></PubmedArticle></root>"


def test_pubmed_efetch_full(monkeypatch):
    monkeypatch.setenv("NCBI_API_KEY", "k")
    set_get(monkeypatch, FakeResp(200, text=PM_XML))
    out = S.pubmed_efetch("99")
    assert out["title"] == "The Title"
    assert out["abstract"] == "Part one. Part two."
    assert out["year"] == "2001"
    assert out["journal"] == "J Test"
    assert out["doi"] == "10.1/x"
    assert out["authors"] == ["Jane Doe"]


def test_pubmed_efetch_no_doi(monkeypatch):
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    set_get(monkeypatch, FakeResp(200, text=PM_XML_NO_DOI))
    assert S.pubmed_efetch("99")["doi"] is None


def test_pubmed_efetch_get_none(monkeypatch):
    set_get(monkeypatch, FakeResp(500))
    assert S.pubmed_efetch("99") is None


def test_pubmed_efetch_bad_xml(monkeypatch):
    set_get(monkeypatch, FakeResp(200, text="<bad"))
    assert S.pubmed_efetch("99") is None


def test_pubmed_efetch_no_article(monkeypatch):
    set_get(monkeypatch, FakeResp(200, text=PM_XML_NO_ARTICLE))
    assert S.pubmed_efetch("99") is None


# --------------------------------------------------------------------------- pubmed pmid_for_doi
def test_pmid_for_doi_ok(monkeypatch):
    set_get(
        monkeypatch, FakeResp(200, json_data={"esearchresult": {"idlist": ["123"]}})
    )
    assert S.pubmed_pmid_for_doi("10.1/x") == "123"


def test_pmid_for_doi_empty(monkeypatch):
    set_get(monkeypatch, FakeResp(200, json_data={"esearchresult": {"idlist": []}}))
    assert S.pubmed_pmid_for_doi("10.1/x") is None


def test_pmid_for_doi_none(monkeypatch):
    set_get(monkeypatch, FakeResp(500))
    assert S.pubmed_pmid_for_doi("10.1/x") is None


# --------------------------------------------------------------------------- zenodo
def test_zenodo_ok(monkeypatch):
    set_get(monkeypatch, FakeResp(200, json_data={"hits": {"hits": [{"id": 1}]}}))
    assert S.zenodo_by_doi("10.1/x") == {"id": 1}


def test_zenodo_empty(monkeypatch):
    set_get(monkeypatch, FakeResp(200, json_data={"hits": {"hits": []}}))
    assert S.zenodo_by_doi("10.1/x") is None


def test_zenodo_none(monkeypatch):
    set_get(monkeypatch, FakeResp(500))
    assert S.zenodo_by_doi("10.1/x") is None
