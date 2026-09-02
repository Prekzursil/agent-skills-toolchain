#!/usr/bin/env python3
"""Named probe 1: completeness — every taxonomy code has a non-empty remediation.

Signal 1 is the JSON join (taxonomy codes vs mapping commands). Signal 2 is the
catalog unittest test_every_code_has_a_remediation. A new code without a mapping
must make the completeness check go red (negative control).
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

from plugin.doctor.coverage import missing_mappings, validate_join  # noqa: E402
from plugin.doctor.io import load_mapping  # noqa: E402

RESULT = HERE / "probe1-result.json"


def run_catalog_unittest() -> dict:
    env_cmd = [
        sys.executable,
        "-B",
        str(TOOLS / "plugin" / "tests" / "test_doctor_coverage.py"),
    ]
    proc = subprocess.run(
        env_cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return {"exit_code": proc.returncode, "output_tail": tail[-2000:], "pass": proc.returncode == 0}


def main() -> int:
    report = validate_join()
    extra = "PLUGIN.HEALTH.TEST_UNMAPPED"
    tax = json.loads((TOOLS / "plugin" / "data" / "error-taxonomy.json").read_text(encoding="utf-8"))
    tax["codes"].append(
        {
            "code": extra,
            "category": "health",
            "severity": "error",
            "retryable": True,
        }
    )
    negative_missing = missing_mappings(taxonomy=tax, mapping=load_mapping())
    negative_ok = extra in negative_missing
    unit = run_catalog_unittest()

    out = {
        "probe": "probe1-coverage",
        "unit_id": "IMP-0050",
        "join": report,
        "negative_control": {
            "code": extra,
            "missing": negative_missing,
            "completeness_went_red": negative_ok,
        },
        "catalog_test": {
            "path": "tools/plugin/tests/test_doctor_coverage.py::test_every_code_has_a_remediation",
            **unit,
        },
        "pass": bool(report["complete"] and negative_ok and unit["pass"]),
    }
    RESULT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("probe", "pass", "join") if k in out}, default=str)[:2000])
    print(
        "complete={complete} tax={n} missing={m} neg_red={neg} unittest={ut}".format(
            complete=report["complete"],
            n=report["taxonomy_count"],
            m=report["missing_mappings"],
            neg=negative_ok,
            ut=unit["pass"],
        )
    )
    if not out["pass"]:
        print("FAILED:IMP-0050-probe1 completeness")
        return 1
    print("SUCCESS:IMP-0050-probe1 every taxonomy code has a non-empty remediation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
