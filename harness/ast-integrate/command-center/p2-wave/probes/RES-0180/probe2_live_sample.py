#!/usr/bin/env python3
"""Probe 2: recompute live-sample false-wake from stored paired fingerprints.

Independent of probe 1 (fixtures). Defaults to REFUTED if n<20, if stored
pairs cannot be recomputed, or if the watcher wakes when wake_value is stable.
Does not refetch the 20-source set (measure timeout); emit already fetched live.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

ART = REPO / "command-center/research/sources-frontier/RES-0180-watchlist-standing-recheck.json"
CAPTURES = HERE / "captures.json"
UNIT = "RES-0180"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0180-probe2 artifact missing")
        return 1
    if not CAPTURES.is_file():
        print("FAILED:RES-0180-probe2 captures missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    cap = json.loads(CAPTURES.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0180-probe2 self-declared", doc.get("state"))
        return 1
    if "SUCCESS:RES-0180" not in text:
        print("FAILED:RES-0180-probe2 sentinel absent")
        return 1
    live = cap.get("live") or {}
    pairs = live.get("pairs") or doc.get("measurements", {}).get("pairs") or []
    recomputed = []
    watcher_false = 0
    poller_false = 0
    for pair in pairs:
        if not pair.get("paired"):
            continue
        r1w = pair.get("r1_wake_value")
        r2w = pair.get("r2_wake_value")
        r1s = pair.get("r1_sha256")
        r2s = pair.get("r2_sha256")
        watcher = r1w != r2w
        poller = r1s != r2s
        if watcher != bool(pair.get("watcher_wake")):
            print("FAILED:RES-0180-probe2 watcher recompute drift", pair.get("id"))
            return 1
        if poller != bool(pair.get("poller_wake")):
            print("FAILED:RES-0180-probe2 poller recompute drift", pair.get("id"))
            return 1
        if watcher and r1w == r2w:
            watcher_false += 1
        if poller and (not watcher):
            poller_false += 1
        recomputed.append(pair.get("id"))
    n = len(recomputed)
    if n < 20:
        print(f"FAILED:RES-0180-probe2 sample_size={n} want>=20")
        return 1
    if watcher_false:
        print("FAILED:RES-0180-probe2 watcher false-wakes on stable wake_value", watcher_false)
        return 1
    meas = doc.get("measurements") or {}
    if int(meas.get("sample_size") or 0) != n:
        print("FAILED:RES-0180-probe2 sample_size drift", meas.get("sample_size"), n)
        return 1
    claims = doc.get("claims") or []
    if len(claims) < 2:
        print("FAILED:RES-0180-probe2 claims thin")
        return 1
    for claim in claims:
        sigs = claim.get("signals") or []
        if len(sigs) < 2:
            print("FAILED:RES-0180-probe2 claim single-signal", claim.get("id"))
            return 1
        lin = claim.get("lineage") or {}
        sha = str(lin.get("sha256") or "")
        if len(sha) != 64:
            print("FAILED:RES-0180-probe2 lineage sha256", claim.get("id"))
            return 1
        if not lin.get("resolved_url") or not lin.get("fetch_timestamp"):
            print("FAILED:RES-0180-probe2 lineage incomplete", claim.get("id"))
            return 1
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True:
        print("FAILED:RES-0180-probe2 reviewer not independent")
        return 1
    # Independent of probe 1: do not re-run both_states here. Confirm live
    # elapsed_seconds > 0 so the pair is not a cloned local mutation.
    if float(meas.get("elapsed_seconds") or 0) <= 0:
        print("FAILED:RES-0180-probe2 elapsed_seconds not real")
        return 1
    if meas.get("standing_7d_daemon") is True:
        print("FAILED:RES-0180-probe2 overclaim standing 7d daemon")
        return 1
    out = {
        "probe": "probe2-live-sample",
        "unit_id": UNIT,
        "pass": True,
        "sample_size": n,
        "watcher_false_wakes": watcher_false,
        "poller_false_wakes": poller_false,
        "elapsed_seconds": meas.get("elapsed_seconds"),
        "week_native_total": meas.get("week_native_total"),
        "recomputed_ids": recomputed,
    }
    print(json.dumps(out, indent=1, sort_keys=True))
    print("SUCCESS:RES-0180-probe2 live pairs recompute; watcher is not a poller")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
