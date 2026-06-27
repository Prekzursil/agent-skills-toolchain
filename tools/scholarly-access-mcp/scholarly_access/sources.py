"""Clients for LEGITIMATE scholarly sources only.

All keys are read by environment-variable NAME (never hard-coded). Missing key => that
source is skipped, never a failure. Every call is timeout-bounded and returns None on error
so the resolver degrades gracefully instead of crashing.

Sources: Crossref, OpenAlex, Unpaywall, Europe PMC, arXiv, Semantic Scholar (keyless),
CORE (keyed), DOAJ, PubMed/NCBI E-utilities, Zenodo. No shadow libraries.
"""

from __future__ import annotations

import os
import re
from typing import Any, Optional

import requests
from defusedxml.ElementTree import (
    fromstring as _safe_xml,
)  # XXE/billion-laughs-safe parse

UA = "scholarly-access-mcp/0.1 (mailto:%s)" % os.environ.get(
    "UNPAYWALL_EMAIL", "research@localhost"
)
TIMEOUT = 30


def _get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, Any] | None = None,
    timeout: int = TIMEOUT,
):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    try:
        r = requests.get(url, params=params, headers=h, timeout=timeout)
        if r.status_code == 200:
            return r
    except requests.RequestException:
        return None
    return None


def _json(url: str, **kw) -> Optional[Any]:
    r = _get(url, **kw)
    if r is None:
        return None
    try:
        return r.json()
    except ValueError:
        return None


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
def crossref_by_doi(doi: str) -> Optional[dict[str, Any]]:
    d = _json(
        f"https://api.crossref.org/works/{doi}",
        params={"mailto": os.environ.get("UNPAYWALL_EMAIL", "")},
    )
    return d.get("message") if d else None


def crossref_search(title: str, rows: int = 5) -> list[dict[str, Any]]:
    d = _json(
        "https://api.crossref.org/works",
        params={
            "query.bibliographic": title,
            "rows": rows,
            "mailto": os.environ.get("UNPAYWALL_EMAIL", ""),
        },
    )
    return (d.get("message", {}).get("items", []) if d else []) or []


# ---------------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------------
def openalex_by_doi(doi: str) -> Optional[dict[str, Any]]:
    return _json(
        f"https://api.openalex.org/works/https://doi.org/{doi}",
        params={"mailto": os.environ.get("UNPAYWALL_EMAIL", "")},
    )


def openalex_search(title: str, per_page: int = 5) -> list[dict[str, Any]]:
    d = _json(
        "https://api.openalex.org/works",
        params={
            "search": title,
            "per_page": per_page,
            "mailto": os.environ.get("UNPAYWALL_EMAIL", ""),
        },
    )
    return (d.get("results", []) if d else []) or []


# ---------------------------------------------------------------------------
# Unpaywall (OA discovery) — requires UNPAYWALL_EMAIL
# ---------------------------------------------------------------------------
def unpaywall(doi: str) -> Optional[dict[str, Any]]:
    email = os.environ.get("UNPAYWALL_EMAIL")
    if not email:
        return None
    return _json(f"https://api.unpaywall.org/v2/{doi}", params={"email": email})


# ---------------------------------------------------------------------------
# Europe PMC
# ---------------------------------------------------------------------------
def europepmc_search(query: str, page_size: int = 5) -> list[dict[str, Any]]:
    d = _json(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        params={"query": query, "format": "json", "pageSize": page_size},
    )
    return (d.get("resultList", {}).get("result", []) if d else []) or []


# ---------------------------------------------------------------------------
# arXiv (Atom XML)
# ---------------------------------------------------------------------------
_ATOM = "{http://www.w3.org/2005/Atom}"


def arxiv_lookup(arxiv_id: str = "", title: str = "") -> Optional[dict[str, Any]]:
    params = (
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
) -> Optional[dict[str, Any]]:
    pid = f"DOI:{doi}" if doi else (f"ARXIV:{arxiv}" if arxiv else "")
    if not pid:
        return None
    return _json(
        f"https://api.semanticscholar.org/graph/v1/paper/{pid}",
        params={"fields": fields},
    )


# ---------------------------------------------------------------------------
# CORE (keyed)
# ---------------------------------------------------------------------------
def core_search(doi: str = "", title: str = "") -> Optional[dict[str, Any]]:
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
        results = r.json().get("results", [])
    except ValueError:
        return None
    return results[0] if results else None


# ---------------------------------------------------------------------------
# DOAJ
# ---------------------------------------------------------------------------
def doaj_by_doi(doi: str) -> Optional[dict[str, Any]]:
    d = _json(f"https://doaj.org/api/search/articles/doi:{doi}")
    res = d.get("results", []) if d else []
    return res[0] if res else None


# ---------------------------------------------------------------------------
# PubMed / NCBI E-utilities (NCBI_API_KEY optional, raises limits)
# ---------------------------------------------------------------------------
def pubmed_efetch(pmid: str) -> Optional[dict[str, Any]]:
    params = {"db": "pubmed", "id": pmid, "retmode": "xml"}
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


def pubmed_pmid_for_doi(doi: str) -> Optional[str]:
    d = _json(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        params={"db": "pubmed", "term": f"{doi}[DOI]", "retmode": "json"},
    )
    ids = d.get("esearchresult", {}).get("idlist", []) if d else []
    return ids[0] if ids else None


# ---------------------------------------------------------------------------
# Zenodo
# ---------------------------------------------------------------------------
def zenodo_by_doi(doi: str) -> Optional[dict[str, Any]]:
    d = _json("https://zenodo.org/api/records", params={"q": f'doi:"{doi}"', "size": 1})
    hits = d.get("hits", {}).get("hits", []) if d else []
    return hits[0] if hits else None
