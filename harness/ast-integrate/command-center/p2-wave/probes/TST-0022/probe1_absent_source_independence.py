#!/usr/bin/env python3
"""Probe 1: live gate on absent-source / same-probe / independent fixtures.

Instrument: subprocess claim_gate.py --claims --format json (behavioral).
The catalog tests_required names are executed in-process against the live suite.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GATE = REPO / ".agents/skills/claim-verify-gate/scripts/claim_gate.py"
TESTS = REPO / ".agents/skills/claim-verify-gate/scripts/test_claim_gate.py"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(GATE.parent))
import fixtures as F  # noqa: E402
import test_claim_gate as T  # noqa: E402

RAW = HERE / "probe1-gate-fixtures.raw.json"


def run_gate(doc: dict, path: Path) -> tuple[int, dict]:
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        [sys.executable, "-B", str(GATE), "--claims", str(path), "--format", "json"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    try:
        payload = json.loads(p.stdout)
    except json.JSONDecodeError:
        payload = {"ok": None, "stdout": p.stdout[-2000:], "stderr": p.stderr[-1000:]}
    return p.returncode, payload


def rules_of(payload: dict) -> list[str]:
    found: list[str] = []
    for claim in payload.get("claims") or []:
        for v in claim.get("violations") or []:
            if isinstance(v, dict) and v.get("rule"):
                found.append(str(v["rule"]))
    return found


def main() -> int:
    T.FAILURES.clear()
    T.test_confirmed_without_source_probe_is_a_violation()
    T.test_same_probe_rerun_is_a_violation()
    T.test_genuinely_independent_pair_passes()
    named_fail = list(T.FAILURES)

    with tempfile.TemporaryDirectory(prefix="tst0022-p1-") as tmp:
        td = Path(tmp)
        rc_abs, abs_doc = run_gate(F.absent_source_doc(), td / "absent.json")
        rc_same, same_doc = run_gate(F.same_probe_doc(), td / "same.json")
        rc_ok, ok_doc = run_gate(F.independent_doc(), td / "independent.json")

    abs_rules = rules_of(abs_doc)
    same_rules = rules_of(same_doc)
    ok_rules = rules_of(ok_doc)

    fail = False
    if named_fail:
        fail = True
    if rc_abs == 0 or "no-source-probe" not in abs_rules:
        fail = True
    if rc_same == 0 or "same-probe-rerun" not in same_rules:
        fail = True
    if rc_ok != 0 or ok_doc.get("ok") is not True or ok_rules:
        fail = True
    if "same-probe-rerun" in abs_rules:
        fail = True

    hole_would_pass = F.hole_compare_first(None, F.VERIFIER)
    if hole_would_pass is not True:
        fail = True

    payload = {
        "probe": "probe1-absent-source-independence",
        "unit_id": "TST-0022",
        "named_tests_ran": [
            "test_confirmed_without_source_probe_is_a_violation",
            "test_same_probe_rerun_is_a_violation",
            "test_genuinely_independent_pair_passes",
        ],
        "named_test_failures": named_fail,
        "absent_source": {
            "exit_code": rc_abs,
            "ok": abs_doc.get("ok"),
            "rules": abs_rules,
            "hole_algorithm_would_pass": hole_would_pass,
        },
        "same_probe": {
            "exit_code": rc_same,
            "ok": same_doc.get("ok"),
            "rules": same_rules,
        },
        "independent": {
            "exit_code": rc_ok,
            "ok": ok_doc.get("ok"),
            "rules": ok_rules,
        },
        "pass": not fail,
        "gate": str(GATE.relative_to(REPO)).replace("\\", "/"),
        "gate_exists": GATE.is_file(),
        "tests_path": str(TESTS.relative_to(REPO)).replace("\\", "/"),
        "cli": ["--claims", "<ledger>", "--format", "json"],
    }
    RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print(
        f"absent rc={rc_abs} no-source-probe={'no-source-probe' in abs_rules} "
        f"hole_would_pass={hole_would_pass}"
    )
    print(f"same rc={rc_same} same-probe-rerun={'same-probe-rerun' in same_rules}")
    print(f"independent rc={rc_ok} ok={ok_doc.get('ok')} rules={ok_rules}")
    if named_fail:
        print(f"named-test failures: {named_fail}")
    if fail:
        print("FAILED:TST-0022-probe1 gate fixtures")
        return 1
    print("SUCCESS:TST-0022-probe1 absent-source / same-probe / independent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
