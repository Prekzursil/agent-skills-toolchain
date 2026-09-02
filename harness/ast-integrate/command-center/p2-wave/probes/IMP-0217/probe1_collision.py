#!/usr/bin/env python3
"""Named probe 1: sibling Subworkflows with identical internal ids do not collide.

Signal 1: the colliding-internal-id fixture completes with two DISTINCT
receipt ids (sib.left::shared-step and sib.right::shared-step) and two
artifact files whose payloads differ (ALPHA vs BETA).

Signal 2 (both-states / mutation): the same fixture with namespacing
deleted last-write-wins onto a single internal id; the two payloads
cannot both survive. Production must stay green; the mutant must go red.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_fixture  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0217.json"
LEFT = "sib.left::shared-step"
RIGHT = "sib.right::shared-step"


def _task_ids(result) -> list[str]:
    return sorted(
        rid for rid, rec in result.receipts.items() if rec.get("kind") == "task"
    )


def _payloads(result) -> dict[str, str]:
    return {
        rid: rec["payload"]
        for rid, rec in result.receipts.items()
        if rec.get("kind") == "task"
    }


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0217-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0217" not in text:
        print("FAILED:IMP-0217-probe1 sentinel-absent")
        return 1
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0217":
        print("FAILED:IMP-0217-probe1 unit_id", doc.get("unit_id"))
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0217-p1-") as tmp:
        root = Path(tmp) / "named"
        result, fixture = run_fixture(root, namespacing=True)
        mutant, _ = run_fixture(Path(tmp) / "mutant", namespacing=False)

        want_ids = list(fixture["expected"]["distinct_receipt_ids"])
        got_ids = _task_ids(result)
        payloads = _payloads(result)
        left_space = Path(result.artifact_spaces["sib.left"])
        right_space = Path(result.artifact_spaces["sib.right"])
        left_file = left_space / "shared-step" / "out.txt"
        right_file = right_space / "shared-step" / "out.txt"

        if got_ids != sorted(want_ids):
            print(f"FAILED:IMP-0217-probe1 receipt_ids={got_ids} want={want_ids}")
            return 1
        if payloads.get(LEFT) != "ALPHA" or payloads.get(RIGHT) != "BETA":
            print(f"FAILED:IMP-0217-probe1 payloads={payloads}")
            return 1
        if not left_file.is_file() or not right_file.is_file():
            print("FAILED:IMP-0217-probe1 isolated artifact files missing")
            return 1
        if left_file.read_text(encoding="utf-8") != "ALPHA":
            print("FAILED:IMP-0217-probe1 left artifact", left_file.read_text(encoding="utf-8"))
            return 1
        if right_file.read_text(encoding="utf-8") != "BETA":
            print("FAILED:IMP-0217-probe1 right artifact", right_file.read_text(encoding="utf-8"))
            return 1
        if left_space.resolve() == right_space.resolve():
            print("FAILED:IMP-0217-probe1 artifact spaces not isolated")
            return 1
        if LEFT not in result.receipts or RIGHT not in result.receipts:
            print("FAILED:IMP-0217-probe1 namespaced receipts missing")
            return 1
        if result.receipts[LEFT]["id"] == result.receipts[RIGHT]["id"]:
            print("FAILED:IMP-0217-probe1 receipt ids not distinct")
            return 1

        mutant_ids = _task_ids(mutant)
        mutant_payloads = set(_payloads(mutant).values())
        mutant_files = [
            Path(p).read_text(encoding="utf-8")
            for p in mutant.artifacts.values()
            if Path(p).is_file()
        ]
        collided = (
            len(set(mutant_ids)) < 2
            or len(mutant_payloads) < 2
            or len(set(mutant_files)) < 2
        )
        if not collided:
            print(
                "FAILED:IMP-0217-probe1 namespacing mutant did not collide "
                f"ids={mutant_ids} payloads={sorted(mutant_payloads)} files={mutant_files}"
            )
            return 1

        print(f"named_receipts={got_ids}")
        print(f"payloads={payloads}")
        print("artifact_spaces_isolated=true")
        print(f"mutant_task_ids={mutant_ids} mutant_payloads={sorted(mutant_payloads)}")
        print("mutant_collided=true namespacing_deleted_goes_red=true")
        print("SUCCESS:IMP-0217-probe1 sibling-internal-id-collision")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
