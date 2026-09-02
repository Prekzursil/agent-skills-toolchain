#!/usr/bin/env python3
"""Probe 1: live BM25 paired comparison plus both-state mutants.

Known-good: three true claims stay silent. Known-broken always-contradiction
mutant fires on those controls. All-silent mutant cannot match observed
false-claim hits. Raw strings generate queries without structured fields.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from compare import RESULT_BUDGET, run_comparison  # noqa: E402
from generator import generate  # noqa: E402

ART = (
    REPO
    / "command-center/research/evidence-quality"
    / "RES-0147-disconfirming-query-generation.json"
)
RAW = HERE / "probe1-both-states.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0147-probe1 {msg}")
    return 1


def main() -> int:
    live = run_comparison(generator="v1", ranker="bm25")
    silent = run_comparison(generator="v1", ranker="bm25", mutant="all-silent")
    always = run_comparison(
        generator="v1", ranker="bm25", mutant="always-contradiction"
    )
    s = live["summary"]
    raw_rows = generate("The Moon is made of cheese.")
    raw_qs = [r["query"].lower() for r in raw_rows]
    families = {r["family"] for r in raw_rows}

    report = {
        "probe": "probe1-both-states",
        "unit_id": "RES-0147",
        "backend": live["backend"],
        "result_budget": live["result_budget"],
        "summary": s,
        "negative_control_silent": (
            s["negative_control_generated_hits"] == 0
            and s["negative_control_baseline_hits"] == 0
            and s["negative_control_count"] == 3
        ),
        "sensitivity_generated_false_hits": s["generated_surface_count_false_claims"],
        "all_silent_matches_observed": (
            silent["summary"]["generated_surface_count_all"]
            == s["generated_surface_count_all"]
            and silent["summary"]["baseline_surface_count_all"]
            == s["baseline_surface_count_all"]
        ),
        "always_contradiction_fires_on_true_controls": (
            always["summary"]["negative_control_generated_hits"] == 3
        ),
        "raw_claim_query_count": len(raw_rows),
        "raw_claim_has_moon": any("moon" in q for q in raw_qs),
        "raw_claim_has_does_not_work": any("does not work" in q for q in raw_qs),
        "raw_claim_families": sorted(families),
        "claim_count": s["claim_count"],
    }
    RAW.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k != "summary"}, indent=2)[:3000])

    if s["claim_count"] != 20 or s["false_claim_count"] != 17:
        return fail(f"claim mix {s['claim_count']}/{s['false_claim_count']}")
    if live["result_budget"] != RESULT_BUDGET:
        return fail("budget")
    if not report["negative_control_silent"]:
        return fail("negative-control-fired-on-true-claims")
    if s["generated_surface_count_false_claims"] < 1:
        return fail("sensitivity-all-silent-on-false-claims")
    if report["all_silent_matches_observed"]:
        return fail("all-silent-mutant-indistinguishable")
    if not report["always_contradiction_fires_on_true_controls"]:
        return fail("always-contradiction-mutant-silent")
    if always["summary"]["negative_control_generated_hits"] != 3:
        return fail("always-contradiction-did-not-fail-true-controls")
    if len(raw_rows) < 8:
        return fail("raw-claim-too-few-queries")
    if not report["raw_claim_has_moon"] or not report["raw_claim_has_does_not_work"]:
        return fail("raw-claim-templates-missing")
    required_families = {
        "negation",
        "failure_vocabulary",
        "x_does_not_work",
        "competitor_framing",
        "issue_tracker",
    }
    if not required_families <= families:
        return fail(f"families {sorted(families)}")

    if not ART.is_file():
        return fail("catalog artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:RES-0147" not in text:
        return fail("sentinel missing")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")
    meas = (doc.get("measurements") or {}).get("bm25_v1") or {}
    if int(meas.get("generated_surface_count_false_claims", -1)) != s[
        "generated_surface_count_false_claims"
    ]:
        return fail("artifact-live-false-hit-drift")
    if int(meas.get("negative_control_generated_hits", -1)) != 0:
        return fail("artifact-negative-control-drift")
    if int(meas.get("claim_count", -1)) != 20:
        return fail("artifact-claim-count")

    print(
        "neg_silent=True always_fires=True all_silent_distinct=True "
        f"false_hits={s['generated_surface_count_false_claims']}/"
        f"{s['baseline_surface_count_false_claims']} "
        f"rate_diff={s['rate_difference_false_claims']:.6f}"
    )
    print("SUCCESS:RES-0147-probe1 both-states and live BM25 comparison")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
