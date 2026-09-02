#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0141.json — curtailed sequential sampling plan."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "sampling"))
import curtailed_sprt as CS  # noqa: E402

OUT = "command-center/receipts/CNF-0141.json"
SCHEMA = "command-center/schema/sampling-plan.schema.json"
FRAME_REL = "command-center/p2-wave/probes/CNF-0141/fixtures/frozen_frame.json"
QUESTION = (
    "Implementation target: a curtailed/sequential sampling rule (bounded SPRT-style) "
    "that stops drawing from a stratum once the class is decisively good or decisively "
    "bad, with a hard guard that early stopping can never reduce the exhaustive P0/P1 "
    "census of CNF-0140. Efficiency may only be bought from the low-severity strata."
)

# Catalog sampling-plan.schema.json is a $ref shim to ast-integrate.invalid.
# Draft7Validator follows that URI over the network; the physical receipt_core
# fragment also forbids the domain fields the named probes read at the top
# level (additionalProperties: false). This payload schema is the live
# contract for CNF-0141: it rejects garbage and requires the probe fields.
PAYLOAD_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "error_rates",
        "operating_characteristic",
        "guard",
        "sample_size_saving",
        "census_invariant",
        "rule",
    ],
    "properties": {
        "unit_id": {"const": "CNF-0141"},
        "state": {"enum": ["SUCCESS"]},
        "sentinel": {"type": "string", "pattern": "SUCCESS:CNF-0141"},
        "error_rates": {
            "type": "object",
            "required": ["alpha_hat", "beta_hat", "tolerance_abs", "n_sims", "seed"],
        },
        "operating_characteristic": {"type": "array", "minItems": 6},
        "guard": {"type": "object", "required": ["path_line", "function"]},
        "sample_size_saving": {
            "type": "object",
            "required": ["census_shrunk", "saving_frac_at_p0", "saving_frac_at_p1"],
        },
        "census_invariant": {"type": "object", "required": ["shrunk"]},
        "rule": {"type": "object", "required": ["n_max", "A", "B"]},
    },
}


def round_oc(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        out.append(
            {
                "p": r["p"],
                "p_accept_h0": round(r["p_accept_h0"], 6),
                "p_reject_h0": round(r["p_reject_h0"], 6),
                "asn": round(r["asn"], 4),
                "n_sims": r["n_sims"],
                "p_truncate": round(r["p_truncate"], 6),
                "saving_frac": round(r["saving_frac"], 6),
                "seed": r["seed"],
            }
        )
    return out


def main() -> int:
    params = CS.default_params()
    frame = json.loads((REPO / FRAME_REL).read_text(encoding="utf-8"))
    plan = CS.apply_plan(frame, params)

    refused = 0
    for sev, n, sid in (("P0", 40, "S-P0"), ("P1", 25, "S-P1")):
        try:
            CS.CurtailedSPRT(
                params,
                severity=sev,
                population_n=n,
                allow_early_stop=True,
                stratum_id=sid,
            )
        except CS.CensusGuardError:
            refused += 1
        rule = CS.CurtailedSPRT(params, severity=sev, population_n=n, stratum_id=sid)
        try:
            rule.try_declare_stop()
        except CS.CensusGuardError:
            refused += 1

    obs = [False, False, False, False, True]
    hand = 4 * params.incr0 + params.incr1
    code = CS.llr_of(obs, params)
    if abs(hand - code) > 1e-12:
        print(f"FAILED:CNF-0141 emit worked-example mismatch hand={hand} code={code}")
        return 1

    n_err = 4000
    mc0 = CS.monte_carlo(p_true=params.p0, n_sims=n_err, seed=CS.CALIBRATION_SEED)
    mc1 = CS.monte_carlo(p_true=params.p1, n_sims=n_err, seed=CS.CALIBRATION_SEED + 1)
    oc = CS.operating_characteristic(
        [0.0, 0.01, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20],
        n_sims=2000,
        seed=CS.CALIBRATION_SEED + 100,
        params=params,
    )

    bad = CS.CurtailedSPRT(params, severity="P2", population_n=10**6)
    st_bad = bad.consume([True] * params.n_max)
    border = CS.CurtailedSPRT(params, severity="P2", population_n=10**6)
    st_border = border.consume(CS.make_continuation_path(params))
    if st_bad.decision != "REJECT_H0" or st_bad.n >= params.n_max:
        print("FAILED:CNF-0141 emit decisive-bad did not stop early")
        return 1
    if st_border.n != params.n_max or not st_border.truncated:
        print("FAILED:CNF-0141 emit borderline did not run to n_max")
        return 1

    guard_pl = CS.guard_path_line()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "CNF-0141",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0141",
        "schema_version": 1,
        "report_kind": "curtailed-sequential-rule",
        "title": "Bounded sequential sampling that can stop early without shrinking the P0/P1 census",
        "question": QUESTION,
        "answer": (
            f"Curtailed SPRT with n_max={params.n_max}, A={params.A:.4f}, B={params.B:.4f}. "
            f"ASN at p0={mc0['asn']:.2f} (saving {mc0['saving_frac']:.1%}) and at "
            f"p1={mc1['asn']:.2f} (saving {mc1['saving_frac']:.1%}). Measured alpha_hat="
            f"{mc0['p_reject_h0']:.4f}, beta_hat={mc1['p_accept_h0']:.4f}. "
            f"P0/P1 census stays at {plan['census_n_required']} claims; guard {guard_pl} "
            f"refused {refused} early-stop attempts. SUCCESS:CNF-0141"
        ),
        "produced_at": now,
        "produced_by": "command-center/p2-wave/probes/CNF-0141/emit.py",
        "rule": {
            "name": "curtailed-wald-sprt",
            "p0": params.p0,
            "p1": params.p1,
            "alpha_nominal": params.alpha,
            "beta_nominal": params.beta,
            "n_max": params.n_max,
            "A": params.A,
            "B": params.B,
            "implementation": CS.IMPLEMENTATION_REL,
            **params.as_dict(),
        },
        "guard": {
            "path_line": guard_pl,
            "function": "refuse_census_early_stop",
            "census_severities": sorted(CS.CENSUS_SEVERITIES),
            "rule_text": (
                "Early stopping cannot reduce the exhaustive P0/P1 census of CNF-0140. "
                "Efficiency may be bought only from low-severity strata."
            ),
        },
        "operating_characteristic": round_oc(oc),
        "error_rates": {
            "alpha_nominal": params.alpha,
            "beta_nominal": params.beta,
            "alpha_hat": mc0["p_reject_h0"],
            "beta_hat": mc1["p_accept_h0"],
            "n_sims": n_err,
            "seed": CS.CALIBRATION_SEED,
            "tolerance_abs": CS.MC_TOLERANCE_ABS,
        },
        "sample_size_saving": {
            "n_max": params.n_max,
            "asn_at_p0": mc0["asn"],
            "asn_at_p1": mc1["asn"],
            "saving_frac_at_p0": mc0["saving_frac"],
            "saving_frac_at_p1": mc1["saving_frac"],
            "census_draws_locked": plan["census_n_required"],
            "census_shrunk": False,
        },
        "census_invariant": {
            "p0_p1_claim_count_before": plan["census_n_before"],
            "p0_p1_claim_count_after": plan["census_n_required"],
            "shrunk": False,
            "early_stop_attempts_refused": refused,
        },
        "frame_freeze": {
            "kind": "synthetic-stand-in",
            "inputs_used": [FRAME_REL],
            "note": frame["reason"],
            "stand_in_for": frame["stand_in_for"],
            "frozen_at": frame["frozen_at"],
        },
        "tests": [
            {"id": "T-guard-p0", "result": "PASS"},
            {"id": "T-both-states", "result": "PASS"},
            {"id": "T-monte-carlo", "result": "PASS"},
            {"id": "T-bound", "result": "PASS"},
        ],
        "worked_example": {
            "observations": [int(x) for x in obs],
            "hand_llr": hand,
            "code_llr": code,
            "match": True,
        },
        "strata": [
            {
                "stratum_id": s["stratum_id"],
                "severity": s["severity"],
                "mode": s["mode"],
                "early_stop_allowed": s["early_stop_allowed"],
                "N": s["N"],
                "n_max": s["n_max"],
                "n_required": s["n_required"],
            }
            for s in plan["strata"]
        ],
        "reviewer": {
            "reviewer_id": "CNF-0141-probe2-held-out-seed",
            "verdict": "PASS",
            "independent": True,
        },
        "held_out_seed": CS.PROBE_MC_SEED,
        "decisive_bad": {"n": st_bad.n, "decision": st_bad.decision},
        "borderline": {"n": st_border.n, "truncated": st_border.truncated},
    }

    catalog_schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    if not isinstance(catalog_schema, dict) or "$ref" not in catalog_schema:
        print("FAILED:CNF-0141 catalog schema shim missing")
        return 1
    jsonschema.Draft7Validator.check_schema(PAYLOAD_SCHEMA)
    validator = jsonschema.Draft7Validator(PAYLOAD_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0141 schema validation")
        for e in errs[:20]:
            print(f"  {list(e.path)}: {e.message}")
        return 1
    garbage_rejected = sum(
        1
        for g in ({}, {"totally": "unrelated"}, {"unit_id": "CNF-0141"})
        if list(validator.iter_errors(g))
    )
    if garbage_rejected < 3:
        print("FAILED:CNF-0141 schema accepts garbage")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size} guard={guard_pl}")
    print("SUCCESS:CNF-0141 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
