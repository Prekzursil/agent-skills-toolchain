#!/usr/bin/env python3
"""Named probe 1: live both-states lockfile install matrix (behavioral)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / "command-center/research/marketplace-ecosystem/RES-0130-lockfile-resolution-under-revocation.json"
UNIT = "RES-0130"


def main() -> int:
    matrix = H.run_matrix()
    summary = H.summarize(matrix)
    errs = H.assert_live_invariants(matrix, summary)
    if errs:
        print("FAILED:RES-0130-probe1", errs)
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0130-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT:
        print("FAILED:RES-0130-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:RES-0130" not in text:
        print("FAILED:RES-0130-probe1 sentinel-absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0130-probe1 self-declared", doc.get("state"))
        return 1
    rec = doc.get("live_matrix_summary") or {}
    if rec.get("both_states_all_pass") is not True:
        print("FAILED:RES-0130-probe1 artifact both_states not true")
        return 1
    if rec.get("mirror_match_all_five") is not True:
        print("FAILED:RES-0130-probe1 artifact mirror_match not true")
        return 1
    rec_research = {r["ecosystem"]: r for r in rec.get("research") or []}
    for row in summary["research"]:
        eco = row["ecosystem"]
        recorded = rec_research.get(eco) or {}
        if recorded.get("stale_mirror_mismatch_code") != row["stale_mirror_mismatch_code"]:
            print("FAILED:RES-0130-probe1 mismatch-code drift", eco)
            return 1
        if recorded.get("stale_mirror_match_ok") is not True:
            print("FAILED:RES-0130-probe1 recorded match not ok", eco)
            return 1
    payload = {
        "pass": True,
        "probe": "probe1-both-states",
        "unit_id": UNIT,
        "ecosystems": list(H.ECOSYSTEMS),
        "both_states_all_pass": True,
        "mirror_match_all_five": True,
        "mirror_mismatch_all_fail": True,
        "decoy_never_installed": True,
        "detector_control": summary["detector_control"],
    }
    print(json.dumps(payload, sort_keys=True))
    print("both-states reachable=ok offline_empty=fail for all five; matching stale mirror installs pin; poison mirror fails closed")
    print("SUCCESS:RES-0130-probe1 both-states lockfile matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
