#!/usr/bin/env python3
"""Probe 1: launch the unified cockpit and confirm the registry pane is live.

Independent signal (1): the new pane renders with live values, confirmed by
launching the cockpit. Pre-existing panes still render (count + content).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))
sys.path.insert(0, str(REPO / "tools" / "monitorcore"))
sys.path.insert(0, str(HERE))

from cockpit_pane import PANE_ID  # noqa: E402
from monitorcore.cockpit import BASELINE_PANE_IDS  # noqa: E402
from scenario import make_health  # noqa: E402

OUT = HERE / "probe1-cockpit-live.raw.json"


def main() -> int:
    health, _clock, store_path = make_health(stale=False)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(REPO / "tools" / "monitorcore"),
            str(REPO / "tools" / "marketplace"),
            env.get("PYTHONPATH", ""),
        ]
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "monitorcore.unified",
            "cockpit",
            "--store",
            str(store_path),
            "--format",
            "json",
        ],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        print("FAILED:IMP-0128-probe1 cockpit launch")
        print(proc.stdout[-1500:])
        print(proc.stderr[-1500:])
        return 1
    doc = json.loads(proc.stdout)
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    ids = doc.get("pane_ids") or []
    if doc.get("baseline_count") != 5:
        print(f"FAILED:IMP-0128-probe1 baseline_count={doc.get('baseline_count')}")
        return 1
    if list(doc.get("baseline_ids") or []) != list(BASELINE_PANE_IDS):
        print("FAILED:IMP-0128-probe1 baseline ids changed")
        return 1
    if PANE_ID not in ids:
        print(f"FAILED:IMP-0128-probe1 registry pane missing ids={ids}")
        return 1
    if doc.get("pane_count") != 6:
        print(f"FAILED:IMP-0128-probe1 pane_count={doc.get('pane_count')}")
        return 1
    panes = {p["id"]: p for p in doc["panes"]}
    for pid in BASELINE_PANE_IDS:
        pane = panes[pid]
        if pane.get("kind") != "baseline" or not pane.get("lines"):
            print(f"FAILED:IMP-0128-probe1 baseline pane {pid} empty")
            return 1
    reg = panes[PANE_ID]
    statuses = reg.get("statuses") or {}
    values = reg.get("values") or {}
    if any(statuses.get(k) != "FRESH" for k in values):
        print(f"FAILED:IMP-0128-probe1 not live statuses={statuses}")
        return 1
    if values.get("index_lint_status") != "CLEAN":
        print(f"FAILED:IMP-0128-probe1 lint={values.get('index_lint_status')}")
        return 1
    if values.get("mirror_conflict_count") != 2:
        print(f"FAILED:IMP-0128-probe1 conflicts={values.get('mirror_conflict_count')}")
        return 1
    if values.get("blocked_publish_count") != 1:
        print(f"FAILED:IMP-0128-probe1 blocked={values.get('blocked_publish_count')}")
        return 1
    measured = reg.get("measured_at") or {}
    if not measured or not all(measured.values()):
        print("FAILED:IMP-0128-probe1 missing measured_at")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-cockpit-live",
                "unit_id": "IMP-0128",
                "pane_count": doc["pane_count"],
                "baseline_count": doc["baseline_count"],
                "registry_values": values,
                "launch_exit": proc.returncode,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0128-probe1 cockpit launch live registry pane")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
