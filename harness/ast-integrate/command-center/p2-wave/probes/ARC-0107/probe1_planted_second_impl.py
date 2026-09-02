#!/usr/bin/env python3
"""Probe 1: plant a partial re-implementation and assert the detector finds it.

Both-states: fire on the planted tree, silent on the clean tree. A
zero-duplicate verdict is accepted only after the planted control ran.
Use-versus-mention: docs/mention_only.py must not be reported as a fork.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

TREE = HERE / "fixtures" / "tree"


def main() -> int:
    report = D.scan_with_control(TREE)
    findings = report["planted_findings"]
    kinds = {s["kind"] for s in findings}
    functions = {s["function"] for s in findings}
    paths = {s["path"] for s in findings}

    checks = [
        ("control_ran_before_verdict", report.get("control_ran_before_zero_duplicate_verdict")),
        ("control_fired", report.get("control_fired")),
        ("silent_on_clean", report.get("silent_on_clean")),
        ("zero_duplicate_accepted", report.get("zero_duplicate_accepted")),
        ("method_is_ast", report.get("method") == "ast-import-graph"),
        ("used_grep_false", report.get("used_grep") is False),
        ("mention_only_not_flagged", report.get("mention_only_not_flagged")),
        ("planted_partial_path", "fanin/fork_partial.py" in paths),
        ("planted_truthiness_path", "fanin/fork_truthiness.py" in paths),
        ("found_local_copy", "reduce_completion" in functions),
        ("found_is_complete", "is_complete" in functions),
        ("found_truthiness_kind", "truthiness-stand-in" in kinds or "local-copy" in kinds),
        ("clean_fan_in_count", report["clean"]["fan_in_count"] == 7),
        ("clean_canonical_present", report["clean"]["canonical_present"] is True),
        ("clean_missing_imports_empty", not report["clean"]["missing_imports"]),
    ]
    payload = {
        "probe": "probe1-planted-second-impl",
        "unit_id": "ARC-0107",
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
            print(f"FAILED:ARC-0107-probe1 {name}")
            return 1
    print("SUCCESS:ARC-0107-probe1 planted second implementation found; clean silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
