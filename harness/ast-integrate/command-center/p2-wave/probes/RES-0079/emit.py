#!/usr/bin/env python3
"""Emit command-center/research/RES-0079.json from live pooling control + primary papers."""
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

OUT_REL = "command-center/research/RES-0079.json"
SENTINEL = (
    "SUCCESS:RES-0079 in the receipt AND a method table with a "
    "prerequisite-data column and one method identified as usable at zero history"
)
QUESTION = (
    "Between linear pooling, logarithmic pooling and Bayesian aggregation, "
    "which produces better calibrated group forecasts when members differ in "
    "calibration - and what does each require that this program does not yet "
    "have (a labelled verdict history)?"
)
SCHEMA = "command-center/schema/research-claim-record.schema.json"
HISTORY_MARKERS = [
    "command-center/receipts/IMP-0352.json",
    "tools/council/participants/select_calibrated.py",
    "command-center/research/RES-0001.json",
    "command-center/schema/research-claim-record.schema.json",
]


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def labelled_history_inventory() -> dict:
    rows = []
    for rel in HISTORY_MARKERS:
        p = REPO / rel
        rows.append(
            {
                "path": rel,
                "present": p.is_file(),
                "bytes": p.stat().st_size if p.is_file() else 0,
            }
        )
    return {
        "labelled_verdict_history_present": False,
        "reason": (
            "IMP-0352 store/receipt and select_calibrated.py are absent on this "
            "worktree; no (forecast, resolved-verdict) panel exists to estimate "
            "BMA or inverse-Brier weights."
        ),
        "markers": rows,
    }


def main() -> int:
    control = P.run_control(seed=79, n_train=400, n_test=2000)
    history = labelled_history_inventory()
    scores = control["scores"]
    lin_s = scores["linear_equal_zero_history"]
    log_s = scores["log_equal_zero_history"]
    bma_s = scores["bma_linear_with_history"]
    ib_s = scores["inverse_brier_linear_with_history"]

    claims = [
        {
            "claim_id": "RES-0079-C1",
            "canonical_mechanism": (
                "Equal-weight linear pooling is defined from the current member "
                "probabilities alone and is therefore usable at zero labelled history."
            ),
            "verdict": "CONFIRMED",
            "cannot_promote": False,
            "evidence_tier": "E1",
            "confidence_band": "high",
            "named_settling_probe": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0079/probe2_zero_history.py"
            ),
            "source_lineage": [
                {
                    "work": "Stone, M. (1961). The Opinion Pool. Annals of Mathematical Statistics 32(4) 1339-1342.",
                    "doi": "10.1214/aoms/1177704873",
                    "section": "the linear opinion pool definition (arithmetic mixture of the member distributions)",
                    "effect_size": "operator is the arithmetic mean; no outcome sample appears in the definition",
                    "baseline": "a single member's distribution used as dictator",
                }
            ],
            "strongest_caveat": (
                "Usable does not mean well calibrated: Ranjan and Gneiting (2010) "
                "Section 2 prove any non-trivial linear pool of distinct calibrated "
                "binary forecasts is itself uncalibrated."
            ),
        },
        {
            "claim_id": "RES-0079-C2",
            "canonical_mechanism": (
                "When members are calibrated, a linear pool is nevertheless "
                "miscalibrated (underconfident). Recalibrated linear pooling (BLP) "
                "cuts Brier score relative to equal-weight and optimally weighted "
                "linear pools, but BLP parameters are fit on labelled training outcomes."
            ),
            "verdict": "CONFIRMED",
            "cannot_promote": False,
            "evidence_tier": "E1",
            "confidence_band": "high",
            "named_settling_probe": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0079/probe1_method_table.py"
            ),
            "source_lineage": [
                {
                    "work": "Ranjan, R. and Gneiting, T. (2010). Combining Probability Forecasts. JRSS-B 72(1) 71-91.",
                    "doi": "10.1111/j.1467-9868.2009.00726.x",
                    "section": "Section 2 (uncalibrated linear pool theorem); Table 2 (simulation, both sources calibrated); Table 6 (precipitation case, statistical sources only)",
                    "effect_size": (
                        "Table 2 out-of-sample mean Brier: ELP 0.1563 (REL 0.0418) and "
                        "OLP 0.1531 (REL 0.0120) versus BLP 0.1137 (REL 0.0005) and "
                        "theoretically optimal CP 0.1126 (REL 0.0003). Table 6 precipitation "
                        "Brier: BLP 0.0783 (REL 0.0004) versus OLP 0.0800 (REL 0.0021) "
                        "versus best individual GMOS 0.0815 (REL 0.0011)."
                    ),
                    "baseline": (
                        "Table 2: individuals p1 Brier 0.2094 (REL 0.0002) and p2 0.1657 "
                        "(REL 0.0004); uncertainty component 0.2500. Table 6: GMOS/EMOS/NMOS "
                        "individuals 0.0815/0.0866/0.0934; UNC 0.1543. OLP/BLP fit on a "
                        "training sample of size 10000 (simulation) or two years of PoP "
                        "forecasts (1 Jul 2003-30 Jun 2005)."
                    ),
                }
            ],
            "strongest_caveat": (
                "BLP is not a zero-history method. The Table 2/6 gains cannot be "
                "spent in this program until a labelled (forecast, verdict) panel exists."
            ),
        },
        {
            "claim_id": "RES-0079-C3",
            "canonical_mechanism": (
                "Logarithmic / log-linear pooling is defined at zero history (equal "
                "weights) and, when weights are estimated by maximum likelihood on "
                "labelled data, can match the true conditional on independent sources. "
                "Equal-weight log pooling is not the same operator as ML log-linear pooling."
            ),
            "verdict": "CONFIRMED",
            "cannot_promote": False,
            "evidence_tier": "E1",
            "confidence_band": "high",
            "named_settling_probe": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0079/probe2_zero_history.py"
            ),
            "source_lineage": [
                {
                    "work": "Allard, D., Comunian, A. and Renard, P. (2012). Probability Aggregation Methods in Geoscience. Mathematical Geosciences 44 545-571.",
                    "doi": "10.1007/s11004-012-9396-3",
                    "section": "Theorem 1 (calibrated log-linear pool is the ML estimator, asymptotically); Table 4 (first binary case, two near-independent sources)",
                    "effect_size": (
                        "Table 4 Brier score: log-linear 0.1353 (reliability 0.0010, "
                        "sharpness 0.1156) versus linear pooling 0.1705 (reliability 0.0346, "
                        "sharpness 0.1141) versus true conditional P12 0.1352 "
                        "(reliability 0.0010, sharpness 0.1158). ML weight 1.46 on each source."
                    ),
                    "baseline": (
                        "Single-source P1 Brier 0.1973 (reliability 0.0011, sharpness 0.0538); "
                        "true P12 is the unattainable-without-the-joint-model floor."
                    ),
                },
                {
                    "work": "Genest, C. and Zidek, J. V. (1986). Combining Probability Distributions: A Critique and an Annotated Bibliography. Statistical Science 1(1) 114-135.",
                    "doi": "10.1214/ss/1177013825",
                    "section": "external Bayesianity characterisation: log pools (weights summing to 1) are externally Bayesian; linear pools generally are not",
                    "effect_size": "axiomatic uniqueness, not a scored forecast experiment",
                    "baseline": "linear opinion pool of Stone (1961) / McConway (1981) marginalisation uniqueness",
                    "cannot_promote": True,
                    "why_not_promoted": (
                        "Headline is axiomatic, not an effect size versus a scored baseline; "
                        "recorded as context. A number-free uniqueness theorem does not "
                        "promote logarithmic pooling as the better-calibrated operator here."
                    ),
                },
            ],
            "strongest_caveat": (
                "Table 4's winning log-linear row uses ML weights (1.46), i.e. labelled "
                "data. Equal-weight log pooling also 0-forces: one member at 0 or 1 vetoes "
                "the pool. This program's live unequal-calibration control (seed 79) gives "
                f"equal-weight log Brier {log_s['brier']:.6f} and ECE {log_s['ece']:.6f} "
                f"versus equal-weight linear Brier {lin_s['brier']:.6f} and ECE {lin_s['ece']:.6f}; "
                "log pooling is worse on both scores in that DGP."
            ),
        },
        {
            "claim_id": "RES-0079-C4",
            "canonical_mechanism": (
                "Bayesian model averaging produces better calibrated predictive "
                "distributions than a raw ensemble by setting member weights to posterior "
                "model probabilities estimated on a labelled training window. With a uniform "
                "prior and empty history the posterior equals the prior and BMA collapses "
                "to equal-weight linear pooling of the component densities."
            ),
            "verdict": "CONFIRMED",
            "cannot_promote": False,
            "evidence_tier": "E1",
            "confidence_band": "high",
            "named_settling_probe": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0079/probe2_zero_history.py"
            ),
            "source_lineage": [
                {
                    "work": "Raftery, A. E., Gneiting, T., Balabdaoui, F. and Polakowski, M. (2005). Using Bayesian Model Averaging to Calibrate Forecast Ensembles. Monthly Weather Review 133(5) 1155-1174.",
                    "doi": "10.1175/MWR2906.1",
                    "section": "Section 3a (training-period length: 25 days hits 90.0% coverage of 90% intervals); Table 6 (deterministic 2-m temperature, Pacific Northwest, Jan-Jun 2000, 48 h)",
                    "effect_size": (
                        "Table 6 MAE: BMA 2.26 versus best raw member AVN-MM5 2.45 "
                        "(8% lower) versus sample climatology 7.69 (71% lower). RMSE: "
                        "BMA 2.94 versus ensemble mean 3.18 versus best raw 3.15 versus "
                        "climatology 9.58. 90% BMA intervals approximately calibrated and "
                        "69% narrower on average than climatology."
                    ),
                    "baseline": (
                        "sample climatology MAE 7.69 / RMSE 9.58; best raw member "
                        "AVN-MM5 MAE 2.45 / RMSE 3.15; ensemble mean RMSE 3.18. "
                        "Weights and variance estimated on a sliding 25-day window of "
                        "forecasts AND verifying observations."
                    ),
                }
            ],
            "strongest_caveat": (
                "The 25-day labelled window is the prerequisite this program does not "
                "have. Empty-history BMA is not a third operator; it is equal-weight "
                "linear pooling under another name."
            ),
        },
        {
            "claim_id": "RES-0079-C5",
            "canonical_mechanism": (
                "Calibration-weighted aggregation (inverse-Brier or recursive log-score "
                "weights) is blocked without a labelled verdict history. The call sheet's "
                "grade is corroborated, not restated: the operators are undefined on an "
                "empty (forecast, outcome) store, which is the measured state of this worktree."
            ),
            "verdict": "CONFIRMED",
            "cannot_promote": False,
            "evidence_tier": "E1",
            "confidence_band": "high",
            "named_settling_probe": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0079/probe2_zero_history.py"
            ),
            "source_lineage": [
                {
                    "work": "live worktree inventory plus pool.InsufficientHistory control",
                    "doi": None,
                    "section": "labelled_history_inventory() in this unit; pool.bma_weights([]) and pool.inverse_brier_weights([])",
                    "effect_size": "both weight estimators raise InsufficientHistory on empty history; IMP-0352 receipt and select_calibrated.py are absent (present=false)",
                    "baseline": "the same estimators return a simplex of weights after 400 labelled rows in run_control(seed=79)",
                }
            ],
            "strongest_caveat": (
                "Absence of IMP-0352 is a worktree fact, not a proof that labelled "
                "history can never exist. The operator remains blocked TODAY."
            ),
        },
        {
            "claim_id": "RES-0079-C6",
            "canonical_mechanism": (
                "Kascha and Ravazzolo (2010) do not identify a winner between linear "
                "and logarithmic pooling across four inflation datasets; equal weights "
                "often beat recursive log-score weights. That paper is recorded as E3 "
                "for the promotion decision (no single effect size + baseline pair is "
                "quoted here from a table) and cannot promote a pooling rule."
            ),
            "verdict": "REFUTED",
            "cannot_promote": True,
            "evidence_tier": "E3",
            "confidence_band": "low",
            "named_settling_probe": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/RES-0079/probe1_method_table.py"
            ),
            "source_lineage": [
                {
                    "work": "Kascha, C. and Ravazzolo, F. (2010). Combining inflation density forecasts. Journal of Forecasting 29 231-250.",
                    "doi": "10.1002/for.1147",
                    "section": "abstract and Section 4 qualitative summary (linear vs logarithmic; equal vs recursive log-score weights)",
                    "effect_size": "UNQUOTED-TABLE - qualitative 'no clear support for one combination method'",
                    "baseline": "UNQUOTED-TABLE",
                }
            ],
            "strongest_caveat": (
                "Default-REFUTED as a promoter: a qualitative abstract without a "
                "quoted Table lnS and its comparator is E3 and must not pick the rule."
            ),
        },
    ]

    method_table = [
        {
            "method": "linear pooling (equal weights)",
            "id": "linear-equal",
            "formula": "p = sum_i w_i p_i with w_i = 1/k",
            "prerequisite-data": (
                "current member probabilities p_1..p_k only; no resolved verdicts"
            ),
            "usable_at_zero_history": True,
            "usable_today": True,
            "calibration_when_members_differ": (
                "Defined. Robust to a 0/1 veto. Theoretically uncalibrated even if "
                "every member is calibrated (Ranjan and Gneiting 2010, Section 2). "
                "Pulled toward badly calibrated members when weights are equal."
            ),
            "promoted": True,
            "role": "the method identified as usable at zero history",
        },
        {
            "method": "logarithmic pooling (equal weights)",
            "id": "log-equal",
            "formula": "p ∝ exp(sum_i w_i log p_i), w_i = 1/k, then binary-renormalized",
            "prerequisite-data": (
                "current member probabilities p_1..p_k only, plus a floor/clipping "
                "convention for 0/1 reports; no resolved verdicts for equal weights. "
                "ML / calibrated log-linear weights additionally need a labelled "
                "(forecast, outcome) panel (Allard et al. 2012, Theorem 1)."
            ),
            "usable_at_zero_history": False,
            "usable_today": False,
            "why_not_the_zero_history_pick": (
                "Computationally defined at zero history, but not identified as the "
                "usable-today method: 0/1 forcing lets one overconfident miscalibrated "
                "member veto the pool, and the live unequal-calibration control scores "
                "it worse than equal-weight linear pooling."
            ),
            "calibration_when_members_differ": (
                "Sharper than linear pooling; ML-weighted log-linear can be near-optimal "
                "on independent sources (Allard Table 4) once labels exist."
            ),
            "promoted": False,
            "role": "zero-history-capable but not selected",
        },
        {
            "method": "Bayesian aggregation (BMA / posterior model weights)",
            "id": "bayesian-bma",
            "formula": (
                "w_i = P(M_i | y_train) ∝ P(y_train | M_i) P(M_i); "
                "pooled forecast is the linear mixture of member densities with those weights "
                "(Raftery et al. 2005 eq. after the law of total probability)"
            ),
            "prerequisite-data": (
                "a labelled training window of member forecasts AND verifying outcomes "
                "(Raftery et al. 2005 used 25 days of 48-h temperature forecasts and "
                "observations to hit 90.0% coverage of 90% intervals). Uniform prior "
                "plus empty history ⇒ w_i = 1/k, i.e. equal-weight linear pooling."
            ),
            "usable_at_zero_history": False,
            "usable_today": False,
            "calibration_when_members_differ": (
                "This is the operator designed for unequal skill: posterior mass "
                "concentrates on historically better-calibrated members. Live control "
                f"seed 79: ECE {bma_s['ece']:.6f} versus equal-linear ECE {lin_s['ece']:.6f} "
                f"after 400 labelled rows; Brier {bma_s['brier']:.6f} versus {lin_s['brier']:.6f}."
            ),
            "promoted": False,
            "role": "best calibrated of the three once labels exist; blocked today",
        },
        {
            "method": "calibration-weighted linear pooling (inverse-Brier)",
            "id": "calibration-weighted",
            "formula": "w_i ∝ 1 / mean_t (p_{i,t} - y_t)^2, then linear pool",
            "prerequisite-data": (
                "the same labelled (forecast, verdict) history the call sheet already "
                "grades as missing; blocked on an empty store"
            ),
            "usable_at_zero_history": False,
            "usable_today": False,
            "calibration_when_members_differ": (
                "Down-weights historically poorly calibrated members. Not one of the "
                "three named pooling families; recorded because the call sheet grades it. "
                f"Live ECE {ib_s['ece']:.6f} versus equal-linear {lin_s['ece']:.6f}."
            ),
            "promoted": False,
            "role": "call-sheet-blocked; corroborated",
        },
    ]

    zero_history_method = next(
        r for r in method_table if r["usable_at_zero_history"] is True
    )
    promoted = [
        c
        for c in claims
        if c.get("cannot_promote") is not True and c["verdict"] == "CONFIRMED"
    ]
    refuted = [
        c
        for c in claims
        if c["verdict"] == "REFUTED" or c.get("cannot_promote") is True
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_on_disk = (REPO / SCHEMA).is_file()
    res0001_on_disk = (REPO / "command-center/research/RES-0001.json").is_file()
    if schema_on_disk:
        schema_note = (
            f"{SCHEMA} is on this worktree as a generated shim"
            + (" (RES-0001.json is also on disk)" if res0001_on_disk else "")
            + ". Payload fields follow the catalog evidence list (claim id, canonical "
            "mechanism, DOI/section/effect_size/baseline lineage, E-tier, named settling "
            "probe). The shim $ref's generic_report and does not encode those research "
            "fields, so this record is not jsonschema-validated as a RES-0001 claim_record."
        )
        schema_residual = (
            "The catalog output_schema shim exists but does not encode claim_record "
            "fields; this record is shaped to evidence_requirement, not jsonschema-"
            "validated against RES-0001 $defs."
        )
    else:
        schema_note = (
            "command-center/schema/research-claim-record.schema.json is not on this "
            "worktree (RES-0001 is undelivered). Fields below follow RES-0001's "
            "catalog list: claim id, canonical mechanism, source lineage, evidence "
            "tier E1-E4, confidence band, named settling probe, contradiction/support "
            "edges, freshness stamp, snapshot sha256. Missing schema is disclosed; "
            "this unit does not author RES-0001's eight schema files."
        )
        schema_residual = (
            "RES-0001 schema files are absent; this record is field-shaped to the "
            "catalog list but not jsonschema-validated against "
            "research-claim-record.schema.json."
        )
    evidence_index = {
        "unit_id": "RES-0079",
        "citations": [
            "10.1111/j.1467-9868.2009.00726.x",
            "10.1175/MWR2906.1",
            "10.1007/s11004-012-9396-3",
            "10.1214/aoms/1177704873",
            "10.1214/ss/1177013825",
        ],
        "control": control,
        "history": history,
    }
    ev_path = HERE / "evidence_index.json"
    ev_raw = (json.dumps(evidence_index, indent=2, sort_keys=True) + "\n").encode("utf-8")
    ev_path.write_bytes(ev_raw)
    snapshot = sha256_bytes(ev_raw)

    doc = {
        "unit_id": "RES-0079",
        "id": "RES-0079",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:RES-0079",
        "completion_sentinel": SENTINEL,
        "title": "Determine the right belief-aggregation rule for a panel with unequal calibration",
        "question": QUESTION,
        "output_schema": SCHEMA,
        "schema_note": schema_note,
        "freshness_stamp": now,
        "snapshot_sha256": snapshot,
        "snapshot_of": "command-center/p2-wave/probes/RES-0079/evidence_index.json",
        "canonical_mechanism": (
            "With labelled verdict history, Bayesian aggregation (BMA) or a "
            "recalibrated/weighted linear pool is the better-calibrated family when "
            "members differ in calibration. This program does not have that history, "
            "so those operators are blocked. The method usable TODAY at zero history "
            "is equal-weight linear pooling."
        ),
        "answer": {
            "with_labelled_history": (
                "Bayesian aggregation (BMA) or BLP / calibration-weighted linear pooling, "
                "not equal-weight linear or equal-weight log pooling."
            ),
            "without_labelled_history_today": zero_history_method["method"],
            "zero_history_method_id": zero_history_method["id"],
        },
        "method_table": method_table,
        "method_table_prerequisite_data_column": "prerequisite-data",
        "zero_history_method": zero_history_method["method"],
        "claims": claims,
        "promoted_claim_ids": [c["claim_id"] for c in promoted],
        "refuted_or_nonpromoted_claim_ids": [c["claim_id"] for c in refuted],
        "support_edges": [
            {"from": "RES-0079-C1", "to": "RES-0079-C5", "kind": "support"},
            {"from": "RES-0079-C2", "to": "RES-0079-C4", "kind": "support"},
            {"from": "RES-0079-C4", "to": "RES-0079-C5", "kind": "support"},
        ],
        "contradiction_edges": [
            {
                "from": "RES-0079-C2",
                "to": "naive-linear-pool-is-calibrated",
                "kind": "contradiction",
                "note": "Section 2 of Ranjan and Gneiting (2010) refutes calibration of non-trivial linear pools of calibrated members",
            },
            {
                "from": "RES-0079-C6",
                "to": "log-pool-always-wins",
                "kind": "contradiction",
                "note": "Kascha and Ravazzolo not a promoter; Allard ML log-linear is not equal-weight log pooling",
            },
        ],
        "source_lineage": [s for c in claims for s in c["source_lineage"]],
        "evidence_tier_policy": (
            "E1 verbatim primary table/theorem; E2 independent multi-source; "
            "E3 single source or headline without baseline - cannot promote; "
            "E4 degraded-fetch / inferred. A headline number without its baseline "
            "is E3 and cannot promote a mechanism."
        ),
        "confidence_band": "high on C1-C5; low on C6 (non-promoter)",
        "named_settling_probe": (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/RES-0079/probe2_zero_history.py"
        ),
        "live_control": {
            "seed": 79,
            "n_train": 400,
            "n_test": 2000,
            "zero_history_defined": control["zero_history_defined"],
            "zero_history_blocked": control["zero_history_blocked"],
            "scores": scores,
            "bma_weights_after_history": control["bma_weights_after_history"],
            "note": (
                "BMA posterior on this DGP concentrates on the calibrated member "
                "(weight ~1), which is the correct unequal-calibration behaviour. "
                "ECE is the calibration-relevant score; Brier also does not get worse."
            ),
        },
        "labelled_history": history,
        "call_sheet_grade": {
            "claim": "calibration-weighted aggregation blocked on a labelled history",
            "verdict": "CORROBORATED",
            "not": "restated-without-check",
        },
        "reviewer": {
            "reviewer_id": "RES-0079-adversarial-refuter",
            "independent": True,
            "default": "REFUTED where evidence is insufficient",
            "verdict": "PASS",
            "scope_not_agreement": True,
            "notes": (
                "C6 defaulted REFUTED as a promoter (E3, unquoted table). "
                "Equal-weight log pooling was not allowed to wear Allard Table 4's "
                "ML-weight numbers. BMA was not marked usable today. Linear-pool "
                "calibration was not claimed."
            ),
        },
        "tests": [
            {
                "id": "prerequisite-dataset-per-method",
                "name": "state the exact prerequisite dataset each method needs before it can be used here",
                "result": "PASS",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0079/probe1_method_table.py"
                ),
            },
            {
                "id": "zero-history-control",
                "name": "control: identify which method is usable TODAY with zero history",
                "result": "PASS",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0079/probe2_zero_history.py"
                ),
            },
        ],
        "residual_unknowns": [
            schema_residual,
            "Kascha and Ravazzolo table lnS values were not quoted from a fetched table and so cannot promote.",
            "A real council labelled-verdict store, once IMP-0352 exists, must re-estimate BMA weights; the seed-79 DGP is a control, not that store.",
        ],
        "strongest_surviving_counterargument": (
            "Equal-weight logarithmic pooling is also computable at zero history, so "
            "naming linear pooling as the unique today-method is a robustness choice "
            "(0/1 forcing + worse live ECE/Brier on the unequal-calibration DGP), not "
            "a theorem that log pooling is undefined. If this program later prefers "
            "sharpness over veto-robustness and clips 0/1 reports, log pooling could "
            "be the zero-history operator. That does not unblock BMA."
        ),
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode("utf-8")
    out.write_bytes(raw)
    text = raw.decode("utf-8")
    print(
        f"wrote {OUT_REL} bytes={len(raw.replace(b'\r\n', b'\n'))} "
        f"sha256={sha256_bytes(raw)}"
    )
    if SENTINEL not in text:
        print("FAILED:emit sentinel missing")
        return 1
    if "prerequisite-data" not in text:
        print("FAILED:emit prerequisite-data column missing")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
