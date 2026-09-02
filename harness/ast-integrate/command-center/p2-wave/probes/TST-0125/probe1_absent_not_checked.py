#!/usr/bin/env python3
"""test_absent_thresholds_file_yields_not_checked_not_pass"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from resolver import FAIL, NOT_CHECKED, PASS, evaluate_project  # noqa: E402


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0125-p1-") as tmp:
        root = Path(tmp)
        empty = root / "ungated-python"
        write(empty / "pyproject.toml", "[project]\nname='ungated'\nversion='0'\n")
        # Near-miss name must not count as the SSOT file.
        decoy = root / "decoy-name"
        write(decoy / "pyproject.toml", "[project]\nname='decoy'\nversion='0'\n")
        write(decoy / "coverage-thresholds.json", json.dumps({"enforcement": {"command": "true"}}))
        # Nested empty package.json project.
        nested = root / "apps" / "web"
        write(nested / "package.json", '{"name":"web","private":true}\n')

        rows = [evaluate_project(p) for p in (empty, decoy, nested)]

    banned_pass = [r for r in rows if r["verdict"] == PASS]
    banned_fail = [r for r in rows if r["verdict"] == FAIL]
    not_checked = [r for r in rows if r["verdict"] == NOT_CHECKED]
    if banned_pass:
        print("FAILED:TST-0125-probe1 absence folded into PASS")
        print(json.dumps(banned_pass, indent=2)[:4000])
        return 1
    if banned_fail:
        print("FAILED:TST-0125-probe1 absence folded into FAIL (must be NOT-CHECKED)")
        print(json.dumps(banned_fail, indent=2)[:4000])
        return 1
    if len(not_checked) != 3:
        print(f"FAILED:TST-0125-probe1 expected 3 NOT-CHECKED got {len(not_checked)}")
        print(json.dumps(rows, indent=2)[:4000])
        return 1
    for row in rows:
        if row["has_thresholds_file"] or row["coverage_gated"] or row["thresholds_file"]:
            print("FAILED:TST-0125-probe1 absent project reported as gated")
            print(json.dumps(row, indent=2)[:4000])
            return 1
        if "no .coverage-thresholds.json" not in (row.get("reason") or ""):
            print("FAILED:TST-0125-probe1 reason did not surface absence")
            print(json.dumps(row, indent=2)[:4000])
            return 1

    out = {
        "probe": "probe1-absent-not-checked",
        "unit_id": "TST-0125",
        "test": "test_absent_thresholds_file_yields_not_checked_not_pass",
        "projects": 3,
        "verdicts": [r["verdict"] for r in rows],
        "reasons": [r["reason"] for r in rows],
        "any_pass": False,
        "decoy_without_dot_prefix_ignored": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("absent=3 NOT-CHECKED=3 PASS=0 FAIL=0 decoy_ignored=True")
    print("SUCCESS:TST-0125-probe1 absent thresholds file yields NOT-CHECKED not pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
