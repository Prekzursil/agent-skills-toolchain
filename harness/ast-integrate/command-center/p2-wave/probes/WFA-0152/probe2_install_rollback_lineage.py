#!/usr/bin/env python3
"""Probe 2: install / rollback / re-resolve lineage on a fixture marketplace."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from common import COMPLETION_SENTINEL, OUTPUT_REL, UNIT_ID  # noqa: E402
from scenario import install_rollback_cycle  # noqa: E402


def main() -> int:
    art_path = REPO / OUTPUT_REL
    if not art_path.is_file() or art_path.stat().st_size <= 0:
        print("FAILED:WFA-0152-probe2 artifact missing")
        return 1
    text = art_path.read_text(encoding="utf-8")
    if COMPLETION_SENTINEL not in text:
        print("FAILED:WFA-0152-probe2 sentinel-absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0152-probe2 self-declared", doc.get("state"))
        return 1
    if doc.get("answers", {}).get("install_rollback_resolves_lineage") is not True:
        print("FAILED:WFA-0152-probe2 artifact does not claim lineage resolve after rollback")
        return 1

    with tempfile.TemporaryDirectory(prefix="wfa0152-p2-") as tmp_s:
        live = install_rollback_cycle(Path(tmp_s))

    if not live.get("pass"):
        print("FAILED:WFA-0152-probe2 live install/rollback cycle did not pass")
        print(json.dumps(live, sort_keys=True, default=str)[:4000])
        return 1

    if live["install_version"] != "1.1.0" or live["rollback_version"] != "1.0.0":
        print("FAILED:WFA-0152-probe2 versions", live["install_version"], live["rollback_version"])
        return 1
    if not live["every_ref_resolved_after_rollback"]:
        print("FAILED:WFA-0152-probe2 lineage unresolved after rollback")
        return 1
    if live["lost_on_rollback"]:
        print("FAILED:WFA-0152-probe2 rollback lost lineage that 1.0.0 still declares", live["lost_on_rollback"])
        return 1
    if "mech.fuse" not in live["added_by_minor"]:
        print("FAILED:WFA-0152-probe2 minor add did not carry mech.fuse", live["added_by_minor"])
        return 1
    if not (live["tamper_missing_record"] or {}).get("fired"):
        print("FAILED:WFA-0152-probe2 tamper missing-record did not fire")
        return 1
    if not (live["tamper_unresolved_source"] or {}).get("fired"):
        print("FAILED:WFA-0152-probe2 planted unresolved source did not fire")
        return 1

    art_lin = doc.get("lineage_carry_through") or {}
    if art_lin.get("every_ref_resolved_after_rollback") is False:
        print("FAILED:WFA-0152-probe2 artifact overclaims rollback resolve")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-install-rollback-lineage",
                "unit_id": UNIT_ID,
                "install_version": live["install_version"],
                "rollback_version": live["rollback_version"],
                "lineage_before": live["lineage_before_rollback"],
                "lineage_after": live["lineage_after_rollback"],
                "added_by_minor": live["added_by_minor"],
                "lost_on_rollback": live["lost_on_rollback"],
                "tamper_missing_fired": True,
                "tamper_unresolved_fired": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0152-probe2 install, rollback, re-resolve lineage compared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
