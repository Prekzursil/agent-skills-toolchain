#!/usr/bin/env python3
"""Shared paths, parsers, and differential classification for RES-0169."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAP = HERE / "captures"
INDEX = CAP / "index.json"
ART_REL = (
    "command-center/research/deep-research-design/"
    "RES-0169-backend-filter-capability-matrix.json"
)
SCHEMA_REL = "command-center/schema/compatibility-matrix.schema.json"
SENTINEL = "SUCCESS:RES-0169"
UNIT_ID = "RES-0169"

FILTERS = ("domain", "language", "region", "recency")
LIVE_BACKENDS = (
    "openalex",
    "wikipedia",
    "crossref",
    "arxiv",
    "pubmed",
    "europepmc",
    "github",
    "hn_algolia",
)
UNREACHABLE_BACKENDS = (
    "tavily",
    "exa",
    "brave",
    "searxng",
    "duckduckgo",
)
BACKENDS = LIVE_BACKENDS + UNREACHABLE_BACKENDS

# (backend, filter) -> (unfiltered_capture_id, filtered_capture_id)
PAIRS: dict[tuple[str, str], tuple[str, str]] = {
    ("openalex", "language"): ("openalex-unfiltered", "openalex-language"),
    ("openalex", "region"): ("openalex-unfiltered", "openalex-region"),
    ("openalex", "recency"): ("openalex-unfiltered", "openalex-recency"),
    ("openalex", "domain"): ("openalex-unfiltered", "openalex-domain"),
    ("wikipedia", "language"): ("wikipedia-en", "wikipedia-de"),
    ("wikipedia", "domain"): ("wikipedia-en", "wikipedia-srdomain"),
    ("wikipedia", "region"): ("wikipedia-en", "wikipedia-region"),
    ("wikipedia", "recency"): ("wikipedia-en", "wikipedia-srsince"),
    ("crossref", "recency"): ("crossref-unfiltered", "crossref-recency"),
    ("crossref", "language"): ("crossref-unfiltered", "crossref-language"),
    ("crossref", "region"): ("crossref-unfiltered", "crossref-region"),
    ("crossref", "domain"): ("crossref-unfiltered", "crossref-domain"),
    ("arxiv", "recency"): ("arxiv-unfiltered", "arxiv-recency"),
    ("arxiv", "language"): ("arxiv-unfiltered", "arxiv-language"),
    ("arxiv", "region"): ("arxiv-unfiltered", "arxiv-region"),
    ("arxiv", "domain"): ("arxiv-unfiltered", "arxiv-domain"),
    ("pubmed", "language"): ("pubmed-unfiltered", "pubmed-language"),
    ("pubmed", "recency"): ("pubmed-unfiltered", "pubmed-recency"),
    ("pubmed", "region"): ("pubmed-unfiltered", "pubmed-region"),
    ("pubmed", "domain"): ("pubmed-unfiltered", "pubmed-domain"),
    ("europepmc", "language"): ("europepmc-unfiltered", "europepmc-language"),
    ("europepmc", "recency"): ("europepmc-unfiltered", "europepmc-recency"),
    ("europepmc", "region"): ("europepmc-unfiltered", "europepmc-region"),
    ("europepmc", "domain"): ("europepmc-unfiltered", "europepmc-domain"),
    ("github", "language"): ("github-unfiltered", "github-language"),
    ("github", "recency"): ("github-unfiltered", "github-recency"),
    ("github", "domain"): ("github-unfiltered", "github-domain"),
    ("github", "region"): ("github-unfiltered", "github-region"),
    ("hn_algolia", "recency"): ("hn-unfiltered", "hn-recency"),
    ("hn_algolia", "language"): ("hn-unfiltered", "hn-language"),
    ("hn_algolia", "region"): ("hn-unfiltered", "hn-region"),
    ("hn_algolia", "domain"): ("hn-unfiltered", "hn-domain"),
}

# First filter on each live backend that must change the set if the detector works.
POSITIVE_CONTROL_FILTER = {
    "openalex": "language",
    "wikipedia": "language",
    "crossref": "recency",
    "arxiv": "recency",
    "pubmed": "language",
    "europepmc": "language",
    "github": "language",
    "hn_algolia": "recency",
}

DOCS = {
    "openalex": "docs-openalex-filters",
    "wikipedia": "docs-mediawiki-search-paraminfo",
    "crossref": "docs-crossref-rest-api",
    "arxiv": "docs-arxiv-api-manual",
    "pubmed": "docs-pubmed-eutils",
    "europepmc": "docs-europepmc-restful",
    "github": "docs-github-repo-search",
    "hn_algolia": "docs-hn-algolia-api",
    "tavily": "docs-tavily-search",
    "exa": "docs-exa-search",
    "brave": "docs-brave-web-search",
    "searxng": "docs-searxng-search-api",
    "duckduckgo": "docs-ddg-lite-challenge",
}

AUTH = {
    "tavily": "auth-tavily",
    "exa": "auth-exa",
    "brave": "auth-brave",
    "searxng": "auth-searxng-localhost",
    "duckduckgo": "auth-ddg-html-challenge",
}

BANDS = (
    "Almost certain",
    "Highly likely",
    "Likely",
    "Even chance",
    "Unlikely",
    "Highly unlikely",
    "Remote",
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return sha256_bytes(raw), len(raw)


def load_index() -> dict:
    return json.loads(INDEX.read_text(encoding="utf-8"))


def capture_path(capture_id: str) -> Path:
    return CAP / f"{capture_id}.raw"


def load_capture_bytes(capture_id: str) -> bytes:
    path = capture_path(capture_id)
    if not path.is_file():
        raise FileNotFoundError(capture_id)
    return path.read_bytes()


def live_sha(capture_id: str) -> str:
    return sha256_bytes(load_capture_bytes(capture_id))


def row_by_id(index: dict, capture_id: str) -> dict:
    for row in index.get("sources") or []:
        if row.get("id") == capture_id:
            return row
    raise KeyError(capture_id)


def assert_snippet(index: dict, capture_id: str, snippet: str) -> dict:
    row = row_by_id(index, capture_id)
    raw = load_capture_bytes(capture_id)
    text = raw.decode("utf-8", errors="replace")
    if snippet not in text:
        raise AssertionError(f"snippet absent from {capture_id}: {snippet[:80]}")
    live = sha256_bytes(raw)
    recorded = str(row.get("sha256") or "")
    if recorded != live:
        raise AssertionError(
            f"lineage sha mismatch {capture_id}: recorded={recorded} live={live}"
        )
    return {**row, "text": text, "raw": raw, "live_sha256": live}


def parse_openalex(text: str) -> tuple[list[str], int | None]:
    d = json.loads(text)
    ids = [str(x.get("id")) for x in d.get("results") or [] if x.get("id")]
    count = (d.get("meta") or {}).get("count")
    return ids, int(count) if count is not None else None


def parse_wiki(text: str) -> tuple[list[str], int | None]:
    d = json.loads(text)
    hits = ((d.get("query") or {}).get("search") or [])
    ids = [str(x.get("pageid")) for x in hits if x.get("pageid") is not None]
    total = ((d.get("query") or {}).get("searchinfo") or {}).get("totalhits")
    return ids, int(total) if total is not None else None


def parse_crossref(text: str) -> tuple[list[str], int | None]:
    d = json.loads(text)
    msg = d.get("message") or {}
    ids = [str(x.get("DOI")) for x in msg.get("items") or [] if x.get("DOI")]
    total = msg.get("total-results")
    return ids, int(total) if total is not None else None


def parse_arxiv(text: str) -> tuple[list[str], int | None]:
    ids = re.findall(r"<id>(https?://arxiv.org/abs/[^<]+)</id>", text)
    m = re.search(r"<opensearch:totalResults[^>]*>(\d+)</opensearch:totalResults>", text)
    return ids, int(m.group(1)) if m else None


def parse_pubmed(text: str) -> tuple[list[str], int | None]:
    d = json.loads(text)
    es = d.get("esearchresult") or {}
    ids = [str(x) for x in es.get("idlist") or []]
    count = es.get("count")
    return ids, int(count) if count is not None else None


def parse_europepmc(text: str) -> tuple[list[str], int | None]:
    d = json.loads(text)
    hits = ((d.get("resultList") or {}).get("result") or [])
    ids = [str(x.get("id")) for x in hits if x.get("id")]
    total = d.get("hitCount")
    return ids, int(total) if total is not None else None


def parse_github(text: str) -> tuple[list[str], int | None]:
    d = json.loads(text)
    ids = [str(x.get("id")) for x in d.get("items") or [] if x.get("id") is not None]
    total = d.get("total_count")
    return ids, int(total) if total is not None else None


def parse_hn(text: str) -> tuple[list[str], int | None]:
    d = json.loads(text)
    ids = [str(x.get("objectID")) for x in d.get("hits") or [] if x.get("objectID")]
    total = d.get("nbHits")
    return ids, int(total) if total is not None else None


PARSERS = {
    "openalex": parse_openalex,
    "wikipedia": parse_wiki,
    "crossref": parse_crossref,
    "arxiv": parse_arxiv,
    "pubmed": parse_pubmed,
    "europepmc": parse_europepmc,
    "github": parse_github,
    "hn_algolia": parse_hn,
}


def jaccard(a: set[str], b: set[str]) -> float | None:
    if not a and not b:
        return None
    union = a | b
    if not union:
        return None
    return len(a & b) / len(union)


def strongly_changed(base: dict, filt: dict) -> bool:
    if int(base.get("http_status") or 0) != 200:
        return False
    if int(filt.get("http_status") or 0) != 200:
        return False
    cu, cf = base.get("count"), filt.get("count")
    if cu is not None and cf is not None:
        cu, cf = int(cu), int(cf)
        delta = abs(cu - cf)
        if cu != cf and delta >= max(10, int(0.05 * max(cu, cf, 1))):
            return True
    su, sf = set(base.get("ids") or []), set(filt.get("ids") or [])
    if not su and not sf:
        return False
    if not su or not sf:
        return True
    jac = jaccard(su, sf)
    return jac is not None and jac <= 0.5


def classify_pair(base: dict, filt: dict, positive_control_changed: bool) -> str:
    if int(base.get("http_status") or 0) != 200:
        return "UNREACHABLE"
    fst = filt.get("http_status")
    if fst is None:
        return "UNREACHABLE"
    if int(fst) >= 400:
        return "REJECTED"
    if int(fst) != 200:
        return "UNREACHABLE"
    if strongly_changed(base, filt):
        return "NATIVE"
    if positive_control_changed:
        return "IGNORED"
    return "UNREACHABLE"


def pair_stats(index: dict, backend: str, filt: str) -> dict:
    uid, fid = PAIRS[(backend, filt)]
    base = row_by_id(index, uid)
    other = row_by_id(index, fid)
    su, sf = set(base.get("ids") or []), set(other.get("ids") or [])
    changed = strongly_changed(base, other)
    return {
        "unfiltered": base,
        "filtered": other,
        "strongly_changed": changed,
        "id_jaccard": jaccard(su, sf),
        "count_unfiltered": base.get("count"),
        "count_filtered": other.get("count"),
        "unfiltered_capture_id": uid,
        "filtered_capture_id": fid,
    }


def positive_control_changed(index: dict, backend: str) -> bool:
    filt = POSITIVE_CONTROL_FILTER[backend]
    st = pair_stats(index, backend, filt)
    return bool(st["strongly_changed"])


def classify_cell(index: dict, backend: str, filt: str) -> dict:
    if backend in UNREACHABLE_BACKENDS:
        auth = AUTH[backend]
        docs = DOCS[backend]
        arow = row_by_id(index, auth)
        drow = row_by_id(index, docs)
        return {
            "backend": backend,
            "filter": filt,
            "verdict": "UNREACHABLE",
            "evidence_basis": "auth-probe",
            "positive_control_changed": False,
            "strongly_changed": False,
            "unfiltered_capture_id": auth,
            "filtered_capture_id": docs,
            "id_jaccard": None,
            "count_unfiltered": None,
            "count_filtered": None,
            "auth": arow,
            "docs": drow,
        }
    st = pair_stats(index, backend, filt)
    pc = positive_control_changed(index, backend)
    verdict = classify_pair(st["unfiltered"], st["filtered"], pc)
    return {
        "backend": backend,
        "filter": filt,
        "verdict": verdict,
        "evidence_basis": "differential-live",
        "positive_control_changed": pc,
        "strongly_changed": st["strongly_changed"],
        "unfiltered_capture_id": st["unfiltered_capture_id"],
        "filtered_capture_id": st["filtered_capture_id"],
        "id_jaccard": st["id_jaccard"],
        "count_unfiltered": st["count_unfiltered"],
        "count_filtered": st["count_filtered"],
        "unfiltered": st["unfiltered"],
        "filtered": st["filtered"],
        "docs": row_by_id(index, DOCS[backend]),
    }


def emulate_wikipedia_domain(index: dict) -> dict:
    """Client post-filter: keep only arxiv.org hosts from en.wikipedia search hits."""
    row = row_by_id(index, "wikipedia-en")
    titles = row.get("titles") or []
    urls = [
        "https://en.wikipedia.org/wiki/" + str(t).replace(" ", "_") for t in titles
    ]
    kept = [u for u in urls if "arxiv.org" in (urlparse(u).netloc or "")]
    return {
        "attempted": True,
        "changed": len(kept) != len(urls),
        "method": "post-filter en.wikipedia search URLs to netloc arxiv.org",
        "n_unfiltered": len(urls),
        "n_after": len(kept),
    }


def snippet_from(text: str, needle: str, width: int = 80) -> str:
    i = text.find(needle)
    if i < 0:
        body = text[:width]
        return body if len(body) >= 8 else ((text or "no-body") + "--------")[:width]
    start = max(0, i - 20)
    return text[start : start + width]
