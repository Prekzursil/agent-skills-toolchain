#!/usr/bin/env python3
"""Live probe 2: independent conformance pass + broken-template goes red."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PKG = REPO / "tools" / "marketplace"
sys.path.insert(0, str(PKG))

from conformance import check_conformance
from package_linter import lint_package
from scaffolder import KINDS, scaffold


def main() -> int:
    conf_rows = []
    with tempfile.TemporaryDirectory(prefix="imp-0116-p2-") as tmp:
        for kind in KINDS:
            name = f"conf-{kind.replace('-', '-')}"
            path = scaffold(kind, name, tmp)
            report = check_conformance(path)
            conf_rows.append(
                {
                    "kind": kind,
                    "ok": report.ok,
                    "violations": [v.check for v in report.violations],
                    "detail": [v.detail for v in report.violations],
                }
            )
        broken = scaffold(
            "skill",
            "broken-template",
            tmp,
            mutations={"license": "NOT-A-LICENSE"},
        )
        lint = lint_package(broken)
        # Independence: SPDX break is a linter finding; conformance does not check SPDX.
        conf_broken = check_conformance(broken)

        # Second mutation: drop Usage section so conformance goes red while
        # the linter (which does not read README Usage) stays a different surface.
        usage_dest = Path(tmp) / "usage-dest"
        usage_dest.mkdir()
        no_usage = scaffold("hook", "no-usage-hook", usage_dest)
        readme = no_usage / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8").replace("## Usage", "## Notes"), encoding="utf-8")
        lint_no_usage = lint_package(no_usage)
        conf_no_usage = check_conformance(no_usage)

    conf_ok = all(r["ok"] for r in conf_rows)
    break_red = (not lint.ok) and any(f.rule == "spdx-license" for f in lint.findings)
    usage_red = (not conf_no_usage.ok) and any(v.check == "readme-usage" for v in conf_no_usage.violations)
    independent = conf_broken.ok and lint_no_usage.ok  # SPDX break != usage break
    payload = {
        "probe": "probe2",
        "unit": "IMP-0116",
        "conformance": conf_rows,
        "conformance_all_ok": conf_ok,
        "broken_template": {
            "lint_ok": lint.ok,
            "lint_rules": [f.rule for f in lint.findings],
            "conformance_ok": conf_broken.ok,
            "goes_red": break_red,
        },
        "usage_stripped": {
            "lint_ok": lint_no_usage.ok,
            "conformance_ok": conf_no_usage.ok,
            "conformance_checks": [v.check for v in conf_no_usage.violations],
            "goes_red": usage_red,
        },
        "surfaces_independent": independent,
    }
    print(json.dumps(payload, indent=2))
    if not conf_ok:
        print("FAILED:IMP-0116-probe2 generated artifact failed conformance")
        return 1
    if not break_red:
        print("FAILED:IMP-0116-probe2 broken template did not go red")
        return 1
    if not usage_red:
        print("FAILED:IMP-0116-probe2 usage-strip did not fail conformance")
        return 1
    if not independent:
        print("FAILED:IMP-0116-probe2 linter and conformance are not independent")
        return 1
    print("SUCCESS:IMP-0116-probe2 conformance and negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
