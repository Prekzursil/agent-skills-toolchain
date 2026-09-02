#!/usr/bin/env python3
"""Probe 2: re-run a stratified sample N=10 times at a pinned SHA.

Mechanically different from probe 1 (no history join). A unit that passes
6 of 10 is flaky regardless of how its history was recorded.
Control: a known-deterministic unit must pass 10 of 10; otherwise the
environment is unstable and no flakiness is attributed to the unit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ledger as L  # noqa: E402

ART = L.REPO / "command-center/adversarial/ADV-0090-rerun-until-green-laundering.json"


def main() -> int:
    report = L.probe2_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    emp = report["empirical"]
    both = emp["both_states"]
    print(
        f"pinned_sha={emp['pinned_sha'][:12]} env_stable={emp['environment_stable']} "
        f"control={emp['control_pass_n']}/{emp['n']}"
    )
    flaky = emp["per_unit"]["planted-flaky-6-of-10"]
    print(
        f"flaky pass_n={flaky['pass_n']} class={flaky['classification']} "
        f"good={both['good_10_of_10_not_flaky']} "
        f"bad={both['bad_6_of_10_classified_flaky']}"
    )
    if not report["pass"]:
        print("FAILED:ADV-0090-probe2 fixed-SHA repeats")
        return 1
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:ADV-0090" not in text:
            print("FAILED:ADV-0090-probe2 artifact sentinel absent")
            return 1
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            print(f"FAILED:ADV-0090-probe2 self-declared {doc.get('state')}")
            return 1
        tests = {t["id"]: t for t in doc.get("tests") or [] if isinstance(t, dict)}
        if tests.get("T-deterministic-control-10-of-10", {}).get("result") != "PASS":
            print("FAILED:ADV-0090-probe2 artifact control not PASS")
            return 1
    print(
        "SUCCESS:ADV-0090-probe2 control 10/10; planted 6/10 classified FLAKY; "
        "environment stable so attribution is valid"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
