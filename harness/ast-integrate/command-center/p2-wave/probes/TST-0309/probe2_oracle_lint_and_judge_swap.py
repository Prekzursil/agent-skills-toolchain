#!/usr/bin/env python3
"""Probe 2: oracle-first lint (both states) and judge-swap bound.

Mechanically different from probe 1:
  * walks official ledger records and the lint, not the kappa walker
  * recomputes kappa from the receipt's raw per-case table via the matrix
    path AND an index bootstrap (statistics-reviewer mandate)
  * judge-swap disagreement, plus an identical-judge control that must be 0

Both-states:
  * good official ledger => lint silent
  * planted official judge score on a deterministic case => lint fires
  * score_case(force_judge=True) raises OracleFirstViolation
  * oracle_kind rewritten on the record still fires when the case map is passed
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.cases import (  # noqa: E402
    cases_by_id,
    judged_only,
    load_corpus,
    materialize_corpus,
    overlap_only,
)
from bench.extrapolate import disagreement_rate, extrapolate_error_bar  # noqa: E402
from bench.judges import JUDGE_A, JUDGE_B, judge_label  # noqa: E402
from bench.kappa import (  # noqa: E402
    bootstrap_kappa,
    cohen_kappa_from_matrix,
    confusion_counts,
    error_direction,
    wilson_interval,
)
from bench.ledger import lint_official_ledger  # noqa: E402
from bench.oracle import oracle_label  # noqa: E402
from bench.oracle_first import (  # noqa: E402
    LINT_CODE,
    OracleFirstViolation,
    plant_official_judge_score,
    score_case,
    score_corpus,
)

UNIT = "TST-0309"
ART = REPO / "command-center/receipts/TST-0309.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def close(a: float, b: float, atol: float = 1e-12) -> bool:
    return math.isclose(a, b, rel_tol=0.0, abs_tol=atol)


def main() -> int:
    materialize_corpus(REPO)
    cases = load_corpus(REPO)
    by_id = cases_by_id(cases)
    overlap = overlap_only(cases)
    judged = judged_only(cases)
    if not judged:
        return fail("judged-only subset empty")

    official = score_corpus(overlap, role="official") + score_corpus(
        judged, role="official", judge_id=JUDGE_A
    )
    lint_good = lint_official_ledger(official, by_id)
    if lint_good:
        return fail(f"good ledger flagged {lint_good}")

    plant_case = next(c for c in overlap if oracle_label(c) == "match")
    plant_row = plant_official_judge_score(plant_case, JUDGE_A)
    lint_bad = lint_official_ledger(official + [plant_row], by_id)
    if not any(f.get("code") == LINT_CODE for f in lint_bad):
        return fail(f"plant did not fire lint {lint_bad}")
    if any(f.get("code") == LINT_CODE for f in lint_good):
        return fail("lint not silent on good twin")

    try:
        score_case(plant_case, role="official", judge_id=JUDGE_A, force_judge=True)
    except OracleFirstViolation as exc:
        if exc.code != LINT_CODE:
            return fail(f"force_judge code {exc.code}")
    else:
        return fail("force_judge did not raise")

    laundered = dict(plant_row)
    laundered["oracle_kind"] = "judged"
    lint_launder = lint_official_ledger([laundered], by_id)
    if not any(f.get("code") == LINT_CODE for f in lint_launder):
        return fail("rewritten oracle_kind laundered the lint")

    judge_a = [judge_label(c, JUDGE_A) for c in overlap]
    judge_b = [judge_label(c, JUDGE_B) for c in overlap]
    swap = disagreement_rate(judge_a, judge_b)
    if swap["disagreements"] != 7:
        return fail(f"judge-swap disagreements={swap['disagreements']} want 7")
    ident = disagreement_rate(judge_a, list(judge_a))
    if ident["disagreements"] != 0:
        return fail("identical-judge control was not zero")

    oracle = [oracle_label(c) for c in overlap]
    direction = error_direction(oracle, judge_a)
    extra = extrapolate_error_bar(
        overlap_errors=direction["errors"],
        overlap_n=direction["n"],
        judged_only_n=len(judged),
        direction=direction["direction"],
        false_match=direction["false_match"],
        false_mismatch=direction["false_mismatch"],
    )
    lo, hi = wilson_interval(direction["errors"], direction["n"])
    if extra["judged_only_n"] != len(judged):
        return fail("extrapolation n mismatch")
    if not close(extra["wilson95"][0], lo) or not close(extra["wilson95"][1], hi):
        return fail("extrapolation Wilson does not match live Wilson")

    # Statistics reviewer: recompute from raw pairs via matrix + bootstrap.
    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0309" not in text:
        return fail("receipt sentinel absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"receipt self-declared {st}")
    raw = doc.get("raw_overlap_pairs") or []
    if len(raw) != 50:
        return fail(f"raw pairs n={len(raw)}")
    re_o = [r["oracle"] for r in raw]
    re_a = [r["judge_a"] for r in raw]
    re_b = [r["judge_b"] for r in raw]
    reviewer = cohen_kappa_from_matrix(confusion_counts(re_o, re_a))
    boot = bootstrap_kappa(re_o, re_a, seed=20260824)
    if not close(reviewer["kappa"], 0.72):
        return fail(f"reviewer matrix kappa={reviewer['kappa']}")
    if not close(boot["kappa"], reviewer["kappa"]):
        return fail("bootstrap point estimate drifted from matrix kappa")
    if not (boot["ci95"][0] <= boot["kappa"] <= boot["ci95"][1]):
        return fail(f"kappa outside bootstrap ci {boot['ci95']}")
    swap_raw = disagreement_rate(re_a, re_b)
    if swap_raw["disagreements"] != swap["disagreements"]:
        return fail("receipt judge-swap does not match live labels")

    det_official = [r for r in official if r.get("oracle_kind") == "deterministic"]
    if any(r.get("used_oracle") is not True for r in det_official):
        return fail("a deterministic official score did not use the oracle")
    if any(str(r.get("scorer", "")).startswith("judge.") for r in det_official):
        return fail("a deterministic official score used a judge scorer")

    payload = {
        "pass": True,
        "probe": "probe2-oracle-lint-and-judge-swap",
        "unit_id": UNIT,
        "lint_code": LINT_CODE,
        "lint_good_findings": 0,
        "lint_plant_fired": True,
        "launder_fired": True,
        "force_judge_raised": True,
        "judge_swap_disagreements": swap["disagreements"],
        "judge_swap_rate": swap["disagreement_rate"],
        "identical_judge_disagreements": 0,
        "reviewer_kappa": reviewer["kappa"],
        "reviewer_method": reviewer["method"],
        "bootstrap_ci95": boot["ci95"],
        "extrapolation": extra,
        "plants_detected": 1,
        "plants_expected": 1,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"lint_plant=1 lint_good=0 swap={swap['disagreements']}/50 "
        f"reviewer_kappa={reviewer['kappa']}"
    )
    print("SUCCESS:TST-0309-probe2 oracle-first lint and judge-swap (computed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
