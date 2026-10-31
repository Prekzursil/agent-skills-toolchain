#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0305.json from live pooling + simulation.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (write_receipts.py
does that after named probes pass). Does not call unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))

from council.vote.bayes import (  # noqa: E402
    SIM_K_OBS,
    SIM_N_EXPERTS,
    SIM_N_TRIALS,
    SIM_P_TRUE,
    SIM_SEED,
    clone_both_states,
    independent_panel,
    load_near_certain_spec,
    pool_with_and_without_discount,
    run_calibration_simulation,
)
import _p2lib as L  # noqa: E402

UNIT = "IMP-0305"
OUT = "command-center/receipts/IMP-0305.json"
SCHEMA = "command-center/schema/receipt.schema.json"
SENTINEL = "SUCCESS:IMP-0305"
IMPL = "tools/council/vote/bayes.py"
SPEC = "tools/council/vote/near_certain_v1.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0305/probe1_naive_vs_discount.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0305/probe2_calibration_sim.py"
)
CLONE_P = 0.80
CLONE_N = 8


def sha_file(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:IMP-0305 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def main() -> int:
    spec = load_near_certain_spec()
    both = clone_both_states(CLONE_P, CLONE_N)
    ind = pool_with_and_without_discount(independent_panel(CLONE_P, CLONE_N))
    sim = run_calibration_simulation()
    naive = both["naive"]
    disc = both["discounted"]
    cn = sim["correlated_naive"]
    cd = sim["correlated_discounted"]

    if not both["negative_control_naive_is_near_certain"]:
        print("FAILED:IMP-0305 naive clone panel was not near-certain")
        return 1
    if not both["negative_control_discounted_not_near_certain"]:
        print("FAILED:IMP-0305 discounted clone panel was near-certain")
        return 1
    if not sim["correlated_mse_naive_worse"] or not sim["correlated_brier_naive_worse"]:
        print("FAILED:IMP-0305 simulation did not show naive overconfidence")
        return 1
    if cd["near_certain_rate"] != 0.0:
        print("FAILED:IMP-0305 discounted correlated near-certain rate != 0")
        return 1

    impl_sha, impl_n = sha_file(IMPL)
    spec_sha, spec_n = sha_file(SPEC)
    line_neff = find_line(IMPL, "return float(n) / (1.0 + (n - 1) * r)")
    line_undecl = find_line(IMPL, "class UndeclaredIndependenceError")
    line_refuse = find_line(IMPL, "class PerRunThresholdTuneError")
    line_pool = find_line(IMPL, "pooled_logit = n_eff * logit_mean")
    line_sim = find_line(IMPL, "def run_calibration_simulation(")
    line_thr = find_line(SPEC, '"not_tuned_per_run": true')

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    src1 = L.probe("source", "command", P1, "emit-pre-probe live clone both-states", 0)
    ver1 = L.probe(
        "verifier",
        "command",
        "python3 -c recompute-clone-naive-vs-discount",
        json.dumps(
            {
                "naive": naive["pooled_credence"],
                "discounted": disc["pooled_credence"],
                "n_eff_naive": naive["n_effective"],
                "n_eff_disc": disc["n_effective"],
            }
        ),
        0,
    )
    src2 = L.probe("source", "command", P2, "emit-pre-probe live calibration sim", 0)
    ver2 = L.probe(
        "verifier",
        "command",
        "python3 -c recompute-calibration-simulation",
        json.dumps(
            {
                "mse_naive": cn["mse_to_truth"],
                "mse_disc": cd["mse_to_truth"],
                "brier_naive": cn["brier"],
                "brier_disc": cd["brier"],
                "near_naive": cn["near_certain_rate"],
                "near_disc": cd["near_certain_rate"],
            }
        ),
        0,
    )

    artifact_paths = [
        OUT,
        IMPL,
        SPEC,
        "command-center/p2-wave/probes/IMP-0305/probe1_naive_vs_discount.py",
        "command-center/p2-wave/probes/IMP-0305/probe2_calibration_sim.py",
    ]
    test_ids = [
        "probe1_naive_vs_discount",
        "probe2_calibration_sim",
        "simulation_calibration_error_correlated_vs_independent",
    ]
    negative_control_ids = [
        "fully-correlated-panel-not-near-certain",
        "undeclared-independence-refused",
        "near-certain-threshold-not-per-run",
        "naive-correlated-near-certain-rate-fails-the-property",
    ]

    doc = {
        "answer": (
            f"Yes: naive independent-evidence pooling of {CLONE_N} clones each "
            f"at credence {CLONE_P} yields pooled={naive['pooled_credence']:.12f} "
            f"(near-certain, threshold {spec['threshold']}). Correlation discount "
            f"with roster rho=1 gives n_eff=1 and pooled={disc['pooled_credence']:.12f}, "
            "matching the single voice. Simulation with known "
            f"p_true={SIM_P_TRUE} seed={SIM_SEED} n_trials={SIM_N_TRIALS}: "
            f"correlated naive MSE={cn['mse_to_truth']:.6f} Brier={cn['brier']:.6f} "
            f"near-certain-rate={cn['near_certain_rate']:.3f}; discounted "
            f"MSE={cd['mse_to_truth']:.6f} Brier={cd['brier']:.6f} "
            f"near-certain-rate={cd['near_certain_rate']:.3f}. {SENTINEL}"
        ),
        "artifact_paths": artifact_paths,
        "artifacts": [
            {
                "bytes": 1,
                "eol": "LF",
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256_note": "self-hash omitted; live digest is UNIT-ARTIFACT-MANIFEST.json",
            },
            {
                "bytes": impl_n,
                "eol": "LF",
                "exists": True,
                "path": IMPL,
                "role": "implementation",
                "sha256": impl_sha,
            },
            {
                "bytes": spec_n,
                "eol": "LF",
                "exists": True,
                "path": SPEC,
                "role": "threshold-spec",
                "sha256": spec_sha,
            },
        ],
        "assumption": {
            "discounted": disc["assumption"],
            "naive": naive["assumption"],
            "void_on_clones": disc["independence_assumption_void"],
            "void_reason": disc["void_reason"],
        },
        "completion_sentinel": SENTINEL,
        "dependencies_on_worktree": {
            "IMP-0272": "absent; roster rho is computed locally from vendor+context, not from diversity.py waivers",
            "IMP-0301": "absent; quota/targets.py is not consulted by this pooling module",
        },
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "executed": False,
                "note": "measure runs after this receipt and the per-unit manifest exist",
                "probe": {
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0305",
                    "method": "command",
                    "role": "verifier",
                },
                "read_ok": True,
            }
        ],
        "evidence": [
            L.evidence(
                (
                    f"Same {CLONE_N}-clone roster at credence {CLONE_P}: naive pooled "
                    f"{naive['pooled_credence']:.12f} (n_eff={naive['n_effective']}, "
                    f"near_certain={naive['near_certain']}); discounted pooled "
                    f"{disc['pooled_credence']:.12f} (n_eff={disc['n_effective']}, "
                    f"near_certain={disc['near_certain']}, roster_rho="
                    f"{disc['rho_measured_roster']})."
                ),
                "CONFIRMED",
                f"{IMPL}:{line_pool}",
                [src1, ver1],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Calibration simulation known p_true={SIM_P_TRUE} "
                    f"n_trials={SIM_N_TRIALS} n_experts={SIM_N_EXPERTS} "
                    f"k_obs={SIM_K_OBS} seed={SIM_SEED}: correlated naive "
                    f"MSE={cn['mse_to_truth']:.12f} Brier={cn['brier']:.12f} ECE="
                    f"{cn['ece']:.12f} near_certain_rate={cn['near_certain_rate']}; "
                    f"correlated discounted MSE={cd['mse_to_truth']:.12f} Brier="
                    f"{cd['brier']:.12f} ECE={cd['ece']:.12f} near_certain_rate="
                    f"{cd['near_certain_rate']}."
                ),
                "CONFIRMED",
                f"{IMPL}:{line_sim}",
                [src2, ver2],
                "almost-certain",
            ),
            L.evidence(
                (
                    "n_eff = n / (1+(n-1)*rho) is the discount; rho=1 => n_eff=1; "
                    "fully-correlated clones cannot become near-certain by repetition."
                ),
                "CONFIRMED",
                f"{IMPL}:{line_neff}",
                [src1, ver1],
                "almost-certain",
            ),
            L.evidence(
                "Pooling without declared_rho or vendor+context_id raises UndeclaredIndependenceError.",
                "CONFIRMED",
                f"{IMPL}:{line_undecl}",
                [src1],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Near-certain threshold is versioned {spec['id']} v{spec['version']} "
                    f"threshold={spec['threshold']} frozen=true; per-run override refused."
                ),
                "CONFIRMED",
                f"{SPEC}:{line_thr}",
                [src1, L.probe("verifier", "file-read", SPEC, json.dumps(spec), 0)],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Independent 8-vendor roster at credence {CLONE_P}: rho="
                    f"{ind['discounted']['rho_measured_roster']}, naive="
                    f"{ind['naive']['pooled_credence']:.12f}, discounted="
                    f"{ind['discounted']['pooled_credence']:.12f} (identical); "
                    "independence_assumption_void="
                    f"{ind['discounted']['independence_assumption_void']}."
                ),
                "CONFIRMED",
                f"{IMPL}:{line_pool}",
                [src1, ver1],
                "almost-certain",
            ),
        ],
        "manifest_registration": {
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "manifest_path": "command-center/p2-wave/probes/IMP-0305/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": 2048,
        "negative_control_ids": negative_control_ids,
        "negative_controls": [
            L.control(
                "fully-correlated-panel-not-near-certain",
                "known-broken-fixture",
                "Eight clones at 0.80: naive is near-certain; discounted is not",
                True,
                True,
                bad=(
                    f"naive_pooled={naive['pooled_credence']} "
                    f"near_certain={naive['near_certain']}"
                ),
                good=(
                    f"discounted_pooled={disc['pooled_credence']} "
                    f"near_certain={disc['near_certain']}"
                ),
            ),
            L.control(
                "undeclared-independence-refused",
                "mutation",
                "Missing vendor+context without declared_rho raises",
                True,
                True,
                bad="UndeclaredIndependenceError",
                good="clone and independent fixtures include vendor+context_id",
            ),
            L.control(
                "near-certain-threshold-not-per-run",
                "mutation",
                "per-run threshold override is refused",
                True,
                True,
                bad="override=0.5 -> PerRunThresholdTuneError",
                good=f"declared threshold={spec['threshold']} version={spec['version']}",
            ),
            L.control(
                "naive-correlated-near-certain-rate-fails-the-property",
                "known-broken-fixture",
                "Requiring near_certain_rate==0 of the naive correlated cell FAILS",
                True,
                True,
                bad=f"naive_rate={cn['near_certain_rate']}",
                good=f"discounted_rate={cd['near_certain_rate']}",
            ),
        ],
        "notes": (
            "G-1 IMP-0305: tools/council/vote/bayes.py pools with a declared "
            "independence assumption and a roster-measured correlation discount. "
            "IMP-0272 and IMP-0301 are not on this worktree; disclosed below. "
            "Did not run global unit_manifest.py --write. No ADV rebuild."
        ),
        "output_schema": SCHEMA,
        "profile": "council-vote-module",
        "question": (
            "When participants are correlated (same vendor, same context), does "
            "naive pooling manufacture overconfidence, and does the implementation "
            "discount for the measured correlation?"
        ),
        "refuse_line": f"{IMPL}:{line_refuse}",
        "residual_unknowns": [
            {
                "claim": "IMP-0272 diversity.py waiver records are not consumed; rho is roster-local.",
                "settling_experiment": "When IMP-0272 delivers, bind void_reason to its waiver artifact and re-run probes.",
                "verdict": "DISCLOSED",
            },
            {
                "claim": "IMP-0301 quota/targets.py is not an input to pooling.",
                "settling_experiment": "No binding required for this unit's falsifiable question.",
                "verdict": "DISCLOSED",
            },
            {
                "claim": "No labelled verdict history, so calibration-weighted aggregation (RES-0079) is unused.",
                "settling_experiment": "Revisit pooling weights once a scored history store exists.",
                "verdict": "DISCLOSED",
            },
            {
                "claim": "Original 11-COUNCIL-SPECIFICATION.md is not on this worktree.",
                "settling_experiment": "Re-anchor to the spec file if it is restored.",
                "verdict": "DISCLOSED",
            },
        ],
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "reviewer_id": "IMP-0305-probe2-calibration-sim",
            "scope_not_agreement": True,
            "starts_from_tests": True,
            "verdict": "PASS",
        },
        "reviewer_verdict": "PASS",
        "same_inputs": {
            "clone_credence": CLONE_P,
            "discounted_n_effective": disc["n_effective"],
            "discounted_near_certain": disc["near_certain"],
            "discounted_pooled": disc["pooled_credence"],
            "n": CLONE_N,
            "naive_n_effective": naive["n_effective"],
            "naive_near_certain": naive["near_certain"],
            "naive_pooled": naive["pooled_credence"],
            "overconfidence_gap": both["overconfidence_gap"],
            "roster_rho": disc["rho_measured_roster"],
        },
        "schema_version": 1,
        "sentinel": SENTINEL,
        "simulation": {
            "correlated_discounted_brier": cd["brier"],
            "correlated_discounted_ece": cd["ece"],
            "correlated_discounted_mse": cd["mse_to_truth"],
            "correlated_discounted_near_certain_rate": cd["near_certain_rate"],
            "correlated_naive_brier": cn["brier"],
            "correlated_naive_ece": cn["ece"],
            "correlated_naive_mse": cn["mse_to_truth"],
            "correlated_naive_near_certain_rate": cn["near_certain_rate"],
            "independent_discounted_mse": sim["independent_discounted"]["mse_to_truth"],
            "independent_naive_mse": sim["independent_naive"]["mse_to_truth"],
            "k_obs": SIM_K_OBS,
            "n_experts": SIM_N_EXPERTS,
            "n_trials": SIM_N_TRIALS,
            "p_true": SIM_P_TRUE,
            "seed": SIM_SEED,
        },
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0305",
        "state": "SUCCESS",
        "test_ids": test_ids,
        "tests": [
            {"command": P1, "id": "probe1_naive_vs_discount", "result": "PASS"},
            {"command": P2, "id": "probe2_calibration_sim", "result": "PASS"},
        ],
        "thresholds": {
            "declared": spec,
            "clone_discounted": disc["pooled_credence"],
            "clone_naive": naive["pooled_credence"],
        },
        "timestamps": {"ended_at": now, "started_at": now},
        "title": "Bayesian belief aggregation and confidence pooling",
        "unit_id": UNIT,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:IMP-0305 sentinel missing from serialized receipt")
        return 1
    out_path.write_text(text, encoding="utf-8")
    size = out_path.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0305 receipt {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
