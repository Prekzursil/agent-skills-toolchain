#!/usr/bin/env python3
"""Probe 2 — process-table observation during the same class of run.

Mechanically different from probe 1: watches /proc command lines so a hook
that executes without successfully writing its beacon is still caught.
Does not use beacon-file presence as its pass criterion.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from harness import run_campaign, verdicts_from  # noqa: E402


def main() -> int:
    doc = run_campaign("proc")
    targets, tests, overall = verdicts_from(doc)
    control_proc = doc.get("proc_control") or []
    liveness = bool((doc.get("detector_liveness") or {}).get("pass"))
    # Control must not spawn ADV0026_BEACON children. Liveness still required
    # so a dead detector cannot mint REFUTED.
    ok = (not control_proc) and liveness
    out = {
        "pass": ok,
        "probe": "probe2-process-table",
        "unit_id": "ADV-0026",
        "overall": overall,
        "hostile_children": doc.get("proc_hostile"),
        "control_children": control_proc,
        "n_hostile_children": len(doc.get("proc_hostile") or []),
        "n_control_children": len(control_proc),
        "targets": targets,
        "tests": tests,
        "runtime_started": bool((doc.get("hostile_run") or {}).get("started")),
        "runtime_reason": (doc.get("hostile_run") or {}).get("reason"),
        "trust_gate": bool((doc.get("hostile_run") or {}).get("trust_gate")),
        "runtime_stderr_tail": (doc.get("hostile_run") or {}).get("stderr") or "",
        "detector_liveness": doc.get("detector_liveness"),
    }
    print(json.dumps(out, sort_keys=True))
    if not ok:
        print("FAILED:ADV-0026-probe2 control children or detector liveness")
        return 1
    print("SUCCESS:ADV-0026-probe2 process-table observation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
