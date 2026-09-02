"""Probe 2: planted rival predicate fails the AST sweep (detector control).

Both-states: fire on the planted copy, silent on the clean production tree.
A zero-duplicate verdict is accepted only after the planted control ran.
Use-versus-mention: docs/completion_notes.py must not be reported as a fork.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.rival_scan import EXPECTED_ROLES, scan_with_control  # noqa: E402

SCAN_ROOT = REPO / "tools" / "agentspec"
UNIT = "IMP-0226"


def main() -> int:
    report = scan_with_control(SCAN_ROOT)
    findings = report["planted_findings"]
    kinds = {s["kind"] for s in findings}
    functions = {s["function"] for s in findings}
    paths = {s["path"] for s in findings}
    clean = report["clean"]

    checks = [
        (
            "control_ran_before_verdict",
            report.get("control_ran_before_zero_duplicate_verdict"),
        ),
        ("control_fired", report.get("control_fired")),
        ("silent_on_clean", report.get("silent_on_clean")),
        ("zero_duplicate_accepted", report.get("zero_duplicate_accepted")),
        ("method_is_ast", report.get("method") == "ast-import-graph"),
        ("used_grep_false", report.get("used_grep") is False),
        ("mention_only_not_flagged", report.get("mention_only_not_flagged")),
        ("planted_partial_path", any("fork_partial" in p for p in paths)),
        ("planted_truthiness_path", any("fork_truthiness" in p for p in paths)),
        ("found_local_copy_judge", "judge" in functions),
        ("found_is_complete", "is_complete" in functions),
        (
            "found_truthiness_or_local_copy",
            "truthiness-stand-in" in kinds or "local-copy" in kinds,
        ),
        ("clean_fan_in_count", clean["fan_in_count"] == 7),
        ("clean_roles", set(clean["roles_present"]) == EXPECTED_ROLES),
        ("clean_canonical_present", clean["canonical_present"] is True),
        ("clean_missing_imports_empty", not clean["missing_imports"]),
        ("clean_zero_duplicates", clean["zero_duplicates"] is True),
    ]
    payload = {
        "probe": "probe2-planted-rival",
        "unit_id": UNIT,
        "method": report.get("method"),
        "control_fired": report.get("control_fired"),
        "silent_on_clean": report.get("silent_on_clean"),
        "zero_duplicate_accepted": report.get("zero_duplicate_accepted"),
        "planted_paths": report.get("planted_paths"),
        "finding_count": len(findings),
        "finding_functions": sorted(functions),
        "finding_paths": sorted(paths),
        "finding_kinds": sorted(kinds),
        "checks": {name: bool(ok) for name, ok in checks},
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:{UNIT}-probe2 {name}")
            return 1
    print("SUCCESS:IMP-0226-probe2 planted rival detected; clean silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
