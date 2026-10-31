"""Tool logic for the scholarly-access MCP. Pure functions returning JSON-able dicts,
so the test client can exercise them with no MCP transport. Every OA URL passes through
policy.assert_lawful before it is returned or fetched.
"""

from __future__ import annotations

import difflib
import hashlib
import os
from pathlib import Path
from typing import cast

import requests

from . import policy, sources as S


# External-API JSON nodes are honestly typed as ``object``; these zero-branch
# casts treat a node as the object / array its API contract specifies. They are
# identity at runtime, so control flow and values are unchanged.
def _obj(x: object) -> dict[str, object]:
    return cast("dict[str, object]", x)


def _arr(x: object) -> list[object]:
    return cast("list[object]", x)


def _title_sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


# ---------------------------------------------------------------------------
# resolve / fetch_metadata
# ---------------------------------------------------------------------------
def _canonical_from_crossref(m: dict[str, object]) -> dict[str, object]:
    return {
        "title": (_arr(m.get("title")) or [""])[0],
        "authors": [
            f"{_obj(a).get('given', '')} {_obj(a).get('family', '')}".strip()
            for a in _arr(m.get("author", []))
        ],
        "year": str(
            _arr(
                _arr(_obj(m.get("issued", {})).get("date-parts", [[None]]))[0] or [None]
            )[0]
            or ""
        ),
        "journal": (_arr(m.get("container-title")) or [""])[0],
        "doi": str(m.get("DOI") or "").lower() or None,
        "type": m.get("type"),
    }


def resolve(identifier: str) -> dict[str, object]:
    """Canonical metadata + normalized identifiers + source confidence."""
    kind, val = S.classify_identifier(identifier)
    identifiers: dict[str, object] = {}
    sources_used: list[object] = []
    out: dict[str, object] = {
        "input": identifier,
        "input_kind": kind,
        "identifiers": identifiers,
        "sources_used": sources_used,
    }

    meta: dict[str, object] | None = None
    if kind == "doi":
        identifiers["doi"] = val
        m = S.crossref_by_doi(val)
        if m:
            meta = _canonical_from_crossref(m)
            sources_used.append("crossref")
        oa = S.openalex_by_doi(val)
        if oa:
            sources_used.append("openalex")
            identifiers["openalex"] = oa.get("id")
            if not meta:
                meta = {
                    "title": oa.get("title"),
                    "year": str(oa.get("publication_year") or ""),
                    "doi": val,
                    "authors": [
                        _obj(_obj(a)["author"])["display_name"]
                        for a in _arr(oa.get("authorships", []))
                    ],
                }
        pmid = S.pubmed_pmid_for_doi(val)
        if pmid:
            identifiers["pmid"] = pmid
    elif kind == "pmid":
        identifiers["pmid"] = val
        pm = S.pubmed_efetch(val)
        if pm:
            sources_used.append("pubmed")
            pm_doi = str(pm.get("doi") or "").lower() or None
            meta = {
                "title": pm.get("title"),
                "authors": pm.get("authors"),
                "year": pm.get("year"),
                "journal": pm.get("journal"),
                "doi": pm_doi,
            }
            if pm_doi:
                identifiers["doi"] = pm_doi
    elif kind == "arxiv":
        identifiers["arxiv"] = val
        ax = S.arxiv_lookup(arxiv_id=val)
        if ax:
            sources_used.append("arxiv")
            meta = {
                "title": ax.get("title"),
                "authors": ax.get("authors"),
                "year": ax.get("published"),
                "journal": "arXiv",
                "doi": None,
            }
    else:  # title search — pick best candidate, but only accept above a relevance threshold
        THRESH = 0.55
        best: dict[str, object] | None = None
        best_sim: float = 0.0
        best_src: str | None = None
        for it in S.crossref_search(val, rows=5):
            cand = _canonical_from_crossref(_obj(it))
            sim = _title_sim(val, str(cand.get("title", "")))
            if sim > best_sim:
                best, best_sim, best_src = cand, sim, "crossref"
        for it in S.openalex_search(val, per_page=5):
            ito = _obj(it)
            sim = _title_sim(val, str(ito.get("title", "")))
            if sim > best_sim:
                best = {
                    "title": ito.get("title"),
                    "year": str(ito.get("publication_year") or ""),
                    "doi": str(ito.get("doi") or "").replace("https://doi.org/", "")
                    or None,
                    "authors": [],
                }
                best_sim, best_src = sim, "openalex"
        if best and best_sim >= THRESH:
            meta = best
            sources_used.append(best_src)
            out["title_match_similarity"] = round(best_sim, 2)
            if meta.get("doi"):
                identifiers["doi"] = meta["doi"]
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
    out["confidence"] = round(min(1.0, 0.5 + 0.25 * len(sources_used)), 2)
    return out


def fetch_metadata(identifier: str) -> dict[str, object]:
    """Full metadata incl. abstract + references where legally available."""
    r = resolve(identifier)
    if not r.get("resolved"):
        return r
    identifiers = _obj(r["identifiers"])
    doi = identifiers.get("doi")
    arxiv = identifiers.get("arxiv")
    pmid = identifiers.get("pmid")
    abstract = ""
    references: list[object] = []
    if pmid:
        pm = S.pubmed_efetch(str(pmid))
        if pm:
            abstract = str(pm.get("abstract", ""))
    if not abstract and arxiv:
        ax = S.arxiv_lookup(arxiv_id=str(arxiv))
        if ax:
            abstract = str(ax.get("summary", ""))
    s2 = S.semanticscholar(doi=str(doi or ""), arxiv=str(arxiv or ""))
    if s2:
        _arr(r["sources_used"]).append("semanticscholar")
        abstract = abstract or str(s2.get("abstract") or "")
        references = [
            _obj(x).get("title")
            for x in _arr(s2.get("references") or [])
            if _obj(x).get("title")
        ][:50]
    r["abstract"] = abstract
    r["references"] = references
    return r


# ---------------------------------------------------------------------------
# find_oa_pdf — gather candidate OA URLs from legitimate sources, lawful-filter
# ---------------------------------------------------------------------------
def _candidates(doi: str, arxiv: str = "") -> list[dict[str, object]]:
    """Collect candidate OA PDF URLs with provenance. Each is policy-checked by caller."""
    cands: list[dict[str, object]] = []
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
            for loc in [
                up.get("best_oa_location"),
                *_arr(up.get("oa_locations") or []),
            ]:
                lo = _obj(loc)
                if loc and lo.get("url_for_pdf"):
                    cands.append(
                        {
                            "url": lo["url_for_pdf"],
                            "source": "unpaywall",
                            "license": lo.get("license"),
                            "version": lo.get("version"),
                            "host_type": lo.get("host_type"),
                        }
                    )
        oa = S.openalex_by_doi(doi)
        if oa:
            best_loc = _obj(oa.get("best_oa_location") or {})
            if best_loc.get("pdf_url"):
                cands.append(
                    {
                        "url": best_loc["pdf_url"],
                        "source": "openalex",
                        "license": best_loc.get("license"),
                        "version": best_loc.get("version"),
                    }
                )
        s2 = S.semanticscholar(doi=doi, fields="openAccessPdf")
        if s2 and _obj(s2.get("openAccessPdf") or {}).get("url"):
            cands.append(
                {
                    "url": _obj(s2["openAccessPdf"])["url"],
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
            for link in _arr(_obj(dj.get("bibjson", {})).get("link", [])):
                lk = _obj(link)
                if lk.get("type") == "fulltext" and lk.get("url"):
                    cands.append(
                        {
                            "url": lk["url"],
                            "source": "doaj",
                            "license": "DOAJ-listed-OA",
                        }
                    )
    return cands


def find_oa_pdf(
    identifier: str = "", doi: str = "", arxiv: str = ""
) -> dict[str, object]:
    """Return a single LAWFUL OA PDF URL (allowlisted host) + license/source/evidence, or none."""
    if identifier and not (doi or arxiv):
        r = resolve(identifier)
        ids = _obj(r.get("identifiers", {}))
        doi = str(ids.get("doi", "") or "")
        arxiv = str(ids.get("arxiv", "") or "")
    evidence: list[object] = []
    chosen: dict[str, object] | None = None
    for c in _candidates(doi, arxiv):
        url = str(c["url"])
        if policy.is_denied(url):
            evidence.append(
                {
                    "url": c["url"],
                    "source": c["source"],
                    "verdict": "DENIED (shadow library) — skipped",
                }
            )
            continue
        if policy.is_allowed_host(url):
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
) -> dict[str, object]:
    if identifier and not (doi or arxiv):
        r = resolve(identifier)
        ids = _obj(r.get("identifiers", {}))
        if not r.get("resolved") and not ids.get("doi"):
            return {
                "status": policy.UNKNOWN,
                "reason": "could not resolve identifier",
                "input": identifier,
            }
        doi = str(ids.get("doi", "") or "")
        arxiv = str(ids.get("arxiv", "") or "")

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
                "reason": (
                    "is_oa=true but only a free-to-read page (no redistributable PDF on an allowlisted host); "
                    + "open the landing page in a browser — we do NOT circumvent the access control."
                ),
                "oa_status": up.get("oa_status"),
                "landing_page": _obj(up.get("best_oa_location") or {}).get("url"),
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
) -> dict[str, object]:
    if identifier and not doi:
        doi = str(_obj(resolve(identifier).get("identifiers", {})).get("doi", "") or "")
    refs: list[dict[str, object]] = []
    cites: list[dict[str, object]] = []
    src: str | None = None
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
            {
                "title": _obj(x).get("title"),
                "doi": _obj(_obj(x).get("externalIds") or {}).get("DOI"),
            }
            for x in _arr(s2.get("references") or [])
        ][:limit]
        cites = [
            {
                "title": _obj(x).get("title"),
                "doi": _obj(_obj(x).get("externalIds") or {}).get("DOI"),
            }
            for x in _arr(s2.get("citations") or [])
        ][:limit]
    elif doi:
        oa = S.openalex_by_doi(doi)
        if oa:
            src = "openalex"
            refs = [
                {"openalex": rid} for rid in _arr(oa.get("referenced_works") or [])
            ][:limit]
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
) -> dict[str, object]:
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
            "error": (
                f"not a PDF (status {r.status_code}, magic {r.content[:5]!r}) — "
                + "likely a bot-wall/landing page; refusing to save. Open the page in a browser instead."
            ),
            "url": url,
        }
    name = filename or (url.rstrip("/").split("/")[-1] or "paper")
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    path = dest / name
    _ = path.write_bytes(r.content)
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
def summarize(identifier: str = "", doi: str = "") -> dict[str, object]:
    meta = fetch_metadata(identifier or doi)
    if not meta.get("resolved"):
        return meta
    m = _obj(meta.get("metadata", {}))
    ids = _obj(meta["identifiers"])
    acc = access_status(
        doi=str(ids.get("doi", "") or ""),
        arxiv=str(ids.get("arxiv", "") or ""),
    )
    return {
        "title": m.get("title"),
        "authors": _arr(m.get("authors", []))[:8],
        "year": m.get("year"),
        "venue": m.get("journal"),
        "doi": m.get("doi"),
        "identifiers": meta["identifiers"],
        "abstract": meta.get("abstract") or "(no abstract legally available)",
        "access_status": acc.get("status"),
        "reference_count": len(_arr(meta.get("references", []))),
        "note": "Digest of legally-available metadata/abstract only — the calling agent writes the prose summary.",
    }


def batch_resolve(identifiers: list[str]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    unresolved: list[str] = []
    for ident in identifiers:
        r = resolve(ident)
        if not r.get("resolved"):
            unresolved.append(ident)
            rows.append({"input": ident, "resolved": False})
            continue
        ids = _obj(r["identifiers"])
        doi = str(ids.get("doi", "") or "")
        acc = access_status(doi=doi, arxiv=str(ids.get("arxiv", "") or ""))
        m = _obj(r.get("metadata", {}))
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
