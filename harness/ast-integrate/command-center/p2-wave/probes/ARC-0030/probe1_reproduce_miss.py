#!/usr/bin/env python3
"""Probe 1: reproduce the never-selected installed-skill miss under A4.

Both-states: A4 index-select misses gold while metrics stay green; a
body-aware control and A1 always-on catch it. Uninstalling gold leaves
the turn metric vector unchanged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/A4/REFUTATION.json"
DESIGN = REPO / "command-center/phase3/A4/DESIGN.json"


def main() -> int:
    run = S.run_scenario()
    printable = {k: run[k] for k in sorted(run) if k != "pass"}
    print(json.dumps(printable, sort_keys=True, default=str)[:4000])
    if not run.get("pass"):
        print("FAILED:ARC-0030-probe1 scenario did not reproduce")
        return 1
    if not ART.is_file():
        print("FAILED:ARC-0030-probe1 REFUTATION.json missing")
        return 1
    if not DESIGN.is_file():
        print("FAILED:ARC-0030-probe1 DESIGN.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0030-probe1 self-declared {doc.get('state')}")
        return 1
    rec = (doc.get("scenario") or {}).get("reproduction") or {}
    rec_ok = (
        rec.get("silent_miss_under_a4") is True
        and rec.get("body_aware_catches") is True
        and rec.get("a1_always_on_catches") is True
        and rec.get("turn_metrics_identical_if_uninstalled") is True
    )
    if not rec_ok:
        print("FAILED:ARC-0030-probe1 REFUTATION reproduction flags false")
        return 1
    proc = doc.get("scenario", {}).get("procedure") or []
    if len(proc) < 4:
        print("FAILED:ARC-0030-probe1 procedure too short")
        return 1
    silent = str((doc.get("scenario") or {}).get("silent_loss_file") or "")
    if not silent.startswith("command-center/phase3/A4/DESIGN.json:"):
        print(f"FAILED:ARC-0030-probe1 silent_loss_file not DESIGN.json: {silent}")
        return 1
    if run["gold_never_selected"] is not True:
        print("FAILED:ARC-0030-probe1 gold was selected")
        return 1
    if run["metrics_all_green_on_miss"] is not True:
        print("FAILED:ARC-0030-probe1 metrics not green on miss")
        return 1
    if run["a4_selected"] != ["wf.catalog-class.discovery-only"]:
        print(f"FAILED:ARC-0030-probe1 unexpected selection {run['a4_selected']}")
        return 1
    named = doc.get("epistemic_miss") or {}
    if named.get("computed_not_asserted") is not True:
        print("FAILED:ARC-0030-probe1 epistemic_miss not computed")
        return 1
    if named.get("selected_ids") != run["a4_selected"]:
        print("FAILED:ARC-0030-probe1 artifact selected_ids != live run")
        return 1
    if "SUCCESS:ARC-0030" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0030-probe1 sentinel absent")
        return 1
    print(
        "silent="
        f"{run.get('silent_miss_under_a4')} body={run.get('body_aware_catches')} "
        f"a1={run.get('a1_always_on_catches')} green={run.get('metrics_all_green_on_miss')}"
    )
    print("SUCCESS:ARC-0030-probe1 epistemic-silence scenario reproduced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
