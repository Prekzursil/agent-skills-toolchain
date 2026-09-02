#!/usr/bin/env python3
"""Probe 1: reproduce A1-manifest vs A2-ssot overlapping ownership.

Both-states: A1-only and A2-only tables are singular; maximal union is not.
Split-brain drift > 0; agree-state drift = 0 still FAIL-CLOSED on duplicates.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import compose as C  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/A9/REFUTATION.json"
A9_DESIGN = REPO / "command-center/phase3/A9/DESIGN.json"


def main() -> int:
    run = S.run_scenario()
    printable = {
        k: run[k]
        for k in sorted(run)
        if k not in {"pass", "maximal_table", "named_pair"}
    }
    print(json.dumps(printable, sort_keys=True, default=str)[:4000])
    if not run.get("pass"):
        print("FAILED:ARC-0065-probe1 scenario did not reproduce")
        return 1
    if A9_DESIGN.is_file():
        print("FAILED:ARC-0065-probe1 A9 DESIGN.json exists; this unit must not rebuild it")
        return 1
    if not ART.is_file():
        print("FAILED:ARC-0065-probe1 REFUTATION.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0065-probe1 self-declared {doc.get('state')}")
        return 1
    rec = (doc.get("scenario") or {}).get("reproduction") or {}
    rec_ok = (
        rec.get("a1_only_singular") is True
        and rec.get("a2_only_singular") is True
        and rec.get("maximal_has_duplicate") is True
        and rec.get("split_brain_drift") is True
        and rec.get("agree_still_duplicate") is True
        and rec.get("hybrid_worse_than_best_single") is True
        and rec.get("hybrid_confirmed_better") is False
    )
    if not rec_ok:
        print("FAILED:ARC-0065-probe1 REFUTATION reproduction flags false")
        return 1
    proc = doc.get("scenario", {}).get("procedure") or []
    if len(proc) < 4:
        print("FAILED:ARC-0065-probe1 procedure too short")
        return 1
    det = doc.get("singularity_detector") or {}
    if "duplicate_class_count" not in det or "best_single_duplicate_class_count" not in det:
        print("FAILED:ARC-0065-probe1 detector counts missing")
        return 1
    if int(det["duplicate_class_count"]) != int(run["maximal_duplicate_class_count"]):
        print("FAILED:ARC-0065-probe1 artifact dup count != live extract")
        return 1
    if int(det["best_single_duplicate_class_count"]) != int(
        run["best_single_duplicate_class_count"]
    ):
        print("FAILED:ARC-0065-probe1 artifact best-single != live")
        return 1
    live_dups = run["maximal_duplicate_classes"]
    art_dups = det.get("duplicate_classes") or {}
    if art_dups != live_dups:
        print("FAILED:ARC-0065-probe1 artifact duplicate classes != live")
        return 1
    pair = doc.get("named_pair") or {}
    subs = [s.get("id") for s in (pair.get("subsystems") or [])]
    if subs != [C.NAMED_A, C.NAMED_B]:
        print(f"FAILED:ARC-0065-probe1 named pair {subs}")
        return 1
    silent = str((doc.get("scenario") or {}).get("silent_loss_file") or "")
    if not silent.startswith("command-center/phase3/A1/DESIGN.json:"):
        print(f"FAILED:ARC-0065-probe1 silent_loss_file not A1 DESIGN: {silent}")
        return 1
    if "SUCCESS:ARC-0065" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0065-probe1 sentinel absent")
        return 1
    print(
        "a1_singular="
        f"{run['a1_only_duplicate_class_count']==0} "
        f"a2_singular={run['a2_only_duplicate_class_count']==0} "
        f"maximal_dup={run['maximal_duplicate_class_count']} "
        f"split_drift={run['split']['drift_count']} "
        f"agree_drift={run['agree']['drift_count']} "
        f"hybrid_worse={run['hybrid_worse_than_best_single']}"
    )
    print("SUCCESS:ARC-0065-probe1 overlapping-authority pair reproduced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
