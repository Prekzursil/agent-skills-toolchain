#!/usr/bin/env python3
"""WFA-0114 head-to-head scoring rubric (re-materialized 2026-10-26).

Computes - never judges - the four named components (correctness, coverage,
recovery, usability) from recorded run data, scores matched-intersection
head-to-head arms, operationalises material complementarity as a measured
unique-solve coverage delta, removes (never down-weights) uncomputable
components, and enforces the pre-certification freeze. Re-authored by the
shard22 wave-4 builder after the prior builder lost its probe dir; the
formulas are the ones recorded in WFA-0114-headtohead-scoring-rubric.json.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "recorded_runs.json"

AGREEMENT_FLOOR = 0.75
COMPLEMENT_DELTA_FLOOR = 0.10
NAMED_COMPONENTS = ["correctness", "coverage", "recovery", "usability"]
HUMAN_COMPONENT = "human_usability_rating"

FORMULAS = {
    "correctness": (
        "n_oracle_pass / n_matched, where n_matched is the matched-intersection "
        "size and an unattempted matched case counts as not-pass (failed arm "
        "never dropped from the comparison)."
    ),
    "coverage": (
        "n_attempted / n_matched on the same matched intersection. Distinct "
        "from correctness: an arm can attempt every case and still fail them."
    ),
    "recovery": (
        "n_recovered / n_first_attempt_failures on matched cases, where "
        "recovered means first_attempt_oracle != pass and retry_oracle == pass. "
        "Uncomputable when n_first_attempt_failures == 0."
    ),
    "usability": (
        "mean over attempted matched cases of "
        "1 - min(1, (checkpoints + abort + budget_exhausted) / 4). Uncomputable "
        "when no matched case was attempted."
    ),
    "human_usability_rating": (
        "mean of two raters 0-4 scores / 4, retained only when the Cohen kappa "
        "on the paired ratings is >= 0.75; otherwise REMOVED, not down-weighted."
    ),
    "material_complementarity": (
        "|solved(fusion) minus union(solved(sources))| / |corpus|. Material when "
        "delta >= 0.10 and at least one unique solve. Unique solves are NEVER "
        "added to the head-to-head composite."
    ),
}


class FreezeViolation(Exception):
    """A certification was attempted against an unfrozen or mutated rubric."""


def freeze_payload() -> dict:
    return {
        "agreement_floor": AGREEMENT_FLOOR,
        "asymmetric_cases_folded_into_head_to_head": False,
        "complement_delta_floor": COMPLEMENT_DELTA_FLOOR,
        "formulas": FORMULAS,
        "human_component": HUMAN_COMPONENT,
        "named_computed_components": NAMED_COMPONENTS,
        "stage_count_is_not_a_component": True,
        "uncomputable_policy": "remove_not_downweight",
        "weight_policy": "equal_among_retained_this_comparison",
    }


def freeze_digest() -> str:
    canon = json.dumps(freeze_payload(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def cohen_kappa(r1, r2):
    n = len(r1)
    cats = sorted(set(r1) | set(r2))
    po = sum(1 for a, b in zip(r1, r2) if a == b) / n
    pe = sum(
        (sum(1 for x in r1 if x == c) / n) * (sum(1 for x in r2 if x == c) / n)
        for c in cats
    )
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def inter_rater_status(fixture: dict) -> dict:
    ir = fixture["inter_rater"]
    out = {}
    for key in ("high_agreement", "low_agreement"):
        r1, r2 = ir[key]["rater_1"], ir[key]["rater_2"]
        kappa = cohen_kappa(r1, r2)
        all_scores = r1 + r2
        value = (sum(all_scores) / len(all_scores)) / 4
        retained = kappa >= AGREEMENT_FLOOR
        row = {
            "id": HUMAN_COMPONENT,
            "kappa": kappa,
            "value": value,
            "agreement_floor": AGREEMENT_FLOOR,
            "status": "retained" if retained else "removed",
        }
        if not retained:
            row["reason"] = (
                "cohen_kappa=%.4f below floor %.2f; removed not weighted down"
                % (kappa, AGREEMENT_FLOOR)
            )
        out[key] = row
    return out


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def arm_components(arm: dict, matched: list) -> dict:
    n_matched = len(matched)
    attempted = [c for c in matched if arm[c]["attempted"]]
    n_attempted = len(attempted)

    def final_pass(c):
        a = arm[c]
        return a["attempted"] and (
            a["first_attempt_oracle"] == "pass" or a["retry_oracle"] == "pass"
        )

    n_pass = sum(1 for c in matched if final_pass(c))
    comps = {
        "correctness": {
            "id": "correctness",
            "formula": FORMULAS["correctness"],
            "n_pass": n_pass,
            "n_matched": n_matched,
            "value": n_pass / n_matched,
            "status": "retained",
        },
        "coverage": {
            "id": "coverage",
            "formula": FORMULAS["coverage"],
            "n_attempted": n_attempted,
            "n_matched": n_matched,
            "value": n_attempted / n_matched,
            "status": "retained",
        },
    }
    first_fails = [
        c
        for c in matched
        if arm[c]["attempted"] and arm[c]["first_attempt_oracle"] != "pass"
    ]
    n_recoverable = len(first_fails)
    if n_recoverable == 0:
        comps["recovery"] = {
            "id": "recovery",
            "formula": FORMULAS["recovery"],
            "status": "removed",
            "reason": "no recoverable first-attempt failures on matched cases",
        }
    else:
        n_recovered = sum(1 for c in first_fails if arm[c]["retry_oracle"] == "pass")
        comps["recovery"] = {
            "id": "recovery",
            "formula": FORMULAS["recovery"],
            "n_recovered": n_recovered,
            "n_recoverable": n_recoverable,
            "value": n_recovered / n_recoverable,
            "status": "retained",
        }
    if n_attempted == 0:
        comps["usability"] = {
            "id": "usability",
            "formula": FORMULAS["usability"],
            "status": "removed",
            "reason": (
                "no attempted matched cases; telemetry ratio has empty denominator"
            ),
        }
    else:
        terms = [
            1 - min(1, (arm[c]["checkpoints"] + arm[c]["abort"]
                        + arm[c]["budget_exhausted"]) / 4)
            for c in attempted
        ]
        comps["usability"] = {
            "id": "usability",
            "formula": FORMULAS["usability"],
            "n_attempted": n_attempted,
            "value": sum(terms) / len(terms),
            "status": "retained",
        }
    return comps


def composite(components: dict, retained_ids: list, missing_as_zero: bool = False) -> float:
    if missing_as_zero:
        vals = [components[i].get("value", 0.0) for i in retained_ids]
    else:
        vals = [components[i]["value"] for i in retained_ids]
    return sum(vals) / len(vals)


def score_scenario(scen: dict, matched: list, corpus: list) -> dict:
    fusion = arm_components(scen["fusion"], matched)
    retained = [i for i in NAMED_COMPONENTS if fusion[i]["status"] == "retained"]
    fusion_comp = composite(fusion, retained) if retained else 0.0
    zero_filled = composite(fusion, NAMED_COMPONENTS, missing_as_zero=True)
    src_comps = {}
    for src in ("source_a", "source_b"):
        comps = arm_components(scen[src], matched)
        src_ret = [i for i in NAMED_COMPONENTS if comps[i]["status"] == "retained"]
        src_comps[src] = {
            "components": comps,
            "retained": src_ret,
            "value": composite(comps, src_ret) if src_ret else 0.0,
        }
    both = [
        i
        for i in NAMED_COMPONENTS
        if fusion[i]["status"] == "retained"
        and all(i in v["retained"] for v in src_comps.values())
    ]
    head_to_head = {}
    for src in ("source_a", "source_b"):
        # fair head-to-head: every arm is scored on the SAME comparison
        # component set (the components retained on all sides)
        head_to_head[src] = composite(src_comps[src]["components"], both) if both else 0.0
    best_source = max(head_to_head.values()) if head_to_head else 0.0
    hh_fusion = composite(fusion, both) if both else 0.0
    outperforms = bool(both) and hh_fusion > best_source

    def solved(arm, extra):
        out = set(extra or [])
        for cid in matched:
            a = arm[cid]
            if a["attempted"] and (
                a["first_attempt_oracle"] == "pass" or a["retry_oracle"] == "pass"
            ):
                out.add(cid)
        return out

    solved_fusion = solved(scen["fusion"], scen.get("fusion_extra_solves"))
    solved_sources = set()
    for src in ("source_a", "source_b"):
        solved_sources |= solved(scen[src], scen.get("source_extra_solves"))
    n_corpus = len(corpus)
    n_unique = len(solved_fusion - solved_sources)
    delta = n_unique / n_corpus
    material = delta >= COMPLEMENT_DELTA_FLOOR and n_unique >= 1
    if outperforms:
        decision = "OUTPERFORMS"
    elif material:
        decision = "MATERIALLY_COMPLEMENTARY"
    else:
        decision = "REJECT"
    if outperforms:
        reason = "fusion comparison-composite strictly exceeds every source"
    elif material:
        reason = (
            "fusion does not outperform on head-to-head composite; "
            "unique coverage delta %.1f >= 0.1" % delta
        )
    else:
        reason = (
            "neither head-to-head outperformance nor material coverage delta; "
            "stage count is not a qualifying signal"
        )
    return {
        "fusion_named": [fusion[i] for i in NAMED_COMPONENTS],
        "fusion_arm_composite": {
            "retained_ids": retained,
            "n_retained": len(retained),
            "removed_ids": [i for i in NAMED_COMPONENTS if i not in retained],
            "n_removed": len(NAMED_COMPONENTS) - len(retained),
            "value": fusion_comp,
            "uncomputable_policy": "remove_not_downweight",
            "weight_policy": "equal_among_retained_this_comparison",
        },
        "fusion_zero_filled_named_composite": zero_filled,
        "fusion_comparison_composite": {
            "retained_ids": both,
            "value": hh_fusion,
            "weight_policy": "equal_among_retained_this_comparison",
        },
        "comparison_component_ids": both,
        "sources": [
            {
                "arm_id": src,
                "comparison_composite": {
                    "retained_ids": both,
                    "value": head_to_head[src],
                    "weight_policy": "equal_among_retained_this_comparison",
                },
                "stages": scen["stages"][src],
            }
            for src in ("source_a", "source_b")
        ],
        "best_source_comparison_composite": best_source,
        "complement": {
            "formula": FORMULAS["material_complementarity"],
            "floor": COMPLEMENT_DELTA_FLOOR,
            "delta": delta,
            "n_corpus": n_corpus,
            "n_unique": n_unique,
            "unique_case_ids": sorted(solved_fusion - solved_sources),
            "material": material,
            "folded_into_head_to_head": False,
        },
        "fusion_stages": scen["stages"]["fusion"],
        "outperforms": outperforms,
        "materially_complementary": material,
        "decision": decision,
        "reason": reason,
    }


def certify(frozen: bool, frozen_digest: str, live_digest: str) -> dict:
    if not frozen:
        return {"decision": "REFUSED", "reason": "rubric not frozen before certification"}
    if frozen_digest != live_digest:
        return {"decision": "REFUSED", "reason": "post-hoc formula change after freeze"}
    return {"decision": "CERTIFIED", "reason": "frozen rubric digest matches live"}


def main() -> int:
    fixture = load_fixture()
    out = {}
    for name, scen in fixture["scenarios"].items():
        out[name] = score_scenario(
            scen, fixture["matched_intersection"], fixture["corpus_ids"]
        )
    out["inter_rater"] = inter_rater_status(fixture)
    out["freeze_digest"] = freeze_digest()
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
