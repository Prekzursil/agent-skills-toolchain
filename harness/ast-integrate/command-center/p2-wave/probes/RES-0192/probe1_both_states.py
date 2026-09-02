#!/usr/bin/env python3
"""Probe 1: both-states on the decision rule plus the required negative control.

Known-good: Q1 rapid misses 0 decision-relevant claims AND the live rule
recommends RAPID. Q2 rapid misses >=1 decision-relevant claim AND the live
rule recommends SYSTEMATIC.

Known-broken: always-systematic mutant recommends SYSTEMATIC on Q1, collapsing
the rule. Detector must fire on the mutant and stay silent on the live rule.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from catalog import SENTINEL, UNIT  # noqa: E402
from measure import run  # noqa: E402

ART = (
    REPO
    / "command-center/research/deep-research-design/"
    / "RES-0192-rapid-versus-systematic-review-protocol.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0192-probe1 {msg}")
    return 1


def main() -> int:
    live = run()
    if live.get("index_failures"):
        return fail(f"capture failures {live['index_failures']}")
    bs = live["both_states"]
    q_by = {q["question_id"]: q for q in live["questions"]}
    q1, q2, q3 = q_by["Q1"], q_by["Q2"], q_by["Q3"]

    print(
        json.dumps(
            {
                "Q1_rule": q1["rule"]["protocol"],
                "Q2_rule": q2["rule"]["protocol"],
                "Q3_rule": q3["rule"]["protocol"],
                "Q1_decision_relevant_misses": q1["diff"]["n_decision_relevant_misses"],
                "Q2_decision_relevant_misses": q2["diff"]["n_decision_relevant_misses"],
                "Q3_decision_relevant_misses": q3["diff"]["n_decision_relevant_misses"],
                "Q2_miss_ids": [m["id"] for m in q2["diff"]["decision_relevant_misses"]],
                "discriminates": bs["discriminates"],
            },
            sort_keys=True,
        )
    )

    if q1["diff"]["n_decision_relevant_misses"] != 0:
        return fail("negative control failed: Q1 rapid missed decision-relevant claims")
    if q1["rule"]["protocol"] != "RAPID":
        return fail("rule collapsed toward always-systematic on Q1")
    if q2["diff"]["n_decision_relevant_misses"] < 1:
        return fail("Q2 rapid missed nothing decision-relevant; rule not validated")
    if q2["rule"]["protocol"] != "SYSTEMATIC":
        return fail("rule recommended RAPID on Q2 despite decision-relevant misses")
    if q3["rule"]["protocol"] != "RAPID":
        return fail("Q3 should be RAPID")
    if not bs["discriminates"]:
        return fail("both-states did not discriminate live rule vs always-systematic")
    if not bs["known_broken"]["fails_negative_control"]:
        return fail("always-systematic mutant did not fail the negative control")
    if not bs["known_broken_always_rapid"]["ignores_q2_misses"]:
        return fail("always-rapid mutant did not ignore Q2 misses")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")
    stored = (doc.get("measurements") or {}).get("live_rule") or {}
    if stored.get("Q1") != "RAPID" or stored.get("Q2") != "SYSTEMATIC":
        return fail(f"artifact live_rule drifted {stored}")
    stored_nc = (doc.get("measurements") or {}).get("negative_control") or {}
    if stored_nc.get("pass") is not True:
        return fail("artifact negative_control.pass is not True")
    stored_miss = (doc.get("measurements") or {}).get("q2_decision_relevant_misses")
    if stored_miss != q2["diff"]["n_decision_relevant_misses"]:
        return fail("artifact Q2 miss count drifted from live")

    print(
        f"Q1={q1['rule']['protocol']} misses={q1['diff']['n_decision_relevant_misses']} "
        f"Q2={q2['rule']['protocol']} misses={q2['diff']['n_decision_relevant_misses']} "
        f"Q3={q3['rule']['protocol']} discriminates={bs['discriminates']}"
    )
    print("SUCCESS:RES-0192-probe1 both-states + negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
