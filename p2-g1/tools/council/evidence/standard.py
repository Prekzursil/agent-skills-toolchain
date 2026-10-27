"""Evidence-standard tier enforcement (IMP-0365)."""
from __future__ import annotations

import json
from pathlib import Path

CLASSIFIER_INPUT_FIELD = "source.type"
DECLARED_FLOORS = (
    "anecdote",
    "cited-source",
    "replicated-study",
    "peer-reviewed-only",
    "executable-proof-only",
)
_TIER_RANK = {name: i for i, name in enumerate(DECLARED_FLOORS)}
_TYPE_TO_TIER = {
    "anecdote": "anecdote",
    "assertion": "anecdote",
    "blog": "cited-source",
    "citation": "cited-source",
    "study": "replicated-study",
    "peer-reviewed": "peer-reviewed-only",
    "executable": "executable-proof-only",
}
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "labelled_claims.json"


class UnderTierError(Exception):
    pass


def load_labelled_claims() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def preset_for(floor: str) -> dict:
    if floor not in _TIER_RANK:
        raise KeyError(floor)
    return {"floor": floor, "classifier_input_field": CLASSIFIER_INPUT_FIELD}


def read_field(claim: dict, field: str):
    if field == CLASSIFIER_INPUT_FIELD:
        return _source_type_value(claim)
    cur: object = claim
    for part in str(field).split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _source_type_value(claim: dict):
    src = claim.get("source")
    if not isinstance(src, dict):
        return None
    return src.get("type")


def classify_source_type(claim: dict) -> str:
    raw = _source_type_value(claim)
    if raw is None:
        return "anecdote"
    return _TYPE_TO_TIER.get(str(raw), "anecdote")


def classify_by_claimant_assertion(claim: dict) -> str:
    asserted = claim.get("claimed_tier") or claim.get("asserted_source_type")
    if asserted in _TIER_RANK:
        return str(asserted)
    mapped = _TYPE_TO_TIER.get(str(asserted or ""))
    return mapped or "executable-proof-only"


def misclassification_report(claims: list[dict]) -> dict:
    mismatches = []
    for claim in claims:
        truth = classify_source_type(claim)
        asserted = classify_by_claimant_assertion(claim)
        if truth != asserted:
            mismatches.append(claim["id"])
    return {
        "shows_misclassification": bool(mismatches),
        "n": len(claims),
        "n_mismatch": len(mismatches),
        "mismatch_ids": mismatches,
        "classifier_input_field": CLASSIFIER_INPUT_FIELD,
        "rows": [
            {
                "claim_id": c["id"],
                "truth": classify_source_type(c),
                "asserted": classify_by_claimant_assertion(c),
            }
            for c in claims
        ],
    }


def expected_admitted_ids(floor: str, claims: list[dict]) -> list[str]:
    need = _TIER_RANK[floor]
    out = []
    for c in claims:
        if _TIER_RANK[classify_source_type(c)] >= need:
            out.append(c["id"])
    return out


def bind_decision(preset: dict, claims: list[dict]) -> dict:
    floor = str(preset.get("floor"))
    admitted = expected_admitted_ids(floor, claims)
    refused = [c["id"] for c in claims if c["id"] not in admitted]
    admissions = [
        {
            "claim_id": cid,
            "classifier_input_field": CLASSIFIER_INPUT_FIELD,
            "admitted": True,
        }
        for cid in admitted
    ]
    return {
        "supporting_claim_ids": admitted,
        "refused_claim_ids": refused,
        "binding": bool(admitted),
        "classifier_input_field": CLASSIFIER_INPUT_FIELD,
        "admissions": admissions,
        "floor": floor,
    }


def admit_claim(preset: dict, claim: dict) -> dict:
    raw = _source_type_value(claim)
    floor = str(preset.get("floor"))
    tier = classify_source_type(claim)
    admitted = _TIER_RANK[tier] >= _TIER_RANK[floor]
    return {
        "claim_id": claim.get("id"),
        "admitted": admitted,
        "classifier_input_field": CLASSIFIER_INPUT_FIELD,
        "classifier_input_value": raw,
        "classified_tier": tier,
    }


def attach_claim(decision: dict, claim_id: str) -> dict:
    if claim_id in (decision.get("refused_claim_ids") or []):
        raise UnderTierError(claim_id)
    supporting = list(decision.get("supporting_claim_ids") or [])
    if claim_id not in supporting:
        supporting.append(claim_id)
        decision["supporting_claim_ids"] = supporting
    return decision


def classification_pass(claims: list[dict], preset: dict | None = None) -> list[dict]:
    floor = str((preset or {}).get("floor") or "anecdote")
    rows = []
    for c in claims:
        rec = admit_claim({"floor": floor}, c)
        rec["admitted"] = rec["admitted"]
        rows.append(rec)
    return rows
