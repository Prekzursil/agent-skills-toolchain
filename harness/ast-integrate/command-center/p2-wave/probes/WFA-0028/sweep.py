"""Niche/archival/non-English orchestration sweep with independent corroboration."""
from __future__ import annotations

import copy

from catalog import MAINSTREAM, SOURCES
from legal_review import review as _legal
from onion_gate import classify_url, onion_class_enabled


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def _quote(src: dict) -> str:
    return src.get("original_quote") or src.get("original_quote") or ""


def corroborate(tokens: list[str], mainstream: list[dict], niche_url: str) -> dict:
    needed = [_norm(t) for t in tokens if t]
    hits: list[dict] = []
    for doc in mainstream:
        if doc.get("url") == niche_url:
            continue
        blob = _norm(str(doc.get("text") or ""))
        if needed and all(tok in blob for tok in needed):
            hits.append(
                {"id": doc["id"], "url": doc["url"], "surface": doc.get("surface")}
            )
    return {
        "corroborated": bool(hits),
        "hits": hits,
        "status": "CORROBORATED" if hits else "UNVERIFIED",
    }


def _finding(src: dict, corr: dict) -> dict:
    quote = _quote(src)
    translation = src.get("translation") or quote
    return {
        "mechanism_id": src["mechanism_id"],
        "mechanism": src["mechanism"],
        "source_class": src["class"],
        "language": src["language"],
        "source": {
            "id": src["id"],
            "url": src["url"],
            "retrieved_at": src.get("retrieved_at"),
            "archive_timestamp": src.get("archive_timestamp"),
            "title": src.get("title"),
        },
        "evidence_a": {
            "original_language": src["language"],
            "original_quote": quote,
            "original_quote": quote,
            "translation": translation,
        },
        "evidence_b": corr,
        "proposal_only": bool(src.get("proposal_only") or src.get("proposal_only")),
        "survives_mainstream_corroboration": corr["status"] == "CORROBORATED",
        "appears_only_in_niche_or_archival": corr["status"] != "CORROBORATED",
        "grade": corr["status"],
    }


def promote(finding: dict) -> dict:
    if finding.get("grade") != "CORROBORATED":
        return {
            "promoted": False,
            "reason": "archival-or-niche-only-without-corroboration-stays-UNVERIFIED",
        }
    if finding.get("proposal_only"):
        return {"promoted": False, "reason": "proposal-only-not-a-shipped-mechanism"}
    return {
        "promoted": True,
        "reason": "corroborated-against-independent-mainstream-surface",
    }


def run(
    *,
    sources: list[dict] | None = None,
    mainstream: list[dict] | None = None,
    onion_enabled: bool | None = None,
) -> dict:
    srcs = copy.deepcopy(sources if sources is not None else SOURCES)
    ms = copy.deepcopy(mainstream if mainstream is not None else MAINSTREAM)
    gate = onion_class_enabled()
    if onion_enabled is not None:
        gate = dict(gate)
        gate["enabled"] = bool(onion_enabled)
        gate["reason"] = "forced-for-probe" if onion_enabled else "forced-off-for-probe"

    skipped: list[dict] = []
    findings: list[dict] = []
    actions = ["read-fixture"]
    urls: list[str] = []
    quotes: list[str] = []
    onion_live = 0

    for src in srcs:
        url = src.get("url") or ""
        urls.append(url)
        cls = classify_url(url, enabled=gate["enabled"])
        if cls["onion"]:
            skipped.append(cls)
            if cls["action"] == "allow-read":
                onion_live += 1
            continue
        queued = src.get("queued_only") or src.get("queued_only")
        if queued or not src.get("mechanism_id"):
            continue
        q = _quote(src)
        if q:
            quotes.append(q)
        tokens = src.get("tokens") or src.get("tokens") or []
        corr = corroborate(tokens, ms, url)
        findings.append(_finding(src, corr))

    legal = _legal(
        actions=actions,
        urls=urls,
        quotes=quotes,
        onion_fetches=onion_live,
    )
    legal.setdefault("consume_allowed", legal.get("consume_allowed", legal.get("pass")))
    legal.setdefault("pass", legal.get("pass"))
    corroborated = [f for f in findings if f["grade"] == "CORROBORATED"]
    unverified = [f for f in findings if f["grade"] == "UNVERIFIED"]
    return {
        "onion_gate": gate,
        "onion_skipped": skipped,
        "onion_skipped": skipped,
        "legal_review": legal,
        "findings": findings,
        "corroborated": corroborated,
        "unverified": unverified,
        "only_niche_or_archival": [
            f for f in findings if f["appears_only_in_niche_or_archival"]
        ],
        "counts": {
            "sources_considered": len(srcs),
            "onion_queued": len(skipped),
            "findings": len(findings),
            "corroborated": len(corroborated),
            "unverified": len(unverified),
            "only_niche_or_archival": sum(
                1 for f in findings if f["appears_only_in_niche_or_archival"]
            ),
        },
    }
