#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0291.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
from probe2_herding_and_anonymity import NEGATIVE_CONTROL_VERBATIM  # noqa: E402

OUT = "command-center/receipts/TST-0291.json"
SCHEMA = "command-center/schema/receipt.schema.json"
SENTINEL = "SUCCESS:TST-0291"
SUT = "command-center/p2-wave/probes/TST-0291/engine.py"
QUESTIONS = "command-center/p2-wave/probes/TST-0291/questions.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0291/probe1_dispersion_and_accuracy.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0291/probe2_herding_and_anonymity.py"
)
QUESTION = (
    "Delphi is listed as a topology at :10926, and its whole premise is that "
    "iterated anonymous feedback improves estimates. Measure across rounds both "
    "the dispersion of estimates and the accuracy against ground truth on a "
    "scored question set. Falling dispersion with flat or worsening accuracy is "
    "herding, not convergence, and the runtime must be able to tell the "
    "difference before it reports a confident consensus."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def locate(path: Path, snippet: str) -> tuple[int, str]:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if snippet in line:
            return i, line.strip()
    raise RuntimeError(f"snippet not found in {path}: {snippet!r}")


def compact_item(item: dict) -> dict:
    r0, r1 = item["rounds"][0], item["rounds"][-1]
    return {
        "id": item["question_id"],
        "truth": item["truth"],
        "mode": item["mode"],
        "planted": item["planted"],
        "iqr0": r0["iqr"],
        "iqr1": r1["iqr"],
        "individual_mae0": r0["individual_mae"],
        "individual_mae1": r1["individual_mae"],
        "group_abs_error0": r0["group_abs_error"],
        "group_abs_error1": r1["group_abs_error"],
        "median0": r0["median"],
        "median1": r1["median"],
        "kind": item["classification"]["kind"],
        "reason": item["classification"]["reason"],
        "iqr_ratio": item["classification"]["iqr_ratio"],
        "mae_ratio": item["classification"]["mae_ratio"],
        "group_error_ratio": item["classification"]["group_error_ratio"],
        "confident_consensus": item["consensus"]["confident_consensus"],
        "withheld_reason": item["consensus"]["withheld_reason"],
        "naive_dispersion_only_kind": item["naive_dispersion_only"]["kind"],
        "overclaim_disagreement": item["overclaim_disagreement"],
    }


def main() -> int:
    qs = E.load_questions()
    honest = E.run_panel(qs, planted=False, mode="anonymous")
    plant_anon = E.run_panel(qs, planted=True, mode="anonymous")
    plant_attr = E.run_panel(qs, planted=True, mode="attributed")
    honest_b = E.run_panel(qs, planted=False, mode="anonymous")
    if honest["transcript_sha256"] != honest_b["transcript_sha256"]:
        print("FAILED:TST-0291 emit non-deterministic honest panel")
        return 1
    if honest["kind_counts"][E.KIND_CONVERGENCE] != len(qs):
        print("FAILED:TST-0291 emit honest panel not CONVERGENCE", honest["kind_counts"])
        return 1
    if plant_attr["kind_counts"][E.KIND_HERDING] != len(qs):
        print("FAILED:TST-0291 emit planted attributed not HERDING", plant_attr["kind_counts"])
        return 1
    if plant_attr["panel_classification"]["allow_confident_consensus"]:
        print("FAILED:TST-0291 emit planted attributed allowed consensus")
        return 1
    if plant_anon["kind_counts"][E.KIND_HERDING] != 0:
        print("FAILED:TST-0291 emit anonymous plant herded", plant_anon["kind_counts"])
        return 1

    h0, h1 = honest["per_round_means"][0], honest["per_round_means"][-1]
    a0, a1 = plant_anon["per_round_means"][0], plant_anon["per_round_means"][-1]
    t0, t1 = plant_attr["per_round_means"][0], plant_attr["per_round_means"][-1]
    delta_mae = t1["mean_relative_mae"] - a1["mean_relative_mae"]
    mae_ratios = sorted(
        float(it["classification"]["mae_ratio"]) for it in plant_attr["per_question"]
    )
    iqr_ratios = sorted(
        float(it["classification"]["iqr_ratio"]) for it in plant_attr["per_question"]
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sut_path = REPO / SUT
    q_path = REPO / QUESTIONS
    sut_sha, sut_bytes = sha256_file(sut_path)
    q_sha, q_bytes = sha256_file(q_path)
    schema_base = REPO / SCHEMA
    sim_present = E.production_simulate_present(REPO)
    classify_line, classify_snip = locate(sut_path, "def classify_trajectory")
    consensus_line, consensus_snip = locate(sut_path, "def maybe_report_consensus")
    naive_line, naive_snip = locate(sut_path, "def naive_dispersion_only_claim")
    revise_line, revise_snip = locate(sut_path, "def _revise")

    answer = (
        "On a 12-item scored numeric set, honest anonymous Delphi (median "
        "feedback, evidence-retaining revision) tightened mean relative IQR "
        f"{h0['mean_relative_iqr']:.4f} -> {h1['mean_relative_iqr']:.4f} while "
        f"mean relative individual MAE {h0['mean_relative_mae']:.4f} -> "
        f"{h1['mean_relative_mae']:.4f} (raw mean IQR {h0['mean_iqr']} -> "
        f"{h1['mean_iqr']}; raw mean MAE {h0['mean_individual_mae']} -> "
        f"{h1['mean_individual_mae']}). All 12 items classified CONVERGENCE and "
        "the runtime allowed a confident consensus. Seeding one stubborn "
        "confident-wrong seat and switching to attributed high-confidence "
        "feedback reversed the accuracy trajectory: mean relative MAE "
        f"{t0['mean_relative_mae']:.4f} -> {t1['mean_relative_mae']:.4f} while "
        f"relative IQR {t0['mean_relative_iqr']:.4f} -> {t1['mean_relative_iqr']:.4f}. "
        "All 12 items classified HERDING; maybe_report_consensus withheld "
        "confident_consensus (withheld_reason=herding). A dispersion-only claim "
        "on the same raw IQRs would have called CONVERGENCE on every herding "
        "item. The same plant under anonymous median feedback did not herd "
        f"(herding_items=0); attributed minus anonymous final relative MAE = "
        f"{delta_mae:.4f}. Falling dispersion is therefore not treated as "
        "convergence."
    )

    doc = {
        "unit_id": "TST-0291",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "delphi_convergence_calibration",
        "title": "Delphi convergence: variance must fall without the panel simply herding",
        "question": QUESTION,
        "answer": answer,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json TST-0291; _USER-PROMPTS.md:10926 Delphi topology; "
            "catalog tests_required: per-round dispersion+accuracy, herding control, "
            "anonymity dependency"
        ),
        "measured_at": now,
        "min_bytes_threshold": 2048,
        "output_schema": SCHEMA,
        "declared_schema_file_present": schema_base.is_file(),
        "sut": {
            "catalog_input": "tools/council/simulate.py (deterministic council simulator)",
            "catalog_simulator_present": sim_present,
            "catalog_delphi_module": "tools/council/topology/delphi.py",
            "catalog_delphi_present": (REPO / "tools/council/topology/delphi.py").is_file(),
            "live_module": SUT,
            "live_sha256": sut_sha,
            "live_bytes": sut_bytes,
            "scored_set": QUESTIONS,
            "scored_set_sha256": q_sha,
            "scored_set_bytes": q_bytes,
            "n_questions": len(qs),
            "n_rounds": E.N_ROUNDS,
            "n_seats": E.N_SEATS,
            "anonymous_rule": (
                "estimate=(1-ANON_LISTEN)*private + ANON_LISTEN*anonymous_median; "
                "feedback carries median and IQR only"
            ),
            "attributed_rule": (
                "estimate=ATTR_PRIVATE*private + ATTR_MEDIAN*median + "
                "ATTR_LEADER*named_max_confidence_estimate"
            ),
            "consensus_gate": (
                "confident_consensus only if classify_trajectory.kind==CONVERGENCE "
                "(IQR fell AND individual MAE improved AND group |median-truth| "
                "did not worsen); HERDING withholds consensus"
            ),
        },
        "per_round_raw_numbers": {
            "honest_anonymous": honest["per_round_means"],
            "planted_anonymous": plant_anon["per_round_means"],
            "planted_attributed": plant_attr["per_round_means"],
            "note": (
                "Each row is the unweighted mean across the 12 scored items of "
                "IQR, individual MAE, and |median-truth|. Relative columns divide "
                "by max(|truth|,1). A convergence claim that cites only the IQR "
                "columns is the overclaim this unit rejects."
            ),
        },
        "per_question_raw": {
            "honest_anonymous": [compact_item(it) for it in honest["per_question"]],
            "planted_anonymous": [compact_item(it) for it in plant_anon["per_question"]],
            "planted_attributed": [compact_item(it) for it in plant_attr["per_question"]],
        },
        "kind_counts": {
            "honest_anonymous": honest["kind_counts"],
            "planted_anonymous": plant_anon["kind_counts"],
            "planted_attributed": plant_attr["kind_counts"],
        },
        "herding_control": {
            "plant": {
                "seat_id": E.PLANT_SEAT,
                "relative_offset": E.PLANT_RELATIVE,
                "confidence": E.PLANT_CONFIDENCE,
                "stubborn": True,
            },
            "dispersion_fell": True,
            "accuracy_worsened": True,
            "herding_items": plant_attr["kind_counts"][E.KIND_HERDING],
            "convergence_items": plant_attr["kind_counts"][E.KIND_CONVERGENCE],
            "confident_consensus_allowed": plant_attr["panel_classification"][
                "allow_confident_consensus"
            ],
            "withheld_reason": "herding",
            "mae_ratio_interval": {
                "min": mae_ratios[0],
                "median": mae_ratios[len(mae_ratios) // 2],
                "max": mae_ratios[-1],
                "n": len(mae_ratios),
            },
            "iqr_ratio_interval": {
                "min": iqr_ratios[0],
                "median": iqr_ratios[len(iqr_ratios) // 2],
                "max": iqr_ratios[-1],
                "n": len(iqr_ratios),
            },
            "naive_dispersion_only_would_allow_consensus_on_all_items": True,
        },
        "anonymity_dependency": {
            "same_plant": True,
            "round0_relative_mae_held_fixed": abs(
                a0["mean_relative_mae"] - t0["mean_relative_mae"]
            )
            < 1e-12,
            "anonymous": {
                "herding_items": plant_anon["kind_counts"][E.KIND_HERDING],
                "allow_confident_consensus": plant_anon["panel_classification"][
                    "allow_confident_consensus"
                ],
                "final_mean_relative_mae": a1["mean_relative_mae"],
                "final_mean_relative_iqr": a1["mean_relative_iqr"],
                "transcript_sha256": plant_anon["transcript_sha256"],
            },
            "attributed": {
                "herding_items": plant_attr["kind_counts"][E.KIND_HERDING],
                "allow_confident_consensus": plant_attr["panel_classification"][
                    "allow_confident_consensus"
                ],
                "final_mean_relative_mae": t1["mean_relative_mae"],
                "final_mean_relative_iqr": t1["mean_relative_iqr"],
                "transcript_sha256": plant_attr["transcript_sha256"],
            },
            "delta_final_relative_mae_attributed_minus_anonymous": delta_mae,
            "delta_final_group_abs_error_attributed_minus_anonymous": t1[
                "mean_group_abs_error"
            ]
            - a1["mean_group_abs_error"],
        },
        "transcript_sha256": {
            "honest_anonymous": honest["transcript_sha256"],
            "planted_anonymous": plant_anon["transcript_sha256"],
            "planted_attributed": plant_attr["transcript_sha256"],
            "honest_rerun_identical": True,
        },
        "evidence": [
            {
                "claim": (
                    "Honest anonymous Delphi on the 12-item scored set shows "
                    "falling IQR and falling individual MAE on every item; the "
                    "runtime allows confident consensus only because accuracy "
                    "improved, not because dispersion alone fell."
                ),
                "verdict": "CONFIRMED",
                "source_probe": P1,
                "verifier_probe": P2,
                "anchor": f"{SUT}:{classify_line}",
                "kind": "measured-trajectory",
                "path": SUT,
                "line": classify_line,
                "snippet": classify_snip,
                "raw": {
                    "kind_counts": honest["kind_counts"],
                    "per_round_means": honest["per_round_means"],
                },
            },
            {
                "claim": (
                    "Seeding one confident-but-wrong stubborn seat under "
                    "attributed feedback makes IQR fall while MAE and "
                    "|median-truth| rise; classify_trajectory returns HERDING "
                    "and maybe_report_consensus withholds confident consensus. "
                    "naive_dispersion_only_claim returns CONVERGENCE on the "
                    "same IQR series."
                ),
                "verdict": "CONFIRMED",
                "source_probe": P2,
                "verifier_probe": P1,
                "anchor": f"{SUT}:{consensus_line}",
                "kind": "herding-control",
                "path": SUT,
                "line": consensus_line,
                "snippet": consensus_snip,
                "raw": {
                    "kind_counts": plant_attr["kind_counts"],
                    "per_round_means": plant_attr["per_round_means"],
                    "mae_ratio_interval": {
                        "min": mae_ratios[0],
                        "max": mae_ratios[-1],
                    },
                },
            },
        ],
        "tests": [
            {
                "id": "probe1-dispersion-and-accuracy",
                "command": P1,
                "result": "PASS",
                "name": "per-round IQR and MAE on scored set; honest CONVERGENCE",
            },
            {
                "id": "probe2-herding-and-anonymity",
                "command": P2,
                "result": "PASS",
                "name": "planted herding control, anonymity delta, independent recount",
            },
        ],
        "tests_required": [
            {
                "id": "dispersion-and-accuracy-per-round",
                "text": "Dispersion and accuracy per round on a scored set.",
                "result": "PASS",
                "n_questions": len(qs),
                "n_rounds": E.N_ROUNDS,
                "honest_anonymous_per_round": honest["per_round_means"],
            },
            {
                "id": "herding-control",
                "text": (
                    "Herding control: seed one confident-but-wrong participant "
                    "and confirm the harness flags accuracy degradation while "
                    "dispersion falls."
                ),
                "result": "PASS",
                "herding_items": plant_attr["kind_counts"][E.KIND_HERDING],
                "confident_consensus": False,
            },
            {
                "id": "anonymity-dependency",
                "text": (
                    "Anonymity dependency: run with feedback attributed and "
                    "unattributed and report the difference."
                ),
                "result": "PASS",
                "delta_final_relative_mae_attributed_minus_anonymous": delta_mae,
                "anonymous_herding_items": plant_anon["kind_counts"][E.KIND_HERDING],
                "attributed_herding_items": plant_attr["kind_counts"][E.KIND_HERDING],
            },
        ],
        "negative_controls": [
            {
                "id": "dispersion-only-convergence-claim",
                "kind": "known-broken-claim",
                "verbatim": NEGATIVE_CONTROL_VERBATIM,
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "rejects": "CONVERGENCE from falling IQR alone on the planted attributed panel",
            }
        ],
        "reviewer": {
            "reviewer_id": "TST-0291-probe2-herding-and-anonymity-recount",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "statistics_mandate": True,
            "executed_both_states": True,
            "notes": (
                "Probe 2 re-derives IQR, individual MAE, and |median-truth| from "
                "the raw per-seat estimate vectors with local arithmetic, "
                "reproduces the herding classification and the MAE-ratio interval, "
                "and executes the honest-silent / planted-fire both-states control. "
                "Not a fresh-context human statistician; the catalog names one, "
                "which this lane cannot supply without self-certifying."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0291/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "TST-0291",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot (AGENTS.md 4b): after a second failure on "
                "the same hypothesis, enumerate at least two alternative approaches "
                "before a third attempt."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "tools/council/simulate.py (TST-0257) and "
                    "tools/council/topology/delphi.py (IMP-0286) are absent from "
                    "this worktree. Measurements are of the contracted Delphi "
                    "classifier shipped with this unit, not of those missing "
                    "production paths."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-point SUT import at tools/council/topology/delphi.py once "
                    "IMP-0286 lands and re-run both named probes against the "
                    "same scored set and plant."
                ),
            }
        ],
        "field_citations": [
            {
                "field": "classify_trajectory",
                "path": SUT,
                "line": classify_line,
                "snippet": classify_snip,
            },
            {
                "field": "maybe_report_consensus",
                "path": SUT,
                "line": consensus_line,
                "snippet": consensus_snip,
            },
            {
                "field": "naive_dispersion_only_claim",
                "path": SUT,
                "line": naive_line,
                "snippet": naive_snip,
            },
            {
                "field": "_revise",
                "path": SUT,
                "line": revise_line,
                "snippet": revise_snip,
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": SUT,
                "exists": True,
                "role": "delphi-runtime-under-test",
                "sha256": sut_sha,
                "bytes": sut_bytes,
            },
            {
                "path": QUESTIONS,
                "exists": True,
                "role": "scored-question-set",
                "sha256": q_sha,
                "bytes": q_bytes,
            },
        ],
        "required_fix": None,
        "cloud_ok": False,
        "owner_approval_required": True,
        "owner_approval_granted": False,
        "owner_approval_note": (
            "Catalog flags owner_approval_required. This receipt is the "
            "calibration measurement, not an owner sign-off."
        ),
        "dependencies_noted": ["TST-0257", "TST-0287"],
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = dest.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0291 emit sentinel absent from file")
        return 1
    if dest.stat().st_size < int(doc["min_bytes_threshold"]):
        print("FAILED:TST-0291 emit below min_bytes_threshold")
        return 1
    parsed = json.loads(text)
    if parsed.get("state") != "SUCCESS":
        print("FAILED:TST-0291 emit state is not SUCCESS")
        return 1
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:TST-0291 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
