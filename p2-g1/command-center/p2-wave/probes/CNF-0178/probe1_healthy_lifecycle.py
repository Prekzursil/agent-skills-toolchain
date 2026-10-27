#!/usr/bin/env python3
"""Named probe 1: published-artifact install/update/rollback/uninstall + repo-absence.

Signal: filesystem manifests (path, size, sha256) at each lifecycle step.
Rollback proof is restored command behaviour, not the version string.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import SEED_A, V1_BEHAVIOR, V2_BEHAVIOR, healthy_lifecycle  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0178.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0178-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0178":
        print("FAILED:CNF-0178-probe1 unit_id", doc.get("unit_id"))
        return 1
    text = json.dumps(doc)
    if "SUCCESS:CNF-0178" not in text:
        print("FAILED:CNF-0178-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0178-probe1 self-declared", doc.get("state"))
        return 1

    live = healthy_lifecycle(SEED_A)
    if not live.get("ok"):
        print("FAILED:CNF-0178-probe1 healthy lifecycle")
        return 1
    if live["behaviors"]["install"] != V1_BEHAVIOR:
        print("FAILED:CNF-0178-probe1 install behaviour")
        return 1
    if live["behaviors"]["update"] != V2_BEHAVIOR:
        print("FAILED:CNF-0178-probe1 update behaviour")
        return 1
    if live["behaviors"]["rollback"] != V1_BEHAVIOR:
        print("FAILED:CNF-0178-probe1 rollback did not restore v1 behaviour")
        return 1
    if not live.get("repo_absence", {}).get("ok"):
        print("FAILED:CNF-0178-probe1 repo present on install path")
        print(json.dumps(live.get("repo_absence"), indent=2)[:2000])
        return 1
    if not live.get("user_data_byte_identical_after_uninstall"):
        print("FAILED:CNF-0178-probe1 uninstall mutated user data")
        return 1
    if not live.get("owned_paths_removed"):
        print("FAILED:CNF-0178-probe1 owned paths remain")
        return 1

    recorded = (doc.get("baseline_repro") or {}).get("behaviors") or {}
    if recorded.get("rollback") != V1_BEHAVIOR:
        print("FAILED:CNF-0178-probe1 artifact rollback behaviour drift")
        return 1
    if not (doc.get("baseline_repro") or {}).get("repo_absence", {}).get("ok"):
        print("FAILED:CNF-0178-probe1 artifact repo-absence not ok")
        return 1

    payload = {
        "pass": True,
        "probe": "probe1-healthy-lifecycle",
        "unit_id": "CNF-0178",
        "behaviors": live["behaviors"],
        "repo_absence_ok": True,
        "user_data_intact": True,
        "steps": [s["step"] for s in live["steps"]],
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "install="
        + V1_BEHAVIOR
        + " update="
        + V2_BEHAVIOR
        + " rollback="
        + V1_BEHAVIOR
        + " repo_absent=True user_data_intact=True"
    )
    print("SUCCESS:CNF-0178-probe1 published-artifact lifecycle filesystem-diff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
