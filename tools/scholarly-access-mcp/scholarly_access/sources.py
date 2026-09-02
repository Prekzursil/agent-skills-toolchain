"""Clients for LEGITIMATE scholarly sources only.

All keys are read by environment-variable NAME (never hard-coded). Missing key => that
source is skipped, never a failure. Every call is timeout-bounded and returns None on error
so the resolver degrades gracefully instead of crashing.

Sources: Crossref, OpenAlex (OPENALEX_API_KEY optional), Unpaywall, Europe PMC (search,
full-text XML, annotations), arXiv, Semantic Scholar (keyless), CORE (keyed), DOAJ,
PubMed/NCBI E-utilities, Zenodo, OpenCitations (keyless, CC0). No shadow libraries.

Two fetch styles coexist on purpose. The resolver clients (`_get`/`_json`) return None on
any failure because a missing source must degrade, not crash. The newer per-source tools
(OpenCitations, Europe PMC full text / annotations) use `_fetch`/`_fetch_json`, which raise
`UpstreamError` carrying the real HTTP status so the tool can report a truthful error.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import cast

import requests
from defusedxml.ElementTree import (
    fromstring as _safe_xml,
)  # XXE/billion-laughs-safe parse

UA = "scholarly-access-mcp/0.1 (mailto:%s)" % os.environ.get(
    "UNPAYWALL_EMAIL", "research@localhost"
)
TIMEOUT = 30


# ---------------------------------------------------------------------------
# JSON shape helpers. External APIs return JSON whose static shape is unknown,
# so a parsed node is honestly typed as ``object``. These zero-branch casts let
# the call sites treat a node as the object / array the API contract says it is.
# They are identity at runtime (cast performs no check), so they never alter the
# control flow or values — only what the type checker knows.
# ---------------------------------------------------------------------------
def _obj(x: object) -> dict[str, object]:
    return cast("dict[str, object]", x)


def _arr(x: object) -> list[object]:
    return cast("list[object]", x)


def _get(
    url: str,
    *,
    params: Mapping[str, str | int] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: int = TIMEOUT,
) -> requests.Response | None:
    h: dict[str, str] = {"User-Agent": UA}
    if headers:
        h.update(headers)
    try:
        r = requests.get(url, params=params, headers=h, timeout=timeout)
        if r.status_code == 200:
            return r
    except requests.RequestException:
        return None
    return None


def _json(
    url: str,
    *,
    params: Mapping[str, str | int] | None = None,
    headers: Mapping[str, str] | None = None,
) -> object | None:
    r = _get(url, params=params, headers=headers)
    if r is None:
        return None
    try:
        return cast("object", r.json())
    except ValueError:
        return None


class UpstreamError(Exception):
    """A request that did not yield HTTP 200, keeping the truthful upstream status.

    ``status`` is the HTTP status code, or None when no response arrived (timeout,
    DNS, connection reset). The message never embeds the URL or the exception text,
    so nothing that might sit in a query string (an email, a key) can be echoed.
    """

    def __init__(self, message: str, *, status: int | None, url: str) -> None:
        super().__init__(message)
        self.status: int | None = status
        self.url: str = url

    def envelope(self) -> dict[str, object]:
        return {"error": str(self), "upstream_status": self.status, "url": self.url}


def _fetch(
    url: str,
    *,
    params: Mapping[str, str | int] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: int = TIMEOUT,
) -> requests.Response:
    """Like ``_get`` but raises ``UpstreamError`` instead of returning None."""
    h: dict[str, str] = {"User-Agent": UA}
    if headers:
        h.update(headers)
    try:
        r = requests.get(url, params=params, headers=h, timeout=timeout)
    except requests.RequestException as e:
        raise UpstreamError(
            f"request failed: {type(e).__name__}", status=None, url=url
        ) from e
    if r.status_code != 200:
        raise UpstreamError(
            f"upstream returned HTTP {r.status_code}", status=r.status_code, url=url
        )
    return r


def _fetch_json(url: str, *, params: Mapping[str, str | int] | None = None) -> object:
    r = _fetch(url, params=params)
    try:
        return cast("object", r.json())
    except ValueError as e:
        raise UpstreamError(
            "upstream returned HTTP 200 with a non-JSON body", status=200, url=url
        ) from e


# ---------------------------------------------------------------------------
# Identifier normalisation
# ---------------------------------------------------------------------------
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.I)
ARXIV_RE = re.compile(r"\b(\d{4}\.\d{4,5})(v\d+)?\b")
PMID_RE = re.compile(r"^\d{6,9}$")


def classify_identifier(s: str) -> tuple[str, str]:
    """Return (kind, value): kind in {doi, arxiv, pmid, title}."""
    s = (s or "").strip()
    low = s.lower()
    if low.startswith("10.") or "doi.org/" in low:
        m = DOI_RE.search(s)
        if m:
            return "doi", m.group(0).rstrip(".")
    if low.startswith("arxiv:") or low.startswith("arxiv "):
        m = ARXIV_RE.search(s)
        if m:
            return "arxiv", m.group(1) + (m.group(2) or "")
    # bare modern arXiv id (YYMM.NNNNN[vN]) — the whole string, no prefix
    if re.fullmatch(r"\d{4}\.\d{4,5}(v\d+)?", s):
        return "arxiv", s
    if PMID_RE.match(s):
        return "pmid", s
    m = DOI_RE.search(s)
    if m:
        return "doi", m.group(0).rstrip(".")
    m = ARXIV_RE.search(s)
    if m and ("arxiv" in low or "/abs/" in low):
        return "arxiv", m.group(1) + (m.group(2) or "")
    return "title", s


# ---------------------------------------------------------------------------
# Crossref
# ---------------------------------------------------------------------------
def crossref_by_doi(doi: str) -> dict[str, object] | None:
    d = _json(
        f"https://api.crossref.org/works/{doi}",
        params={"mailto": os.environ.get("UNPAYWALL_EMAIL", "")},
    )
    return _obj(_obj(d).get("message")) if d else None


def crossref_search(title: str, rows: int = 5) -> list[object]:
    d = _json(
        "https://api.crossref.org/works",
        params={
            "query.bibliographic": title,
            "rows": rows,
            "mailto": os.environ.get("UNPAYWALL_EMAIL", ""),
        },
    )
    return _arr((_obj(_obj(d).get("message", {})).get("items", []) if d else []) or [])


# ---------------------------------------------------------------------------
# OpenAlex — OPENALEX_API_KEY optional. OpenAlex now meters a free daily budget per
# key; keyless calls run on the smaller anonymous budget. The key may be sent as the
# `api_key` query parameter or as `Authorization: Bearer <key>` — "both work
# identically" (https://developers.openalex.org/guides/authentication, page dated
# 2026-08-19, read 2026-09-02). We send the header so the key never appears in a
# URL, a request log, or an exception message. `mailto` (polite-pool
# identification) is kept alongside it.
# ---------------------------------------------------------------------------
def openalex_authenticated() -> bool:
    """True iff OPENALEX_API_KEY is set, i.e. every OpenAlex call carries the key.

    Surfaced verbatim as ``openalex_authenticated`` in tool results; the key value
    itself is never returned or logged.
    """
    return bool(os.environ.get("OPENALEX_API_KEY"))


def _openalex_headers() -> dict[str, str]:
    key = os.environ.get("OPENALEX_API_KEY")
    return {"Authorization": f"Bearer {key}"} if key else {}


def openalex_by_doi(doi: str) -> dict[str, object] | None:
    return _obj(
        _json(
            f"https://api.openalex.org/works/https://doi.org/{doi}",
            params={"mailto": os.environ.get("UNPAYWALL_EMAIL", "")},
            headers=_openalex_headers(),
        )
    )


def openalex_search(title: str, per_page: int = 5) -> list[object]:
    d = _json(
        "https://api.openalex.org/works",
        params={
            "search": title,
            "per_page": per_page,
            "mailto": os.environ.get("UNPAYWALL_EMAIL", ""),
        },
        headers=_openalex_headers(),
    )
    return _arr((_obj(d).get("results", []) if d else []) or [])


# ---------------------------------------------------------------------------
# Unpaywall (OA discovery) — requires UNPAYWALL_EMAIL
# ---------------------------------------------------------------------------
def unpaywall(doi: str) -> dict[str, object] | None:
    email = os.environ.get("UNPAYWALL_EMAIL")
    if not email:
        return None
    return _obj(_json(f"https://api.unpaywall.org/v2/{doi}", params={"email": email}))


# ---------------------------------------------------------------------------
# Europe PMC — search, full-text XML (OA subset only), text-mined annotations.
# Endpoints probed 2026-09-02: fullTextXML returns JATS `<article>` for OA PMCIDs
# and HTTP 404 for anything else; annotationsByArticleIds returns a JSON list with
# one object per article — `[]` for an unknown id, and for an unknown `type` name the
# article object with an empty `annotations` list (HTTP 200 either way).
# ---------------------------------------------------------------------------
EUROPEPMC_REST = "https://www.ebi.ac.uk/europepmc/webservices/rest"
EUROPEPMC_ANNOTATIONS = (
    "https://www.ebi.ac.uk/europepmc/annotations_api/annotationsByArticleIds"
)


def europepmc_search(query: str, page_size: int = 5) -> list[object]:
    d = _json(
        f"{EUROPEPMC_REST}/search",
        params={"query": query, "format": "json", "pageSize": page_size},
    )
    return _arr(
        (_obj(_obj(d).get("resultList", {})).get("result", []) if d else []) or []
    )


def europepmc_fulltext_url(pmcid: str) -> str:
    return f"{EUROPEPMC_REST}/{pmcid}/fullTextXML"


def europepmc_fulltext_xml(pmcid: str) -> str:
    """Raw JATS XML for an open-access PMCID. Raises UpstreamError (404 = not in the
    OA full-text subset; Europe PMC serves nothing else, and neither do we)."""
    return _fetch(europepmc_fulltext_url(pmcid)).text


def europepmc_annotations(article_id: str, type_: str = "") -> list[object]:
    """Annotations API. ``article_id`` is ``SOURCE:ID`` (``MED:16060722`` for a PMID,
    ``PMC:PMC1182327`` for a PMCID); ``type_`` is an optional server-side filter such as
    ``Gene_Proteins`` or ``Diseases``. Raises UpstreamError."""
    params: dict[str, str | int] = {"articleIds": article_id, "format": "JSON"}
    if type_:
        params["type"] = type_
    return _arr(_fetch_json(EUROPEPMC_ANNOTATIONS, params=params))


# ---------------------------------------------------------------------------
# OpenCitations — keyless, CC0. The v2 Index lives on api.opencitations.net (the
# documented `opencitations.net/index/api/v2/...` path 301s there; probed 2026-09-02).
# Rows: {oci, citing, cited, creation, timespan, journal_sc, author_sc}, where
# `citing`/`cited` are space-separated id lists ("omid:br/... doi:10.... pmid:...").
# There is no limit parameter, so rows are sorted newest-first server-side and capped
# client-side by the caller. Meta v1 gives title/author/pub_date for `__`-joined ids;
# its `author` field reads "Surname, Given [orcid:... omid:...]; Surname, Given [...]".
# ---------------------------------------------------------------------------
OPENCITATIONS_INDEX = "https://api.opencitations.net/index/v2"
OPENCITATIONS_META = "https://api.opencitations.net/meta/v1/metadata"


def opencitations_index(kind: str, doi: str) -> list[object]:
    """``kind`` is ``citations`` (works citing ``doi``) or ``references`` (works ``doi``
    cites). Unknown DOIs yield ``[]`` upstream, not an error. Raises UpstreamError."""
    return _arr(
        _fetch_json(
            f"{OPENCITATIONS_INDEX}/{kind}/doi:{doi}",
            params={"sort": "desc(creation)"},
        )
    )


def opencitations_meta(dois: list[str]) -> list[object]:
    """Batch bibliographic metadata for up to a few dozen DOIs. Raises UpstreamError."""
    ids = "__".join(f"doi:{d}" for d in dois)
    return _arr(_fetch_json(f"{OPENCITATIONS_META}/{ids}"))


# ---------------------------------------------------------------------------
# arXiv (Atom XML)
# ---------------------------------------------------------------------------
_ATOM = "{http://www.w3.org/2005/Atom}"


def arxiv_lookup(arxiv_id: str = "", title: str = "") -> dict[str, object] | None:
    params: dict[str, str | int] = (
        {"id_list": arxiv_id}
        if arxiv_id
        else {"search_query": f"ti:{title}", "max_results": 1}
    )
    r = _get("http://export.arxiv.org/api/query", params=params)
    if r is None:
        return None
    try:
        root = _safe_xml(r.text)
    except Exception:
        return None
    e = root.find(f"{_ATOM}entry")
    if e is None:
        return None
    pdf = None
    for link in e.findall(f"{_ATOM}link"):
        if link.get("title") == "pdf" or link.get("type") == "application/pdf":
            pdf = link.get("href")
    return {
        "title": (e.findtext(f"{_ATOM}title") or "").strip(),
        "summary": (e.findtext(f"{_ATOM}summary") or "").strip(),
        "id": (e.findtext(f"{_ATOM}id") or "").strip(),
        "authors": [a.findtext(f"{_ATOM}name") for a in e.findall(f"{_ATOM}author")],
        "pdf_url": pdf,
        "published": (e.findtext(f"{_ATOM}published") or "")[:4],
    }


# ---------------------------------------------------------------------------
# Semantic Scholar (KEYLESS graph API — the provided key 403s, keyless works)
# ---------------------------------------------------------------------------
def semanticscholar(
    doi: str = "",
    arxiv: str = "",
    fields: str = "title,year,abstract,openAccessPdf,externalIds,references.title,citations.title",
) -> dict[str, object] | None:
    pid = f"DOI:{doi}" if doi else (f"ARXIV:{arxiv}" if arxiv else "")
    if not pid:
        return None
    return _obj(
        _json(
            f"https://api.semanticscholar.org/graph/v1/paper/{pid}",
            params={"fields": fields},
        )
    )


# ---------------------------------------------------------------------------
# CORE (keyed)
# ---------------------------------------------------------------------------
def core_search(doi: str = "", title: str = "") -> dict[str, object] | None:
    key = os.environ.get("CORE_API_KEY")
    if not key:
        return None
    q = f'doi:"{doi}"' if doi else title
    r = _get(
        "https://api.core.ac.uk/v3/search/works",
        params={"q": q, "limit": 3},
        headers={"Authorization": f"Bearer {key}"},
    )
    if r is None:
        return None
    try:
        results = _arr(_obj(cast("object", r.json())).get("results", []))
    except ValueError:
        return None
    return _obj(results[0]) if results else None


# ---------------------------------------------------------------------------
# DOAJ
# ---------------------------------------------------------------------------
def doaj_by_doi(doi: str) -> dict[str, object] | None:
    d = _json(f"https://doaj.org/api/search/articles/doi:{doi}")
    res = _arr(_obj(d).get("results", []) if d else [])
    return _obj(res[0]) if res else None


# ---------------------------------------------------------------------------
# PubMed / NCBI E-utilities (NCBI_API_KEY optional, raises limits)
# ---------------------------------------------------------------------------
def pubmed_efetch(pmid: str) -> dict[str, object] | None:
    params: dict[str, str | int] = {"db": "pubmed", "id": pmid, "retmode": "xml"}
    if os.environ.get("NCBI_API_KEY"):
        params["api_key"] = os.environ["NCBI_API_KEY"]
    r = _get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi", params=params)
    if r is None:
        return None
    try:
        root = _safe_xml(r.text)
    except Exception:
        return None
    art = root.find(".//Article")
    if art is None:
        return None
    doi = None
    for aid in root.findall(".//ArticleId"):
        if aid.get("IdType") == "doi":
            doi = aid.text
    return {
        "title": art.findtext("ArticleTitle") or "",
        "abstract": " ".join(t.text or "" for t in art.findall(".//AbstractText")),
        "year": (art.findtext(".//PubDate/Year") or ""),
        "journal": art.findtext(".//Journal/Title") or "",
        "doi": doi,
        "authors": [
            f"{a.findtext('ForeName') or ''} {a.findtext('LastName') or ''}".strip()
            for a in art.findall(".//Author")
        ],
    }


def pubmed_pmid_for_doi(doi: str) -> str | None:
    d = _json(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        params={"db": "pubmed", "term": f"{doi}[DOI]", "retmode": "json"},
    )
    ids = _arr(_obj(_obj(d).get("esearchresult", {})).get("idlist", []) if d else [])
    return str(ids[0]) if ids else None


# ---------------------------------------------------------------------------
# Zenodo
# ---------------------------------------------------------------------------
def zenodo_by_doi(doi: str) -> dict[str, object] | None:
    d = _json("https://zenodo.org/api/records", params={"q": f'doi:"{doi}"', "size": 1})
    hits = _arr(_obj(_obj(d).get("hits", {})).get("hits", []) if d else [])
    return _obj(hits[0]) if hits else None
