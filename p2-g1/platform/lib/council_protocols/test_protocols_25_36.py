"""Tests for the PHASE-2C council protocol blueprints P25-P36.

Two halves, and the second is the important one:

* FORWARD tests assert the 12 shipped files hold - they validate, they round-trip, their
  stopping rules are both satisfiable and falsifiable, and they meet the lane's content floors.
* DETECTOR CONTROLS assert the gate FIRES on a known-broken input. A floor that has never gone
  red is indistinguishable from a no-op, and every mutation below was chosen because a real
  authoring mistake would produce exactly that shape.

Run from the repo root: python -m pytest platform/lib/council_protocols/ -q
"""

from __future__ import annotations

import copy
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from council_protocols._shared import PRODUCERS, missing_producers  # noqa: E402
from council_protocols.analysis import all_trees, analyse  # noqa: E402
from council_protocols.build import (  # noqa: E402
    BUILDERS,
    EXPECTED,
    MIN_ANTI_FAILURE_CONTROLS,
    OUT_DIR,
    REPORT,
    _content_floors,
    _dumps,
    _spec_name,
)
from councilspec.expression import evaluate, parse, unparse  # noqa: E402
from councilspec.validate import validate_spec  # noqa: E402

SPECS = [b() for b in BUILDERS]
IDS = [s["council_id"] for s in SPECS]


def _on_disk(spec):
    path = os.path.join(OUT_DIR, _spec_name(spec))
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------ forward: inventory


def test_lane_delivers_exactly_twelve_protocols():
    assert len(SPECS) == EXPECTED == 12
    assert len(set(IDS)) == 12, f"duplicate council_id: {IDS}"


def test_council_ids_cover_p25_through_p36():
    prefixes = sorted(cid.split("-", 1)[0] for cid in IDS)
    assert prefixes == [f"p{n}" for n in range(25, 37)]


@pytest.mark.parametrize("spec", SPECS, ids=IDS)
def test_file_exists_and_matches_regeneration(spec):
    path = os.path.join(OUT_DIR, _spec_name(spec))
    assert os.path.isfile(path), f"{path} absent - run build.py build"
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    assert raw == _dumps(spec), "on-disk bytes drifted from the authored source"


# ------------------------------------------------------------------ forward: validation


@pytest.mark.parametrize("spec", SPECS, ids=IDS)
def test_on_disk_file_validates(spec):
    res = validate_spec(_on_disk(spec))
    assert res["schema_ok"], res["schema_errors"]
    assert not res["semantic_errors"], res["semantic_errors"]
    assert res["ok"]


@pytest.mark.parametrize("spec", SPECS, ids=IDS)
def test_source_expression_round_trips(spec):
    stopping = _on_disk(spec)["stopping"]
    src, tree = stopping["source_expression"], stopping["expression"]
    assert parse(src) == tree, "source_expression parses to a different tree"
    assert parse(unparse(tree)) == tree, "unparse/parse is not tree-idempotent"


@pytest.mark.parametrize("spec", SPECS, ids=IDS)
def test_every_expression_is_both_satisfiable_and_falsifiable(spec):
    disk = _on_disk(spec)
    trees = list(all_trees(disk))
    assert trees, "no stopping expression at all"
    for path, tree in trees:
        a = analyse(tree)
        assert not a["duplicate_metrics"], f"{path} repeats {a['duplicate_metrics']}"
        assert a["satisfiable"], f"{path} can never fire"
        assert a["falsifiable"], f"{path} is a tautology - it would fire on round 0"
        # Re-execute the published snapshots rather than trusting the analyser's own verdict.
        assert evaluate(tree, a["satisfying"]) is True, (
            f"{path} satisfying snapshot did not fire"
        )
        assert evaluate(tree, a["not_satisfying"]) is False, (
            f"{path} negative snapshot fired"
        )


@pytest.mark.parametrize("spec", SPECS, ids=IDS)
def test_conjunctive_rules_have_no_survivor_leaf(spec):
    """A single-leaf flip must break a conjunctive rule.

    Honest scope: for a FLAT conjunction over distinct metrics this is guaranteed by the
    semantics of all_of, so it is a regression guard (against a duplicated metric or a nested
    disjunction sneaking in), not evidence that the conditions were well chosen.
    """
    for path, tree in all_trees(_on_disk(spec)):
        a = analyse(tree)
        if a["root"] != "all_of":
            continue
        assert a["load_bearing"] == a["leaves"], f"{path} survivors={a['survivors']}"


# ------------------------------------------------------------------ forward: content floors


@pytest.mark.parametrize("spec", SPECS, ids=IDS)
def test_content_floors_hold(spec):
    floors = _content_floors(_on_disk(spec))
    assert floors["ok"], floors["failures"]
    assert len(floors["brief_controls_declared"]) >= MIN_ANTI_FAILURE_CONTROLS
    assert floors["fast_unanimity_response"], "fast unanimity triggers nothing concrete"


@pytest.mark.parametrize("spec", SPECS, ids=IDS)
def test_every_custom_metric_names_a_producer(spec):
    uncovered = set()
    for _path, tree in all_trees(_on_disk(spec)):
        uncovered |= missing_producers(tree)
    assert not uncovered, (
        f"custom metric(s) nothing is obliged to compute: {sorted(uncovered)}"
    )


@pytest.mark.parametrize("spec", SPECS, ids=IDS)
def test_receipt_schema_reference_resolves(spec):
    """Cross-lane integration probe: the receipt schema these protocols name must exist."""
    ref = _on_disk(spec)["outputs"]["receipt_schema"]
    target = os.path.join(os.path.dirname(_LIB), *ref.split("/")[1:])
    assert os.path.isfile(target), f"{ref} does not resolve to a file ({target})"


def test_producers_map_has_no_unused_entries():
    used = set()
    for spec in SPECS:
        for _path, tree in all_trees(spec):
            for metric in _iter_metrics(tree):
                if metric.startswith("custom:"):
                    used.add(metric)
    unused = sorted(set(PRODUCERS) - used)
    assert not unused, f"PRODUCERS carries entries no protocol uses: {unused}"


def _iter_metrics(tree):
    if not isinstance(tree, dict):
        return
    if "metric" in tree:
        yield tree["metric"]
        return
    for key in ("all_of", "any_of"):
        for child in tree.get(key, []) or []:
            yield from _iter_metrics(child)
    if "not" in tree:
        yield from _iter_metrics(tree["not"])
    if "weighted" in tree:
        for clause in tree["weighted"].get("clauses", []) or []:
            yield from _iter_metrics(clause.get("when"))


def test_report_exists_and_claims_all_twelve_pass():
    assert os.path.isfile(REPORT), "validation report absent - run build.py verify"
    with open(REPORT, "r", encoding="utf-8") as fh:
        report = json.load(fh)
    assert report["protocols_pass"] == EXPECTED, report["protocols_pass"]
    assert report["status"] == "PASS"
    assert report["generated_at_utc"], "report still carries the UNKNOWN skeleton"


# ------------------------------------------------------------------ DETECTOR CONTROLS


def test_control_floor_fires_when_controls_are_thinned():
    spec = copy.deepcopy(SPECS[0])
    spec["anti_failure"]["controls"] = ["echo_chamber", "silence"]  # 2 < floor of 3
    floors = _content_floors(spec)
    assert not floors["ok"]
    assert any("floor" in f for f in floors["failures"]), floors["failures"]


def test_control_floor_fires_when_fast_unanimity_response_is_removed():
    spec = copy.deepcopy(SPECS[0])
    spec["anti_failure"]["fast_unanimity_response"] = []
    floors = _content_floors(spec)
    assert not floors["ok"]
    assert any("fast_unanimity_response" in f for f in floors["failures"])


def test_control_floor_fires_when_a_response_obligation_is_undeclared():
    spec = copy.deepcopy(SPECS[0])
    del spec["protocol"]["obligations"]["cross_examination"]
    floors = _content_floors(spec)
    assert not floors["ok"]
    assert any("cross_examination" in f for f in floors["failures"])


def test_control_floor_fires_when_the_novelty_quota_is_removed():
    spec = copy.deepcopy(SPECS[0])
    for stage in spec["protocol"]["sequence"]:
        for key in ("ideas_per_participant", "novel_ideas_per_round"):
            (stage.get("quotas") or {}).pop(key, None)
    floors = _content_floors(spec)
    assert not floors["ok"]
    assert any("quota" in f for f in floors["failures"]), floors["failures"]


def test_control_validator_fires_on_a_broken_source_expression():
    spec = copy.deepcopy(SPECS[0])
    spec["stopping"]["source_expression"] = "independent_positions >= 99"
    res = validate_spec(spec)
    assert not res["ok"]
    assert any("SEM-001" in m for m in res["semantic_errors"]), res["semantic_errors"]


def test_control_validator_fires_on_an_unknown_top_level_key():
    spec = copy.deepcopy(SPECS[0])
    spec["stopping_rules"] = ["not a real key"]
    res = validate_spec(spec)
    assert not res["ok"]
    assert res["schema_errors"]


def test_control_producer_check_fires_on_an_unmapped_custom_metric():
    tree = parse("custom:metric_nobody_computes >= 1")
    assert missing_producers(tree) == {"custom:metric_nobody_computes"}


def test_control_analyser_reports_an_unsatisfiable_rule():
    tree = parse("ALL[participants_active >= 5, participants_active <= 2]")
    a = analyse(tree)
    assert a["duplicate_metrics"] == ["participants_active"]
    assert a["satisfiable"] is False, (
        "a rule that can never fire was reported satisfiable"
    )


def test_control_analyser_reports_a_tautology():
    tree = parse("ANY[unanimity == true, unanimity != true]")
    a = analyse(tree)
    assert a["satisfiable"] is True
    assert a["falsifiable"] is False, (
        "a rule that always fires was reported falsifiable"
    )


def test_control_analyser_finds_a_survivor_in_a_nested_disjunction():
    """The survivor check is not vacuous once a disjunction is nested inside a conjunction."""
    tree = parse(
        "ALL[rounds_elapsed >= 2, ANY[unanimity == true, consent_reached == true]]"
    )
    a = analyse(tree)
    assert a["root"] == "all_of"
    assert a["load_bearing"] < a["leaves"], (
        "a nested ANY leaf should survive a single flip"
    )
    assert set(a["survivors"]) == {"unanimity", "consent_reached"}


def test_control_analyser_handles_negated_leaf_polarity():
    """A leaf under NOT satisfies the root when its own comparison is FALSE."""
    tree = parse(
        "ALL[rounds_elapsed >= 2, NOT unresolved_load_bearing_counterexample >= 1]"
    )
    a = analyse(tree)
    assert a["satisfiable"] and a["falsifiable"]
    assert a["satisfying"]["unresolved_load_bearing_counterexample"] < 1
    assert evaluate(tree, a["satisfying"]) is True
    assert evaluate(tree, a["not_satisfying"]) is False
    assert a["load_bearing"] == a["leaves"] == 2
