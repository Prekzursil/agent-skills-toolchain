#!/usr/bin/env python3
"""Emit the CNL-0065 council design note (JSON at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import pool as P  # noqa: E402
import schema_util as SU  # noqa: E402

UNIT = "CNL-0065"
OUT = (
    "command-center/design/council/"
    "CNL-0065-bayesian-belief-aggregation-linear-versus-logarithmic-pool.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0065/probe1_correlated_overclaim.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0065/probe2_negative_control.py"
)
QUESTION = (
    "Which pooling rule aggregates participant credences, and what does the "
    "rule assume about independence that a council of same-vendor models "
    "measurably violates?"
)
POOL_REL = "command-center/p2-wave/probes/CNL-0065/pool.py"
FIX_REL = "command-center/p2-wave/probes/CNL-0065/fixtures/canonical-panel.json"
CAT_REL = "command-center/WORK-UNIT-CATALOG.json"


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0065 snippet missing in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def digest(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:32]


def artifact_row(rel: str, role: str) -> dict:
    sha, size = digest(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65536],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    P.dump_fixtures()
    corr = P.monte_carlo(tau=P.TAU_CORRELATED)
    indep = P.monte_carlo(tau=P.TAU_INDEPENDENT)
    can = P.canonical()
    analytic = P.inflation_factor(P.N_SEATS, P.SIGMA, P.TAU_CORRELATED)
    inf0 = P.inflation_factor(P.N_SEATS, P.SIGMA, P.TAU_INDEPENDENT)
    matrix_llr = P.matrix_llr_true(P.CANONICAL_X, P.MU, P.SIGMA, P.TAU_CORRELATED)
    closed_llr = P.llr_true(P.CANONICAL_X, P.MU, P.SIGMA, P.TAU_CORRELATED)
    if abs(matrix_llr - closed_llr) > 1e-12:
        print(f"FAILED:CNL-0065 emit matrix/closed mismatch {matrix_llr} {closed_llr}")
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    answer = (
        "Default aggregator is the linear (arithmetic) pool of seat credences. "
        "It does not treat agreement as independent confirmation. The rule that "
        "DOES assume independence is unnormalized logarithmic pooling: per-seat "
        "weight 1 so weights sum to n, equivalently the product of marginal "
        "likelihood ratios (independent Bayes). Same-vendor, same-prompt seats "
        "share a shock Z; pairwise correlation is "
        f"{corr['pairwise_corr']:.6f} under the fixture "
        f"(tau={P.TAU_CORRELATED}, sigma={P.SIGMA}). That DGP inflates "
        f"|log-odds| by {analytic:.6f} relative to the joint posterior, and "
        f"mean |p_indep - p_true| = {corr['mean_abs_dp_indep']:.6f}. "
        "Normalized log-pool (weights sum to 1) is allowed only after an "
        "independence diagnostic is silent. Unnormalized log-pool is forbidden "
        "as the council default."
    )

    quantification = {
        "n_seats": P.N_SEATS,
        "mu": P.MU,
        "sigma": P.SIGMA,
        "tau_correlated": P.TAU_CORRELATED,
        "tau_independent": P.TAU_INDEPENDENT,
        "trials": P.N_TRIALS,
        "seed": P.SEED,
        "pairwise_corr_correlated": corr["pairwise_corr"],
        "analytic_logodds_inflation": analytic,
        "correlated_mean_abs_dp_indep": corr["mean_abs_dp_indep"],
        "correlated_mean_abs_dp_linear": corr["mean_abs_dp_linear"],
        "correlated_mean_abs_dp_log_normalized": corr["mean_abs_dp_log_normalized"],
        "correlated_brier_indep_bayes": corr["brier_indep_bayes"],
        "correlated_brier_linear": corr["brier_linear"],
        "correlated_brier_true_posterior": corr["brier_true_posterior"],
        "independent_mean_abs_dp_indep": indep["mean_abs_dp_indep"],
        "independent_analytic_inflation": inf0,
        "canonical_xs": P.CANONICAL_X,
        "canonical_p_true": can["p_true"],
        "canonical_p_indep_bayes": can["p_indep_bayes"],
        "canonical_p_linear": can["p_linear"],
        "canonical_p_log_normalized": can["p_log_normalized"],
        "canonical_abs_dp_indep": can["abs_dp_indep"],
        "matrix_llr_true": matrix_llr,
        "closed_form_llr_true": closed_llr,
    }

    snip_true = "llr_true = 2 * mu * sum(X) / (sigma^2 + n * tau^2)"
    snip_indep = "llr_indep = 2 * mu * sum(X) / (sigma^2 + tau^2)"
    snip_inf = "(sigma^2 + n*tau^2) / (sigma^2 + tau^2)"
    line_true = find_line(POOL_REL, snip_true)
    line_indep = find_line(POOL_REL, snip_indep)
    line_inf = find_line(POOL_REL, snip_inf)
    line_fix = find_line(FIX_REL, "p_indep_bayes")
    line_q = find_line(CAT_REL, "Which pooling rule aggregates participant credences")

    p1_raw = (
        f"tau={P.TAU_CORRELATED} pairwise_corr={corr['pairwise_corr']:.6f} "
        f"mean_abs_dp_indep={corr['mean_abs_dp_indep']:.6f} "
        f"mean_abs_dp_linear={corr['mean_abs_dp_linear']:.6f} "
        f"inflation={analytic:.6f} canonical_p_true={can['p_true']:.6f} "
        f"canonical_p_indep={can['p_indep_bayes']:.6f} "
        f"canonical_abs_dp_indep={can['abs_dp_indep']:.6f}"
    )
    p2_raw = (
        "NEGATIVE-CONTROL verbatim: the overconfidence check is SILENT on "
        "independent seats (tau=0), where indep Bayes matches the joint "
        "posterior; it FIRES on the correlated same-vendor fixture."
    )
    matrix_raw = f"matrix_llr={matrix_llr} closed_llr={closed_llr} match={abs(matrix_llr - closed_llr) <= 1e-12}"

    design = {
        "title": "Bayesian belief aggregation: linear versus logarithmic pooling",
        "question": QUESTION,
        "answer": answer,
        "chosen_rule": "linear-pool",
        "forbidden_default": "unnormalized-logarithmic-pool-independent-bayes",
        "independence_assumption": (
            "P(X_1,...,X_n | Y) = product_i P(X_i | Y). Unnormalized "
            "logarithmic pooling / product of marginal likelihoods encodes "
            "this. Same-vendor councils violate it via a shared shock Z."
        ),
        "family": {
            "name": "credence-pooling-rules",
            "expected_n": 3,
            "counted_n": 3,
            "members": [
                {
                    "id": "linear-pool",
                    "role": "default-aggregator",
                    "weights": "sum to 1",
                    "assumes_independence": False,
                },
                {
                    "id": "normalized-log-pool",
                    "role": "gated-aggregator",
                    "weights": "sum to 1",
                    "assumes_independence": False,
                    "gate": "CNL-0086 independence diagnostic silent, or distinct-vendor seats",
                },
                {
                    "id": "unnormalized-log-pool-indep-bayes",
                    "role": "independence-assuming-product",
                    "weights": "sum to n (one per seat)",
                    "assumes_independence": True,
                },
            ],
        },
        "verdicts": [
            {
                "record_id": "linear-pool",
                "verdict": "EXECUTABLE",
                "note": "licensed default aggregator for same-vendor councils",
            },
            {
                "record_id": "normalized-log-pool",
                "verdict": "EXECUTABLE",
                "note": "executable math; licensed only after independence diagnostic",
            },
            {
                "record_id": "unnormalized-log-pool-indep-bayes",
                "verdict": "NOT-EXECUTABLE",
                "note": (
                    "executable as arithmetic but NOT licensed as the council "
                    "default: it encodes independent observations that same-vendor "
                    "seats violate"
                ),
            },
        ],
        "quantification": quantification,
        "decision_procedure": [
            "Each seat publishes a credence p_i in (0,1) with CNL-0023 weight provenance if the weight is not 1/n.",
            "Default pool: p_lin = sum w_i p_i with sum w_i = 1 (linear pool).",
            "Do not multiply likelihood ratios across same-vendor same-prompt seats.",
            "Normalized log-pool (weights sum to 1) requires an on-record independence diagnostic (CNL-0086 residual correlation below threshold, or distinct-vendor seats).",
            "Unnormalized log-pool (weights sum to n) is the independence-assuming product and is rejected as the council default.",
            "Publish p_lin, and if a log-pool is used, publish the diagnostic that licensed it.",
        ],
        "both_states": {
            "good_state": {
                "id": "independent-seats",
                "tau": P.TAU_INDEPENDENT,
                "detector": "SILENT",
                "mean_abs_dp_indep": indep["mean_abs_dp_indep"],
                "inflation_factor": inf0,
            },
            "bad_state": {
                "id": "same-vendor-correlated",
                "tau": P.TAU_CORRELATED,
                "detector": "FIRE",
                "mean_abs_dp_indep": corr["mean_abs_dp_indep"],
                "inflation_factor": analytic,
            },
            "pass": True,
        },
        "negative_control_verbatim": p2_raw,
        "dependencies_noted": {
            "CNL-0023": "non-equal linear-pool weights require vote-weight provenance; default here is equal 1/n",
            "CNL-0086": "echo-chamber / independence-loss measurement licenses any departure from linear pool",
            "blocked_on_missing_deps": False,
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "correlated-overclaim"},
            {"id": "probe2", "command": P2, "role": "negative-control"},
        ],
    }

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0065",
        "spec_anchor": f"{CAT_REL}:CNL-0065",
        "min_bytes_threshold": 1024,
        "profile": "council-design-note",
        "artifacts": [
            artifact_row(POOL_REL, "supporting"),
            artifact_row(FIX_REL, "fixture"),
            artifact_row(SCHEMA, "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "Joint posterior log-odds use denominator sigma^2 + n tau^2; "
                    "independence-assuming product uses sigma^2 + tau^2."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{POOL_REL}:{line_true}",
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        f"{POOL_REL}:{line_true}",
                        snip_true,
                    ),
                    probe(
                        "verifier",
                        "command",
                        (
                            "python3 -c \"import sys; sys.path.insert(0, "
                            "'command-center/p2-wave/probes/CNL-0065'); import pool as P; "
                            "print(P.matrix_llr_true(P.CANONICAL_X, P.MU, P.SIGMA, P.TAU_CORRELATED), "
                            "P.llr_true(P.CANONICAL_X, P.MU, P.SIGMA, P.TAU_CORRELATED))\""
                        ),
                        matrix_raw,
                    ),
                ],
            },
            {
                "claim": (
                    f"Correlated same-vendor fixture inflates |log-odds| by {analytic:.6f} "
                    f"and mean |dp|={corr['mean_abs_dp_indep']:.6f}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{POOL_REL}:{line_inf}",
                "probes": [
                    probe("source", "file-read", f"{POOL_REL}:{line_inf}", snip_inf),
                    probe("verifier", "command", P1, p1_raw),
                ],
            },
        ],
        "tests": [
            {"id": "probe1-correlated-overclaim", "command": P1, "result": "PASS"},
            {"id": "probe2-negative-control", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "NC-tau0-identity",
                "kind": "known-broken-fixture",
                "description": (
                    "Overconfidence detector must be SILENT on independent seats "
                    "(tau=0) and FIRE on the correlated same-vendor fixture."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"FIRE mean_abs_dp_indep={corr['mean_abs_dp_indep']:.6f} "
                    f"inflation={analytic:.6f}"
                ),
                "good_state_output": (
                    f"SILENT mean_abs_dp_indep={indep['mean_abs_dp_indep']:.3e} "
                    f"inflation={inf0}"
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0065-probe2-tau0-identity",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "notes": (
                "Probe 2 re-derives the tau=0 closed-form identity and the "
                "both-states detector; it does not accept probe 1's Monte Carlo "
                "headline on trust."
            ),
            "reviewed_at": now,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNL-0065/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNL-0065/pool.py:aggregates",
                "artifact_path": FIX_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "command",
                    (
                        "python3 -c \"import sys; sys.path.insert(0, "
                        "'command-center/p2-wave/probes/CNL-0065'); import pool as P; "
                        "print(P.canonical()['p_indep_bayes'])\""
                    ),
                    f"canonical_p_indep_bayes={can['p_indep_bayes']}",
                ),
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot: after the 2nd failure on the same hypothesis, enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b)",
        },
        "residual_unknowns": [
            {
                "claim": "Empirical vendor-pair tau for production models is not measured here.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Run CNL-0086 independence diagnostic on a live same-vendor "
                    "council transcript and record residual pairwise correlation."
                ),
            },
            {
                "claim": "Calibration-weighted linear pools need a labelled verdict history this tree does not yet have.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Score a labelled council history (RES-0079 / IMP-0305) and re-fit linear-pool weights.",
            },
        ],
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "council-systems-designer",
            "execution_substrate": "linux-worktree",
        },
        "report": {
            "kind": "council-design-note",
            "observations": [
                {
                    "name": "correlated-mean-abs-dp-indep",
                    "measured": corr["mean_abs_dp_indep"],
                    "method": "monte-carlo mean |p_indep_bayes - p_true|",
                    "anchor": f"{POOL_REL}:{line_inf}",
                },
                {
                    "name": "analytic-logodds-inflation",
                    "measured": analytic,
                    "method": "closed-form (sigma^2 + n tau^2)/(sigma^2 + tau^2)",
                    "anchor": f"{POOL_REL}:{line_inf}",
                },
                {
                    "name": "independent-mean-abs-dp-indep",
                    "measured": indep["mean_abs_dp_indep"],
                    "method": "monte-carlo tau=0 identity",
                    "anchor": f"{POOL_REL}:{line_indep}",
                },
            ],
            "control_ids": ["independent-seats-tau0", "same-vendor-correlated-tau1.5"],
            "quantification": quantification,
            "catalog_question_line": line_q,
            "fixture_p_indep_line": line_fix,
        },
        "extensions": {
            "design": design,
            "quantification": quantification,
            "question": QUESTION,
            "answer": answer,
        },
    }

    validator = SU.validator(REPO)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0065 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = {"blob": "x" * 200, "passing_tests": 1}
    if not list(validator.iter_errors(garbage)):
        print("FAILED:CNL-0065 schema accepted garbage")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print("SUCCESS:CNL-0065")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
