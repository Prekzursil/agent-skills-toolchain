#!/usr/bin/env python3
"""Probe 1: three-point snapshot differential (files, registry analog, tasks)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from common import COMPLETION_SENTINEL, OUTPUT_REL, UNIT_ID  # noqa: E402
from scenario import run_three_point  # noqa: E402
from validate_artifact import load_artifact, validate  # noqa: E402


def main() -> int:
    doc, text = load_artifact()
    errors = validate(doc, text)
    if errors:
        print("FAILED:ADV-0047-probe1 artifact " + ";".join(errors[:8]))
        return 1
    if COMPLETION_SENTINEL not in text:
        print("FAILED:ADV-0047-probe1 sentinel-absent")
        return 1

    with tempfile.TemporaryDirectory(prefix="adv0047-p1-") as tmp_s:
        live = run_three_point(Path(tmp_s))

    diff = live["differential"]
    if not diff["control_install_created_nonempty"]:
        print("FAILED:ADV-0047-probe1 install-created set empty")
        return 1
    if diff["install_created_count"] < 1:
        print("FAILED:ADV-0047-probe1 count")
        return 1
    if not diff["intentional_retention"]:
        print("FAILED:ADV-0047-probe1 intentional retention not listed")
        return 1
    if not diff["unintentional_residue"]:
        print("FAILED:ADV-0047-probe1 expected unintentional residue")
        return 1
    overlap = set(diff["intentional_retention"]) & set(diff["unintentional_residue"])
    if overlap:
        print("FAILED:ADV-0047-probe1 mixed classification", sorted(overlap))
        return 1
    if diff["user_data_deleted"]:
        print("FAILED:ADV-0047-probe1 user data deleted (P1)")
        return 1
    if not diff["user_data_byte_identical"]:
        print("FAILED:ADV-0047-probe1 user data mutated")
        return 1
    if not diff["registry_residue"]:
        print("FAILED:ADV-0047-probe1 registry analog residue missing")
        return 1
    if not diff["tasks_residue"]:
        print("FAILED:ADV-0047-probe1 task residue missing")
        return 1
    art_diff = ((doc.get("three_point") or {}).get("differential")) or {}
    if int(art_diff.get("install_created_count") or 0) != diff["install_created_count"]:
        print(
            "FAILED:ADV-0047-probe1 artifact count mismatch",
            art_diff.get("install_created_count"),
            diff["install_created_count"],
        )
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-snapshot-diff",
                "unit_id": UNIT_ID,
                "install_created_count": diff["install_created_count"],
                "residue_count": len(diff["residue_files"]),
                "intentional_n": len(diff["intentional_retention"]),
                "unintentional_n": len(diff["unintentional_residue"]),
                "registry_residue": diff["registry_residue"],
                "tasks_residue": diff["tasks_residue"],
                "mcp_residue": diff["mcp_residue"],
                "user_data_kept": diff["user_data_kept"],
                "control_nonempty": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:ADV-0047-probe1 three-point snapshot differential")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
