#!/usr/bin/env python3
"""ADV-0144 compliance-trace checker.

Walks a lineage graph. For every claim whose transitive lineage includes a
controversial source, requires four resolvable records: label, independent
corroboration from a different class AND origin, fetch audit-log, and
pre-output legal/safety review. Unresolvable lineage is INCOMPLETE, never
out of scope. Same-origin corroboration does not satisfy. This module
reads logs and lineage only; it performs no Tor or onion access.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CORPUS = HERE / "fixtures" / "corpus.json"

FOUR_RECORDS = ("label", "corroboration", "audit_log", "pre_output_review")
CONTROVERSIAL_CLASSES = frozenset(
    {"onion", "tor", "tor-onion", "controversial", "darkweb-public-research"}
)
CONTROVERSIAL_LABELS = frozenset({"TOR-DERIVED"})
RESEARCH_GLOBS = (
    "command-center/research/**/*.json",
    "command-center/CLAIM-REGISTRY.json",
)


def load_corpus(path: Path | None = None) -> dict[str, Any]:
    p = path or CORPUS
    return json.loads(p.read_text(encoding="utf-8"))


def host_of(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    return (parsed.hostname or "").lower()


def is_onion_url(url: str) -> bool:
    host = host_of(url)
    return bool(host) and host.endswith(".onion")


def source_class_of(src: dict[str, Any]) -> str:
    explicit = str(src.get("source_class") or src.get("class") or "").strip()
    if explicit:
        return explicit
    url = str(src.get("url") or src.get("resolved_url") or "")
    if is_onion_url(url):
        return "onion"
    host = host_of(url)
    if host.endswith("rfc-editor.org") or host.endswith("ietf.org"):
        return "standards-document"
    if "torproject.org" in host:
        return "standards-document"
    if host:
        return "clearnet"
    return "unclassified"


def origin_id_of(src: dict[str, Any]) -> str:
    explicit = str(src.get("origin_id") or "").strip()
    if explicit:
        return explicit
    host = host_of(str(src.get("url") or src.get("resolved_url") or ""))
    if host:
        return f"host:{host}"
    return str(src.get("id") or "")


def is_controversial_source(src: dict[str, Any]) -> bool:
    if source_class_of(src) in CONTROVERSIAL_CLASSES:
        return True
    return is_onion_url(str(src.get("url") or src.get("resolved_url") or ""))


def index_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        rid = str(row.get("id") or "")
        if rid:
            out[rid] = row
    return out


def stores_from_corpus(corpus: dict[str, Any]) -> dict[str, Any]:
    sources = list(corpus.get("sources") or [])
    return {
        "sources": index_by_id(sources),
        "audit": index_by_id(list(corpus.get("audit_log") or [])),
        "reviews": index_by_id(list(corpus.get("reviews") or [])),
        "consumers": list(corpus.get("consumers") or []),
        "claims": list(corpus.get("claims") or []),
    }


def consumers_for(claim_id: str, stores: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for item in stores.get("consumers") or []:
        if str(item.get("claim_id") or "") != claim_id:
            continue
        rows.append(
            {
                "artifact": str(item.get("artifact") or ""),
                "how": str(item.get("how") or "consumed"),
            }
        )
    return rows


def resolve_lineage(
    claim: dict[str, Any], stores: dict[str, Any]
) -> tuple[bool, list[dict[str, Any]]]:
    ids = list(claim.get("lineage") or [])
    if not ids:
        return False, []
    sources: list[dict[str, Any]] = []
    for sid in ids:
        src = stores["sources"].get(str(sid))
        if src is None:
            return False, sources
        sources.append(src)
    return True, sources


def controversial_sources_in(
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [s for s in sources if is_controversial_source(s)]


def label_present(claim: dict[str, Any]) -> bool:
    label = claim.get("label")
    if isinstance(label, str) and label.strip() in CONTROVERSIAL_LABELS:
        return True
    labels = claim.get("labels") or []
    if isinstance(labels, list):
        return any(str(x) in CONTROVERSIAL_LABELS for x in labels)
    return False


def corroboration_independent(
    claim: dict[str, Any],
    stores: dict[str, Any],
    controversial: list[dict[str, Any]],
) -> tuple[bool, str]:
    """True only when a corroborating source is a different class AND origin."""
    ids = list(claim.get("corroborating_sources") or [])
    if not ids:
        return False, "no-corroborating-source"
    if not controversial:
        return False, "no-controversial-origin-to-compare"
    origin_ids = {origin_id_of(s) for s in controversial}
    classes = {source_class_of(s) for s in controversial}
    saw_same_origin = False
    saw_same_class = False
    for cid in ids:
        src = stores["sources"].get(str(cid))
        if src is None:
            continue
        oid = origin_id_of(src)
        cls = source_class_of(src)
        if oid in origin_ids:
            saw_same_origin = True
            continue
        if cls in classes or cls in CONTROVERSIAL_CLASSES:
            saw_same_class = True
            continue
        return True, f"independent:{cid}:{cls}:{oid}"
    if saw_same_origin:
        return False, "same-origin-corroboration-rejected"
    if saw_same_class:
        return False, "same-class-corroboration-rejected"
    return False, "corroborating-source-unresolved"


def audit_present(claim: dict[str, Any], stores: dict[str, Any]) -> bool:
    aid = claim.get("audit_log_id")
    if not aid:
        return False
    entry = stores["audit"].get(str(aid))
    return isinstance(entry, dict) and bool(entry.get("id"))


def review_present(claim: dict[str, Any], stores: dict[str, Any]) -> bool:
    rid = claim.get("review_id")
    if not rid:
        return False
    entry = stores["reviews"].get(str(rid))
    if not isinstance(entry, dict):
        return False
    kind = str(entry.get("kind") or "")
    return "legal" in kind or "safety" in kind or kind == "legal-safety"


def evaluate_claim(claim: dict[str, Any], stores: dict[str, Any]) -> dict[str, Any]:
    cid = str(claim.get("id") or "")
    resolvable, sources = resolve_lineage(claim, stores)
    controversial = controversial_sources_in(sources) if resolvable else []
    # Unresolvable lineage is INCOMPLETE, never out of scope.
    if resolvable:
        controversial_flag = bool(controversial)
    else:
        controversial_flag = True
    in_scope = (not resolvable) or controversial_flag or bool(claim.get("planted"))
    label_ok = label_present(claim)
    corr_ok, corr_reason = corroboration_independent(claim, stores, controversial)
    audit_ok = audit_present(claim, stores)
    review_ok = review_present(claim, stores)
    verdict = {
        "label": bool(label_ok),
        "corroboration": bool(corr_ok),
        "audit_log": bool(audit_ok),
        "pre_output_review": bool(review_ok),
    }
    missing = [name for name in FOUR_RECORDS if not verdict[name]]
    complete = resolvable and controversial_flag and not missing
    completeness = "COMPLETE" if complete else "INCOMPLETE"
    return {
        "claim_id": cid,
        "planted": bool(claim.get("planted")),
        "role": claim.get("role"),
        "lineage_resolvable": resolvable,
        "controversial_lineage": controversial_flag,
        "in_scope": in_scope,
        "four_record_verdict": verdict,
        "completeness": completeness,
        "missing": missing,
        "corroboration_reason": corr_reason,
        "controversial_source_ids": [str(s.get("id")) for s in controversial],
        "downstream_consumers": consumers_for(cid, stores),
    }


def inverted_empty_is_complete(
    claim: dict[str, Any], stores: dict[str, Any]
) -> dict[str, Any]:
    """Mutant: reports COMPLETE for any claim object, including empty records."""
    cid = str(claim.get("id") or "")
    return {
        "claim_id": cid,
        "lineage_resolvable": True,
        "controversial_lineage": True,
        "four_record_verdict": {
            "label": True,
            "corroboration": True,
            "audit_log": True,
            "pre_output_review": True,
        },
        "completeness": "COMPLETE",
        "missing": [],
        "downstream_consumers": [],
        "inverted": True,
    }


def refuse_everything(
    claim: dict[str, Any], stores: dict[str, Any]
) -> dict[str, Any]:
    """Mutant: reports INCOMPLETE even when all four records resolve."""
    row = evaluate_claim(claim, stores)
    row["completeness"] = "INCOMPLETE"
    row["missing"] = list(FOUR_RECORDS)
    row["four_record_verdict"] = {k: False for k in FOUR_RECORDS}
    row["refuses_everything"] = True
    return row


def evaluate_all(corpus: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    body = corpus if corpus is not None else load_corpus()
    stores = stores_from_corpus(body)
    rows = []
    for claim in stores["claims"]:
        rows.append(evaluate_claim(claim, stores))
    return rows


def claim_by_id(corpus: dict[str, Any], cid: str) -> dict[str, Any]:
    for claim in corpus.get("claims") or []:
        if str(claim.get("id")) == cid:
            return claim
    raise KeyError(cid)


def artifact_payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Compliance-trace rows live under report (receipt_core forbids extras)."""
    report = doc.get("report")
    if isinstance(report, dict) and isinstance(report.get("traces"), list):
        return report
    return doc


def harvest_production(repo: Path | None = None) -> dict[str, Any]:
    """Census research artifacts. Does not fetch onion. Lineage is read only."""
    root = repo or REPO
    scanned = 0
    claims_seen = 0
    controversial = 0
    unresolvable = 0
    files: list[dict[str, Any]] = []
    for pattern in RESEARCH_GLOBS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            scanned += 1
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                files.append({"path": rel, "parseable": False})
                continue
            n_claims, n_cont, n_unres, onion_urls = _scan_doc(doc)
            claims_seen += n_claims
            controversial += n_cont
            unresolvable += n_unres
            files.append(
                {
                    "path": rel,
                    "parseable": True,
                    "claims": n_claims,
                    "controversial_lineage_claims": n_cont,
                    "unresolvable_lineage_claims": n_unres,
                    "onion_urls_in_lineage": onion_urls,
                }
            )
    res0119 = (root / "command-center/research/RES-0119.json").is_file()
    res0138 = (
        root
        / "command-center/research/sources-frontier/"
        / "RES-0138-tor-research-stage-design-and-legal-gate.json"
    ).is_file()
    return {
        "files_scanned": scanned,
        "claims_seen": claims_seen,
        "production_controversial_lineage_claims": controversial,
        "production_unresolvable_lineage_claims": unresolvable,
        "res_0119_present": res0119,
        "res_0138_present": res0138,
        "files": files,
    }


def _scan_doc(doc: Any) -> tuple[int, int, int, list[str]]:
    claims = _extract_claim_like(doc)
    n_cont = 0
    n_unres = 0
    onion_urls: list[str] = []
    for claim in claims:
        urls = _lineage_urls(claim)
        if not urls and not _has_lineage_pointer(claim):
            n_unres += 1
            continue
        hit = False
        for url in urls:
            if is_onion_url(url):
                onion_urls.append(url)
                hit = True
        cls = str(claim.get("source_class") or "")
        if cls in CONTROVERSIAL_CLASSES:
            hit = True
        if hit:
            n_cont += 1
    return len(claims), n_cont, n_unres, onion_urls


def _extract_claim_like(doc: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(doc, dict):
        for key in ("claims", "evidence"):
            val = doc.get(key)
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict) and (
                        "id" in item or "claim" in item or "text" in item
                    ):
                        found.append(item)
        if "claims" not in doc and "id" in doc and "source_lineage" in doc:
            found.append(doc)
    return found


def _has_lineage_pointer(claim: dict[str, Any]) -> bool:
    for key in ("lineage", "source_lineage", "rails"):
        if claim.get(key):
            return True
    return False


def _lineage_urls(claim: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    lin = claim.get("lineage")
    if isinstance(lin, dict):
        url = lin.get("resolved_url") or lin.get("url")
        if url:
            urls.append(str(url))
    elif isinstance(lin, list):
        for item in lin:
            if isinstance(item, str) and ("://" in item or item.endswith(".onion")):
                urls.append(item)
            elif isinstance(item, dict):
                url = item.get("resolved_url") or item.get("url")
                if url:
                    urls.append(str(url))
    sl = claim.get("source_lineage")
    if isinstance(sl, dict):
        url = sl.get("url") or sl.get("resolved_url")
        if url:
            urls.append(str(url))
    for rail in claim.get("rails") or []:
        if isinstance(rail, dict):
            url = rail.get("permalink") or rail.get("url")
            if url:
                urls.append(str(url))
    return urls
