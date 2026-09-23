"""Tool logic for the scholarly-access MCP. Pure functions returning JSON-able dicts,
so the test client can exercise them with no MCP transport. Every OA URL passes through
policy.assert_lawful before it is returned or fetched.
"""

from __future__ import annotations

import difflib
import hashlib
import os
import re
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING, cast

import requests
from defusedxml.ElementTree import fromstring as _safe_xml

from . import policy, sources as S

if TYPE_CHECKING:  # annotation only; every parse goes through defusedxml above
    from xml.etree.ElementTree import Element


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
    if kind in ("doi", "title"):
        # Both branches below consult OpenAlex; say truthfully whether the calls
        # carried OPENALEX_API_KEY (keyed daily budget) or ran anonymously.
        out["openalex_authenticated"] = S.openalex_authenticated()
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
    oa_auth: bool | None = None  # set only when the OpenAlex fallback is consulted
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
        oa_auth = S.openalex_authenticated()
        oa = S.openalex_by_doi(doi)
        if oa:
            src = "openalex"
            refs = [
                {"openalex": rid} for rid in _arr(oa.get("referenced_works") or [])
            ][:limit]
    out: dict[str, object] = {
        "doi": doi or None,
        "source": src,
        "references": refs,
        "cited_by": cites,
        "counts": {"references": len(refs), "cited_by": len(cites)},
    }
    if oa_auth is not None:
        out["openalex_authenticated"] = oa_auth
    return out


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


# ---------------------------------------------------------------------------
# Shared envelope for the per-source tools below (OpenCitations, Europe PMC).
# Success: {"ok": True, "source": ..., ...}. Failure: {"ok": False, "error": ...,
# "upstream_status": int|None, "url": ...} — the upstream status is always reported.
# ---------------------------------------------------------------------------
def _failed(source: str, err: S.UpstreamError, **ids: object) -> dict[str, object]:
    return {"ok": False, "source": source, **ids, **err.envelope()}


def _bad_input(source: str, error: str, **ids: object) -> dict[str, object]:
    return {
        "ok": False,
        "source": source,
        **ids,
        "error": error,
        "upstream_status": None,
    }


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(int(value), hi))


# ---------------------------------------------------------------------------
# OpenCitations — citations_for_doi / references_for_doi (keyless, CC0)
# ---------------------------------------------------------------------------
OPENCITATIONS_MAX = 100
_META_BATCH = 25  # DOIs per Meta request; keeps the `__`-joined URL short

SELF_CITATION_NOTE = (
    "self_citation_suspect is a HEURISTIC: True when the cited and citing works share a "
    "first-author surname (surnames from OpenCitations Meta, diacritics folded); None when "
    "either surname is unknown. Common surnames give false positives; self-citation by a "
    "non-first author gives false negatives. opencitations_author_sc is the Index's own "
    "author-overlap flag (any shared author identifier) and is reported alongside. "
    "Rows are newest-first (server-side sort) and capped client-side — the API has no limit "
    "parameter, so heavily cited works mean one large upstream response. "
    "Data: OpenCitations Index + Meta, CC0."
)


def _fold(s: str) -> str:
    """Lower-case and strip diacritics so 'Müller' == 'Muller' == 'MÜLLER'."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip().lower()


def _first_surname(author_field: str) -> str:
    """OpenCitations Meta ``author`` = "Surname, Given [ids]; Surname, Given [ids]"."""
    first = re.sub(r"\[.*?\]", "", author_field.split(";")[0])
    return _fold(first.split(",")[0])


def _doi_in(ids: str) -> str | None:
    """The ``doi:`` token of an OpenCitations space-separated id list, lower-cased."""
    for tok in ids.split():
        if tok.startswith("doi:"):
            return tok[4:].lower()
    return None


def _meta_lookup(
    dois: list[str], warnings: list[object]
) -> dict[str, dict[str, object]]:
    """title / pub_date / first-author surname per DOI via OpenCitations Meta, in
    batches. A failed batch becomes a warning carrying the upstream status — the
    citation rows are still returned, only the enrichment degrades to None."""
    out: dict[str, dict[str, object]] = {}
    uniq = sorted(set(dois))
    for start in range(0, len(uniq), _META_BATCH):
        batch = uniq[start : start + _META_BATCH]
        try:
            rows = S.opencitations_meta(batch)
        except S.UpstreamError as e:
            warnings.append({"stage": "opencitations-meta", **e.envelope()})
            continue
        for row in rows:
            r = _obj(row)
            d = _doi_in(str(r.get("id") or ""))
            if d:
                out[d] = {
                    "title": str(r.get("title") or "") or None,
                    "date": str(r.get("pub_date") or "") or None,
                    "surname": _first_surname(str(r.get("author") or "")),
                }
    return out


def _opencitations(kind: str, doi: str, limit: int) -> dict[str, object]:
    """Shared body of citations_for_doi (kind='citations', other side = citing) and
    references_for_doi (kind='references', other side = cited)."""
    other_side = "citing" if kind == "citations" else "cited"
    id_kind, val = S.classify_identifier(doi)
    if id_kind != "doi":
        return _bad_input("opencitations", f"not a DOI: {doi!r}", doi=None)
    doi = val.lower()
    limit = _clamp(limit, 1, OPENCITATIONS_MAX)
    try:
        rows = S.opencitations_index(kind, doi)
    except S.UpstreamError as e:
        return _failed("opencitations", e, doi=doi)
    kept = [_obj(r) for r in rows[:limit]]
    warnings: list[object] = []
    others = [_doi_in(str(r.get(other_side) or "")) for r in kept]
    meta = _meta_lookup([doi, *[d for d in others if d]], warnings)
    me = meta.get(doi, {})
    mine = str(me.get("surname") or "")
    items: list[object] = []
    for r, other in zip(kept, others):
        m = meta.get(other or "", {})
        theirs = str(m.get("surname") or "")
        # `creation` is the CITING work's date. For citations that is the other work;
        # for references the other work is the cited one, whose date comes from Meta.
        date = (r.get("creation") or None) if kind == "citations" else m.get("date")
        items.append(
            {
                f"{other_side}_doi": other,
                "title": m.get("title"),
                "date": date,
                "timespan": r.get("timespan") or None,  # cited -> citing, ISO 8601
                "oci": r.get("oci"),
                "first_author_surname": theirs or None,
                "self_citation_suspect": (mine == theirs)
                if (mine and theirs)
                else None,
                "opencitations_author_sc": r.get("author_sc") == "yes",
                "opencitations_journal_sc": r.get("journal_sc") == "yes",
            }
        )
    return {
        "ok": True,
        "source": "opencitations",
        "doi": doi,
        "work": {
            "doi": doi,
            "title": me.get("title"),
            "date": me.get("date"),
            "first_author_surname": mine or None,
        },
        "count": len(items),
        "total_upstream": len(rows),
        "truncated": len(rows) > len(items),
        kind: items,
        "warnings": warnings,
        "license": "CC0-1.0",
        "note": SELF_CITATION_NOTE,
    }


def citations_for_doi(doi: str, limit: int = OPENCITATIONS_MAX) -> dict[str, object]:
    """Works that cite ``doi`` (OpenCitations Index, newest first, ``limit`` <= 100)."""
    return _opencitations("citations", doi, limit)


def references_for_doi(doi: str, limit: int = OPENCITATIONS_MAX) -> dict[str, object]:
    """Works that ``doi`` cites (OpenCitations Index, ``limit`` <= 100)."""
    return _opencitations("references", doi, limit)


# ---------------------------------------------------------------------------
# Europe PMC — full text (OA subset, JATS XML -> plain-text sections) + annotations
# ---------------------------------------------------------------------------
FULLTEXT_DEFAULT_CHARS = 60_000
FULLTEXT_MAX_CHARS = 200_000
ANNOTATIONS_MAX = 500
_XLINK_HREF = "{http://www.w3.org/1999/xlink}href"


def _norm_pmcid(s: str) -> str | None:
    """``pmc1182327`` -> ``PMC1182327``. The prefix is required: bare digits are a
    PMID, and silently prefixing them would fetch a different article's full text."""
    m = re.fullmatch(r"PMC(\d{1,9})", s.strip(), re.I)
    return f"PMC{m.group(1)}" if m else None


def _classify_epmc_id(s: str) -> str | None:
    """``PMC1182327`` -> ``PMC:PMC1182327``; bare digits are a PMID -> ``MED:16060722``."""
    s = s.strip()
    if re.fullmatch(r"PMC\d{1,9}", s, re.I):
        return f"PMC:{s.upper()}"
    if re.fullmatch(r"\d{1,9}", s):
        return f"MED:{s}"
    return None


def _text_of(node: Element) -> str:
    """Concatenated text of a JATS node (inline markup dropped, whitespace collapsed)."""
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip()


def _child_text(node: Element, path: str) -> str:
    """``_text_of`` the first ``path`` match under ``node``, or ''. (``findtext`` would
    stop at the first inline child: ``<title>The <italic>X</italic></title>`` -> 'The '.)"""
    el = node.find(path)
    return _text_of(el) if el is not None else ""


def _section_text(node: Element) -> str:
    """Paragraphs of a JATS section (nested subsections flattened) joined by single
    spaces. A node with no ``<p>`` at all (e.g. a bare-text abstract) yields its own
    text, heading excluded."""
    paras = [t for t in (_text_of(p) for p in node.iter("p")) if t]
    if paras:
        return " ".join(paras)
    pieces = [node.text or ""]
    for child in node:
        if child.tag != "title":
            pieces.extend(child.itertext())
        pieces.append(child.tail or "")
    return re.sub(r"\s+", " ", "".join(pieces)).strip()


def europepmc_fulltext(
    pmcid: str, max_chars: int = FULLTEXT_DEFAULT_CHARS
) -> dict[str, object]:
    """Plain-text sections of an open-access article from Europe PMC's full-text XML.

    Only the OA subset is served (404 otherwise — reported as such, never worked
    around). Total text is capped at ``max_chars`` with ``truncated`` set when cut.
    The fetch URL passes ``policy.assert_lawful`` like every other full-text fetch.
    """
    norm = _norm_pmcid(pmcid)
    if not norm:
        return _bad_input(
            "europepmc",
            f"not a PMCID (expected PMC + digits, e.g. PMC1182327): {pmcid!r}",
            pmcid=None,
        )
    max_chars = _clamp(max_chars, 1_000, FULLTEXT_MAX_CHARS)
    url = S.europepmc_fulltext_url(norm)
    policy.assert_lawful(url)
    try:
        xml = S.europepmc_fulltext_xml(norm)
    except S.UpstreamError as e:
        out = _failed("europepmc", e, pmcid=norm)
        if e.status == 404:
            out["reason"] = (
                "Europe PMC serves full-text XML only for its open-access subset; "
                "this PMCID is not in it (or does not exist). Cite the landing page — "
                "we do not fetch full text from anywhere else."
            )
        return out
    try:
        root = _safe_xml(xml)
    except Exception:
        return _bad_input(
            "europepmc", "upstream returned unparseable XML", pmcid=norm, url=url
        )
    sections: list[object] = []
    used = 0
    truncated = False
    candidates: list[tuple[str, str]] = []
    abstract = root.find(".//front//abstract")
    if abstract is not None:
        candidates.append(("Abstract", _section_text(abstract)))
    for sec in root.findall("./body/sec"):
        title = _child_text(sec, "title") or "(untitled section)"
        candidates.append((title, _section_text(sec)))
    for title, body in candidates:
        room = max_chars - used
        if room <= 0:
            truncated = True
            break
        if len(body) > room:
            body, truncated = body[:room], True
        used += len(body)
        sections.append({"title": title, "text": body, "chars": len(body)})
    lic = root.find(".//permissions/license")
    return {
        "ok": True,
        "source": "europepmc",
        "pmcid": norm,
        "url": url,
        "title": _child_text(root, ".//front//article-title") or None,
        "license": (
            {"text": _text_of(lic) or None, "url": lic.get(_XLINK_HREF)}
            if lic is not None
            else None
        ),
        "sections": sections,
        "section_count": len(sections),
        "chars": used,
        "max_chars": max_chars,
        "truncated": truncated,
    }


def europepmc_annotations(
    article_id: str, type: str = "", limit: int = 200
) -> dict[str, object]:
    """Text-mined annotations (genes/proteins, diseases, chemicals, ...) for a PMCID or
    PMID from Europe PMC's Annotations API, optionally filtered by ``type``."""
    ident = _classify_epmc_id(article_id)
    if not ident:
        return _bad_input(
            "europepmc",
            f"not a PMCID (PMC1234567) or PMID (digits): {article_id!r}",
            article_id=None,
        )
    limit = _clamp(limit, 1, ANNOTATIONS_MAX)
    try:
        rows = S.europepmc_annotations(ident, type)
    except S.UpstreamError as e:
        return _failed("europepmc", e, article_id=ident)
    article: dict[str, object] | None = None
    anns: list[dict[str, object]] = []
    for row in rows:  # the API returns one object per article id; we send one id
        r = _obj(row)
        article = {
            "source": r.get("source"),
            "ext_id": r.get("extId"),
            "pmcid": r.get("pmcid"),
        }
        for a in _arr(r.get("annotations") or []):
            ao = _obj(a)
            anns.append(
                {
                    "type": ao.get("type"),
                    "exact": ao.get("exact"),
                    "prefix": ao.get("prefix"),
                    "postfix": ao.get("postfix"),
                    "section": ao.get("section"),
                    "provider": ao.get("provider"),
                    "tags": [
                        {"name": _obj(t).get("name"), "uri": _obj(t).get("uri")}
                        for t in _arr(ao.get("tags") or [])
                    ],
                }
            )
    kept = anns[:limit]
    return {
        "ok": True,
        "source": "europepmc",
        "article_id": ident,
        "type_filter": type or None,
        "article": article,
        "types": sorted({str(a["type"]) for a in kept}),
        "count": len(kept),
        "total_upstream": len(anns),
        "truncated": len(anns) > len(kept),
        "annotations": kept,
        "note": (
            "Europe PMC answers HTTP 200 with an empty annotations list both when an "
            "article has none (of the requested type) and when the type name is unknown "
            "to it, and HTTP 200 + [] for an id it does not know — so an empty result is "
            "not proof of absence. Valid type names: https://europepmc.org/AnnotationsApi"
        ),
    }
