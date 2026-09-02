#!/usr/bin/env python3
"""Probe 1: each ROLLBACK-MANIFEST entry's named artifacts still exist.

Both-states control: a fixture entry pointing at a live file is present;
a fixture entry pointing at a planted-absent path is missing. A checker
that is silent on both is measuring nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = E.REPO / "command-center/audit/AUD-0093-rollback-manifest-reality.json"
SENTINEL = (
    "SUCCESS:AUD-0093 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0093-probe1 {msg}")
    return 1


def main() -> int:
    loc, entries = E.load_live_entries()
    existence = [E.check_references(e) for e in entries]
    coverage = E.coverage_for_executed(entries)
    controls = E.fixture_manifest_controls()
    missing_n = sum(row["missing_n"] for row in existence)
    covered_n = sum(1 for row in coverage if row["covered_by_manifest"])
    chosen = loc.get("chosen") or {}

    payload = {
        "probe": "probe1-entry-artifacts",
        "manifest_present": loc["present"],
        "manifest_path": chosen.get("path"),
        "entry_n": len(entries),
        "missing_reference_n": missing_n,
        "covered_n": covered_n,
        "executed_n": len(coverage),
        "coverage": [
            {
                "action_id": row["action_id"],
                "covered_by_manifest": row["covered_by_manifest"],
            }
            for row in coverage
        ],
        "fixture_present_all_exist": controls["present_entry_all_exist"],
        "fixture_missing_n": controls["missing_entry_missing_n"],
        "both_states": controls["both_states"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    if not controls["control_pass"]:
        return fail(
            "existence-detector-does-not-discriminate "
            f"present={controls['present_entry_all_exist']} "
            f"missing_n={controls['missing_entry_missing_n']}"
        )
    if controls["present_entry_all_exist"] is not True:
        return fail("present-fixture not all_exist")
    if controls["missing_entry_missing_n"] < 1:
        return fail("missing-fixture did not report missing")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact-unparseable:{exc}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    ext = doc.get("extensions") or {}
    if bool(ext.get("manifest_present")) != bool(loc["present"]):
        return fail("artifact-manifest-present-mismatch")
    if int(ext.get("entry_n", -1)) != len(entries):
        return fail("artifact-entry-n-mismatch")

    print(
        "NEGATIVE CONTROL verbatim: fixtures/missing-entry.md names "
        "command-center/audit/AUD-0093-DOES-NOT-EXIST.bin; existence "
        f"missing_n={controls['missing_entry_missing_n']} (must be >=1). "
        "fixtures/present-entry.md names tools/lib/handled-ledger.mjs; "
        f"all_exist={controls['present_entry_all_exist']}."
    )
    print(
        "BOTH-STATES: FIRED on planted-absent path; SILENT on live "
        f"tools/lib/handled-ledger.mjs; live manifest_present={loc['present']} "
        f"entries={len(entries)} executed_covered={covered_n}/{len(coverage)}"
    )
    print("SUCCESS:AUD-0093-probe1 entry-artifacts both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
