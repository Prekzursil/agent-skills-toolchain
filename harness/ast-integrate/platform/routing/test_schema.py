"""Schema conformance for the two routing artifacts.

A schema that has never rejected anything is indistinguishable from an empty one, so every
"validates" assertion here is paired with a MUTATION that must be REJECTED.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from routing.index import discover
from routing.router import Router

jsonschema = pytest.importorskip("jsonschema")

SCHEMA_DIR = Path(__file__).resolve().parent / "schema"


def _load(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def decision_schema():
    return _load("routing-decision.schema.json")


@pytest.fixture(scope="module")
def record_schema():
    return _load("capability-record.schema.json")


@pytest.fixture(scope="module")
def r():
    return Router.build()


# --------------------------------------------------------------------- both schemas parse


def test_both_schemas_are_themselves_valid(decision_schema, record_schema):
    for s in (decision_schema, record_schema):
        jsonschema.Draft202012Validator.check_schema(s)


# --------------------------------------------------------------------- capability records


def test_every_indexed_record_validates(record_schema):
    idx = discover()
    v = jsonschema.Draft202012Validator(record_schema)
    errors = []
    for rec in idx.records:
        errors.extend(f"{rec.id}: {e.message}" for e in v.iter_errors(rec.as_dict()))
    assert errors == [], errors[:5]
    assert len(idx.records) > 800, (
        "an empty walk would vacuously satisfy the loop above"
    )


def test_the_record_schema_REJECTS_a_malformed_record(record_schema):
    """BOTH-STATES control for the assertion above."""
    idx = discover()
    good = idx.records[0].as_dict()
    v = jsonschema.Draft202012Validator(record_schema)
    assert list(v.iter_errors(good)) == []

    for mutation in (
        {"id": "NoNamespace"},  # violates the `<cls>:<name>` pattern
        {"cls": "not-a-class"},  # outside the class enum
        {"card_bytes": 0},  # a zero-byte card is not a card
        {"anchor": "x"},  # below minLength
    ):
        bad = dict(good)
        bad.update(mutation)
        assert list(v.iter_errors(bad)), f"schema accepted {mutation}"

    extra = dict(good)
    extra["surprise_field"] = 1
    assert list(v.iter_errors(extra)), "additionalProperties is not being enforced"


# --------------------------------------------------------------------------- decisions


@pytest.mark.parametrize(
    "query",
    [
        "reframe a landscape clip to vertical for tiktok",
        "a council protocol for an entrenched two-party disagreement",
        "the deploy overwrote live-ahead work, I need a safer per-file apply",
        "use reframe but do not use reframe",
        "what is the capital of Mongolia and how many people live there",
    ],
)
def test_real_decisions_validate(r, decision_schema, query):
    payload = r.route(query, k=5).to_dict()
    errs = list(jsonschema.Draft202012Validator(decision_schema).iter_errors(payload))
    assert errs == [], [e.message for e in errs]


def test_an_abstention_satisfies_the_zero_cost_conditional(r, decision_schema):
    """The schema's `if fits == false` branch is only meaningful if a real abstention hits it."""
    d = r.route("what is the capital of Mongolia and how many people live there", k=5)
    assert d.fits is False, "precondition: this query must abstain"
    payload = d.to_dict()
    assert payload["injected_bytes"] == 0 and payload["selected"] == []
    assert (
        list(jsonschema.Draft202012Validator(decision_schema).iter_errors(payload))
        == []
    )


def test_the_schema_REJECTS_an_abstention_that_charged_for_context(r, decision_schema):
    """The conditional branch must BITE. An abstention with a nonzero cost is the exact
    inconsistency worth catching -- it means the router reported silence and injected anyway."""
    d = r.route("what is the capital of Mongolia and how many people live there", k=5)
    bad = copy.deepcopy(d.to_dict())
    bad["injected_bytes"] = 400
    assert list(jsonschema.Draft202012Validator(decision_schema).iter_errors(bad))


def test_the_schema_REJECTS_a_fitting_decision_with_nothing_selected(
    r, decision_schema
):
    d = r.route("reframe a landscape clip to vertical", k=5)
    assert d.fits is True
    bad = copy.deepcopy(d.to_dict())
    bad["selected"] = []
    assert list(jsonschema.Draft202012Validator(decision_schema).iter_errors(bad))


def test_the_schema_REJECTS_an_uncalibrated_confidence_band(r, decision_schema):
    bad = copy.deepcopy(r.route("reframe to vertical", k=3).to_dict())
    bad["confidence_band"] = "very sure"
    assert list(jsonschema.Draft202012Validator(decision_schema).iter_errors(bad))


def test_the_schema_REJECTS_an_unknown_rule_name(r, decision_schema):
    """Every rule lane must be declared. An undeclared rule is an unexplained selection."""
    d = r.route("reframe a landscape clip to vertical", k=3).to_dict()
    hit_bearing = [s for s in d["selected"] if s.get("rule_hits")]
    if not hit_bearing:
        pytest.skip("no rule hits in this decision; nothing to mutate")
    bad = copy.deepcopy(d)
    next(s for s in bad["selected"] if s.get("rule_hits"))["rule_hits"][0]["rule"] = (
        "made-up"
    )
    assert list(jsonschema.Draft202012Validator(decision_schema).iter_errors(bad))


def test_every_rule_name_the_code_can_emit_is_in_the_schema_enum(decision_schema):
    """Keeps `rules.py` and the schema enum in step without waiting for a query to hit
    each lane -- a lane the schema does not know about would reject a valid decision."""
    enum = set(
        decision_schema["properties"]["selected"]["items"]["properties"]["rule_hits"][
            "items"
        ]["properties"]["rule"]["enum"]
    )
    emitted = {
        "exact-name",
        "exact-name-spaced",
        "invoke-token",
        "id-fragment",
        "declared-trigger",
        "tag",
        "category",
        "family",
        "class-hint",
        "anti-trigger",
    }
    assert emitted == enum, emitted ^ enum
