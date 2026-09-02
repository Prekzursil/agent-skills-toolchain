#!/usr/bin/env python3
"""Named probe 1: six negative fixtures + one positive, same invocation.

Each fixture is a separate validator process so the evidence is a real
exit code, not a function return. All seven run inside this one probe.
SUCCESS only when every negative exits non-zero and the positive exits 0.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
VALIDATOR = REPO / "command-center/schema/validate_confirmation_receipt.py"
SCHEMA = REPO / "command-center/schema/confirmation-receipt.schema.json"
SENTINEL = (
    "SUCCESS:CNF-0001 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and all six negative fixtures "
    "exited non-zero and the positive fixture exited zero in the same invocation. "
    "Any other terminal state is FAILED:CNF-0001 <classification> with the "
    "diagnostic tail attached."
)

NEGATIVES = [
    "neg-01-confirmed-empty-source.json",
    "neg-02-same-probe-rerun.json",
    "neg-03-missing-claim-id.json",
    "neg-04-missing-confirmer.json",
    "neg-05-missing-verbatim-output.json",
    "neg-06-missing-residual.json",
]
POSITIVE = "pos-01-complete-receipt.json"
EXPECTED_RULE = {
    "neg-01-confirmed-empty-source.json": "empty-source",
    "neg-02-same-probe-rerun.json": "same-probe-rerun",
    "neg-03-missing-claim-id.json": "missing-claim_id",
    "neg-04-missing-confirmer.json": "missing-confirmer",
    "neg-05-missing-verbatim-output.json": "missing-verbatim-output",
    "neg-06-missing-residual.json": "missing-residual",
}


def run_validator(fixture: Path) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(VALIDATOR), str(fixture)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def main() -> int:
    if not SCHEMA.is_file() or SCHEMA.stat().st_size <= 0:
        print("FAILED:CNF-0001-probe1 confirmation-receipt.schema.json missing")
        return 1
    text = SCHEMA.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:CNF-0001-probe1 completion sentinel absent from schema")
        return 1
    if not VALIDATOR.is_file():
        print("FAILED:CNF-0001-probe1 validator CLI missing")
        return 1

    fixtures = HERE / "fixtures"
    rows = []
    failed = False
    for name in NEGATIVES + [POSITIVE]:
        path = fixtures / name
        if not path.is_file():
            print(f"FAILED:CNF-0001-probe1 fixture missing {name}")
            return 1
        code, out = run_validator(path)
        want_nonzero = name in NEGATIVES
        ok = (code != 0) if want_nonzero else (code == 0)
        print(f"FIXTURE {name} EXIT {code} want={'nonzero' if want_nonzero else '0'} ok={ok}")
        print(out)
        print("---")
        rows.append({"name": name, "exit": code, "ok": ok, "output": out})
        if not ok:
            failed = True
        if want_nonzero:
            rule = EXPECTED_RULE[name]
            if f'"rule": "{rule}"' not in out and f"REJECT:{rule}" not in out:
                # The EXIT line uses comma-joined rules; accept either form.
                if rule not in out:
                    print(f"FAILED:CNF-0001-probe1 {name} rejected but not as {rule}")
                    failed = True

    if failed:
        print("FAILED:CNF-0001-probe1 fixture suite did not match required exits")
        return 1

    hole = next(r for r in rows if r["name"] == NEGATIVES[0])
    print(
        "question=does a receipt with verdict=CONFIRMED and an EMPTY source_probe pass?"
    )
    print(f"answer=NO hole_exit={hole['exit']}")
    print("SUCCESS:CNF-0001-probe1 six negatives nonzero, positive zero, same invocation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
