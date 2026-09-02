#!/usr/bin/env python3
"""Probe 2: DETECTOR CONTROL on the known-broken AND-as-OR fixture.

Reviewer job: re-run this probe. It must FIRE on mutant_and (U∧T / T∧U STOP)
and stay silent on the honest Kleene AND. Reading the report is not this job.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import tables as T  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0089-stopping-truth-table.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0089-probe2 {msg}")
    return 1


def main() -> int:
    det = T.mutant_detector()
    print(
        json.dumps(
            {
                "fires_on_known_broken": det["fires_on_known_broken"],
                "silent_on_honest": det["silent_on_honest"],
                "fixture": det["fixture"],
                "honest_and_as_or": det["honest"]["and_behaved_as_or"],
                "broken_and_as_or": det["known_broken"]["and_behaved_as_or"],
                "broken_findings": [
                    {
                        "id": f["expression_id"],
                        "case": f["case"],
                        "decision": f["observed_decision"],
                        "and_behaved_as_or": f["and_behaved_as_or"],
                    }
                    for f in det["known_broken"]["findings"]
                ],
            },
            sort_keys=True,
        )
    )
    if not det["fires_on_known_broken"]:
        return fail("detector silent on known-broken AND-as-OR mutant")
    if not det["silent_on_honest"]:
        return fail("detector fired on honest Kleene AND")
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    rev = doc.get("reviewer") or {}
    if rev.get("fired_on_broken") is not True:
        return fail("artifact reviewer.fired_on_broken is not true")
    if rev.get("silent_on_honest") is not True:
        return fail("artifact reviewer.silent_on_honest is not true")
    ctrl = (doc.get("and_as_or") or {}).get("detector") or {}
    if ctrl.get("fires_on_known_broken") is not True:
        return fail("artifact detector did not record fire")
    print(
        f"fired_on_broken={det['fires_on_known_broken']} "
        f"silent_on_honest={det['silent_on_honest']}"
    )
    print("SUCCESS:CNF-0089-probe2 detector control fired on known-broken fixture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
