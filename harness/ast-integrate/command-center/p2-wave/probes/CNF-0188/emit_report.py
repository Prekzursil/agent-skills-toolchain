#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0188.json from live extractors + controls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extractors as E  # noqa: E402


def main() -> int:
    report = E.emit_artifact()
    print(
        json.dumps(
            {
                "path": E.ART.relative_to(E.REPO).as_posix(),
                "state": report["state"],
                "sentinel": report["sentinel"],
                "claim_verdict": report["claim_verdict"],
                "floors": [
                    {
                        "id": r["id"],
                        "floor": r["floor"],
                        "resolved": r["resolved_count"],
                        "holds": r["holds"],
                    }
                    for r in report["floors"]
                ],
                "tests_pass": all(t["pass"] for t in report["tests"]),
            },
            indent=2,
        )
    )
    if report["state"] in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0188 emit state={report['state']}")
        return 1
    if "SUCCESS:CNF-0188" not in json.dumps(report):
        print("FAILED:CNF-0188 sentinel missing")
        return 1
    print("SUCCESS:CNF-0188 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
