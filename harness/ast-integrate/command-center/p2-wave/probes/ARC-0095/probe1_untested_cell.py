#!/usr/bin/env python3
"""Named probe 1: remove a test result; the cell reverts to NOT-CHECKED.

Both-states: with the receipt the cell is SUPPORTED; after deletion it is
NOT-CHECKED, is_pass false, and must not stay green / SUPPORTED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import matrix as M  # noqa: E402

ART = REPO / "command-center/phase4/contracts/ARC-0095.json"

AXES = {
    "operating_system": ["linux", "windows"],
    "client": ["claude-code"],
    "client_version": ["2.0.0"],
    "shell": ["bash"],
    "package_version": ["0.1.0"],
}


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0095-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("contract artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "ARC-0095":
        return fail(f"unit_id {doc.get('unit_id')!r}")
    blob = json.dumps(doc)
    if "SUCCESS:ARC-0095" not in blob:
        return fail("sentinel absent")
    rules = doc.get("evidence_rules") or {}
    if rules.get("supported_requires_recorded_run") is not True:
        return fail("contract missing supported_requires_recorded_run")
    if "NOT-CHECKED" not in blob or "UNTESTED" not in blob:
        return fail("contract missing untested representation")

    cid = M.cell_id(
        {
            "operating_system": "linux",
            "client": "claude-code",
            "client_version": "2.0.0",
            "shell": "bash",
            "package_version": "0.1.0",
        }
    )
    receipt = M.make_receipt(
        operating_system="linux",
        client="claude-code",
        client_version="2.0.0",
        shell="bash",
        package_version="0.1.0",
        run_id="arc-0095-probe1-planted",
    )

    with_run = M.generate(
        [receipt],
        axes=AXES,
        infer=False,
        program_ran_on=["linux"],
        expand_versions_from_receipts=False,
    )
    without = M.generate(
        [],
        axes=AXES,
        infer=False,
        program_ran_on=["linux"],
        expand_versions_from_receipts=False,
    )

    green = M.cell_by_id(with_run, cid)
    gone = M.cell_by_id(without, cid)
    if green is None or gone is None:
        return fail("cell missing from generated matrix")
    if green["status"] != "SUPPORTED" or not green["is_pass"]:
        return fail(f"planted receipt did not support cell: {green['status']}")
    if gone["status"] != "NOT-CHECKED":
        return fail(f"after removal status={gone['status']!r} want NOT-CHECKED")
    if gone["is_pass"] or gone["render"]["is_pass"]:
        return fail("untested cell still is_pass / green")
    if gone["status"] == "SUPPORTED" or gone["render"]["token"] in M.PASS_LIKE:
        return fail("untested cell stayed pass-like")
    if gone["render"]["token"] != "NOT-CHECKED":
        return fail(f"token {gone['render']['token']!r}")
    if gone["render"]["display"] != "UNTESTED":
        return fail("display alias UNTESTED missing")
    if not (gone.get("reason") or "").strip():
        return fail("untested cell has blank reason")
    if with_run["supported_cell_count"] < 1:
        return fail("with-receipt matrix has no SUPPORTED cell")
    if without["supported_cell_count"] != 0:
        return fail("after removal a SUPPORTED cell remains")

    installer = dict(receipt)
    installer["run_id"] = "arc-0095-probe1-installer"
    installer["observation_kind"] = "installer-exit"
    installer_mx = M.generate(
        [installer],
        axes=AXES,
        infer=False,
        program_ran_on=["linux"],
        expand_versions_from_receipts=False,
    )
    inst_cell = M.cell_by_id(installer_mx, cid)
    if inst_cell is None or inst_cell["status"] != "NOT-CHECKED":
        return fail("installer-exit was read as a pass")
    if installer_mx["receipts_accepted"] != 0:
        return fail("installer-exit receipt was accepted")

    live_untested = (doc.get("generator_run") or {}).get("untested_cell_count")
    if not isinstance(live_untested, int):
        return fail("live generator_run.untested_cell_count missing")

    summary = {
        "probe": "probe1-untested-cell",
        "unit_id": "ARC-0095",
        "pass": True,
        "with_receipt_status": green["status"],
        "without_receipt_status": gone["status"],
        "reverted_to_not_checked": gone["status"] == "NOT-CHECKED",
        "stayed_green": False,
        "installer_exit_rejected": True,
        "live_untested_cell_count": live_untested,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"with={green['status']} without={gone['status']} "
        f"installer={inst_cell['status']} live_untested={live_untested}"
    )
    print("SUCCESS:ARC-0095-probe1 untested-cell control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
