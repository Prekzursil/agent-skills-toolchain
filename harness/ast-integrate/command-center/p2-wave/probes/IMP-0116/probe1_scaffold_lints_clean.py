#!/usr/bin/env python3
"""Live probe 1: each scaffold kind generates and lints with zero findings."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PKG = REPO / "tools" / "marketplace"
sys.path.insert(0, str(PKG))

from package_linter import lint_package
from scaffolder import KINDS, scaffold


def main() -> int:
    results = []
    with tempfile.TemporaryDirectory(prefix="imp-0116-p1-") as tmp:
        for kind in KINDS:
            name = f"live-{kind.replace('-', '-')}"
            path = scaffold(kind, name, tmp)
            report = lint_package(path)
            results.append(
                {
                    "kind": kind,
                    "path": str(path),
                    "ok": report.ok,
                    "finding_count": len(report.findings),
                    "findings": [f.rule for f in report.findings],
                    "files": sorted(p.relative_to(path).as_posix() for p in path.rglob("*") if p.is_file()),
                }
            )
    all_ok = all(r["ok"] and r["finding_count"] == 0 for r in results)
    print(json.dumps({"probe": "probe1", "unit": "IMP-0116", "results": results, "all_ok": all_ok}, indent=2))
    if not all_ok:
        print("FAILED:IMP-0116-probe1 scaffold produced lint findings")
        return 1
    print("SUCCESS:IMP-0116-probe1 four kinds lint-clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
