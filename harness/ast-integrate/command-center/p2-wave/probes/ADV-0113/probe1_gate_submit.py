#!/usr/bin/env python3
"""Probe 1: submit a claim with a valid verifier and NO source probe.

Acceptance (gate ok=true) is the confirmed hole. Rejection is the hole closed
on this live gate. Also runs the ABSENT-SOURCE regression (not missing-verifier).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import claim_gate as cg  # noqa: E402

FIXTURE = HERE / "fixtures" / "absent_source_valid_verifier.json"
COMPLETE = HERE / "fixtures" / "complete_claim.json"
ABSENT_V = HERE / "fixtures" / "absent_verifier.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    absent = load(FIXTURE)
    complete = load(COMPLETE)
    missing_v = load(ABSENT_V)

    live_absent = cg.check_claim(absent)
    hole_absent = cg.check_claim_pre_fix_hole(absent)
    live_complete = cg.check_claim(complete)
    live_mv = cg.check_claim(missing_v)
    hole_mv = cg.check_claim_pre_fix_hole(missing_v)
    regression = cg.absent_source_regression()

    hole_open = live_absent["ok"] is True
    payload = {
        "pass": (
            live_absent["ok"] is False
            and cg.RULE_NO_SOURCE in live_absent["rules_fired"]
            and hole_absent["ok"] is True
            and live_complete["ok"] is True
            and live_mv["ok"] is False
            and cg.RULE_NO_VERIFIER in live_mv["rules_fired"]
            and cg.RULE_NO_SOURCE not in live_mv["rules_fired"]
            and hole_mv["ok"] is False
            and regression["pass"] is True
        ),
        "probe": "probe1-gate-submit-absent-source",
        "unit_id": "ADV-0113",
        "fixture": FIXTURE.relative_to(REPO).as_posix(),
        "gate": "tools/command-center/claim_gate.py",
        "live_absent_source": live_absent,
        "pre_fix_hole_absent_source": hole_absent,
        "live_complete": live_complete,
        "live_absent_verifier": live_mv,
        "pre_fix_hole_absent_verifier": hole_mv,
        "hole_open_on_live_gate": hole_open,
        "acceptance_is_confirmed_hole": hole_open,
        "absent_source_regression": regression,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:ADV-0113-probe1 absent-source gate regression")
        return 1
    print(
        "SUCCESS:ADV-0113-probe1 live gate rejects valid-verifier+no-source "
        "(no-source-probe); pre-fix mutant still accepts; missing-verifier "
        "is a different rule"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
