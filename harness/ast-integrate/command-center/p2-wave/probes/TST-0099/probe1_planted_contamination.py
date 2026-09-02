#!/usr/bin/env python3
"""Named probe 1: planted shared-index contamination must be detectable.

Control: four file-disjoint writers in ONE worktree, then `git add -A`.
The probe fails closed if that planted sweep is silent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from experiment import N_AGENTS, run_planted_contamination  # noqa: E402

ART = REPO / "command-center/receipts/TST-0099.json"


def main() -> int:
    planted = run_planted_contamination()
    if planted.get("n_agents") != N_AGENTS:
        print(f"FAILED:TST-0099-probe1 n_agents={planted.get('n_agents')}")
        return 1
    if not planted.get("detected"):
        print("FAILED:TST-0099-probe1 planted contamination was silent")
        print(json.dumps(planted, indent=2)[:2000])
        return 1
    quoted = planted.get("sibling_paths_quoted") or []
    if len(quoted) < 1:
        print("FAILED:TST-0099-probe1 no quoted sibling path")
        return 1
    staged = planted.get("staged") or []
    if not any(p.startswith("shard_") and p != "shard_0/work.txt" for p in staged):
        print(f"FAILED:TST-0099-probe1 staged set missed siblings: {staged}")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0099-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0099":
        print("FAILED:TST-0099-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:TST-0099" not in text:
        print("FAILED:TST-0099-probe1 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0099-probe1 self-declared:{st}")
        return 1
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    ctrl = tests.get("test_the_probe_can_detect_a_planted_contamination") or {}
    if ctrl.get("result") != "PASS":
        print("FAILED:TST-0099-probe1 receipt control test not PASS")
        return 1
    if "shard_1/work.txt" not in text:
        print("FAILED:TST-0099-probe1 receipt does not quote a sibling path")
        return 1

    print(json.dumps({
        "probe": "probe1-planted-contamination",
        "unit_id": "TST-0099",
        "detected": True,
        "n_agents": N_AGENTS,
        "staged": staged,
        "quoted": quoted[:4],
        "pass": True,
    }, sort_keys=True))
    print(f"detected=True n_agents={N_AGENTS} quoted={quoted[0]}")
    print("SUCCESS:TST-0099-probe1 planted contamination is detectable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
