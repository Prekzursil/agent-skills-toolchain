#!/usr/bin/env python3
"""Named probe 1: re-run all three kill points; require restore + coherence health.

Does not construct or score the hybrid control (that is probe 2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import PHASES  # noqa: E402
from trial import catalog_kill_points, run_all_kill_points  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0043-partial-upgrade-rollback.json"
SENTINEL = (
    "SUCCESS:CNF-0043 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and all three kill points were "
    "exercised and each has a recorded post-rollback health-check result. Any "
    "other terminal state is FAILED:CNF-0043 <classification> with the "
    "diagnostic tail attached."
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0043-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "CNF-0043":
        print("FAILED:CNF-0043-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0043-probe1 self-declared", doc.get("state"))
        return 1
    if SENTINEL not in text:
        print("FAILED:CNF-0043-probe1 sentinel absent")
        return 1

    recorded = catalog_kill_points(doc)
    if len(recorded) != 3:
        print(f"FAILED:CNF-0043-probe1 recorded kill_points={len(recorded)}")
        return 1
    rec_phases = [k.get("phase") for k in recorded]
    if rec_phases != list(PHASES):
        print("FAILED:CNF-0043-probe1 recorded phases", rec_phases)
        return 1

    live = run_all_kill_points()
    if [k["phase"] for k in live] != list(PHASES):
        print("FAILED:CNF-0043-probe1 live phases", [k["phase"] for k in live])
        return 1

    for rec, got in zip(recorded, live):
        phase = got["phase"]
        if not got.get("kill_landed"):
            print(f"FAILED:CNF-0043-probe1 kill did not land {phase}")
            print(json.dumps(got.get("kill_signature"), indent=2)[:2000])
            return 1
        if not got.get("recovered_to_pre_state"):
            print(f"FAILED:CNF-0043-probe1 not recovered {phase}")
            return 1
        if not got["hash_comparison"].get("identical"):
            print(f"FAILED:CNF-0043-probe1 hash mismatch {phase}")
            print(json.dumps(got["hash_comparison"], indent=2)[:2000])
            return 1
        hc = got["health_check"]
        if hc.get("kind") != "coherence" or not hc.get("ok") or hc.get("hybrid"):
            print(f"FAILED:CNF-0043-probe1 health {phase}")
            print(json.dumps(hc, indent=2)[:2000])
            return 1
        if rec.get("kill_landed") is not True:
            print(f"FAILED:CNF-0043-probe1 artifact kill_landed drift {phase}")
            return 1
        if rec.get("recovered_to_pre_state") is not True:
            print(f"FAILED:CNF-0043-probe1 artifact recovered drift {phase}")
            return 1
        if (rec.get("health_check") or {}).get("kind") != "coherence":
            print(f"FAILED:CNF-0043-probe1 artifact used file-count health {phase}")
            return 1
        if (rec.get("health_check") or {}).get("ok") is not True:
            print(f"FAILED:CNF-0043-probe1 artifact health not ok {phase}")
            return 1
        live_obs = got["kill_signature"]["observed"]
        rec_obs = (rec.get("kill_signature") or {}).get("observed") or {}
        if rec_obs != live_obs:
            print(f"FAILED:CNF-0043-probe1 kill signature drift {phase}")
            print("live", live_obs, "artifact", rec_obs)
            return 1

    out = {
        "probe": "probe1-kill-points",
        "unit_id": "CNF-0043",
        "kill_points": [k["phase"] for k in live],
        "all_kill_landed": True,
        "all_recovered": True,
        "all_coherence_health_ok": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    for k in live:
        print(
            f"phase={k['phase']} landed={k['kill_landed']} "
            f"recovered={k['recovered_to_pre_state']} "
            f"health={k['health_check']['ok']} "
            f"hashes_identical={k['hash_comparison']['identical']}"
        )
    print("SUCCESS:CNF-0043-probe1 three kill-point rollbacks recover pre-state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
