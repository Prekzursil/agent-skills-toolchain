"""Clients for scholarly sources — all sources enabled.

Sources: Crossref, OpenAlex, Unpaywall, Europe PMC, arXiv, Semantic Scholar,
CORE, DOAJ, PubMed/NCBI E-utilities, Zenodo, Sci-Hub (mirror failover),
LibGen, SciDownl-style direct fetch.
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Optional

import requests
from defusedxml.ElementTree import fromstring as _safe_xml

UA = "scholarly-access-mcp/0.2 (mailto:%s)" % os.environ.get("UNPAYWALL_EMAIL", "research@localhost")
TIMEOUT = 30


def _get(url: str, *, params: dict | None = None, headers: dict | None = None, timeout: int = TIMEOUT):
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
def crossref_by_doi(doi: str) -> Optional[dict]:
    d = _json(f"https://api.crossref.org/works/{doi}", params={"mailto": os.environ.get("UNPAYWALL_EMAIL", "")})
    return d.get("message") if d else None


def crossref_search(title: str, rows: int = 5) -> list[dict]:
    d = _json("https://api.crossref.org/works",
              params={"query.bibliographic": title, "rows": rows, "mailto": os.environ.get("UNPAYWALL_EMAIL", "")})
    return (d.get("message", {}).get("items", []) if d else []) or []


# ---------------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------------
def openalex_by_doi(doi: str) -> Optional[dict]:
    return _json(f"https://api.openalex.org/works/https://doi.org/{doi}",
                 params={"mailto": os.environ.get("UNPAYWALL_EMAIL", "")})


def openalex_search(title: str, per_page: int = 5) -> list[dict]:
    d = _json("https://api.openalex.org/works",
              params={"search": title, "per_page": per_page, "mailto": os.environ.get("UNPAYWALL_EMAIL", "")})
    return (d.get("results", []) if d else []) or []


# ---------------------------------------------------------------------------
# Unpaywall
# ---------------------------------------------------------------------------
def unpaywall(doi: str) -> Optional[dict]:
    email = os.environ.get("UNPAYWALL_EMAIL")
    if not email:
        return None
    return _json(f"https://api.unpaywall.org/v2/{doi}", params={"email": email})


# ---------------------------------------------------------------------------
# Europe PMC
# ---------------------------------------------------------------------------
def europepmc_search(query: str, page_size: int = 5) -> list[dict]:
    d = _json("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
              params={"query": query, "format": "json", "pageSize": page_size})
    return (d.get("resultList", {}).get("result", []) if d else []) or []


# ---------------------------------------------------------------------------
# arXiv (Atom XML)
# ---------------------------------------------------------------------------
_ATOM = "{http://www.w3.org/2005/Atom}"


def arxiv_lookup(arxiv_id: str = "", title: str = "") -> Optional[dict]:
    params = {"id_list": arxiv_id} if arxiv_id else {"search_query": f"ti:{title}", "max_results": 1}
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
# Semantic Scholar
# ---------------------------------------------------------------------------
def semanticscholar(doi: str = "", arxiv: str = "", fields: str = "title,year,abstract,openAccessPdf,externalIds,references.title,citations.title") -> Optional[dict]:
    pid = f"DOI:{doi}" if doi else (f"ARXIV:{arxiv}" if arxiv else "")
    if not pid:
        return None
    return _json(f"https://api.semanticscholar.org/graph/v1/paper/{pid}", params={"fields": fields})


# ---------------------------------------------------------------------------
# CORE (keyed)
# ---------------------------------------------------------------------------
def core_search(doi: str = "", title: str = "") -> Optional[dict]:
    key = os.environ.get("CORE_API_KEY")
    if not key:
        return None
    q = f'doi:"{doi}"' if doi else title
    r = _get("https://api.core.ac.uk/v3/search/works", params={"q": q, "limit": 3},
             headers={"Authorization": f"Bearer {key}"})
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
def doaj_by_doi(doi: str) -> Optional[dict]:
    d = _json(f"https://doaj.org/api/search/articles/doi:{doi}")
    res = (d.get("results", []) if d else [])
    return res[0] if res else None


# ---------------------------------------------------------------------------
# PubMed / NCBI E-utilities
# ---------------------------------------------------------------------------
def pubmed_efetch(pmid: str) -> Optional[dict]:
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
    d = _json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
              params={"db": "pubmed", "term": f"{doi}[DOI]", "retmode": "json"})
    ids = (d.get("esearchresult", {}).get("idlist", []) if d else [])
    return ids[0] if ids else None


# ---------------------------------------------------------------------------
# Zenodo
# ---------------------------------------------------------------------------
def zenodo_by_doi(doi: str) -> Optional[dict]:
    d = _json("https://zenodo.org/api/records", params={"q": f'doi:"{doi}"', "size": 1})
    hits = (d.get("hits", {}).get("hits", []) if d else [])
    return hits[0] if hits else None


# ---------------------------------------------------------------------------
# Sci-Hub (mirror failover)
# ---------------------------------------------------------------------------
SCIHUB_MIRRORS = [m.strip() for m in [
    os.environ.get("SCIHUB_MIRROR", "https://sci-hub.se"),
    "https://sci-hub.st",
    "https://sci-hub.ru",
    "https://sci-hub.mksa.top",
    "https://sci-hub.wf",
    "https://sci-hub.ren",
    "https://sci-hub.ee",
] if m and m.strip()]


def scihub_pdf_url(doi: str) -> Optional[dict]:
    """Try Sci-Hub mirrors in order. Returns {url, mirror} or None."""
    if not doi:
        return None
    for mirror in SCIHUB_MIRRORS:
        try:
            r = requests.get(f"{mirror}/{doi}", headers={"User-Agent": UA}, timeout=20, allow_redirects=True)
            if r.status_code != 200:
                continue
            # Direct PDF response
            if r.content[:5].startswith(b"%PDF"):
                return {"url": f"{mirror}/{doi}", "mirror": mirror}
            # Embedded PDF URL in page (iframe/embed/object src)
            m = re.search(r'(?:src|href)=["\']?(https?://[^"\'>\s]+\.pdf[^"\'>\s]*)', r.text, re.I)
            if m:
                return {"url": m.group(1), "mirror": mirror}
            m = re.search(r'(?:src|href)=["\']?(//[^"\'>\s]+\.pdf[^"\'>\s]*)', r.text, re.I)
            if m:
                return {"url": "https:" + m.group(1), "mirror": mirror}
            # Embedded button/link with onclick or data-url
            m = re.search(r'location\.href\s*=\s*["\']?(https?://[^"\'>\s]+\.pdf[^"\'>\s]*)', r.text, re.I)
            if m:
                return {"url": m.group(1), "mirror": mirror}
        except requests.RequestException:
            continue
    return None


# ---------------------------------------------------------------------------
# LibGen (mirror failover)
# ---------------------------------------------------------------------------
LIBGEN_MIRRORS = [m.strip() for m in [
    os.environ.get("LIBGEN_MIRROR", "https://libgen.rs"),
    "https://libgen.is",
    "https://libgen.st",
    "https://libgen.li",
] if m and m.strip()]


def libgen_search(doi: str = "", title: str = "") -> Optional[dict]:
    """Search LibGen by DOI or title. Returns {download_url, title, ...} or None."""
    query = doi or title
    if not query:
        return None
    for mirror in LIBGEN_MIRRORS:
        try:
            # LibGen JSON API
            search_url = f"{mirror}/json.php"
            params = {"fields": "Title,Author,MD5,Extension,Filesize",
                      "limit1": "5"}
            if doi:
                params["doi"] = doi
            else:
                params["title"] = title
            r = requests.get(search_url, params=params, headers={"User-Agent": UA}, timeout=20)
            if r.status_code != 200:
                # Try the search page fallback
                r2 = requests.get(f"{mirror}/search.php",
                                  params={"req": query, "res": 5, "column": "doi" if doi else "title"},
                                  headers={"User-Agent": UA}, timeout=20)
                if r2.status_code != 200:
                    continue
                # Parse MD5 from results page
                md5s = re.findall(r'/book/index\.php\?md5=([A-Fa-f0-9]{32})', r2.text)
                if not md5s:
                    md5s = re.findall(r'md5=([A-Fa-f0-9]{32})', r2.text)
                if md5s:
                    dl_url = f"https://library.lol/main/{md5s[0]}"
                    return {"download_page": dl_url, "md5": md5s[0], "mirror": mirror, "source": "libgen"}
                continue
            data = r.json()
            if isinstance(data, list) and data:
                item = data[0]
                md5 = item.get("MD5") or item.get("md5", "")
                if md5:
                    return {
                        "download_page": f"https://library.lol/main/{md5}",
                        "md5": md5,
                        "title": item.get("Title", ""),
                        "author": item.get("Author", ""),
                        "mirror": mirror,
                        "source": "libgen",
                    }
        except (requests.RequestException, ValueError):
            continue
    return None


def libgen_download_url(md5_or_page_url: str) -> Optional[str]:
    """Resolve a library.lol page to a direct download URL."""
    url = md5_or_page_url
    if not url.startswith("http"):
        url = f"https://library.lol/main/{md5_or_page_url}"
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20, allow_redirects=True)
        if r.status_code != 200:
            return None
        m = re.search(r'href=["\']?(https?://[^"\'>]+)["\']?\s*>\s*GET', r.text, re.I)
        if m:
            return m.group(1)
        m = re.search(r'href=["\']?(https?://download[^"\'>]+)', r.text, re.I)
        if m:
            return m.group(1)
    except requests.RequestException:
        pass
    return None


# ---------------------------------------------------------------------------
# SciDownl-style direct DOI fetch (follows DOI redirect + scrapes PDF link)
# ---------------------------------------------------------------------------
def scidownl_fetch(doi: str) -> Optional[dict]:
    """Try to get a PDF directly from the publisher page via DOI redirect.
    Looks for PDF links on the landing page. Returns {url, source} or None."""
    if not doi:
        return None
    try:
        r = requests.get(f"https://doi.org/{doi}",
                         headers={"User-Agent": UA, "Accept": "text/html"},
                         timeout=20, allow_redirects=True)
        if r.status_code != 200:
            return None
        # Direct PDF
        if r.content[:5].startswith(b"%PDF"):
            return {"url": r.url, "source": "direct-doi"}
        # Look for PDF links on the page
        for pattern in [
            r'href=["\']?([^"\'>]+\.pdf(?:\?[^"\'>]*)?)["\']?',
            r'data-pdf-url=["\']?([^"\'>]+)',
            r'citation_pdf_url["\s]+content=["\']?([^"\'>]+)',
            r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)',
        ]:
            m = re.search(pattern, r.text, re.I)
            if m:
                pdf_url = m.group(1)
                if not pdf_url.startswith("http"):
                    from urllib.parse import urljoin
                    pdf_url = urljoin(r.url, pdf_url)
                return {"url": pdf_url, "source": "publisher-page"}
    except requests.RequestException:
        pass
    return None
