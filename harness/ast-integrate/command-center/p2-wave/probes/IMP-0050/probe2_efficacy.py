#!/usr/bin/env python3
"""Named probe 2: efficacy — each remediating command fixes its own broken fixture.

Runs the mapped command as a subprocess (naive-user copy-paste, --root bound to
the fixture). A no-op command must leave the fixture broken (overclaim control).
Independently re-runs the catalog unittest test_remediation_actually_fixes_the_fixture.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.doctor.efficacy import (  # noqa: E402
    run_all_remediations,
    run_noop_overclaim,
    run_one_remediation,
)
from plugin.doctor.io import taxonomy_codes  # noqa: E402

RESULT = HERE / "probe2-result.json"
NAIVE_CODES = [
    "PLUGIN.HEALTH.HOOKS_UNLOADED",
    "PLUGIN.CONF.MANIFEST_SCHEMA",
    "PLUGIN.COMPAT.SHELL_DISAGREEMENT",
]


def run_catalog_unittest() -> dict:
    proc = subprocess.run(
        [sys.executable, "-B", str(TOOLS / "plugin" / "tests" / "test_doctor_efficacy.py")],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return {"exit_code": proc.returncode, "output_tail": tail[-2000:], "pass": proc.returncode == 0}


def main() -> int:
    codes = taxonomy_codes()
    sweep = run_all_remediations(codes)
    naive = [run_one_remediation(code) for code in NAIVE_CODES]
    naive_ok = all(row["fixed"] for row in naive)
    overclaim = run_noop_overclaim("PLUGIN.HEALTH.HOOKS_UNLOADED")
    unit = run_catalog_unittest()

    out = {
        "probe": "probe2-efficacy",
        "unit_id": "IMP-0050",
        "sweep": {
            "count": sweep["count"],
            "fixed_count": sweep["fixed_count"],
            "failed": sweep["failed"],
            "still_green_when_broken": sweep["still_green_when_broken"],
            "pass": sweep["pass"],
        },
        "naive_user_three": [
            {
                "code": row["code"],
                "fixed": row["fixed"],
                "command": row["command"],
                "exit_code": row["exit_code"],
                "before_ok": row["before_ok"],
                "after_ok": row["after_ok"],
            }
            for row in naive
        ],
        "naive_user_all_fixed": naive_ok,
        "overclaim_control": {
            "code": overclaim["code"],
            "command": "true",
            "before_ok": overclaim["before_ok"],
            "after_ok": overclaim["after_ok"],
            "caught": overclaim["overclaim_caught"],
        },
        "catalog_test": {
            "path": "tools/plugin/tests/test_doctor_efficacy.py::test_remediation_actually_fixes_the_fixture",
            **unit,
        },
        "pass": bool(
            sweep["pass"] and naive_ok and overclaim["overclaim_caught"] and unit["pass"]
        ),
    }
    RESULT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "fixed={fixed}/{count} failed={failed} naive={naive} overclaim_caught={oc} unittest={ut}".format(
            fixed=sweep["fixed_count"],
            count=sweep["count"],
            failed=sweep["failed"],
            naive=naive_ok,
            oc=overclaim["overclaim_caught"],
            ut=unit["pass"],
        )
    )
    if not out["pass"]:
        print("FAILED:IMP-0050-probe2 efficacy")
        print(json.dumps({"failed": sweep["failed"], "naive": naive, "overclaim": overclaim}, default=str)[:3000])
        return 1
    print("SUCCESS:IMP-0050-probe2 remediations fix their fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
