#!/usr/bin/env python3
"""Probe 2: post-hoc margin edit is flagged; at-margin resolves NON_INFERIOR.

Independent reviewer path: the inequality is re-derived here with Decimal
arithmetic and must agree with tools.bench.release_gate.metric_status.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.bench import margins, release_gate  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scenario import BASELINE, CANDIDATE_WIN, comparison  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0301-probe2 {msg}")
    return 1


def independent_status(polarity: str, baseline, candidate, margin) -> str:
    """Second implementation of the inclusive at-margin rule (not a call into the gate)."""
    b, c, m = Decimal(str(baseline)), Decimal(str(candidate)), Decimal(str(margin))
    worse = (b - c) if polarity == "higher_is_better" else (c - b)
    if worse < 0:
        return "IMPROVED"
    if worse == 0:
        return "EQUAL"
    if worse <= m:
        return "NON_INFERIOR"
    return "MATERIAL_REGRESSION"


def main() -> int:
    inv = margins.load_inventory(root=REPO)
    tab = margins.load_margin_table(root=REPO)
    bound = release_gate.bind_table(tab)
    outcome = margins.table_by_id(tab)["outcome_check_rate"]
    if Decimal(str(outcome["margin"])) != Decimal("0.02"):
        return fail(f"unexpected outcome margin {outcome['margin']}")

    # Independent vs gate on three points around the margin.
    cases = [
        ("inside", 0.735, "NON_INFERIOR"),  # worse_delta=0.015 < 0.02
        ("at_margin", 0.73, "NON_INFERIOR"),  # worse_delta=0.02 == margin
        ("beyond", 0.729, "MATERIAL_REGRESSION"),  # worse_delta=0.021 > 0.02
    ]
    for name, cand_val, expect in cases:
        indep = independent_status(
            "higher_is_better", BASELINE["outcome_check_rate"], cand_val, outcome["margin"]
        )
        gate = release_gate.metric_status(
            "higher_is_better", BASELINE["outcome_check_rate"], cand_val, outcome["margin"]
        )
        print(f"boundary {name} candidate={cand_val} independent={indep} gate={gate}")
        if indep != expect or gate != expect or indep != gate:
            return fail(f"{name} expected {expect} got indep={indep} gate={gate}")

    at_cand = deepcopy(CANDIDATE_WIN)
    at_cand["outcome_check_rate"] = 0.73
    rec_at = release_gate.evaluate(
        comparison("p2-at-margin", at_cand, bound),
        table=tab,
        inventory=inv,
        root=REPO,
    )
    row_at = next(r for r in rec_at["metrics"] if r["id"] == "outcome_check_rate")
    print(
        f"at_margin overall={rec_at['verdict']} "
        f"status={row_at['status']} at_margin_flag={row_at['at_margin']}"
    )
    if rec_at["verdict"] != "PASS":
        return fail(f"at-margin must PASS, got {rec_at['verdict']}")
    if row_at["status"] != "NON_INFERIOR" or row_at["at_margin"] is not True:
        return fail(f"at-margin row {row_at}")
    if rec_at["at_margin_resolves"] != "NON_INFERIOR":
        return fail("at_margin_resolves not documented on the record")

    beyond = deepcopy(CANDIDATE_WIN)
    beyond["outcome_check_rate"] = 0.729
    rec_beyond = release_gate.evaluate(
        comparison("p2-beyond", beyond, bound),
        table=tab,
        inventory=inv,
        root=REPO,
    )
    print(f"beyond_margin overall={rec_beyond['verdict']} alarms={rec_beyond['alarms']}")
    if rec_beyond["verdict"] != "REFUSE":
        return fail(f"beyond-margin must REFUSE, got {rec_beyond['verdict']}")
    if not any("outcome_check_rate" in a for a in rec_beyond["alarms"]):
        return fail(f"refuse alarms {rec_beyond['alarms']}")

    # Post-hoc: comparison bound to the frozen table; live table is then edited.
    rec_orig = release_gate.evaluate(
        comparison("p2-posthoc", CANDIDATE_WIN, bound),
        table=tab,
        inventory=inv,
        root=REPO,
    )
    if rec_orig["verdict"] != "PASS":
        return fail(f"pre-mutation control {rec_orig['verdict']}")

    mutated = deepcopy(tab)
    for row in mutated["metrics"]:
        if row["id"] == "outcome_check_rate":
            row["margin"] = 0.50  # looser, would hide a regression if re-scored
    rec_post = release_gate.evaluate(
        comparison("p2-posthoc", CANDIDATE_WIN, bound),
        table=mutated,
        inventory=inv,
        root=REPO,
    )
    print(
        f"posthoc live_sha={rec_post['live_sha256'][:12]} "
        f"bound={str(rec_post['bound_sha256'])[:12]} verdict={rec_post['verdict']}"
    )
    if rec_post["verdict"] != "POST_HOC_MARGIN_CHANGE":
        return fail(f"mutated table silently accepted as {rec_post['verdict']}")
    if rec_post["live_sha256"] == bound:
        return fail("mutated table digest equalled the bound digest")

    rec_late = release_gate.evaluate(
        comparison(
            "p2-late-decision",
            CANDIDATE_WIN,
            bound,
            started_at="2026-07-01T00:00:00Z",
        ),
        table=tab,
        inventory=inv,
        root=REPO,
    )
    print(f"late_decision verdict={rec_late['verdict']}")
    if rec_late["verdict"] != "POST_HOC_MARGIN_DECISION":
        return fail(f"started_at before decided_at verdict={rec_late['verdict']}")

    print(
        json.dumps(
            {
                "at_margin_resolves": "NON_INFERIOR",
                "at_margin_verdict": rec_at["verdict"],
                "beyond_verdict": rec_beyond["verdict"],
                "posthoc_verdict": rec_post["verdict"],
                "late_decision_verdict": rec_late["verdict"],
                "independent_agrees": True,
                "both_states": {
                    "frozen_table": rec_orig["verdict"],
                    "mutated_table": rec_post["verdict"],
                },
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0301-probe2 post-hoc alarm and at-margin NON_INFERIOR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
