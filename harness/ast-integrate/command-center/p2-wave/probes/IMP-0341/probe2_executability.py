#!/usr/bin/env python3
"""IMP-0341 probe 2: executability audit, both-states, published fail_count.

Known-present (vague "investigate further") must FAIL before any clean ledger
is reported. Concrete command-plus-oracle must PASS. fail_count is re-derived
from per-entry rows and must match the receipt's published integer. Adding one
vague row must increase fail_count by 1 (guards a hardcoded constant).
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.outcomes.unresolved import (  # noqa: E402
    audit_entry,
    audit_ledger,
    load_path,
    stopping_condition_15,
)

UNIT = "IMP-0341"
ART = REPO / "command-center" / "receipts" / "IMP-0341.json"
MIXED = HERE / "fixtures" / "mixed-ledger.json"
ORACLE = "command-center/p2-wave/probes/IMP-0341/fixtures/oracle_ok.py"
INPUT = "command-center/p2-wave/probes/IMP-0341/fixtures/input.txt"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0341-probe2 {msg}")
    return 1


def concrete() -> dict:
    return {
        "id": "NC-PASS",
        "question": "Does a concrete command-plus-oracle entry pass the audit?",
        "settling_experiment": {
            "command": f"python3 -B {ORACLE}",
            "inputs": [INPUT, ORACLE],
            "oracle": {"kind": "exit-code", "expect": 0},
        },
    }


def vague() -> dict:
    return {
        "id": "NC-VAGUE",
        "question": "Does a vague experiment string fail the executability audit?",
        "settling_experiment": "investigate further",
    }


def codes(row: dict) -> set[str]:
    return {r.get("code") for r in row.get("reasons") or [] if isinstance(r, dict)}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:IMP-0341" not in json.dumps(receipt):
        return fail("sentinel absent")

    # Known-present first: the vague string must fire.
    vague_row = audit_entry(vague(), root=REPO, index=0)
    if vague_row.get("ok"):
        return fail("vague 'investigate further' passed the audit")
    if "aspiration" not in codes(vague_row) and "unstructured-experiment" not in codes(vague_row):
        return fail(f"vague row reasons {vague_row.get('reasons')}")

    conc_row = audit_entry(concrete(), root=REPO, index=1)
    if not conc_row.get("ok"):
        return fail(f"concrete command-plus-oracle failed: {conc_row}")
    if not (conc_row["command_exists"] and conc_row["inputs_exist"] and conc_row["oracle_defined"]):
        return fail(f"concrete halves incomplete: {conc_row}")

    mixed_entries = load_path(MIXED)
    report = audit_ledger(mixed_entries, root=REPO)
    derived = sum(1 for r in report["entries"] if not r.get("ok"))
    if report["fail_count"] != derived:
        return fail(
            f"fail_count {report['fail_count']} != derived {derived} "
            "(published count must not be a summary)"
        )
    if report["fail_count"] + report["pass_count"] != report["entry_count"]:
        return fail("pass/fail/entry counts do not add up")
    if report["pass_count"] != 1 or report["fail_count"] != 4:
        return fail(
            f"mixed ledger expected pass=1 fail=4 got "
            f"pass={report['pass_count']} fail={report['fail_count']}"
        )
    by_id = {r["id"]: r for r in report["entries"]}
    if by_id["UQ-CONCRETE"].get("ok") is not True:
        return fail("UQ-CONCRETE did not pass")
    if by_id["UQ-VAGUE"].get("ok") is not False:
        return fail("UQ-VAGUE did not fail")
    if "oracle-undefined" not in codes(by_id["UQ-NO-ORACLE"]):
        return fail(f"UQ-NO-ORACLE reasons {by_id['UQ-NO-ORACLE'].get('reasons')}")
    if "input-missing" not in codes(by_id["UQ-MISSING-INPUT"]):
        return fail(f"UQ-MISSING-INPUT reasons {by_id['UQ-MISSING-INPUT'].get('reasons')}")
    if "command-missing" not in codes(by_id["UQ-MISSING-COMMAND"]):
        return fail(f"UQ-MISSING-COMMAND reasons {by_id['UQ-MISSING-COMMAND'].get('reasons')}")

    extra = deepcopy(mixed_entries)
    extra.append(vague())
    bumped = audit_ledger(extra, root=REPO)
    if bumped["fail_count"] != report["fail_count"] + 1:
        return fail(
            f"adding one vague row did not bump fail_count "
            f"{report['fail_count']} -> {bumped['fail_count']}"
        )
    extra_ok = deepcopy(mixed_entries)
    extra_ok.append(concrete())
    stayed = audit_ledger(extra_ok, root=REPO)
    if stayed["fail_count"] != report["fail_count"]:
        return fail("adding a concrete row changed fail_count")
    if stayed["pass_count"] != report["pass_count"] + 1:
        return fail("adding a concrete row did not bump pass_count")

    audit = receipt.get("executability_audit") if isinstance(receipt.get("executability_audit"), dict) else {}
    published = audit.get("fail_count")
    if published != report["fail_count"]:
        return fail(f"receipt fail_count {published} != live {report['fail_count']}")
    if not isinstance(published, int):
        return fail("receipt fail_count is not a published integer")
    failures = audit.get("failures")
    if not isinstance(failures, list) or len(failures) != published:
        return fail("receipt failures[] length does not match fail_count")

    gate = stopping_condition_15(mixed_entries, root=REPO)
    if gate.get("stop_allowed") is not False:
        return fail("stopping condition 15 allowed stop on a ledger with aspirations")
    clean_gate = stopping_condition_15([concrete()], root=REPO)
    if clean_gate.get("stop_allowed") is not True:
        return fail("stopping condition 15 blocked a fully executable ledger")

    payload = {
        "concrete_passed": True,
        "fail_count": report["fail_count"],
        "fail_count_bumps_on_extra_vague": True,
        "hardcoded_count_guard": True,
        "pass": True,
        "pass_count": report["pass_count"],
        "probe": "probe2-executability-audit",
        "published_matches_live": True,
        "stop_blocked_on_mixed": True,
        "unit_id": UNIT,
        "vague_failed": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"vague_failed=True concrete_passed=True fail_count={report['fail_count']} "
        f"published_matches_live=True"
    )
    print("SUCCESS:IMP-0341-probe2 executability audit both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
