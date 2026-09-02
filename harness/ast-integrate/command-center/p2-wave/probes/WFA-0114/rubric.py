#!/usr/bin/env python3
"""Head-to-head scoring rubric for fused vs source workflows (WFA-0114).

Every named component is a formula over recorded run fields, not a judgment.
A component that cannot be computed, or that fails the inter-rater floor, is
REMOVED from the composite — it is not kept at weight zero. Material
complementarity is a coverage delta on the unique-solve set and is never
folded into the head-to-head composite. Certification refuses unless the
rubric spec is frozen and the live spec hash still matches.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from typing import Any, Iterable

NAMED_COMPUTED = ("correctness", "coverage", "recovery", "usability")
HUMAN_COMPONENT = "human_usability_rating"
AGREEMENT_FLOOR = 0.75
COMPLEMENT_DELTA_FLOOR = 0.10
FRICTION_DENOM = 4.0

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
        "1 - min(1, (checkpoints + abort + budget_exhausted) / 4). "
        "Uncomputable when no matched case was attempted."
    ),
    "human_usability_rating": (
        "mean of two raters' 0-4 scores / 4, retained only when Cohen's kappa "
        "on the paired ratings is >= 0.75; otherwise REMOVED, not down-weighted."
    ),
    "material_complementarity": (
        "|solved(fusion) minus union(solved(sources))| / |corpus|. "
        "Material when delta >= 0.10 and at least one unique solve. "
        "Unique solves are NEVER added to the head-to-head composite."
    ),
}

WEIGHT_POLICY = "equal_among_retained_this_comparison"
UNCOMPUTABLE_POLICY = "remove_not_downweight"


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def spec_digest(formulas: dict[str, str] | None = None) -> str:
    payload = {
        "named_computed_components": list(NAMED_COMPUTED),
        "formulas": formulas if formulas is not None else dict(FORMULAS),
        "weight_policy": WEIGHT_POLICY,
        "uncomputable_policy": UNCOMPUTABLE_POLICY,
        "human_component": {
            "id": HUMAN_COMPONENT,
            "agreement_metric": "cohen_kappa",
            "agreement_floor": AGREEMENT_FLOOR,
            "below_floor_policy": "remove_not_downweight",
        },
        "complementarity": {
            "metric": "unique_solved_fraction_of_corpus",
            "formula": FORMULAS["material_complementarity"],
            "floor": COMPLEMENT_DELTA_FLOOR,
            "folded_into_head_to_head": False,
            "stage_count_qualifies": False,
        },
    }
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def cohen_kappa(rater_a: Iterable[int], rater_b: Iterable[int]) -> float:
    a = list(rater_a)
    b = list(rater_b)
    if len(a) != len(b) or not a:
        raise ValueError("raters must be non-empty and equal length")
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    cats = sorted(set(a) | set(b))
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[k] / n) * (cb[k] / n) for k in cats)
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return (po - pe) / (1.0 - pe)


def _run(arm: dict, case_id: str) -> dict:
    return dict((arm.get("runs") or {}).get(case_id) or {})


def _matched(arm: dict, matched_ids: list[str]) -> list[str]:
    return list(matched_ids)


def component_correctness(arm: dict, matched_ids: list[str]) -> dict:
    ids = _matched(arm, matched_ids)
    if not ids:
        return {
            "id": "correctness",
            "status": "removed",
            "reason": "empty matched intersection",
            "formula": FORMULAS["correctness"],
        }
    n_pass = 0
    for cid in ids:
        run = _run(arm, cid)
        oracle = run.get("oracle") or run.get("retry_oracle")
        if oracle == "pass":
            n_pass += 1
    value = n_pass / len(ids)
    return {
        "id": "correctness",
        "status": "retained",
        "value": value,
        "n_pass": n_pass,
        "n_matched": len(ids),
        "formula": FORMULAS["correctness"],
    }


def component_coverage(arm: dict, matched_ids: list[str]) -> dict:
    ids = _matched(arm, matched_ids)
    if not ids:
        return {
            "id": "coverage",
            "status": "removed",
            "reason": "empty matched intersection",
            "formula": FORMULAS["coverage"],
        }
    n_attempted = 0
    for cid in ids:
        run = _run(arm, cid)
        if run.get("attempted") is True:
            n_attempted += 1
    return {
        "id": "coverage",
        "status": "retained",
        "value": n_attempted / len(ids),
        "n_attempted": n_attempted,
        "n_matched": len(ids),
        "formula": FORMULAS["coverage"],
    }


def component_recovery(arm: dict, matched_ids: list[str]) -> dict:
    recoverable: list[str] = []
    recovered: list[str] = []
    for cid in matched_ids:
        run = _run(arm, cid)
        if run.get("attempted") is not True:
            continue
        first = run.get("first_attempt_oracle") or run.get("first_oracle")
        if first == "pass":
            continue
        if first in {"fail", "error", "timeout"}:
            recoverable.append(cid)
            if run.get("retry_oracle") == "pass":
                recovered.append(cid)
    if not recoverable:
        return {
            "id": "recovery",
            "status": "removed",
            "reason": "no recoverable first-attempt failures on matched cases",
            "formula": FORMULAS["recovery"],
            "n_recoverable": 0,
            "n_recovered": 0,
        }
    return {
        "id": "recovery",
        "status": "retained",
        "value": len(recovered) / len(recoverable),
        "n_recovered": len(recovered),
        "n_recoverable": len(recoverable),
        "recovered_case_ids": recovered,
        "formula": FORMULAS["recovery"],
    }


def component_usability(arm: dict, matched_ids: list[str]) -> dict:
    scores: list[float] = []
    for cid in matched_ids:
        run = _run(arm, cid)
        if run.get("attempted") is not True:
            continue
        friction = (
            int(run.get("checkpoints") or 0)
            + int(bool(run.get("abort")))
            + int(bool(run.get("budget_exhausted")))
        )
        scores.append(1.0 - min(1.0, friction / FRICTION_DENOM))
    if not scores:
        return {
            "id": "usability",
            "status": "removed",
            "reason": "no attempted matched cases; telemetry ratio has empty denominator",
            "formula": FORMULAS["usability"],
        }
    return {
        "id": "usability",
        "status": "retained",
        "value": sum(scores) / len(scores),
        "n_attempted": len(scores),
        "formula": FORMULAS["usability"],
    }


def component_human(ratings_a: list[int] | None, ratings_b: list[int] | None) -> dict:
    formula = FORMULAS["human_usability_rating"]
    if not ratings_a or not ratings_b:
        return {
            "id": HUMAN_COMPONENT,
            "status": "removed",
            "reason": "second rater missing; agreement cannot be computed",
            "formula": formula,
        }
    kappa = cohen_kappa(ratings_a, ratings_b)
    if kappa < AGREEMENT_FLOOR:
        return {
            "id": HUMAN_COMPONENT,
            "status": "removed",
            "reason": (
                f"cohen_kappa={kappa:.4f} below floor {AGREEMENT_FLOOR}; "
                "removed not weighted down"
            ),
            "kappa": kappa,
            "agreement_floor": AGREEMENT_FLOOR,
            "formula": formula,
        }
    paired = [(x + y) / 2.0 / 4.0 for x, y in zip(ratings_a, ratings_b)]
    return {
        "id": HUMAN_COMPONENT,
        "status": "retained",
        "value": sum(paired) / len(paired),
        "kappa": kappa,
        "agreement_floor": AGREEMENT_FLOOR,
        "formula": formula,
    }


def score_named(arm: dict, matched_ids: list[str]) -> list[dict]:
    return [
        component_correctness(arm, matched_ids),
        component_coverage(arm, matched_ids),
        component_recovery(arm, matched_ids),
        component_usability(arm, matched_ids),
    ]


def composite_of(components: list[dict]) -> dict:
    retained = [c for c in components if c.get("status") == "retained"]
    removed = [c for c in components if c.get("status") == "removed"]
    if not retained:
        return {
            "value": None,
            "n_retained": 0,
            "n_removed": len(removed),
            "weight_policy": WEIGHT_POLICY,
            "uncomputable_policy": UNCOMPUTABLE_POLICY,
            "retained_ids": [],
            "removed_ids": [c["id"] for c in removed],
        }
    value = sum(float(c["value"]) for c in retained) / len(retained)
    return {
        "value": value,
        "n_retained": len(retained),
        "n_removed": len(removed),
        "weight_policy": WEIGHT_POLICY,
        "uncomputable_policy": UNCOMPUTABLE_POLICY,
        "retained_ids": [c["id"] for c in retained],
        "removed_ids": [c["id"] for c in removed],
    }


def composite_if_zero_filled(named: list[dict]) -> float:
    """What the composite would be if removed components were kept at weight and value 0."""
    vals: list[float] = []
    for cid in NAMED_COMPUTED:
        hit = next((c for c in named if c.get("id") == cid), None)
        if hit and hit.get("status") == "retained":
            vals.append(float(hit["value"]))
        else:
            vals.append(0.0)
    return sum(vals) / len(vals)


def solved_ids(arm: dict, corpus_ids: list[str]) -> set[str]:
    out: set[str] = set()
    for cid in corpus_ids:
        run = _run(arm, cid)
        if run.get("oracle") == "pass":
            out.add(cid)
    return out


def coverage_delta(
    fusion: dict, sources: list[dict], corpus_ids: list[str]
) -> dict:
    fusion_solved = solved_ids(fusion, corpus_ids)
    union: set[str] = set()
    for src in sources:
        union |= solved_ids(src, corpus_ids)
    unique = sorted(fusion_solved - union)
    n = len(corpus_ids)
    delta = (len(unique) / n) if n else None
    material = (
        delta is not None
        and delta >= COMPLEMENT_DELTA_FLOOR
        and len(unique) >= 1
    )
    return {
        "unique_case_ids": unique,
        "delta": delta,
        "n_unique": len(unique),
        "n_corpus": n,
        "floor": COMPLEMENT_DELTA_FLOOR,
        "material": material,
        "folded_into_head_to_head": False,
        "formula": FORMULAS["material_complementarity"],
    }


def comparison_components(arm_named: list[list[dict]]) -> list[str]:
    """Retain a named component only if every arm can compute it."""
    keep: list[str] = []
    for cid in NAMED_COMPUTED:
        statuses = []
        for named in arm_named:
            hit = next((c for c in named if c.get("id") == cid), None)
            statuses.append(hit.get("status") if hit else "removed")
        if statuses and all(s == "retained" for s in statuses):
            keep.append(cid)
    return keep


def comparison_composite(named: list[dict], keep_ids: list[str]) -> dict:
    retained = [
        c
        for c in named
        if c.get("id") in keep_ids and c.get("status") == "retained"
    ]
    if not retained:
        return {
            "value": None,
            "retained_ids": [],
            "weight_policy": WEIGHT_POLICY,
        }
    return {
        "value": sum(float(c["value"]) for c in retained) / len(retained),
        "retained_ids": [c["id"] for c in retained],
        "weight_policy": WEIGHT_POLICY,
    }


class HeadToHeadRubric:
    def __init__(self, formulas: dict[str, str] | None = None) -> None:
        self.formulas = dict(formulas or FORMULAS)
        self.frozen = False
        self.freeze_hash: str | None = None
        self.frozen_at: str | None = None

    def live_digest(self) -> str:
        return spec_digest(self.formulas)

    def freeze(self, at_iso: str) -> str:
        self.freeze_hash = self.live_digest()
        self.frozen = True
        self.frozen_at = at_iso
        return self.freeze_hash

    def mutate_formula(self, name: str, text: str) -> None:
        self.formulas[name] = text

    def freeze_ok(self) -> tuple[bool, str]:
        if not self.frozen or not self.freeze_hash:
            return False, "rubric not frozen before certification"
        if self.live_digest() != self.freeze_hash:
            return False, "post-hoc formula change after freeze"
        return True, "ok"

    def score_arm(
        self,
        arm: dict,
        matched_ids: list[str],
        ratings_a: list[int] | None = None,
        ratings_b: list[int] | None = None,
        include_human: bool = False,
    ) -> dict:
        named = score_named(arm, matched_ids)
        human = None
        components = list(named)
        if include_human:
            human = component_human(ratings_a, ratings_b)
            components.append(human)
        arm_comp = composite_of(components)
        zeroed = composite_if_zero_filled(named)
        return {
            "arm_id": arm.get("id"),
            "stages": arm.get("stages"),
            "named": named,
            "human": human,
            "components": components,
            "arm_composite": arm_comp,
            "zero_filled_named_composite": zeroed,
            "removal_differs_from_zero_fill": (
                arm_comp["value"] is not None
                and abs(arm_comp["value"] - zeroed) > 1e-12
                and arm_comp["n_removed"] > 0
                and any(c["id"] in NAMED_COMPUTED for c in components if c["status"] == "removed")
            ),
        }

    def decide(
        self,
        fusion: dict,
        sources: list[dict],
        matched_ids: list[str],
        corpus_ids: list[str],
    ) -> dict:
        ok, reason = self.freeze_ok()
        if not ok:
            return {
                "decision": "REFUSED",
                "reason": reason,
                "frozen": self.frozen,
                "freeze_hash": self.freeze_hash,
                "live_digest": self.live_digest(),
            }
        fusion_scored = self.score_arm(fusion, matched_ids)
        source_scored = [self.score_arm(s, matched_ids) for s in sources]
        keep = comparison_components(
            [fusion_scored["named"]] + [s["named"] for s in source_scored]
        )
        fusion_cmp = comparison_composite(fusion_scored["named"], keep)
        source_cmps = [
            comparison_composite(s["named"], keep) for s in source_scored
        ]
        source_vals = [c["value"] for c in source_cmps if c["value"] is not None]
        complement = coverage_delta(fusion, sources, corpus_ids)
        fusion_val = fusion_cmp["value"]
        best_source = max(source_vals) if source_vals else None
        outperforms = (
            fusion_val is not None
            and best_source is not None
            and fusion_val > best_source
        )
        if outperforms:
            decision = "OUTPERFORMS"
            why = "fusion comparison-composite strictly exceeds every source"
        elif complement["material"]:
            decision = "MATERIALLY_COMPLEMENTARY"
            why = (
                "fusion does not outperform on head-to-head composite; unique "
                f"coverage delta {complement['delta']} >= {COMPLEMENT_DELTA_FLOOR}"
            )
        else:
            decision = "REJECT"
            why = (
                "neither head-to-head outperformance nor material coverage delta; "
                "stage count is not a qualifying signal"
            )
        return {
            "decision": decision,
            "reason": why,
            "frozen": True,
            "freeze_hash": self.freeze_hash,
            "comparison_component_ids": keep,
            "fusion": {
                "arm_id": fusion.get("id"),
                "stages": fusion.get("stages"),
                "arm_composite": fusion_scored["arm_composite"],
                "comparison_composite": fusion_cmp,
                "named": fusion_scored["named"],
                "zero_filled_named_composite": fusion_scored["zero_filled_named_composite"],
                "removal_differs_from_zero_fill": fusion_scored["removal_differs_from_zero_fill"],
            },
            "sources": [
                {
                    "arm_id": s.get("id"),
                    "stages": s.get("stages"),
                    "arm_composite": ss["arm_composite"],
                    "comparison_composite": sc,
                    "named": ss["named"],
                }
                for s, ss, sc in zip(sources, source_scored, source_cmps)
            ],
            "best_source_comparison_composite": best_source,
            "outperforms": outperforms,
            "materially_complementary": complement["material"],
            "complement": complement,
        }


def load_fixture(path: Any) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
