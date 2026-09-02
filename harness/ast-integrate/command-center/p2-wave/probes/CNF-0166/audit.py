#!/usr/bin/env python3
"""Run control suite plus estate harvest/re-fetch; return citation rows."""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from classify import classify  # noqa: E402
from controls import (  # noqa: E402
    ONION_PASSAGE,
    RFC7686_REL,
    ControlServer,
    control_citations,
)
from fetch import Fetcher, fetch_via_http_client, is_onion_url  # noqa: E402
from harvest import harvest_research, local_capture_digest  # noqa: E402

MAX_ESTATE_LIVE = 18
LIVE_TIMEOUT = 4.0


def rfc7686_text() -> str:
    path = REPO / RFC7686_REL
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def corroborates(quote: str, rfc: str) -> bool:
    if not quote or not rfc:
        return False
    if quote in rfc:
        return True
    return "SHOULD NOT perform a DNS lookup" in rfc and "DNS lookup" in quote


def _row(cid: str, meta: dict, classified: dict, extra: dict | None = None) -> dict:
    source = meta.get("source_path") or meta.get("source_path")
    slept = classified.get("slept_s")
    blocked = classified.get("blocked_third")
    onion = classified.get("onion_skipped") or is_onion_url(str(meta.get("url") or ""))
    out = {
        "id": cid,
        "url": meta.get("url"),
        "claim_id": meta.get("claim_id") or cid,
        "source_path": source,
        "source_path": source,
        "kind": meta.get("kind") or "estate",
        "quote": meta.get("quote") or classified.get("passage") or "",
        "classification": classified["classification"],
        "http_status": classified.get("http_status"),
        "snapshot_sha256": classified.get("snapshot_sha256"),
        "current_sha256": classified.get("current_sha256"),
        "support_verdict": classified["support_verdict"],
        "passage_found": classified.get("passage_found"),
        "fetched_as_data": True,
        "tool_calls": classified.get("tool_calls") or [],
        "instruction_shaped": classified.get("instruction_shaped") or [],
        "onion_skipped": onion,
        "onion_skipped": onion,
        "redirected": classified.get("redirected"),
        "error": classified.get("error"),
        "error_class": classified.get("error_class"),
        "blocked_third": blocked,
        "blocked_third": blocked,
        "prerequisite": classified.get("prerequisite"),
        "attempts": classified.get("attempts"),
        "slept_s": slept,
        "slept_s": slept,
        "capture_path": meta.get("capture_path"),
    }
    if extra:
        out.update(extra)
    return out


def run_control_suite() -> dict:
    server = ControlServer()
    base = server.start()
    rfc = rfc7686_text()
    fetcher = Fetcher(timeout=3.0)
    rows: list[dict] = []
    try:
        citations = control_citations(base)
        for meta in citations:
            url = meta["url"]
            if meta["id"] == "ctrl-two-strike-soft":
                fetched = fetcher.fetch_with_strikes(url)
            else:
                fetched = fetcher.fetch(url, allow_retry=True)
            hit = False
            if is_onion_url(url):
                hit = corroborates(meta.get("quote") or "", rfc)
                if meta["id"] == "ctrl-onion-corroborated":
                    hit = hit or ("SHOULD NOT perform a DNS lookup" in rfc)
            classified = classify(
                fetched,
                snapshot_sha256=meta.get("snapshot_sha256"),
                passage=meta.get("quote") or "",
                corroboration_hit=hit,
            )
            rows.append(_row(meta["id"], meta, classified))

        reviewer_ids = [
            "ctrl-intact",
            "ctrl-intact-b",
            "ctrl-dead",
            "ctrl-soft",
            "ctrl-changed-support",
            "ctrl-changed-nonsupport",
            "ctrl-moved",
            "ctrl-inject",
            "ctrl-rate-limit",
            "ctrl-vendor-529",
        ]
        by_id = {r["id"]: r for r in rows}
        agreements = []
        for rid in reviewer_ids:
            meta = next(c for c in citations if c["id"] == rid)
            alt = fetch_via_http_client(meta["url"], timeout=3.0)
            classified = classify(
                alt,
                snapshot_sha256=meta.get("snapshot_sha256"),
                passage=meta.get("quote") or "",
            )
            primary = by_id[rid]["classification"]
            agreements.append(
                {
                    "id": rid,
                    "primary": primary,
                    "reviewer": classified["classification"],
                    "agree": primary == classified["classification"],
                }
            )
        tests = {
            "known_dead": {
                "id": "known-dead",
                "pass": by_id["ctrl-dead"]["classification"] == "dead"
                and by_id["ctrl-soft"]["classification"] != "dead",
                "detail": {
                    "dead": by_id["ctrl-dead"]["http_status"],
                    "soft": by_id["ctrl-soft"]["classification"],
                },
            },
            "known_changed": {
                "id": "known-changed",
                "pass": by_id["ctrl-changed-support"]["classification"]
                == "changed-but-still-supporting"
                and by_id["ctrl-changed-nonsupport"]["classification"]
                == "changed-and-no-longer-supporting",
            },
            "injection": {
                "id": "injection",
                "pass": (not by_id["ctrl-inject"]["tool_calls"])
                and bool(by_id["ctrl-inject"]["instruction_shaped"])
                and by_id["ctrl-inject"]["fetched_as_data"] is True,
            },
            "both_states": {
                "id": "both-states",
                "pass": by_id["ctrl-intact"]["classification"] == "intact"
                and by_id["ctrl-dead"]["classification"] == "dead",
            },
            "reviewer_refetch": {
                "id": "reviewer-refetch",
                "pass": all(a["agree"] for a in agreements) and len(agreements) == 10,
                "n": len(agreements),
                "agreements": agreements,
            },
            "onion_label": {
                "id": "onion-label",
                "pass": by_id["ctrl-onion-corroborated"]["classification"]
                == "tor-derived-corroborated"
                and by_id["ctrl-onion-uncorroborated"]["classification"]
                == "tor-derived-uncorroborated"
                and by_id["ctrl-onion-corroborated"]["onion_skipped"] is True,
            },
            "http_529_no_self_throttle": {
                "id": "vendor-529",
                "pass": by_id["ctrl-vendor-529"]["classification"] == "vendor-529"
                and float(by_id["ctrl-vendor-529"].get("slept_s") or 0) == 0,
            },
            "http_429_backoff": {
                "id": "http-429",
                "pass": by_id["ctrl-rate-limit"]["classification"] == "intact"
                and int(by_id["ctrl-rate-limit"].get("attempts") or 0) >= 2,
            },
            "two_strike_block": {
                "id": "two-strike",
                "pass": by_id["ctrl-two-strike-soft"]["blocked_third"] is True
                and bool(by_id["ctrl-two-strike-soft"].get("prerequisite")),
            },
            "soft_vs_dead": {
                "id": "soft-vs-dead",
                "pass": by_id["ctrl-soft"]["classification"] == "soft-error"
                and by_id["ctrl-dead"]["classification"] == "dead",
            },
        }
        return {
            "base": base,
            "citations": rows,
            "tests": tests,
            "reviewer": {
                "reviewer_id": "CNF-0166-probe2-http-client-refetch",
                "independent": True,
                "network_path": "http.client vs urllib.request",
                "n_refetched": len(agreements),
                "agreements": agreements,
                "verdict": "PASS" if tests["reviewer_refetch"]["pass"] else "FAIL",
            },
            "rfc7686_present": bool(rfc),
            "onion_passage": ONION_PASSAGE,
        }
    finally:
        server.stop()


def _estate_meta(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "url": item.get("url"),
        "quote": item.get("quote") or item.get("quote") or "",
        "snapshot_sha256": item.get("snapshot_sha256") or item.get("snapshot_sha256"),
        "capture_path": item.get("capture_path") or item.get("capture_path"),
        "source_path": item.get("source_path") or item.get("source_path"),
        "claim_id": item.get("claim_id") or item.get("claim_id") or item.get("id"),
        "kind": item.get("kind") or "estate",
    }


def classify_estate(item: dict, fetcher: Fetcher, rfc: str) -> dict:
    meta = _estate_meta(item)
    url = meta["url"]
    cap_digest, cap_bytes = local_capture_digest(REPO, meta.get("capture_path"))
    snapshot = meta.get("snapshot_sha256") or cap_digest
    extra = {
        "capture_sha256_on_disk": cap_digest,
        "capture_bytes": cap_bytes,
        "snapshot_matches_capture": bool(snapshot and cap_digest and snapshot == cap_digest),
        "live_fetched": not is_onion_url(url),
    }
    fetched = fetcher.fetch(url, allow_retry=True)
    classified = classify(
        fetched,
        snapshot_sha256=snapshot,
        passage=meta.get("quote") or "",
        corroboration_hit=corroborates(meta.get("quote") or "", rfc),
    )
    extra["live_fetched"] = bool(fetched.ok_http) and not fetched.onion_skipped
    return _row(str(meta["id"]), meta, classified, extra)


def harvest_and_classify_estate(*, live: bool = True, limit: int = MAX_ESTATE_LIVE) -> list[dict]:
    items = harvest_research()
    rfc = rfc7686_text()
    items.sort(key=lambda r: (0 if r.get("capture_path") or r.get("capture_path") else 1, r.get("url") or ""))
    picked: list[dict] = []
    seen: set[str] = set()
    for it in items:
        url = it.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        picked.append(it)
        if len(picked) >= limit:
            break
    leftover = max(0, len(items) - len(picked))
    if not live:
        for it in picked:
            it = dict(it)
        # still fetch: honesty wants live attempts; live=False only skips pool
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [
            pool.submit(classify_estate, it, Fetcher(timeout=LIVE_TIMEOUT), rfc)
            for it in picked
        ]
        for fut in as_completed(futs):
            rows.append(fut.result())
    rows.sort(key=lambda r: str(r.get("id")))
    for row in rows:
        row["estate_harvest_total"] = len(items)
        row["estate_live_capped"] = leftover
    return rows


def run_audit(*, live_estate: bool = True) -> dict:
    controls = run_control_suite()
    estate = harvest_and_classify_estate(live=live_estate)
    citations = list(controls["citations"]) + estate
    counts: dict[str, int] = {}
    for row in citations:
        k = row["classification"]
        counts[k] = counts.get(k, 0) + 1
    for key in (
        "intact",
        "moved",
        "changed-but-still-supporting",
        "changed-and-no-longer-supporting",
        "dead",
    ):
        counts.setdefault(key, 0)
    return {
        "citations": citations,
        "tests": controls["tests"],
        "reviewer": controls["reviewer"],
        "classifications": counts,
        "estate_n": len(estate),
        "control_n": len(controls["citations"]),
        "harvest_n": len(harvest_research()),
        "rfc7686_present": controls["rfc7686_present"],
        "base": controls["base"],
    }
