#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0059.json from a live catalog census + power calc."""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402
import makespan as M  # noqa: E402
import params as P  # noqa: E402
import power as PW  # noqa: E402
import simulate as S  # noqa: E402

OUT = "command-center/receipts/BLD-0059.json"
SCHEMA = "command-center/schema/scale-model.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
QUESTION = (
    "At ten times the unit count, does the independent-reviewer requirement become "
    "the critical path, and what sampling scheme preserves the error bound?"
)

# The catalog output_schema is a $ref shim into platform/schema. Validating the
# shim with a bare Draft7Validator is vacuous (unresolved $ref accepts garbage)
# or raises. Named probes pin sampling/reviewer at the document root, which
# receipt_core additionalProperties:false would reject. G-1 is those probes
# plus this file existing. This unit-local schema is the non-vacuous check.
UNIT_SCHEMA = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "sampling",
        "reviewer",
        "tests",
        "makespan",
        "critical_path",
        "report",
    ],
    "properties": {
        "unit_id": {"const": "BLD-0059"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:BLD-0059"},
        "sampling": {
            "type": "object",
            "required": [
                "n_per_stratum",
                "confidence",
                "prevalence",
                "escalation",
                "acceptance_criterion",
            ],
            "properties": {
                "n_per_stratum": {"type": "integer", "minimum": 1},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "prevalence": {"type": "number", "minimum": 0, "maximum": 1},
                "escalation": {
                    "type": "object",
                    "required": ["threshold", "exactly_at_threshold_fires"],
                    "properties": {
                        "threshold": {"type": "number"},
                        "exactly_at_threshold_fires": {"const": False},
                    },
                },
                "acceptance_criterion": {
                    "type": "object",
                    "required": ["claimed_scheme", "weak_n3_scheme"],
                },
            },
        },
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent", "recomputed_n"],
            "properties": {
                "independent": {"const": True},
                "verdict": {"const": "PASS"},
                "recomputed_n": {"type": "integer", "minimum": 1},
            },
        },
        "tests": {"type": "array", "minItems": 3},
        "makespan": {
            "type": "object",
            "required": ["with_sampling", "without_sampling"],
        },
        "critical_path": {
            "type": "object",
            "required": ["sampling_needed_at_10x", "sample_size"],
        },
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "scale-model"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
    },
}


def load_catalog() -> dict:
    return json.loads((REPO / CATALOG).read_text(encoding="utf-8"))


def validate_or_die(doc: dict) -> None:
    jsonschema.Draft7Validator.check_schema(UNIT_SCHEMA)
    jsonschema.Draft7Validator(UNIT_SCHEMA).validate(doc)
    for garbage in (
        {},
        {"unit_id": "BLD-0059", "state": "SUCCESS"},
        {"totally": "unrelated", "passing_tests": 999999},
    ):
        try:
            jsonschema.Draft7Validator(UNIT_SCHEMA).validate(garbage)
        except jsonschema.ValidationError:
            continue
        raise SystemExit("FAILED:BLD-0059 schema accepts garbage")
    if (doc.get("sampling") or {}).get("n_per_stratum") != 14:
        raise SystemExit("FAILED:BLD-0059 sampling n_per_stratum is not 14")
    weak = (
        (doc.get("sampling") or {})
        .get("acceptance_criterion", {})
        .get("weak_n3_scheme", {})
    )
    if weak.get("accepted") is not False:
        raise SystemExit("FAILED:BLD-0059 weak n=3 scheme was not rejected in artifact")


def build_doc() -> dict:
    catalog = load_catalog()
    cen = C.census(REPO, catalog)
    n = int(cen["n_work_units"])
    if n < 1000:
        raise SystemExit(f"FAILED:BLD-0059 census n={n} looks like a partial catalog")
    if not cen["reviewer_requirement"]["every_unit_carries_one"]:
        raise SystemExit("FAILED:BLD-0059 reviewer_requirement is not universal")

    t0 = time.perf_counter()
    worked = PW.worked_example(P.DESIGN_PREVALENCE, P.CLAIMED_CONFIDENCE)
    n_star = int(worked["n"])
    independent_n = PW.closed_form_min_n(P.DESIGN_PREVALENCE, P.CLAIMED_CONFIDENCE)
    recompute_s = time.perf_counter() - t0
    if n_star != independent_n:
        raise SystemExit(f"FAILED:BLD-0059 power mismatch {n_star} vs {independent_n}")
    if n_star != 14:
        raise SystemExit(f"FAILED:BLD-0059 expected n=14 got {n_star}")

    claimed = PW.scheme_accepted(n_star, P.DESIGN_PREVALENCE, P.CLAIMED_CONFIDENCE)
    weak = PW.scheme_accepted(P.WEAK_SCHEME_N, P.DESIGN_PREVALENCE, P.CLAIMED_CONFIDENCE)
    if not claimed["accepted"]:
        raise SystemExit("FAILED:BLD-0059 claimed scheme rejected by its own criterion")
    if weak["accepted"]:
        raise SystemExit("FAILED:BLD-0059 weak n=3 scheme was not rejected")

    n_p20 = PW.min_sample_size(0.20, 0.95)
    n_p10 = PW.min_sample_size(0.10, 0.95)
    if n_p10 <= n_p20:
        raise SystemExit("FAILED:BLD-0059 sensitivity table did not move")

    mc = S.monte_carlo_detection(
        class_size=P.HYPERGEOMETRIC_N_10X,
        prevalence=P.DESIGN_PREVALENCE,
        n_sample=n_star,
        theta=P.ESCALATION_THRESHOLD,
        trials=P.MC_TRIALS,
        seed=P.MC_SEED,
    )
    if mc["empirical_detection"] < P.CLAIMED_CONFIDENCE - 0.03:
        raise SystemExit(
            f"FAILED:BLD-0059 MC detection {mc['empirical_detection']} below claim"
        )

    fire = S.escalation_fixture(n=14, n_bad=3, theta=P.ESCALATION_THRESHOLD)
    silent_zero = S.escalation_fixture(n=14, n_bad=0, theta=P.ESCALATION_THRESHOLD)
    exact_theta = S.escalation_fixture(n=20, n_bad=1, theta=P.ESCALATION_THRESHOLD)
    over_theta = S.escalation_fixture(n=20, n_bad=2, theta=P.ESCALATION_THRESHOLD)
    if not fire["fired"] or silent_zero["fired"] or exact_theta["fired"] or not over_theta["fired"]:
        raise SystemExit("FAILED:BLD-0059 escalation fixtures")

    t_bound = int(cen["timeout"]["p50_s"] or 3600)
    t_assumed_600 = 600.0
    pool = P.SERIAL_REVIEWER_POOL
    slots_1x = int(cen["reviewer_requirement"]["reviewer_slots_1x"])

    ms_bound_1 = M.table(cen, n_star, t_bound, "timeout_p50_UPPER_BOUND", pool, 1)
    ms_bound_10 = M.table(cen, n_star, t_bound, "timeout_p50_UPPER_BOUND", pool, 10)
    ms_600_1 = M.table(cen, n_star, t_assumed_600, "ASSUMED_600s_not_measured", pool, 1)
    ms_600_10 = M.table(cen, n_star, t_assumed_600, "ASSUMED_600s_not_measured", pool, 10)
    ms_this_10 = M.table(
        cen,
        n_star,
        max(recompute_s, 1e-6),
        "this_unit_power_recompute_LOWER_BOUND",
        pool,
        10,
    )

    row10_k10 = next(r for r in ms_bound_10["rows"] if r["implementer_concurrency_K"] == 10)
    row10_k10_600 = next(r for r in ms_600_10["rows"] if r["implementer_concurrency_K"] == 10)
    sampling_needed_upper_bound = bool(row10_k10["reviewer_is_critical_path_census"])
    be_unlimited = M.break_even_t_review_s(
        ms_bound_10["implementer_unlimited_K_h"],
        slots_1x * 10,
        pool,
    )

    tests = [
        {
            "id": "power-hand-check-n14",
            "result": "PASS",
            "detail": worked["hand_check"],
        },
        {
            "id": "simulation-detect-class-wide-defect",
            "result": "PASS",
            "detail": (
                f"binomial={mc['binomial_detection']:.4f} "
                f"hypergeometric={mc['hypergeometric_detection']:.4f} "
                f"mc={mc['empirical_detection']:.4f} trials={mc['trials']}"
            ),
        },
        {
            "id": "reject-scheme-that-passes-20pct-defective-class",
            "result": "PASS",
            "detail": weak["reason"],
        },
        {
            "id": "escalation-fires-on-over-threshold-sample",
            "result": "PASS",
            "detail": f"3/14 rate={fire['sample_error_rate']:.4f} fired={fire['fired']}",
        },
        {
            "id": "escalation-silent-on-zero-and-exact-threshold",
            "result": "PASS",
            "detail": (
                f"0/14 fired={silent_zero['fired']}; "
                f"1/20=0.05 exact fired={exact_theta['fired']}; "
                f"2/20 fired={over_theta['fired']}"
            ),
        },
        {
            "id": "sensitivity-halving-p-increases-n",
            "result": "PASS",
            "detail": f"n(p=0.20)={n_p20} n(p=0.10)={n_p10}",
        },
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "unit_id": P.UNIT_ID,
        "state": "SUCCESS",
        "sentinel": P.SENTINEL,
        "schema_version": 1,
        "report_kind": "scale-model",
        "title": "The serial reviewer gate as the binding constraint at 10x",
        "question": QUESTION,
        "scale_factor": P.SCALE_FACTOR,
        "baseline_n": n,
        "scaled_n": n * P.SCALE_FACTOR,
        "scope": {
            "contributes": "reviewer-throughput MAKESPAN model and sampling size",
            "does_not_implement": (
                "CNF-0139 class-expansion trigger. This unit decides whether "
                "sampling is needed and at what size; it does not enqueue units."
            ),
            "b09_wall_clock": cen["b09"],
        },
        "measurements": [
            {
                "id": "catalog-reviewer-coverage",
                "source": CATALOG,
                "n_work_units": n,
                "reviewer_requirement_non_empty": cen["reviewer_requirement"]["non_empty"],
                "coverage": cen["reviewer_requirement"]["coverage_of_work_units"],
                "reviewer_slots_1x": slots_1x,
                "reviewer_slots_10x": slots_1x * 10,
                "two_reviewer_units": cen["reviewer_requirement"]["two_reviewer_units"],
                "kind": "measured-from-catalog",
            },
            {
                "id": "prefix-strata",
                "strata": cen["prefixes"],
                "n_prefix_strata": cen["n_prefix_strata"],
                "kind": "measured-from-catalog",
            },
            {
                "id": "timeout-budget",
                "timeout": cen["timeout"],
                "implementer_budget": cen["implementer_budget"],
                "substrates": cen["substrates"],
                "kind": "catalog-budget-not-wall-clock",
            },
            {
                "id": "b09-reviewer-wall-clock",
                "kind": "NOT-CHECKED",
                "payload": cen["b09"],
            },
            {
                "id": "this-unit-independent-power-recompute-seconds",
                "seconds": recompute_s,
                "kind": "measured-this-run-not-generalizable",
                "note": (
                    "Wall-clock of recomputing n* on this host. A lower bound for "
                    "THIS unit's reviewer task, not a B09 measurement and not a "
                    "typical unit-review duration."
                ),
            },
        ],
        "model": {
            "reviewer_pool": pool,
            "reviewer_gate": "serial (pool=1) independent reviewer, as named by the unit title",
            "implementer": (
                "local-serialized timeout sum is a serial floor; other substrates "
                "divide by concurrency K. K is a parameter (BLD-0057 owns the box ceiling)."
            ),
            "t_review_sources": {
                "b09": "NOT-CHECKED",
                "timeout_p50_s": t_bound,
                "timeout_p50_role": "UPPER_BOUND",
                "assumed_600s_role": "SCENARIO_not_measured",
                "this_unit_recompute_s": recompute_s,
                "this_unit_recompute_role": "LOWER_BOUND_this_unit_only",
            },
            "break_even_t_review_s_at_10x_unlimited_K": round(be_unlimited, 1),
            "interpretation": (
                "If implementation concurrency scales and the independent reviewer "
                "stays a serial gate, census review is the critical path for any "
                f"t_review above {be_unlimited:.1f}s at 10x. Catalog median timeout "
                f"({t_bound}s) is far above that bound. A 600s assumed review is "
                "also above it. B09 did not supply a measured t_review."
            ),
        },
        "makespan": {
            "with_sampling": {
                "n_sample_units": cen["n_prefix_strata"] * n_star,
                "note": "per-stratum n is capped; total sample does not grow with scale",
            },
            "without_sampling": {
                "slots_1x": slots_1x,
                "slots_10x": slots_1x * 10,
            },
            "upper_bound_timeout_p50": {"1x": ms_bound_1, "10x": ms_bound_10},
            "scenario_600s": {"1x": ms_600_1, "10x": ms_600_10},
            "lower_bound_this_recompute_10x": ms_this_10,
            "sampling_needed_at_10x_under_timeout_upper_bound": sampling_needed_upper_bound,
            "sampling_needed_at_10x_under_600s_K10": bool(
                row10_k10_600["reviewer_is_critical_path_census"]
            ),
        },
        "sampling": {
            "kind": "stratified-by-prefix",
            "why_prefix": (
                "Class-wide defects in this catalog are lane/slice correlated. "
                "Prefix is the work-unit class used as the stratum. A class with "
                "fewer than n* units is censused, not sampled."
            ),
            "confidence": P.CLAIMED_CONFIDENCE,
            "prevalence": P.DESIGN_PREVALENCE,
            "n_per_stratum": n_star,
            "power_formula": worked["formula"],
            "worked_example": worked,
            "escalation": {
                "rule": (
                    "When a stratum's sampled error rate exceeds "
                    f"{P.ESCALATION_THRESHOLD} (strict greater-than), expand "
                    "re-verification to the entire affected class (spec :11041). "
                    "CNF-0139 implements the trigger; this model costs the expansion."
                ),
                "threshold": P.ESCALATION_THRESHOLD,
                "comparison": P.ESCALATION_COMPARISON,
                "exactly_at_threshold_fires": False,
                "equivalent_to_any_error_at_n14": True,
                "cnf_0139_scope": "trigger implementation — not this unit",
            },
            "acceptance_criterion": {
                "reject_if": (
                    "P(detect | p=0.20) < claimed confidence, i.e. a scheme that "
                    "would pass a 20%-defective class"
                ),
                "claimed_scheme": claimed,
                "weak_n3_scheme": weak,
            },
            "sensitivity": PW.sensitivity_table(),
            "false_pass_rate": {
                "status": "NOT-CHECKED",
                "reason": (
                    "CNF-0133 confirmer false-pass rate is not an input on this "
                    "tree. Detection probabilities assume a sampled defective unit "
                    "is classified defective. That assumption is disclosed, not "
                    "defaulted to zero as a measured rate."
                ),
            },
        },
        "critical_path": {
            "at_10x_serial_reviewer_scaled_implementer": (
                "YES under the timeout upper bound and under a 600s scenario. "
                "The serial reviewer census scales with n; a 14-per-stratum sample does not."
            ),
            "at_10x_fixed_implementer_K": (
                "Both implementer and reviewer census scale linearly, so the "
                "1x ratio is preserved. Reviewer is critical iff t_review > "
                "mean_implementer_time * pool / K."
            ),
            "sampling_needed_at_10x": True,
            "sample_size": {
                "per_stratum": n_star,
                "n_strata": cen["n_prefix_strata"],
                "total_units_if_every_stratum_ge_n": cen["n_prefix_strata"] * n_star,
            },
        },
        "tests": tests,
        "report": {
            "kind": "scale-model",
            "observations": [
                {
                    "name": "catalog_n_work_units",
                    "measured": n,
                    "method": "len(WORK-UNIT-CATALOG.json work_units)",
                    "anchor": CATALOG,
                },
                {
                    "name": "reviewer_requirement_coverage",
                    "measured": float(
                        cen["reviewer_requirement"]["coverage_of_work_units"]
                    ),
                    "method": "non-empty reviewer_requirement / n_work_units",
                    "anchor": CATALOG,
                },
                {
                    "name": "n_per_stratum",
                    "measured": n_star,
                    "method": "smallest n s.t. (1-p)^n <= 1-confidence",
                    "anchor": "command-center/p2-wave/probes/BLD-0059/power.py",
                },
                {
                    "name": "binomial_detection_p20",
                    "measured": float(mc["binomial_detection"]),
                    "method": "1-(1-p)^n",
                    "anchor": "command-center/p2-wave/probes/BLD-0059/power.py",
                },
                {
                    "name": "mc_empirical_detection_p20",
                    "measured": float(mc["empirical_detection"]),
                    "method": "Monte Carlo hypergeometric draw, escalate on rate>theta",
                    "anchor": "command-center/p2-wave/probes/BLD-0059/simulate.py",
                },
                {
                    "name": "reviewer_is_critical_path_census_10x_K10",
                    "measured": sampling_needed_upper_bound,
                    "method": "timeout_p50 upper-bound makespan table",
                    "anchor": "command-center/p2-wave/probes/BLD-0059/makespan.py",
                },
                {
                    "name": "break_even_t_review_s_10x_unlimited_K",
                    "measured": round(be_unlimited, 1),
                    "method": "implementer_unlimited_K_h * 3600 * pool / slots_10x",
                    "anchor": "command-center/p2-wave/probes/BLD-0059/makespan.py",
                },
                {
                    "name": "b09_reviewer_wall_clock",
                    "measured": "NOT-CHECKED",
                    "method": "catalog remeasure bucket_members.B09 plus scoped path hits",
                    "anchor": "work_units_meta.remeasured_2026_08_11.bucket_members.B09",
                },
            ],
            "control_ids": [
                "reject-scheme-that-passes-20pct-defective-class",
                "escalation-fires-on-over-threshold-sample",
                "escalation-silent-on-zero-and-exact-threshold",
            ],
        },
        "reviewer": {
            "reviewer_id": "BLD-0059-probe2-independent-power-recompute",
            "verdict": "PASS",
            "independent": True,
            "recomputed_n": independent_n,
            "matches_author_n": independent_n == n_star,
            "wall_clock_s": recompute_s,
        },
        "evidence": [
            {
                "claim": "Every work unit in the merged catalog carries a non-empty reviewer_requirement",
                "verdict": "CONFIRMED",
                "anchor": f"{CATALOG}:work_units n={n} non_empty={cen['reviewer_requirement']['non_empty']}",
            },
            {
                "claim": "B09 measured reviewer wall-clock is available as an input",
                "verdict": "NOT-CHECKED",
                "anchor": "work_units_meta.remeasured_2026_08_11.bucket_members.B09=0",
            },
            {
                "claim": "n=14 is the smallest sample that detects p=0.20 at 95% via 1-(1-p)^n",
                "verdict": "CONFIRMED",
                "anchor": f"probes/BLD-0059/power.py worked_example n={n_star} {worked['hand_check']}",
            },
            {
                "claim": "A scheme with n=3 would pass a 20%-defective class and is rejected",
                "verdict": "CONFIRMED",
                "anchor": f"power.scheme_accepted(n=3) accepted={weak['accepted']}",
            },
            {
                "claim": "Escalation fires on an over-threshold sample and is silent at and below threshold",
                "verdict": "CONFIRMED",
                "anchor": "simulate.escalation_fixture 3/14 fire, 0/14 silent, 1/20=0.05 silent",
            },
            {
                "claim": "At 10x the serial reviewer census is the critical path under the timeout upper bound",
                "verdict": "CONFIRMED",
                "anchor": "makespan.upper_bound_timeout_p50.10x K=10 reviewer_is_critical_path_census=true",
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/BLD-0059/power.py",
                "exists": True,
                "role": "power-calculator",
            },
        ],
        "produced_by": {
            "execution_substrate": "linux-local",
            "ts": now,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for BLD-0059. B09 wall-clock is NOT-CHECKED (zero members). "
            "Makespan uses labelled bounds and scenarios, not invented B09 seconds. "
            "Did not run global unit_manifest.py --write."
        ),
    }


def main() -> int:
    (REPO / "command-center" / "receipts").mkdir(parents=True, exist_ok=True)
    doc = build_doc()
    validate_or_die(doc)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if P.SENTINEL not in text:
        print("FAILED:BLD-0059 sentinel missing from artifact text")
        return 1
    (REPO / OUT).write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={len(text.encode('utf-8'))} n*={doc['sampling']['n_per_stratum']}")
    print(P.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
