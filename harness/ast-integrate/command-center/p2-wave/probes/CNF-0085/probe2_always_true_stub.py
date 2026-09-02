#!/usr/bin/env python3
"""Probe 2: always-true stub must fail the differential (detector control).

Mechanically different from probe 1: this probe never asks the production
fan-in for a verdict. It stubs the candidate to PASS and requires the harness
to go red on every oracle-FAIL row, while remaining silent on the pass control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from artifact_view import stub_control  # noqa: E402
from differential import stub_vs_oracle  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0085-runner-predicate-differential.json"
SENTINEL = (
    "SUCCESS:CNF-0085 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the always-true stub "
    "control failed the differential and the per-condition comparison table "
    "is attached. Any other terminal state is FAILED:CNF-0085 <classification> "
    "with the diagnostic tail attached."
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0085-probe2 confirmation artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:CNF-0085-probe2 catalog sentinel absent")
        return 1
    doc = json.loads(text)
    ctl = stub_control(doc)
    if not isinstance(ctl, dict) or ctl.get("fired_on_bad_state") is not True:
        print("FAILED:CNF-0085-probe2 artifact stub control did not fire")
        return 1

    table = stub_vs_oracle(REPO)
    fail_rows = [r for r in table if r["oracle_verdict"] == "FAIL"]
    pass_rows = [r for r in table if r["oracle_verdict"] == "PASS"]
    if not fail_rows:
        print("FAILED:CNF-0085-probe2 corpus has no FAIL rows; control is vacuous")
        return 1
    missed = [r for r in fail_rows if r["agree"]]
    if missed:
        print("FAILED:CNF-0085-probe2 stub agreed with oracle on a FAIL row")
        print(json.dumps(missed[:8], indent=2, default=str)[:3000])
        return 1
    noisy = [r for r in pass_rows if not r["agree"]]
    if noisy:
        print("FAILED:CNF-0085-probe2 stub disagreed on PASS control")
        print(json.dumps(noisy, indent=2, default=str)[:2000])
        return 1

    out = {
        "fail_rows": len(fail_rows),
        "stub_disagreements_on_fail": len(fail_rows),
        "pass_control_silent": True,
        "differential_went_red": True,
        "pass": True,
        "probe": "probe2-always-true-stub",
        "unit_id": "CNF-0085",
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"stub_red_on_fail_rows={len(fail_rows)} "
        f"silent_on_pass={len(pass_rows)}"
    )
    print("SUCCESS:CNF-0085-probe2 always-true stub failed the differential")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
