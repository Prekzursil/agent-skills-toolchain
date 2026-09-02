#!/usr/bin/env python3
"""Probe 2: insecure-TLS config rejected at parse time + static no-insecure audit.

Independent of probe 1's live servers. Re-reads client source and the JS allowlist.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from matrix import run_parse_controls, static_audit  # noqa: E402


def main() -> int:
    parse = run_parse_controls()
    audit = static_audit()
    print(
        json.dumps(
            {
                "parse_all_pass": parse["all_pass"],
                "parse_cases": {k: {"pass": v["pass"], "problems": v["problems"]} for k, v in parse["cases"].items()},
                "audit_pass": audit["pass"],
                "audit_problems": audit["problems"],
            },
            sort_keys=True,
        )
    )
    if not parse["all_pass"]:
        print("FAILED:TST-0130-probe2 parse controls")
        return 1
    if not audit["pass"]:
        print("FAILED:TST-0130-probe2 static audit")
        return 1
    print("SUCCESS:TST-0130-probe2 insecure-TLS parse-reject static-audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
