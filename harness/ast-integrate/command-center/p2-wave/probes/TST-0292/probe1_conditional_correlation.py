#!/usr/bin/env python3
"""Probe 1: conditional error correlation, prompt-parity, both-states seats.

Independent scripted vendors must keep effective seats well above 1.
Cloned (shared failure-mode) vendors must collapse toward 1.
Prompts and scoring are byte-identical across the pair.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council.calibration.vendor_error_correlation import (  # noqa: E402
    N_ITEMS,
    run_independence_experiment,
)


def _compact(exp: dict) -> dict:
    findings = exp["findings"]
    indep = exp["independent_pair"]
    cloned = exp["cloned_pair"]
    return {
        "probe": "probe1-conditional-correlation",
        "unit_id": "TST-0292",
        "n_items": exp["n_items"],
        "domains": exp["domains"],
        "independent": {
            "joint_error_table": indep["joint_error_table"],
            "phi": indep["phi"],
            "effective_seats": indep["effective_seats"]["effective_seats"],
            "p_codex_wrong_given_claude_wrong": indep["joint_error_table"][
                "p_b_wrong_given_a_wrong"
            ],
            "prompt_parity": indep["prompt_parity"]["ok"],
        },
        "cloned": {
            "joint_error_table": cloned["joint_error_table"],
            "phi": cloned["phi"],
            "effective_seats": cloned["effective_seats"]["effective_seats"],
            "p_codex_wrong_given_claude_wrong": cloned["joint_error_table"][
                "p_b_wrong_given_a_wrong"
            ],
            "prompt_parity": cloned["prompt_parity"]["ok"],
        },
        "hand_computed": {
            "independent_phi": exp["hand_computed"]["independent"]["phi"],
            "cloned_phi": exp["hand_computed"]["cloned"]["phi"],
            "matched": exp["findings"]["hand_tables_match"],
        },
        "live_arm": exp["live_substrate"]["live_arm"],
        "findings": findings,
    }


def main() -> int:
    exp = run_independence_experiment(seed=292)
    report = _compact(exp)
    print(json.dumps(report, sort_keys=True, default=str))
    indep = report["independent"]
    cloned = report["cloned"]
    print(
        "n={n} domains={d} indep_phi={ip:.4f} indep_seats={is_:.4f} "
        "clone_phi={cp:.4f} clone_seats={cs:.4f} "
        "p_b_given_a_indep={pa} p_b_given_a_clone={pb}".format(
            n=report["n_items"],
            d=",".join(report["domains"]),
            ip=indep["phi"],
            is_=indep["effective_seats"],
            cp=cloned["phi"],
            cs=cloned["effective_seats"],
            pa=indep["p_codex_wrong_given_claude_wrong"],
            pb=cloned["p_codex_wrong_given_claude_wrong"],
        )
    )
    failures: list[str] = []
    if report["n_items"] < 100 or report["n_items"] != N_ITEMS:
        failures.append("need-100-plus-items")
    if len(report["domains"]) < 4:
        failures.append("need-several-domains")
    if not indep["prompt_parity"] or not cloned["prompt_parity"]:
        failures.append("prompt-parity-broken")
    if not report["findings"]["hand_tables_match"]:
        failures.append("hand-2x2-mismatch")
    if not report["findings"]["independent_is_real_diversity"]:
        failures.append("independent-pair-did-not-keep-seats")
    if not report["findings"]["cloned_is_expensive_duplication"]:
        failures.append("cloned-pair-did-not-collapse")
    if indep["effective_seats"] <= cloned["effective_seats"]:
        failures.append("independent-seats-not-above-cloned")
    if cloned["joint_error_table"]["both_wrong"] <= indep["joint_error_table"]["both_wrong"]:
        failures.append("cloned-both-wrong-not-higher")
    if failures:
        print("FAILED:TST-0292-probe1 " + ",".join(failures))
        return 1
    print(
        "SUCCESS:TST-0292-probe1 independent seats kept; cloned seats collapsed; "
        "prompt-parity held"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
