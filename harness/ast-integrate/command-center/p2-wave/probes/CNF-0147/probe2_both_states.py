#!/usr/bin/env python3
"""Probe 2: both-states restore and warm-cache masking (different field than probe 1).

Probe 1 reads the unshare control-fetch error. This probe reads whether open-warm
matches open-cold after the blocked cells, and whether warm cache masks silent
downloads while declared-network tests stay red on both cache axes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from matrix import run_matrix  # noqa: E402
from suite import SILENT_COUNT  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0147.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0147-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0147-probe2 self-declared", doc.get("state"))
        return 1

    live = run_matrix()
    if not live["both_states"]["baseline_restored"]:
        print("FAILED:CNF-0147-probe2 baseline not restored after blocked cells")
        print(json.dumps(live["both_states"], indent=2)[:2000])
        return 1
    if live["attribution"]["unknown"]:
        print("FAILED:CNF-0147-probe2 unknown", live["attribution"]["unknown"])
        return 1

    silent = live["attribution"]["silent_download"]
    declared = live["attribution"]["declared_dependency"]
    masked = live["cache_masked"]
    if sorted(masked) != sorted(silent):
        print("FAILED:CNF-0147-probe2 cache-mask set != silent-download")
        return 1
    if len(silent) != SILENT_COUNT or len(declared) != 2:
        print(
            f"FAILED:CNF-0147-probe2 counts silent={len(silent)} "
            f"declared={len(declared)}"
        )
        return 1

    runs = {r["id"]: r for r in live["runs"]}
    bw = {row["id"]: row for row in runs["blocked-warm"]["results"]}
    bc = {row["id"]: row for row in runs["blocked-cold"]["results"]}
    oc = {row["id"]: row for row in runs["open-cold"]["results"]}
    ow = {row["id"]: row for row in runs["open-warm"]["results"]}

    for test_id in silent:
        if not oc[test_id]["ok"] or not ow[test_id]["ok"]:
            print(f"FAILED:CNF-0147-probe2 silent {test_id} not green with network")
            return 1
        if bc[test_id]["ok"]:
            print(f"FAILED:CNF-0147-probe2 silent {test_id} green under blocked-cold")
            return 1
        if not bw[test_id]["ok"]:
            print(f"FAILED:CNF-0147-probe2 silent {test_id} not masked by warm cache")
            return 1
    for test_id in declared:
        if bc[test_id]["ok"] or bw[test_id]["ok"]:
            print(f"FAILED:CNF-0147-probe2 declared {test_id} not red under block")
            return 1
        if not oc[test_id]["ok"]:
            print(f"FAILED:CNF-0147-probe2 declared {test_id} not green with network")
            return 1

    rec = doc.get("cache_interaction") or {}
    rec_masked = list(rec.get("masked_test_ids") or [])
    if sorted(rec_masked) != sorted(masked):
        print("FAILED:CNF-0147-probe2 artifact cache-mask drift")
        return 1
    rec_both = (doc.get("both_states") or {}).get("baseline_restored")
    if rec_both is not True:
        print("FAILED:CNF-0147-probe2 artifact both_states.baseline_restored false")
        return 1
    rec_unknown = (doc.get("attribution") or {}).get("unknown")
    if rec_unknown is None:
        print("FAILED:CNF-0147-probe2 artifact missing attribution.unknown")
        return 1
    if list(rec_unknown):
        print("FAILED:CNF-0147-probe2 artifact unknown bucket nonempty")
        return 1

    hermetic = live["hermetic_ok"]
    for test_id in hermetic:
        for cell in ("open-cold", "blocked-cold", "blocked-warm", "open-warm"):
            row = {r["id"]: r for r in runs[cell]["results"]}[test_id]
            if not row["ok"]:
                print(f"FAILED:CNF-0147-probe2 hermetic {test_id} failed in {cell}")
                return 1

    out = {
        "probe": "probe2-both-states-and-cache",
        "unit_id": "CNF-0147",
        "baseline_restored": True,
        "warm_masks_silent_download": True,
        "declared_red_on_both_cache_axes": True,
        "silent_download_n": len(silent),
        "declared_dependency_n": len(declared),
        "hermetic_n": len(hermetic),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"restored=True masked={len(masked)} declared_red=True "
        f"hermetic={len(hermetic)}"
    )
    print("SUCCESS:CNF-0147-probe2 both-states restore and cache interaction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
