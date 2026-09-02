#!/usr/bin/env python3
"""Consent / no-objection: admissibility bar for an objection.

An objection blocks a consent decision if and only if it is ADMISSIBLE.
Admissibility is falsifiability bound to a seated objector and a named claim.

Two independent signals (neither is a restatement of the other):
  * schema: jsonschema Draft-07 over the objection record
  * evaluation: the claim's registered predicate on the supplied instance
    (or on a vacuity pair)

Unfalsifiable concerns fail both. A concrete counterexample that makes the
predicate False passes both and stands. A schema-valid instance that does
not actually falsify is refused by evaluation — schema alone is not a bar.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_PATH = HERE / "objection.schema.json"
FIXTURES = HERE / "fixtures"

_SCHEMA: dict[str, Any] | None = None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def objection_schema() -> dict[str, Any]:
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = load_json(SCHEMA_PATH)
    return _SCHEMA


def schema_check(objection: dict) -> dict[str, Any]:
    """Signal 1: structural validity. Does not run the claim predicate."""
    errors = sorted(
        e.message for e in jsonschema.Draft7Validator(objection_schema()).iter_errors(objection)
    )
    return {"ok": not errors, "errors": errors}


def _as_set(value: Any, name: str) -> set[str]:
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise ValueError(f"{name} must be a list of strings")
    return set(value)


def exclude_absent(inst: dict) -> bool:
    """True iff no absent seat appears in consent_counted.

    Malformed rosters raise ValueError so garbage cannot masquerade as a break.
    """
    if not isinstance(inst, dict):
        raise ValueError("instance must be an object")
    seats = _as_set(inst.get("seats"), "seats")
    present = _as_set(inst.get("present"), "present")
    counted = _as_set(inst.get("consent_counted"), "consent_counted")
    if not seats:
        raise ValueError("seats must be non-empty")
    if not present.issubset(seats) or not counted.issubset(seats):
        raise ValueError("present/counted must be subsets of seats")
    return counted.isdisjoint(seats - present)


def always_true(_inst: dict) -> bool:
    """Vacuous predicate: used only to show a proposal cannot open consent."""
    return True


PREDICATES = {
    "exclude_absent": exclude_absent,
    "always_true": always_true,
}


def proposal_eligible(proposal: dict) -> dict[str, Any]:
    """A consent window may open only if every claim discriminates.

    The proposer must publish known_good (predicate True) and known_bad
    (predicate False). A claim that cannot fail is not a consent item.
    """
    claims = proposal.get("claims") or []
    if not claims:
        return {"eligible": False, "reason": "NO_CLAIMS"}
    for claim in claims:
        pred_id = str(claim.get("predicate_id") or "")
        pred = PREDICATES.get(pred_id)
        if pred is None:
            return {
                "eligible": False,
                "reason": "PREDICATE_UNKNOWN",
                "claim_id": claim.get("id"),
            }
        try:
            good = pred(claim.get("known_good") or {})
            bad = pred(claim.get("known_bad") or {})
        except ValueError as exc:
            return {
                "eligible": False,
                "reason": "PROPOSER_FIXTURE_MALFORMED",
                "detail": str(exc),
                "claim_id": claim.get("id"),
            }
        if good is not True:
            return {
                "eligible": False,
                "reason": "KNOWN_GOOD_FAILS",
                "claim_id": claim.get("id"),
            }
        if bad is not False:
            return {
                "eligible": False,
                "reason": "KNOWN_BAD_PASSES",
                "claim_id": claim.get("id"),
            }
    return {"eligible": True, "reason": "DISCRIMINATES", "claim_count": len(claims)}


def _inadmissible(
    code: str,
    schema: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "admissible": False,
        "code": code,
        "schema_ok": schema["ok"],
        "schema_errors": schema["errors"],
        "predicate_false": None,
    }
    if extra:
        row.update(extra)
    return row


def _admissible(schema: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    row = {
        "admissible": True,
        "code": "ADMISSIBLE",
        "schema_ok": schema["ok"],
        "schema_errors": schema["errors"],
        "predicate_false": True,
    }
    if extra:
        row.update(extra)
    return row


def evaluate(proposal: dict, objection: dict) -> dict[str, Any]:
    """Signal 2: discrimination. Schema result is recorded, not reused as the verdict."""
    schema = schema_check(objection)
    seated = set(proposal.get("seated") or [])
    seat = str(objection.get("objector_seat") or "")
    if seat not in seated:
        return _inadmissible("NOT_SEATED", schema, {"objector_seat": seat})
    if not proposal.get("window_open", True):
        return _inadmissible("WINDOW_CLOSED", schema)
    target = objection.get("target") if isinstance(objection.get("target"), dict) else {}
    if target.get("proposal_id") != proposal.get("id"):
        return _inadmissible("TARGET_UNKNOWN", schema, {"target": target})
    claim = next(
        (
            c
            for c in (proposal.get("claims") or [])
            if isinstance(c, dict) and c.get("id") == target.get("claim_id")
        ),
        None,
    )
    if claim is None:
        return _inadmissible("TARGET_UNKNOWN", schema, {"target": target})
    pred_id = str(claim.get("predicate_id") or "")
    pred = PREDICATES.get(pred_id)
    if pred is None:
        return _inadmissible("PREDICATE_UNKNOWN", schema, {"predicate_id": pred_id})

    falsifier = objection.get("falsifier") if isinstance(objection.get("falsifier"), dict) else {}
    kind = str(falsifier.get("kind") or "")

    if kind == "counterexample":
        inst = falsifier.get("instance")
        if not isinstance(inst, dict) or not inst:
            return _inadmissible("NO_DISCRIMINATOR", schema)
        try:
            holds = pred(inst)
        except ValueError as exc:
            return _inadmissible("INSTANCE_MALFORMED", schema, {"detail": str(exc)})
        if holds is True:
            return _inadmissible(
                "COUNTEREXAMPLE_DOES_NOT_FALSIFY",
                schema,
                {"predicate_false": False, "predicate_id": pred_id},
            )
        if holds is not False:
            return _inadmissible("NO_DISCRIMINATOR", schema)
        if not schema["ok"]:
            return _inadmissible("SCHEMA_INVALID", schema, {"predicate_false": True})
        return _admissible(schema, {"predicate_id": pred_id, "claim_id": claim.get("id")})

    if kind == "vacuity":
        good_fx = falsifier.get("good_fixture")
        bad_fx = falsifier.get("bad_fixture")
        if not isinstance(good_fx, dict) or not isinstance(bad_fx, dict):
            return _inadmissible("NO_DISCRIMINATOR", schema)
        try:
            g = pred(good_fx)
            b = pred(bad_fx)
        except ValueError as exc:
            return _inadmissible("INSTANCE_MALFORMED", schema, {"detail": str(exc)})
        if g != b:
            return _inadmissible(
                "VACUITY_NOT_SHOWN",
                schema,
                {"good_holds": g, "bad_holds": b, "predicate_id": pred_id},
            )
        if not schema["ok"]:
            return _inadmissible("SCHEMA_INVALID", schema)
        return _admissible(
            schema,
            {
                "code": "ADMISSIBLE",
                "vacuous_predicate": True,
                "predicate_false": None,
                "predicate_id": pred_id,
            },
        )

    code = "UNKNOWN_KIND" if kind else "NO_DISCRIMINATOR"
    if not schema["ok"] and code == "UNKNOWN_KIND":
        # Record both signals on the unfalsifiable fixture.
        return _inadmissible(
            "UNFALSIFIABLE",
            schema,
            {"eval_code": code, "kind": kind},
        )
    return _inadmissible(code, schema, {"kind": kind})


def consent_outcome(proposal: dict, objections: list[dict]) -> dict[str, Any]:
    """Proposal is CONSENTED iff zero admissible objections remain.

    Inadmissible filings are logged and do not block. Silence of a seated
    participant is consent under this protocol only.
    """
    results = [evaluate(proposal, obj) for obj in objections]
    blockers = [r for r in results if r.get("admissible") is True]
    if blockers:
        return {
            "outcome": "BLOCKED",
            "blocker_count": len(blockers),
            "inadmissible_count": len(results) - len(blockers),
            "results": results,
        }
    return {
        "outcome": "CONSENTED",
        "blocker_count": 0,
        "inadmissible_count": len(results),
        "results": results,
    }


def load_proposal(name: str = "proposal.json") -> dict:
    return load_json(FIXTURES / name)


def load_objection(name: str) -> dict:
    return load_json(FIXTURES / name)


def mutant_battery(proposal: dict) -> list[dict]:
    """Four planted-bad classes. Caught iff evaluate() refuses admissibility."""
    claim = (proposal.get("claims") or [{}])[0]
    target = {"proposal_id": proposal.get("id"), "claim_id": claim.get("id")}
    seated = (proposal.get("seated") or ["x"])[0]
    planted = [
        (
            "unfalsifiable_concern",
            {
                "objector_seat": seated,
                "target": target,
                "blocking_claim": "unknown risks; I am not comfortable",
                "falsifier": {"kind": "concern"},
            },
        ),
        (
            "empty_instance",
            {
                "objector_seat": seated,
                "target": target,
                "blocking_claim": "counterexample with no rows",
                "falsifier": {"kind": "counterexample", "instance": {}},
            },
        ),
        (
            "non_falsifying_instance",
            {
                "objector_seat": seated,
                "target": target,
                "blocking_claim": "instance is the proposer's known-good",
                "falsifier": {
                    "kind": "counterexample",
                    "instance": claim.get("known_good") or {"seats": ["a"]},
                },
            },
        ),
        (
            "unseated_objector",
            {
                "objector_seat": "not-a-seat",
                "target": target,
                "blocking_claim": "outsider files the known-bad instance",
                "falsifier": {
                    "kind": "counterexample",
                    "instance": claim.get("known_bad") or {"seats": ["a"]},
                },
            },
        ),
    ]
    rows = []
    for cls, obj in planted:
        ev = evaluate(proposal, obj)
        caught = 0 if ev.get("admissible") else 1
        rows.append(
            {
                "class": cls,
                "planted": 1,
                "caught": caught,
                "recall": 1.0 if caught else 0.0,
                "scope": "admissibility.evaluate",
                "code": ev.get("code"),
            }
        )
    return rows
