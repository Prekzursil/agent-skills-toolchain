"""Tool logic for the scholarly-access MCP. Pure functions returning JSON-able dicts,
so the test client can exercise them with no MCP transport. Every OA URL passes through
policy.assert_lawful before it is returned or fetched.
"""

from __future__ import annotations

import difflib
import hashlib
import os
from pathlib import Path
from typing import Any, Optional

import requests

from . import policy, sources as S


def _title_sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


# ---------------------------------------------------------------------------
# resolve / fetch_metadata
# ---------------------------------------------------------------------------
def _canonical_from_crossref(m: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": (m.get("title") or [""])[0],
        "authors": [
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in m.get("author", [])
        ],
        "year": str(
            (m.get("issued", {}).get("date-parts", [[None]])[0] or [None])[0] or ""
        ),
        "journal": (m.get("container-title") or [""])[0],
        "doi": (m.get("DOI") or "").lower() or None,
        "type": m.get("type"),
    }


def resolve(identifier: str) -> dict[str, Any]:
    """Canonical metadata + normalized identifiers + source confidence."""
    kind, val = S.classify_identifier(identifier)
    out: dict[str, Any] = {
        "input": identifier,
        "input_kind": kind,
        "identifiers": {},
        "sources_used": [],
    }

    meta: Optional[dict[str, Any]] = None
    if kind == "doi":
        out["identifiers"]["doi"] = val
        m = S.crossref_by_doi(val)
        if m:
            meta = _canonical_from_crossref(m)
            out["sources_used"].append("crossref")
        oa = S.openalex_by_doi(val)
        if oa:
            out["sources_used"].append("openalex")
            out["identifiers"]["openalex"] = oa.get("id")
            if not meta:
                meta = {
                    "title": oa.get("title"),
                    "year": str(oa.get("publication_year") or ""),
                    "doi": val,
                    "authors": [
                        a["author"]["display_name"] for a in oa.get("authorships", [])
                    ],
                }
        pmid = S.pubmed_pmid_for_doi(val)
        if pmid:
            out["identifiers"]["pmid"] = pmid
    elif kind == "pmid":
        out["identifiers"]["pmid"] = val
        pm = S.pubmed_efetch(val)
        if pm:
            out["sources_used"].append("pubmed")
            meta = {
                "title": pm["title"],
                "authors": pm["authors"],
                "year": pm["year"],
                "journal": pm["journal"],
                "doi": (pm.get("doi") or "").lower() or None,
            }
            if meta["doi"]:
                out["identifiers"]["doi"] = meta["doi"]
    elif kind == "arxiv":
        out["identifiers"]["arxiv"] = val
        ax = S.arxiv_lookup(arxiv_id=val)
        if ax:
            out["sources_used"].append("arxiv")
            meta = {
                "title": ax["title"],
                "authors": ax["authors"],
                "year": ax["published"],
                "journal": "arXiv",
                "doi": None,
            }
    else:  # title search — pick best candidate, but only accept above a relevance threshold
        THRESH = 0.55
        best, best_sim, best_src = None, 0.0, None
        for it in S.crossref_search(val, rows=5):
            cand = _canonical_from_crossref(it)
            sim = _title_sim(val, cand.get("title", ""))
            if sim > best_sim:
                best, best_sim, best_src = cand, sim, "crossref"
        for it in S.openalex_search(val, per_page=5):
            sim = _title_sim(val, it.get("title", ""))
            if sim > best_sim:
                best = {
                    "title": it.get("title"),
                    "year": str(it.get("publication_year") or ""),
                    "doi": (it.get("doi") or "").replace("https://doi.org/", "")
                    or None,
                    "authors": [],
                }
                best_sim, best_src = sim, "openalex"
        if best and best_sim >= THRESH:
            meta = best
            out["sources_used"].append(best_src)
            out["title_match_similarity"] = round(best_sim, 2)
            if meta.get("doi"):
                out["identifiers"]["doi"] = meta["doi"]
        elif best:
            out["best_rejected_match"] = {
                "title": best.get("title"),
                "similarity": round(best_sim, 2),
                "note": f"below relevance threshold {THRESH} — treated as unresolved",
            }

    if not meta:
        out["resolved"] = False
        out["confidence"] = 0.0
        return out
    out["resolved"] = True
    out["metadata"] = meta
    out["confidence"] = round(min(1.0, 0.5 + 0.25 * len(out["sources_used"])), 2)
    return out


def fetch_metadata(identifier: str) -> dict[str, Any]:
    """Full metadata incl. abstract + references where legally available."""
    r = resolve(identifier)
    if not r.get("resolved"):
        return r
    doi = r["identifiers"].get("doi")
    arxiv = r["identifiers"].get("arxiv")
    pmid = r["identifiers"].get("pmid")
    abstract = ""
    references: list[str] = []
    if pmid:
        pm = S.pubmed_efetch(pmid)
        if pm:
            abstract = pm.get("abstract", "")
    if not abstract and arxiv:
        ax = S.arxiv_lookup(arxiv_id=arxiv)
        if ax:
            abstract = ax.get("summary", "")
    s2 = S.semanticscholar(doi=doi or "", arxiv=arxiv or "")
    if s2:
        r["sources_used"].append("semanticscholar")
        abstract = abstract or (s2.get("abstract") or "")
        references = [
            x.get("title") for x in (s2.get("references") or []) if x.get("title")
        ][:50]
    r["abstract"] = abstract
    r["references"] = references
    return r


# ---------------------------------------------------------------------------
# find_oa_pdf — gather candidate OA URLs from legitimate sources, lawful-filter
# ---------------------------------------------------------------------------
def _candidates(doi: str, arxiv: str = "") -> list[dict[str, Any]]:
    """Collect candidate OA PDF URLs with provenance. Each is policy-checked by caller."""
    cands: list[dict[str, Any]] = []
    if arxiv:
        ax = S.arxiv_lookup(arxiv_id=arxiv)
        if ax and ax.get("pdf_url"):
            cands.append(
                {
                    "url": ax["pdf_url"],
                    "source": "arxiv",
                    "license": "arXiv",
                    "version": "preprint",
                }
            )
    if doi:
        up = S.unpaywall(doi)
        if up:
            for loc in [up.get("best_oa_location")] + (up.get("oa_locations") or []):
                if loc and loc.get("url_for_pdf"):
                    cands.append(
                        {
                            "url": loc["url_for_pdf"],
                            "source": "unpaywall",
                            "license": loc.get("license"),
                            "version": loc.get("version"),
                            "host_type": loc.get("host_type"),
                        }
                    )
        oa = S.openalex_by_doi(doi)
        if oa:
            loc = oa.get("best_oa_location") or {}
            if loc.get("pdf_url"):
                cands.append(
                    {
                        "url": loc["pdf_url"],
                        "source": "openalex",
                        "license": loc.get("license"),
                        "version": loc.get("version"),
                    }
                )
        s2 = S.semanticscholar(doi=doi, fields="openAccessPdf")
        if s2 and (s2.get("openAccessPdf") or {}).get("url"):
            cands.append(
                {
                    "url": s2["openAccessPdf"]["url"],
                    "source": "semanticscholar",
                    "license": None,
                }
            )
        core = S.core_search(doi=doi)
        if core and core.get("downloadUrl"):
            cands.append(
                {
                    "url": core["downloadUrl"],
                    "source": "core",
                    "license": core.get("license"),
                }
            )
        dj = S.doaj_by_doi(doi)
        if dj:
            for link in dj.get("bibjson", {}).get("link", []):
                if link.get("type") == "fulltext" and link.get("url"):
                    cands.append(
                        {
                            "url": link["url"],
                            "source": "doaj",
                            "license": "DOAJ-listed-OA",
                        }
                    )
    return cands


def find_oa_pdf(identifier: str = "", doi: str = "", arxiv: str = "") -> dict[str, Any]:
    """Return a single LAWFUL OA PDF URL (allowlisted host) + license/source/evidence, or none."""
    if identifier and not (doi or arxiv):
        r = resolve(identifier)
        doi = r.get("identifiers", {}).get("doi", "") or ""
        arxiv = r.get("identifiers", {}).get("arxiv", "") or ""
    evidence = []
    chosen = None
    for c in _candidates(doi, arxiv):
        if policy.is_denied(c["url"]):
            evidence.append(
                {
                    "url": c["url"],
                    "source": c["source"],
                    "verdict": "DENIED (shadow library) — skipped",
                }
            )
            continue
        if policy.is_allowed_host(c["url"]):
            evidence.append(
                {"url": c["url"], "source": c["source"], "verdict": "allowlisted OA"}
            )
            if chosen is None:
                chosen = c
        else:
            evidence.append(
                {
                    "url": c["url"],
                    "source": c["source"],
                    "verdict": "off-allowlist — not offered for download",
                }
            )
    return {
        "doi": doi or None,
        "arxiv": arxiv or None,
        "oa_pdf_url": chosen["url"] if chosen else None,
        "license": chosen.get("license") if chosen else None,
        "source": chosen.get("source") if chosen else None,
        "evidence": evidence,
        "policy": policy.POLICY_BANNER,
    }


# ---------------------------------------------------------------------------
# access_status — the honest classification
# ---------------------------------------------------------------------------
def access_status(
    identifier: str = "", doi: str = "", arxiv: str = ""
) -> dict[str, Any]:
    if identifier and not (doi or arxiv):
        r = resolve(identifier)
        if not r.get("resolved") and not r.get("identifiers", {}).get("doi"):
            return {
                "status": policy.UNKNOWN,
                "reason": "could not resolve identifier",
                "input": identifier,
            }
        doi = r.get("identifiers", {}).get("doi", "") or ""
        arxiv = r.get("identifiers", {}).get("arxiv", "") or ""

    oa = find_oa_pdf(doi=doi, arxiv=arxiv)
    if oa["oa_pdf_url"]:
        return {
            "status": policy.OA_PDF,
            "oa_pdf_url": oa["oa_pdf_url"],
            "license": oa["license"],
            "source": oa["source"],
            "doi": doi or None,
            "provenance": oa["evidence"],
        }

    # No lawful downloadable PDF. Decide free-to-read vs subscription vs unavailable.
    up = S.unpaywall(doi) if doi else None
    if up is not None:
        if up.get("is_oa"):
            return {
                "status": policy.FREE_NOT_REDIST,
                "reason": "is_oa=true but only a free-to-read page (no redistributable PDF on an allowlisted host); "
                "open the landing page in a browser — we do NOT circumvent the access control.",
                "oa_status": up.get("oa_status"),
                "landing_page": (up.get("best_oa_location") or {}).get("url"),
                "doi": doi,
                "provenance": oa["evidence"],
            }
        return {
            "status": policy.SUBSCRIPTION,
            "reason": "Unpaywall reports no open-access copy (paywalled). Cite only; no bypass.",
            "doi": doi,
            "provenance": oa["evidence"],
        }
    if not doi and arxiv:
        return {
            "status": policy.OA_PDF if oa["oa_pdf_url"] else policy.UNAVAILABLE,
            "doi": None,
            "arxiv": arxiv,
        }
    return {
        "status": policy.UNAVAILABLE if doi else policy.UNKNOWN,
        "reason": "no DOI / no OA signal located",
        "doi": doi or None,
    }


# ---------------------------------------------------------------------------
# citation_graph
# ---------------------------------------------------------------------------
def citation_graph(
    identifier: str = "", doi: str = "", limit: int = 50
) -> dict[str, Any]:
    if identifier and not doi:
        doi = resolve(identifier).get("identifiers", {}).get("doi", "") or ""
    refs: list[dict[str, Any]] = []
    cites: list[dict[str, Any]] = []
    src = None
    s2 = (
        S.semanticscholar(
            doi=doi,
            fields="references.title,references.externalIds,citations.title,citations.externalIds",
        )
        if doi
        else None
    )
    if s2:
        src = "semanticscholar"
        refs = [
            {"title": x.get("title"), "doi": (x.get("externalIds") or {}).get("DOI")}
            for x in (s2.get("references") or [])
        ][:limit]
        cites = [
            {"title": x.get("title"), "doi": (x.get("externalIds") or {}).get("DOI")}
            for x in (s2.get("citations") or [])
        ][:limit]
    elif doi:
        oa = S.openalex_by_doi(doi)
        if oa:
            src = "openalex"
            refs = [{"openalex": rid} for rid in (oa.get("referenced_works") or [])][
                :limit
            ]
    return {
        "doi": doi or None,
        "source": src,
        "references": refs,
        "cited_by": cites,
        "counts": {"references": len(refs), "cited_by": len(cites)},
    }


# ---------------------------------------------------------------------------
# download_oa_pdf — HARD-GATED
# ---------------------------------------------------------------------------
def download_oa_pdf(
    url: str,
    dest_dir: str = "",
    filename: str = "",
    license: str = "",
    source: str = "",
) -> dict[str, Any]:
    policy.assert_lawful(
        url
    )  # raises on denied/off-allowlist — never construct/fallback
    dest = Path(
        dest_dir or os.environ.get("SCHOLARLY_DOWNLOAD_DIR") or Path.cwd() / "oa_pdfs"
    )
    dest.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(
            url,
            headers={"User-Agent": S.UA, "Accept": "application/pdf"},
            timeout=120,
            allow_redirects=True,
        )
    except requests.RequestException as e:
        return {"ok": False, "error": f"fetch failed: {e}", "url": url}
    # Refuse anything that is not actually a PDF (no fake-OA, no HTML bot-wall page saved as "pdf").
    if r.status_code != 200 or not r.content[:5].startswith(b"%PDF"):
        return {
            "ok": False,
            "error": f"not a PDF (status {r.status_code}, magic {r.content[:5]!r}) — "
            "likely a bot-wall/landing page; refusing to save. Open the page in a browser instead.",
            "url": url,
        }
    name = filename or (url.rstrip("/").split("/")[-1] or "paper")
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    path = dest / name
    path.write_bytes(r.content)
    return {
        "ok": True,
        "path": str(path),
        "bytes": len(r.content),
        "sha256": hashlib.sha256(r.content).hexdigest(),
        "license": license or None,
        "source": source or None,
        "url": url,
    }


# ---------------------------------------------------------------------------
# summarize — assemble a digest from LEGALLY-available text (no full-text scraping)
# ---------------------------------------------------------------------------
def summarize(identifier: str = "", doi: str = "") -> dict[str, Any]:
    meta = fetch_metadata(identifier or doi)
    if not meta.get("resolved"):
        return meta
    m = meta.get("metadata", {})
    acc = access_status(
        doi=meta["identifiers"].get("doi", ""),
        arxiv=meta["identifiers"].get("arxiv", ""),
    )
    return {
        "title": m.get("title"),
        "authors": m.get("authors", [])[:8],
        "year": m.get("year"),
        "venue": m.get("journal"),
        "doi": m.get("doi"),
        "identifiers": meta["identifiers"],
        "abstract": meta.get("abstract") or "(no abstract legally available)",
        "access_status": acc.get("status"),
        "reference_count": len(meta.get("references", [])),
        "note": "Digest of legally-available metadata/abstract only — the calling agent writes the prose summary.",
    }


def batch_resolve(identifiers: list[str]) -> dict[str, Any]:
    rows = []
    unresolved = []
    for ident in identifiers:
        r = resolve(ident)
        if not r.get("resolved"):
            unresolved.append(ident)
            rows.append({"input": ident, "resolved": False})
            continue
        doi = r["identifiers"].get("doi", "")
        acc = access_status(doi=doi, arxiv=r["identifiers"].get("arxiv", ""))
        m = r.get("metadata", {})
        rows.append(
            {
                "input": ident,
                "resolved": True,
                "doi": doi or None,
                "title": m.get("title"),
                "year": m.get("year"),
                "access_status": acc.get("status"),
                "oa_pdf_url": acc.get("oa_pdf_url"),
            }
        )
    return {
        "count": len(identifiers),
        "resolved": len(identifiers) - len(unresolved),
        "unresolved": unresolved,
        "rows": rows,
    }
