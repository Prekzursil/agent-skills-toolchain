#!/usr/bin/env python3
"""Probe 2: detector control on the known-broken unknown-stage-type fixture.

The reviewer job is to re-run THIS probe, not to re-read the confirmation JSON.
Fires only when production validate_workflow.py rejects the planted broken
fixture with WF-UNKNOWN-STAGE-TYPE, the valid twin still passes, and the
permissive stub accepts the same broken fixture (both-states + live detector).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BROKEN = HERE / "fixtures" / "invalid-unknown-stage-type.json"
VALID = HERE / "fixtures" / "valid.json"
PROD = REPO / "command-center" / "schema" / "validate_workflow.py"
STUB = HERE / "permissive_stub.py"


def run(script: Path, fixture: Path) -> tuple[int, dict | None, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(script), str(fixture)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    parsed = None
    try:
        parsed = json.loads(proc.stdout or "")
    except json.JSONDecodeError:
        parsed = None
    return proc.returncode, parsed, text


def main() -> int:
    broken_code, broken_doc, broken_text = run(PROD, BROKEN)
    valid_code, valid_doc, valid_text = run(PROD, VALID)
    stub_code, stub_doc, stub_text = run(STUB, BROKEN)

    fired = (
        broken_code != 0
        and isinstance(broken_doc, dict)
        and broken_doc.get("violation_id") == "WF-UNKNOWN-STAGE-TYPE"
        and broken_doc.get("ok") is False
    )
    silent_on_good = valid_code == 0 and isinstance(valid_doc, dict) and valid_doc.get("ok") is True
    stub_accepts_broken = (
        stub_code == 0 and isinstance(stub_doc, dict) and stub_doc.get("ok") is True
    )

    print(f"broken exit={broken_code} vid={None if not broken_doc else broken_doc.get('violation_id')} fired={fired}")
    print(f"valid exit={valid_code} ok={None if not valid_doc else valid_doc.get('ok')} silent_on_good={silent_on_good}")
    print(f"stub exit={stub_code} ok={None if not stub_doc else stub_doc.get('ok')} stub_accepts_broken={stub_accepts_broken}")

    if not fired:
        print("FAILED:CNF-0083-probe2 detector did not fire on known-broken fixture")
        print(broken_text[-1500:])
        return 1
    if not silent_on_good:
        print("FAILED:CNF-0083-probe2 valid twin was rejected (validator rejecting everything)")
        print(valid_text[-1500:])
        return 1
    if not stub_accepts_broken:
        print("FAILED:CNF-0083-probe2 permissive stub did not accept known-broken")
        print(stub_text[-1500:])
        return 1
    if broken_code == stub_code:
        print("FAILED:CNF-0083-probe2 production matched permissive stub")
        return 1
    print("SUCCESS:CNF-0083-probe2 detector control fired on known-broken fixture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
