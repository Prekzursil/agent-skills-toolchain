#!/usr/bin/env python3
"""Probe 1: reproduce the local commit-ceiling refusal as an executable procedure.

Both-states: 2048-unit local/worktree fan-out is refused; the same batch on
cloud is allowed; a 4-unit local batch is allowed (predicate not vacuous).
RAM (MemAvailable) hides the tighter commit headroom on this box.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/A5/REFUTATION.json"


def main() -> int:
    run = S.run_scenario()
    print(
        json.dumps(
            {
                "vacuity_small_local_allowed": run.get("vacuity_small_local_allowed"),
                "local_2048_refused": run.get("local_2048_refused"),
                "cloud_2048_allowed": run.get("cloud_2048_allowed"),
                "worktree_2048_refused": run.get("worktree_2048_refused"),
                "ram_hides_commit": run.get("ram_hides_commit"),
                "resource_ceiling": run.get("resource_ceiling"),
                "commit_per_worker": run.get("commit_per_worker"),
                "process_blast": run.get("process_blast"),
            },
            sort_keys=True,
        )
    )
    if not run.get("pass"):
        print("FAILED:ARC-0037-probe1 scenario did not reproduce")
        return 1
    if not ART.is_file():
        print("FAILED:ARC-0037-probe1 REFUTATION.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0037-probe1 self-declared {doc.get('state')}")
        return 1
    rec = (doc.get("scenario") or {}).get("reproduction") or {}
    rec_ok = (
        rec.get("vacuity_small_local_allowed") is True
        and rec.get("local_2048_refused") is True
        and rec.get("cloud_2048_allowed") is True
        and rec.get("worktree_2048_refused") is True
        and rec.get("ram_hides_commit") is True
    )
    if not rec_ok:
        print("FAILED:ARC-0037-probe1 REFUTATION reproduction flags false")
        return 1
    proc = doc.get("scenario", {}).get("procedure") or []
    if len(proc) < 4:
        print("FAILED:ARC-0037-probe1 procedure too short")
        return 1
    pred = doc.get("preflight_predicate") or {}
    if pred.get("actionable") is not True or not str(pred.get("executable") or "").strip():
        print("FAILED:ARC-0037-probe1 preflight is not an executable predicate")
        return 1
    print(
        "local_refused="
        f"{run.get('local_2048_refused')} cloud_allowed={run.get('cloud_2048_allowed')} "
        f"small_allowed={run.get('vacuity_small_local_allowed')} "
        f"ram_hides={run.get('ram_hides_commit')}"
    )
    print("SUCCESS:ARC-0037-probe1 commit-ceiling scenario reproduced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
