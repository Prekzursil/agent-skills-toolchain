"""Golden tests for graders.tool_fidelity (BFCL-shaped AST match)."""

from __future__ import annotations

import json

import pytest
from graders.tool_fidelity import (
    Grade,
    grade_irrelevance,
    grade_parallel,
    grade_schema_strict,
    grade_tool_call,
    normalize_call,
    schema_errors,
)

GOLD = {
    "name": "search_notes",
    "args": {"query": ["endpoint eval", "endpoint-eval"], "page_size": [10, ""]},
    "optional": ["page_size"],
}


def wire_call(name: str, args: object, call_id: str = "call_1") -> dict:
    arguments = args if isinstance(args, str) else json.dumps(args)
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def test_grade_is_frozen_and_truthy_on_pass() -> None:
    grade = Grade(True)
    assert grade.passed is True
    assert grade.reasons == ()
    with pytest.raises(AttributeError):
        grade.passed = False  # type: ignore[misc]


def test_simple_known_good_wire_shape() -> None:
    grade = grade_tool_call(
        [wire_call("search_notes", {"query": "endpoint eval"})], GOLD
    )
    assert grade.passed, grade.reasons


def test_simple_known_good_with_optional_arg_supplied() -> None:
    call = wire_call("search_notes", {"query": "endpoint-eval", "page_size": 10})
    assert grade_tool_call([call], GOLD).passed


def test_simple_known_good_simplified_shape() -> None:
    assert grade_tool_call(
        [{"name": "search_notes", "args": {"query": "endpoint eval"}}], GOLD
    ).passed


def test_simple_known_bad_wrong_name() -> None:
    grade = grade_tool_call([wire_call("write_note", {"query": "endpoint eval"})], GOLD)
    assert not grade.passed
    assert any(reason.startswith("name-mismatch") for reason in grade.reasons)


def test_simple_known_bad_undeclared_arg() -> None:
    grade = grade_tool_call(
        [wire_call("search_notes", {"query": "endpoint eval", "limit": 3})], GOLD
    )
    assert not grade.passed
    assert "undeclared-arg:limit" in grade.reasons


def test_simple_known_bad_value_not_accepted() -> None:
    grade = grade_tool_call(
        [wire_call("search_notes", {"query": "something else"})], GOLD
    )
    assert not grade.passed
    assert "value-not-accepted:query" in grade.reasons


def test_simple_known_bad_missing_required_arg() -> None:
    grade = grade_tool_call([wire_call("search_notes", {"page_size": 10})], GOLD)
    assert not grade.passed
    assert "missing-arg:query" in grade.reasons


def test_optional_via_empty_string_marker_only() -> None:
    gold = {"name": "t", "args": {"a": ["x"], "b": ["y", ""]}}
    assert grade_tool_call([wire_call("t", {"a": "x"})], gold).passed
    gold_required_b = {"name": "t", "args": {"a": ["x"], "b": ["y"]}}
    assert not grade_tool_call([wire_call("t", {"a": "x"})], gold_required_b).passed


def test_simple_known_bad_call_count() -> None:
    assert "call-count:0" in grade_tool_call([], GOLD).reasons
    two = [wire_call("search_notes", {"query": "endpoint eval"})] * 2
    assert "call-count:2" in grade_tool_call(two, GOLD).reasons


def test_simple_known_bad_stringified_arguments_not_json() -> None:
    grade = grade_tool_call([wire_call("search_notes", "{not json")], GOLD)
    assert not grade.passed
    assert "arguments-not-json" in grade.reasons


def test_arguments_must_be_an_object() -> None:
    grade = grade_tool_call([wire_call("search_notes", "[1, 2]")], GOLD)
    assert "arguments-not-object" in grade.reasons


def test_normalize_call_shapes() -> None:
    assert normalize_call({"function": {"name": "a", "arguments": {"k": 1}}}) == (
        "a",
        {"k": 1},
    )
    assert normalize_call({"name": "a", "arguments": '{"k": 1}'}) == ("a", {"k": 1})
    assert normalize_call({"name": "a"}) == ("a", {})
    assert normalize_call({"function": {"name": "a", "arguments": None}}) == ("a", {})
    assert normalize_call({"function": {}}) == ("", {})
    assert normalize_call({"function": {"name": "a", "arguments": "nope"}}) == (
        "a",
        None,
    )
    assert normalize_call({"name": "a", "arguments": 7}) == ("a", None)


def test_parallel_known_good_order_independent() -> None:
    golds = [
        {"name": "read_file", "args": {"path": ["a.txt"]}},
        {"name": "read_file", "args": {"path": ["b.txt"]}},
        {"name": "note_add", "args": {"text": ["hi"]}},
    ]
    emitted = [
        wire_call("note_add", {"text": "hi"}, "c3"),
        wire_call("read_file", {"path": "b.txt"}, "c2"),
        wire_call("read_file", {"path": "a.txt"}, "c1"),
    ]
    assert grade_parallel(emitted, golds).passed


def test_parallel_requires_a_perfect_matching_not_greedy() -> None:
    # Gold 0 accepts either value; gold 1 accepts only "b". A greedy matcher that
    # pairs the first emitted "b" with gold 0 would wrongly fail this.
    golds = [
        {"name": "f", "args": {"x": ["a", "b"]}},
        {"name": "f", "args": {"x": ["b"]}},
    ]
    emitted = [wire_call("f", {"x": "b"}, "c1"), wire_call("f", {"x": "a"}, "c2")]
    assert grade_parallel(emitted, golds).passed


def test_parallel_known_bad_count_and_unmatched() -> None:
    golds = [{"name": "f", "args": {"x": ["a"]}}, {"name": "f", "args": {"x": ["b"]}}]
    short = grade_parallel([wire_call("f", {"x": "a"})], golds)
    assert not short.passed
    assert "call-count:1!=2" in short.reasons
    wrong = grade_parallel(
        [wire_call("f", {"x": "a"}), wire_call("f", {"x": "zzz"})], golds
    )
    assert not wrong.passed
    assert wrong.reasons == ("no-perfect-matching",)


def test_parallel_empty_gold_and_empty_emitted_pass() -> None:
    assert grade_parallel([], []).passed


def test_irrelevance_both_states() -> None:
    assert grade_irrelevance([]).passed
    grade = grade_irrelevance([wire_call("search_notes", {"query": "x"})])
    assert not grade.passed
    assert grade.reasons == ("false-call:1",)


SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "max_results": {"type": "integer"},
        "mode": {"type": "string", "enum": ["fast", "deep"]},
        "tags": {"type": "array", "items": {"type": "string"}},
        "opts": {
            "type": "object",
            "properties": {"safe": {"type": "boolean"}},
            "required": ["safe"],
            "additionalProperties": False,
        },
        "ratio": {"type": "number"},
        "nothing": {"type": "null"},
        "either": {"type": ["string", "integer"]},
    },
    "required": ["query"],
    "additionalProperties": False,
}


def test_schema_strict_known_good() -> None:
    args = {
        "query": "q",
        "max_results": 5,
        "mode": "fast",
        "tags": ["a"],
        "opts": {"safe": True},
        "ratio": 0.5,
        "nothing": None,
        "either": 3,
    }
    assert grade_schema_strict(args, SCHEMA).passed
    assert grade_schema_strict(json.dumps(args), SCHEMA).passed


def test_schema_strict_known_bad_stringified_number_and_array() -> None:
    grade = grade_schema_strict(
        {"query": "q", "max_results": "5", "tags": '["a"]'}, SCHEMA
    )
    assert not grade.passed
    assert "$.max_results: expected integer" in grade.reasons
    assert "$.tags: expected array" in grade.reasons


def test_schema_strict_known_bad_enum_required_additional() -> None:
    grade = grade_schema_strict({"mode": "slow", "extra": 1, "opts": {"x": 1}}, SCHEMA)
    assert "$: missing required query" in grade.reasons
    assert "$.mode: not in enum" in grade.reasons
    assert "$: additional property extra" in grade.reasons
    assert "$.opts: missing required safe" in grade.reasons
    assert "$.opts: additional property x" in grade.reasons


def test_schema_strict_rejects_unparseable_and_non_object() -> None:
    assert grade_schema_strict("{nope", SCHEMA).reasons == ("arguments-not-json",)
    assert grade_schema_strict([1], SCHEMA).reasons == ("$: expected object",)


def test_schema_errors_type_matrix() -> None:
    assert schema_errors(True, {"type": "integer"}) == ["$: expected integer"]
    assert schema_errors(1, {"type": "number"}) == []
    assert schema_errors(True, {"type": "number"}) == ["$: expected number"]
    assert schema_errors("s", {"type": "boolean"}) == ["$: expected boolean"]
    assert schema_errors(1, {"type": "null"}) == ["$: expected null"]
    assert schema_errors(1, {"type": "string"}) == ["$: expected string"]
    assert schema_errors(1.5, {"type": ["string", "integer"]}) == [
        "$: expected string|integer"
    ]
    assert schema_errors([1, "a"], {"type": "array", "items": {"type": "integer"}}) == [
        "$[1]: expected integer"
    ]
    assert schema_errors({"a": 1}, {"type": "object"}) == []
    assert (
        schema_errors({"a": 1}, {"type": "object", "additionalProperties": True}) == []
    )
    assert schema_errors(1, {}) == []
    assert schema_errors(1, {"type": "mystery"}) == ["$: unsupported type mystery"]
