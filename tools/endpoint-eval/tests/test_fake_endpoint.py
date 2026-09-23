"""Fixture freshness (every fixture parses and matches its declared shape) + fixture replay."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fake_endpoint import (
    FIXTURES_DIR,
    SCHEMAS_HOUSE,
    SHAPES,
    TOOLS_HOUSE,
    WIRE_FIXTURES,
    WIRE_SEQUENCE,
    FakeEndpoint,
    load_fixture,
    validate_fixture,
)
from graders.bridge_passthrough import CAPABILITY_ABSENT, DEGRADED, compare
from graders.json_axis import refusal_field_rate
from graders.tool_fidelity import grade_schema_strict, grade_tool_call, schema_errors

ALL_FIXTURES = (TOOLS_HOUSE, SCHEMAS_HOUSE, *WIRE_FIXTURES)


def _tool_calls(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    return envelope["body"]["choices"][0]["message"]["tool_calls"]


def test_fixture_directory_holds_exactly_the_declared_set() -> None:
    on_disk = sorted(path.stem for path in FIXTURES_DIR.glob("*.json"))
    assert on_disk == sorted(ALL_FIXTURES)
    assert WIRE_FIXTURES == (
        "wire_429_storm",
        "wire_stringified_args",
        "wire_refusal",
        "wire_bridge_drop",
    )


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_every_fixture_parses_and_matches_its_declared_shape(name: str) -> None:
    document = load_fixture(name)
    assert document["name"] == name
    assert document["shape"] in SHAPES
    assert document["recorded_at"]
    assert validate_fixture(document) == []


def test_tools_house_has_twelve_tools_each_with_a_known_good_and_known_bad_call() -> (
    None
):
    tools = load_fixture(TOOLS_HOUSE)["tools"]
    assert len(tools) == 12
    assert len({tool["name"] for tool in tools}) == 12
    for tool in tools:
        gold = tool["gold"]
        assert gold["name"] == tool["name"]
        properties = tool["parameters"]["properties"]
        assert set(gold["args"]) <= set(properties), tool["name"]
        good = grade_tool_call([tool["good_call"]], gold)
        assert good.passed, (tool["name"], good.reasons)
        assert grade_schema_strict(tool["good_call"]["args"], tool["parameters"]).passed
        bad = grade_tool_call([tool["bad_call"]], gold)
        assert not bad.passed, tool["name"]
        assert tool["prompt"]


def test_schemas_house_has_fifteen_schemas_each_with_both_states() -> None:
    schemas = load_fixture(SCHEMAS_HOUSE)["schemas"]
    assert len(schemas) == 15
    assert len({entry["name"] for entry in schemas}) == 15
    for entry in schemas:
        assert schema_errors(entry["valid"], entry["schema"]) == [], entry["name"]
        assert schema_errors(entry["invalid"], entry["schema"]), entry["name"]


def test_429_storm_replays_three_rate_limits_then_sticks_on_the_final_success() -> None:
    fake = FakeEndpoint("wire_429_storm")
    statuses = [envelope["status"] for envelope in fake.sequence()]
    assert statuses == [429, 429, 429, 200]
    request = {"model": "m", "messages": [{"role": "user", "content": "hi"}]}
    seen = [fake.chat(request)["status"] for _ in range(6)]
    assert seen == [429, 429, 429, 200, 200, 200]
    assert fake.exhausted
    assert len(fake.calls) == 6
    for envelope in fake.sequence()[:3]:
        assert envelope["headers"]["Retry-After"] == "1"
        assert envelope["body"]["error"]["type"] == "rate_limit_error"
    fake.reset()
    assert not fake.exhausted
    assert fake.chat(request)["status"] == 429


def test_replay_hands_out_copies_so_a_grader_cannot_corrupt_the_recording() -> None:
    fake = FakeEndpoint("wire_refusal")
    first = fake.chat({})
    first["body"]["choices"][0]["message"]["refusal"] = "mutated"
    fake.reset()
    assert fake.chat({})["body"]["choices"][0]["message"]["refusal"] != "mutated"
    assert fake.labels() == ["refusal-field", "refusal-flattened"]
    with pytest.raises(KeyError):
        fake.by_label("nope")


def test_stringified_arguments_fixture_grades_both_states() -> None:
    fake = FakeEndpoint("wire_stringified_args")
    gold = fake.document["gold"]
    double_encoded = fake.by_label("double-encoded")
    well_formed = fake.by_label("well-formed")
    bad = grade_tool_call(_tool_calls(double_encoded), gold)
    assert not bad.passed
    assert "arguments-not-object" in bad.reasons
    assert grade_tool_call(_tool_calls(well_formed), gold).passed


def test_refusal_fixture_grades_both_states() -> None:
    fake = FakeEndpoint("wire_refusal")
    kept, flattened = (envelope["body"] for envelope in fake.sequence())
    assert refusal_field_rate([kept]) == 1.0
    assert refusal_field_rate([flattened]) == 0.0
    report = compare(kept, flattened)
    assert report.verdict == DEGRADED
    assert "refusal-flattened" in report.findings


def test_bridge_drop_fixture_fails_closed_as_capability_absent() -> None:
    fake = FakeEndpoint("wire_bridge_drop")
    upstream = fake.by_label("upstream")["body"]
    bridged = fake.by_label("through-bridge")["body"]
    report = compare(upstream, bridged)
    assert not report.passed
    assert report.verdict == CAPABILITY_ABSENT
    assert "tool_calls-stripped" in report.findings
    assert "tool_calls-in-content" in report.findings
    assert compare(upstream, upstream).passed


def test_unknown_fixture_names_the_directory_it_searched() -> None:
    with pytest.raises(FileNotFoundError, match="fixtures"):
        FakeEndpoint("wire_missing")


def test_non_wire_fixture_cannot_be_replayed_as_an_endpoint() -> None:
    with pytest.raises(ValueError, match="wire-sequence"):
        FakeEndpoint(TOOLS_HOUSE)


def _write(directory: Path, name: str, payload: Any) -> None:
    (directory / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")


def _wire_document(name: str = "probe") -> dict[str, Any]:
    return {
        "shape": WIRE_SEQUENCE,
        "name": name,
        "recorded_at": "2026-09-02",
        "description": "d",
        "responses": [{"status": 200, "headers": {}, "body": {"choices": []}}],
    }


def test_load_fixture_rejects_broken_json_and_a_name_mismatch(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not JSON"):
        load_fixture("broken", tmp_path)
    _write(tmp_path, "renamed", _wire_document("other"))
    with pytest.raises(ValueError, match="name"):
        load_fixture("renamed", tmp_path)
    _write(tmp_path, "probe", _wire_document())
    fake = FakeEndpoint("probe", tmp_path)
    assert fake.chat({})["status"] == 200
    assert fake.labels() == []


def test_load_fixture_reports_every_shape_violation_at_once(tmp_path: Path) -> None:
    document = _wire_document("stale")
    document["responses"] = [{"status": "200", "headers": {}}]
    document["labels"] = "x"
    _write(tmp_path, "stale", document)
    with pytest.raises(ValueError, match="is invalid") as excinfo:
        load_fixture("stale", tmp_path)
    message = str(excinfo.value)
    assert "responses[0].status" in message
    assert "responses[0].body" in message
    assert "labels" in message


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (lambda doc: doc.pop("shape"), "shape"),
        (lambda doc: doc.__setitem__("shape", "unknown-shape"), "unknown shape"),
        (lambda doc: doc.pop("recorded_at"), "recorded_at"),
        (lambda doc: doc.pop("name"), "name"),
        (lambda doc: doc.__setitem__("responses", {}), "responses"),
        (lambda doc: doc.__setitem__("responses", []), "responses"),
        (lambda doc: doc.__setitem__("responses", ["x"]), "responses[0]"),
        (lambda doc: doc["responses"][0].__setitem__("status", "200"), "status"),
        (lambda doc: doc["responses"][0].__setitem__("headers", []), "headers"),
        (lambda doc: doc["responses"][0].pop("body"), "body"),
        (lambda doc: doc.__setitem__("labels", ["a", "b"]), "labels"),
        (lambda doc: doc.__setitem__("labels", "a"), "labels"),
    ],
)
def test_wire_shape_violations_are_reported(mutate: Any, fragment: str) -> None:
    document = _wire_document()
    mutate(document)
    errors = validate_fixture(document)
    assert errors
    assert any(fragment in error for error in errors), errors


def test_non_dict_document_is_one_error() -> None:
    assert validate_fixture(["not", "a", "dict"]) == [
        "document: expected a JSON object"
    ]


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (lambda doc: doc.__setitem__("tools", "x"), "tools"),
        (lambda doc: doc["tools"].append("x"), "tools[12]"),
        (lambda doc: doc["tools"][0].pop("gold"), "tools[0]"),
        (lambda doc: doc["tools"][0].__setitem__("parameters", []), "parameters"),
        (lambda doc: doc["tools"][0]["gold"].pop("args"), "gold"),
        (lambda doc: doc["tools"][0].__setitem__("good_call", 3), "good_call"),
    ],
)
def test_tools_house_shape_violations_are_reported(mutate: Any, fragment: str) -> None:
    document = load_fixture(TOOLS_HOUSE)
    mutate(document)
    errors = validate_fixture(document)
    assert errors
    assert any(fragment in error for error in errors), errors


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (lambda doc: doc.__setitem__("schemas", None), "schemas"),
        (lambda doc: doc["schemas"].append({"name": "x"}), "schemas[15]"),
        (lambda doc: doc["schemas"].append("x"), "schemas[15]: expected an object"),
        (lambda doc: doc["schemas"][0].__setitem__("schema", "x"), "schema"),
        (lambda doc: doc["schemas"][0].pop("invalid"), "invalid"),
    ],
)
def test_schemas_house_shape_violations_are_reported(
    mutate: Any, fragment: str
) -> None:
    document = load_fixture(SCHEMAS_HOUSE)
    mutate(document)
    errors = validate_fixture(document)
    assert errors
    assert any(fragment in error for error in errors), errors
