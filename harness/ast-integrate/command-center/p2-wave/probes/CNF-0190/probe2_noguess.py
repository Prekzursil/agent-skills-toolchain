#!/usr/bin/env python3
"""Probe 2: decision-log stale recount + no-guess UNRESOLVED (second signal)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import resolver as R  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0190.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 2048:
        print("FAILED:CNF-0190-probe2 artifact missing or undersized")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0190" not in json.dumps(doc):
        print("FAILED:CNF-0190-probe2 sentinel absent")
        return 1
    if doc.get("confirmation_verdict") == "CONFIRMED" and not doc.get("unresolved_entries"):
        print("FAILED:CNF-0190-probe2 CONFIRMED with empty UNRESOLVED (guess/overclaim)")
        return 1

    estate = C.materialize()
    log_path = estate / "17-DECISION-LOG.md"
    log_text = log_path.read_text(encoding="utf-8")
    mech = R.count_mech_tokens(log_text)
    stale = R.present_tense_collision(log_text)
    if mech["total"] != 0:
        print("FAILED:CNF-0190-probe2 decision log MECH token count", mech)
        return 1
    if not stale:
        print("FAILED:CNF-0190-probe2 decision log not present-tense stale")
        return 1
    dlog = doc.get("decision_log") or {}
    if dlog.get("flag") != "STALE":
        print("FAILED:CNF-0190-probe2 artifact did not flag decision log STALE")
        return 1
    recount = (dlog.get("mech_token_recount") or {}).get("total")
    if recount != 0:
        print("FAILED:CNF-0190-probe2 artifact MECH recount", recount)
        return 1

    hits = R.scan_tree(estate)
    unresolved = [h for h in hits if h["classification"] == R.CLASS_UNRESOLVED]
    if not unresolved:
        print("FAILED:CNF-0190-probe2 zero UNRESOLVED despite planted ambiguous M-16")
        return 1
    planted = [
        h
        for h in unresolved
        if h["id"] == "M-16" and "ambiguous" in h["artifact"].lower()
    ]
    if not planted:
        print("FAILED:CNF-0190-probe2 planted ambiguous M-16 missing from UNRESOLVED")
        return 1
    if not doc.get("unresolved_entries"):
        print("FAILED:CNF-0190-probe2 artifact unresolved_entries empty")
        return 1

    # Second mechanical signal: path-stem namespace must agree on MECH- and
    # abstain on the planted ambiguous M-16 (must not guess a namespace).
    mech_hits = [h for h in hits if h["id"].startswith("MECH-")]
    disagree = []
    for h in mech_hits:
        stem_ns = R.path_stem_namespace(h["artifact"], h["id"])
        if stem_ns not in {None, R.NS_MECH}:
            disagree.append(h)
        if stem_ns == R.NS_MECH and h.get("namespace") != R.NS_MECH:
            disagree.append(h)
    if disagree:
        print("FAILED:CNF-0190-probe2 path-stem disagrees on MECH-", disagree[:3])
        return 1
    for h in planted:
        stem_ns = R.path_stem_namespace(h["artifact"], h["id"])
        if stem_ns is not None:
            print("FAILED:CNF-0190-probe2 path-stem guessed planted M-16 as", stem_ns)
            return 1

    live = doc.get("corpus", {}).get("live_cited_inputs") or []
    unexpected = []
    for row in live:
        if not isinstance(row, dict) or not row.get("present"):
            continue
        path = str(row.get("path") or "").replace("\\", "/").lower()
        kind = str(row.get("kind") or "")
        if kind == "resolution-index" or "option-id-resolution" in path:
            continue
        unexpected.append(row.get("path"))
    if unexpected:
        print("FAILED:CNF-0190-probe2 unexpected live namespace source present", unexpected)
        return 1
    ns_live = doc.get("corpus", {}).get("live_namespace_sources_present") or []
    if ns_live:
        print("FAILED:CNF-0190-probe2 live_namespace_sources_present", ns_live)
        return 1
    idx_live = doc.get("corpus", {}).get("live_resolution_index_present") or []
    if not idx_live:
        print("FAILED:CNF-0190-probe2 live OPTION-ID-RESOLUTION index missing")
        return 1
    cor = doc.get("live_index_corroboration") or {}
    if not cor.get("m16_three_meanings"):
        print("FAILED:CNF-0190-probe2 live index did not corroborate three M-16 meanings")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-noguess",
                "unit_id": "CNF-0190",
                "decision_log_mech_tokens": mech["total"],
                "decision_log_stale": stale,
                "unresolved": len(unresolved),
                "planted_unresolved": len(planted),
                "path_stem_mech_agree": True,
                "path_stem_abstain_on_ambiguous": True,
                "live_resolution_index": True,
                "live_index_m16_three_meanings": True,
                "pass": True,
            }
        )
    )
    print("SUCCESS:CNF-0190-probe2 decision-log stale recount and no-guess UNRESOLVED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
