#!/usr/bin/env python3
"""Named probe 1: re-derive red-at-parent / green-at-fix from fixture source.

Runs time-travel BEFORE reading the artifact conclusion. Then checks the
artifact recorded the same authentic pair (and did not self-declare BLOCKED).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

import timetravel as TT  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0022-pre-fix-timetravel.json"
SENTINEL = (
    "SUCCESS:CNF-0022 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every examined fix has "
    "a recorded red-at-parent and green-at-fix pair, or a filed discrepancy. "
    "Any other terminal state is FAILED:CNF-0022 <classification> with the "
    "diagnostic tail attached."
)


def domain(doc: dict) -> dict:
    """Domain payload lives under report (repro-report class pin)."""
    rep = doc.get("report")
    if isinstance(rep, dict) and isinstance(rep.get("examined_fixes"), list):
        return rep
    return doc


def main() -> int:
    live = TT.run_campaign()
    authentic = next(r for r in live["rows"] if r["id"] == "FIX-ADD-OFFBYONE")
    printable = {
        "probe": "probe1-red-at-parent",
        "unit_id": "CNF-0022",
        "live_pattern": authentic["pattern"],
        "parent_exit_code": authentic["parent_exit_code"],
        "fix_exit_code": authentic["fix_exit_code"],
        "parent_output": authentic["parent_output"],
        "fix_output": authentic["fix_output"],
        "worktree_removed": authentic["worktree_removed"],
        "parent_sha": authentic["parent_sha"],
        "fix_sha": authentic["fix_sha"],
    }
    print(json.dumps(printable, sort_keys=True))
    if authentic["pattern"] != "RED-GREEN":
        print(f"FAILED:CNF-0022-probe1 live pattern {authentic['pattern']}")
        return 1
    if authentic["parent_exit_code"] == 0 or authentic["fix_exit_code"] != 0:
        print("FAILED:CNF-0022-probe1 parent not red or fix not green")
        return 1
    if "RED:" not in authentic["parent_output"]:
        print("FAILED:CNF-0022-probe1 missing verbatim red at parent")
        return 1
    if "GREEN:" not in authentic["fix_output"]:
        print("FAILED:CNF-0022-probe1 missing green at fix")
        return 1
    if not authentic["worktree_removed"]:
        print("FAILED:CNF-0022-probe1 worktree not removed")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0022-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "CNF-0022":
        print("FAILED:CNF-0022-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0022-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text or "SUCCESS:CNF-0022" not in text:
        print("FAILED:CNF-0022-probe1 sentinel absent")
        return 1
    recorded = next(
        (
            r
            for r in domain(doc).get("examined_fixes") or []
            if r.get("id") == "FIX-ADD-OFFBYONE"
        ),
        None,
    )
    if not recorded:
        print("FAILED:CNF-0022-probe1 authentic fix missing from artifact")
        return 1
    if recorded.get("pattern") != "RED-GREEN":
        print("FAILED:CNF-0022-probe1 artifact pattern", recorded.get("pattern"))
        return 1
    if recorded.get("parent_exit_code") == 0 or recorded.get("fix_exit_code") != 0:
        print("FAILED:CNF-0022-probe1 artifact pair is not red/green")
        return 1
    if "RED:" not in str(recorded.get("parent_output") or ""):
        print("FAILED:CNF-0022-probe1 artifact missing verbatim red output")
        return 1
    if recorded.get("classification") != "confirmed-defect-at-parent":
        print("FAILED:CNF-0022-probe1 classification", recorded.get("classification"))
        return 1
    print("SUCCESS:CNF-0022-probe1 red-at-parent green-at-fix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
