#!/usr/bin/env python3
"""Fetch live search/fetch responses and vendor docs for RES-0169 captures."""
from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import common as C

UA = (
    "RES-0169-filter-matrix/1.0 "
    "(ast-integrate local measurement; mailto:res-0169@example.invalid)"
)
CTX = ssl.create_default_context()
TIMEOUT = 30
MAIL = "mailto=res-0169@example.invalid"
OA = f"https://api.openalex.org/works?search=transformer&per_page=10&{MAIL}"
WEN = (
    "https://en.wikipedia.org/w/api.php?action=query&list=search"
    "&srsearch=Newton&srlimit=10&format=json"
)
WDE = (
    "https://de.wikipedia.org/w/api.php?action=query&list=search"
    "&srsearch=Newton&srlimit=10&format=json"
)
CR = "https://api.crossref.org/works?query=transformer&rows=8"
AX = "http://export.arxiv.org/api/query?search_query=all:transformer&start=0&max_results=8"
PM = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    "?db=pubmed&term=transformer&retmax=10&retmode=json"
)
EP = (
    "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    "?query=transformer&format=json&pageSize=8"
)
GH = "https://api.github.com/search/repositories?q=transformer&per_page=5"
HN = "https://hn.algolia.com/api/v1/search?query=transformer&hitsPerPage=8"
YEAR = int(time.time()) - 365 * 24 * 3600

# capture_id, backend, kind, filter, method, url, body, extra_headers, parser_key, sleep
JOBS: list[dict] = [
    {"id": "openalex-unfiltered", "backend": "openalex", "kind": "live", "filter": None, "url": OA, "parser": "openalex", "sleep": 0.2},
    {"id": "openalex-language", "backend": "openalex", "kind": "live", "filter": "language", "url": OA + "&filter=language:de", "parser": "openalex", "sleep": 0.2},
    {"id": "openalex-recency", "backend": "openalex", "kind": "live", "filter": "recency", "url": OA + "&filter=from_publication_date:2025-01-01", "parser": "openalex", "sleep": 0.2},
    {"id": "openalex-region", "backend": "openalex", "kind": "live", "filter": "region", "url": OA + "&filter=institutions.country_code:jp", "parser": "openalex", "sleep": 0.2},
    {"id": "openalex-domain", "backend": "openalex", "kind": "live", "filter": "domain", "url": OA + "&filter=primary_location.source.id:s4306400194", "parser": "openalex", "sleep": 0.2},
    {"id": "wikipedia-en", "backend": "wikipedia", "kind": "live", "filter": None, "url": WEN, "parser": "wikipedia", "sleep": 0.15},
    {"id": "wikipedia-de", "backend": "wikipedia", "kind": "live", "filter": "language", "url": WDE, "parser": "wikipedia", "sleep": 0.15},
    {"id": "wikipedia-srdomain", "backend": "wikipedia", "kind": "live", "filter": "domain", "url": WEN + "&srdomain=arxiv.org", "parser": "wikipedia", "sleep": 0.15},
    {"id": "wikipedia-region", "backend": "wikipedia", "kind": "live", "filter": "region", "url": WEN + "&region=DE", "parser": "wikipedia", "sleep": 0.15},
    {"id": "wikipedia-srsince", "backend": "wikipedia", "kind": "live", "filter": "recency", "url": WEN + "&srsince=20240101", "parser": "wikipedia", "sleep": 0.15},
    {"id": "crossref-unfiltered", "backend": "crossref", "kind": "live", "filter": None, "url": CR, "parser": "crossref", "sleep": 0.4},
    {"id": "crossref-recency", "backend": "crossref", "kind": "live", "filter": "recency", "url": CR + "&filter=from-pub-date:2025-01-01", "parser": "crossref", "sleep": 0.4},
    {"id": "crossref-language", "backend": "crossref", "kind": "live", "filter": "language", "url": CR + "&filter=language:de", "parser": "crossref", "sleep": 0.4},
    {"id": "crossref-region", "backend": "crossref", "kind": "live", "filter": "region", "url": CR + "&region=DE", "parser": "crossref", "sleep": 0.4},
    {"id": "crossref-domain", "backend": "crossref", "kind": "live", "filter": "domain", "url": CR + "&filter=issn:0028-0836", "parser": "crossref", "sleep": 0.4},
    {"id": "arxiv-unfiltered", "backend": "arxiv", "kind": "live", "filter": None, "url": AX, "parser": "arxiv", "sleep": 0.2},
    {"id": "arxiv-recency", "backend": "arxiv", "kind": "live", "filter": "recency", "url": "http://export.arxiv.org/api/query?search_query=all:transformer+AND+submittedDate:[202501010000+TO+202612312359]&start=0&max_results=8", "parser": "arxiv", "sleep": 0.2},
    {"id": "arxiv-language", "backend": "arxiv", "kind": "live", "filter": "language", "url": AX + "&language=de", "parser": "arxiv", "sleep": 0.2},
    {"id": "arxiv-region", "backend": "arxiv", "kind": "live", "filter": "region", "url": AX + "&region=DE", "parser": "arxiv", "sleep": 0.2},
    {"id": "arxiv-domain", "backend": "arxiv", "kind": "live", "filter": "domain", "url": AX + "&domain=wikipedia.org", "parser": "arxiv", "sleep": 0.2},
    {"id": "pubmed-unfiltered", "backend": "pubmed", "kind": "live", "filter": None, "url": PM, "parser": "pubmed", "sleep": 0.4},
    {"id": "pubmed-language", "backend": "pubmed", "kind": "live", "filter": "language", "url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=transformer+AND+german%5Bla%5D&retmax=10&retmode=json", "parser": "pubmed", "sleep": 0.4},
    {"id": "pubmed-recency", "backend": "pubmed", "kind": "live", "filter": "recency", "url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=transformer&datetype=pdat&mindate=2025/01/01&maxdate=2026/12/31&retmax=10&retmode=json", "parser": "pubmed", "sleep": 0.4},
    {"id": "pubmed-region", "backend": "pubmed", "kind": "live", "filter": "region", "url": PM + "&region=DE", "parser": "pubmed", "sleep": 0.4},
    {"id": "pubmed-domain", "backend": "pubmed", "kind": "live", "filter": "domain", "url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=transformer+AND+Nature%5Bta%5D&retmax=10&retmode=json", "parser": "pubmed", "sleep": 0.4},
    {"id": "europepmc-unfiltered", "backend": "europepmc", "kind": "live", "filter": None, "url": EP, "parser": "europepmc", "sleep": 0.2},
    {"id": "europepmc-language", "backend": "europepmc", "kind": "live", "filter": "language", "url": "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=transformer%20LANG:deu&format=json&pageSize=8", "parser": "europepmc", "sleep": 0.2},
    {"id": "europepmc-recency", "backend": "europepmc", "kind": "live", "filter": "recency", "url": "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=transformer%20FIRST_PDATE:%5B2025-01-01%20TO%202026-12-31%5D&format=json&pageSize=8", "parser": "europepmc", "sleep": 0.2},
    {"id": "europepmc-region", "backend": "europepmc", "kind": "live", "filter": "region", "url": EP + "&region=DE", "parser": "europepmc", "sleep": 0.2},
    {"id": "europepmc-domain", "backend": "europepmc", "kind": "live", "filter": "domain", "url": "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=transformer%20JOURNAL:%22Nature%22&format=json&pageSize=8", "parser": "europepmc", "sleep": 0.2},
    {"id": "github-unfiltered", "backend": "github", "kind": "live", "filter": None, "url": GH, "parser": "github", "sleep": 0.3},
    {"id": "github-language", "backend": "github", "kind": "live", "filter": "language", "url": "https://api.github.com/search/repositories?q=transformer+language:rust&per_page=5", "parser": "github", "sleep": 0.3},
    {"id": "github-recency", "backend": "github", "kind": "live", "filter": "recency", "url": "https://api.github.com/search/repositories?q=transformer+created:%3E2025-01-01&per_page=5", "parser": "github", "sleep": 0.3},
    {"id": "github-domain", "backend": "github", "kind": "live", "filter": "domain", "url": GH + "&domain=arxiv.org", "parser": "github", "sleep": 0.3},
    {"id": "github-region", "backend": "github", "kind": "live", "filter": "region", "url": GH + "&region=DE", "parser": "github", "sleep": 0.3},
    {"id": "hn-unfiltered", "backend": "hn_algolia", "kind": "live", "filter": None, "url": HN, "parser": "hn_algolia", "sleep": 0.2},
    {"id": "hn-recency", "backend": "hn_algolia", "kind": "live", "filter": "recency", "url": HN + f"&numericFilters=created_at_i>{YEAR}", "parser": "hn_algolia", "sleep": 0.2},
    {"id": "hn-language", "backend": "hn_algolia", "kind": "live", "filter": "language", "url": HN + "&language=de", "parser": "hn_algolia", "sleep": 0.2},
    {"id": "hn-region", "backend": "hn_algolia", "kind": "live", "filter": "region", "url": HN + "&country=DE", "parser": "hn_algolia", "sleep": 0.2},
    {"id": "hn-domain", "backend": "hn_algolia", "kind": "live", "filter": "domain", "url": HN + "&domain=github.com", "parser": "hn_algolia", "sleep": 0.2},
    {"id": "auth-tavily", "backend": "tavily", "kind": "auth", "filter": None, "url": "https://api.tavily.com/search", "method": "POST", "data": {"query": "transformer", "max_results": 1}, "parser": None, "sleep": 0.2},
    {"id": "auth-exa", "backend": "exa", "kind": "auth", "filter": None, "url": "https://api.exa.ai/search", "method": "POST", "data": {"query": "transformer", "numResults": 1}, "parser": None, "sleep": 0.2},
    {"id": "auth-brave", "backend": "brave", "kind": "auth", "filter": None, "url": "https://api.search.brave.com/res/v1/web/search?q=transformer", "parser": None, "sleep": 0.2},
    {"id": "auth-searxng-localhost", "backend": "searxng", "kind": "auth", "filter": None, "url": "http://127.0.0.1:8080/search?q=transformer&format=json", "parser": None, "sleep": 0.1},
    {"id": "auth-ddg-html-challenge", "backend": "duckduckgo", "kind": "auth", "filter": None, "url": "https://html.duckduckgo.com/html/?q=transformer+paper", "parser": None, "sleep": 0.2},
    {"id": "docs-openalex-filters", "backend": "openalex", "kind": "docs", "url": "https://api.openalex.org/works?search=transformer&group_by=language&per_page=1&mailto=res-0169@example.invalid", "parser": None, "sleep": 0.2},
    {"id": "docs-mediawiki-search-paraminfo", "backend": "wikipedia", "kind": "docs", "url": "https://en.wikipedia.org/w/api.php?action=paraminfo&modules=query+search&format=json", "parser": None, "sleep": 0.15},
    {"id": "docs-crossref-rest-api", "backend": "crossref", "kind": "docs", "url": "https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/", "parser": None, "sleep": 0.2},
    {"id": "docs-arxiv-api-manual", "backend": "arxiv", "kind": "docs", "url": "https://info.arxiv.org/help/api/user-manual.html", "parser": None, "sleep": 0.2},
    {"id": "docs-pubmed-eutils", "backend": "pubmed", "kind": "docs", "url": "https://www.ncbi.nlm.nih.gov/books/NBK25499/", "parser": None, "sleep": 0.3},
    {"id": "docs-europepmc-restful", "backend": "europepmc", "kind": "docs", "url": "https://europepmc.org/RestfulWebService", "parser": None, "sleep": 0.2},
    {"id": "docs-github-repo-search", "backend": "github", "kind": "docs", "url": "https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories", "parser": None, "sleep": 0.2},
    {"id": "docs-hn-algolia-api", "backend": "hn_algolia", "kind": "docs", "url": "https://raw.githubusercontent.com/algolia/hn-search/master/README.md", "parser": None, "sleep": 0.2},
    {"id": "docs-tavily-search", "backend": "tavily", "kind": "docs", "url": "https://docs.tavily.com/documentation/api-reference/endpoint/search", "parser": None, "sleep": 0.2},
    {"id": "docs-exa-search", "backend": "exa", "kind": "docs", "url": "https://docs.exa.ai/reference/search", "parser": None, "sleep": 0.2},
    {"id": "docs-brave-web-search", "backend": "brave", "kind": "docs", "url": "https://brave.com/search/api/", "parser": None, "sleep": 0.2},
    {"id": "docs-searxng-search-api", "backend": "searxng", "kind": "docs", "url": "https://docs.searxng.org/dev/search_api.html", "parser": None, "sleep": 0.2},
    {"id": "docs-ddg-lite-challenge", "backend": "duckduckgo", "kind": "docs", "url": "https://lite.duckduckgo.com/lite/?q=transformer+architecture&df=y", "parser": None, "sleep": 0.2},
]


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_one(job: dict) -> dict:
    url = job["url"]
    method = job.get("method") or "GET"
    headers = {"User-Agent": UA, "Accept": "application/json,text/html;q=0.9,*/*;q=0.8"}
    data = None
    if job.get("data") is not None:
        data = json.dumps(job["data"]).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    fetched_at = utcnow()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX) as resp:
            raw = resp.read()
            status = int(resp.status)
            final = resp.geturl()
            err = None
    except urllib.error.HTTPError as exc:
        raw = exc.read() or b""
        status = int(exc.code)
        final = url
        err = f"HTTPError:{exc.code}"
    except Exception as exc:
        raw = f"{type(exc).__name__}:{exc}".encode("utf-8")
        status = None
        final = url
        err = f"{type(exc).__name__}:{exc}"
    C.CAP.mkdir(parents=True, exist_ok=True)
    (C.CAP / f"{job['id']}.raw").write_bytes(raw)
    text = raw.decode("utf-8", errors="replace")
    ids: list[str] = []
    count = None
    titles: list[str] = []
    parser_key = job.get("parser")
    if parser_key and status == 200:
        try:
            ids, count = C.PARSERS[parser_key](text)
        except Exception:
            ids, count = [], None
        if parser_key == "wikipedia":
            try:
                hits = ((json.loads(text).get("query") or {}).get("search") or [])
                titles = [str(x.get("title") or "") for x in hits]
            except Exception:
                titles = []
    row = {
        "id": job["id"],
        "backend": job.get("backend"),
        "kind": job.get("kind"),
        "filter": job.get("filter"),
        "url": url,
        "final_url": final,
        "method": method,
        "fetched_at": fetched_at,
        "http_status": status,
        "error": err,
        "sha256": C.sha256_bytes(raw),
        "bytes": len(raw),
        "ids": ids,
        "count": count,
        "titles": titles,
        "snippet": C.snippet_from(text, text[:12] if text else "empty"),
    }
    return row


def main() -> int:
    sources = []
    for job in JOBS:
        row = fetch_one(job)
        sources.append(row)
        print(
            f"{row['id']:36} st={row['http_status']} n={len(row['ids'])} "
            f"count={row['count']} bytes={row['bytes']} err={row['error']}"
        )
        time.sleep(float(job.get("sleep") or 0.1))
    index = {
        "unit_id": C.UNIT_ID,
        "fetched_at": utcnow(),
        "user_agent": UA,
        "note": "API key values were not read or written; env names only were considered absent.",
        "sources": sources,
    }
    C.INDEX.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {C.INDEX} sources={len(sources)}")
    # print classification preview
    for be in C.LIVE_BACKENDS:
        pc = C.positive_control_changed(index, be)
        print(f"PC {be}={pc}")
        for filt in C.FILTERS:
            cell = C.classify_cell(index, be, filt)
            print(
                f"  {be:12} {filt:8} {cell['verdict']:12} "
                f"changed={cell['strongly_changed']} jac={cell['id_jaccard']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
