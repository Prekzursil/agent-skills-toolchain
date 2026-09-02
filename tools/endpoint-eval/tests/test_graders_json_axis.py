"""Golden tests for graders.json_axis (three rates + refusal-field rate)."""

from __future__ import annotations

from graders.json_axis import (
    refusal_field_rate,
    refusal_of,
    schema_valid_rate,
    strict_honoured,
    valid_json_rate,
)

SCHEMA = {
    "type": "object",
    "properties": {"label": {"type": "string", "enum": ["a", "b"]}},
    "required": ["label"],
    "additionalProperties": False,
}


def test_valid_json_rate_both_states() -> None:
    assert valid_json_rate(['{"a": 1}', "[1, 2]", "42"]) == 1.0
    assert valid_json_rate(['{"a": 1}', "{nope", ""]) == 1 / 3
    assert valid_json_rate([]) == 0.0


def test_valid_json_rate_accepts_none_content_as_invalid() -> None:
    assert valid_json_rate([None, '{"a": 1}']) == 0.5


def test_schema_valid_rate_both_states() -> None:
    good = ['{"label": "a"}', '{"label": "b"}']
    bad = ['{"label": "zzz"}', '{"label": "a", "extra": 1}', "{nope", '"a"']
    assert schema_valid_rate(good, SCHEMA) == 1.0
    assert schema_valid_rate(good + bad, SCHEMA) == 2 / 6
    assert schema_valid_rate([], SCHEMA) == 0.0


def test_strict_honoured_iff_structured_mode_native() -> None:
    results = [
        {"structured_mode": "native"},
        {"structured_mode": "prompted"},
        {"structured_mode": "unsupported"},
        {},
    ]
    assert strict_honoured(results) == 0.25
    assert strict_honoured([{"structured_mode": "native"}]) == 1.0
    assert strict_honoured([]) == 0.0


def test_refusal_of_reads_hub_and_wire_shapes() -> None:
    assert refusal_of({"refusal": "no"}) == "no"
    wire = {
        "choices": [
            {"message": {"role": "assistant", "content": None, "refusal": "no"}}
        ]
    }
    assert refusal_of(wire) == "no"
    assert (
        refusal_of({"choices": [{"message": {"content": "hi", "refusal": None}}]})
        is None
    )
    assert refusal_of({"choices": []}) is None
    assert refusal_of({"choices": [{}]}) is None
    assert refusal_of({"refusal": ""}) is None
    assert refusal_of({"content": "flattened refusal text"}) is None


def test_refusal_field_rate_both_states() -> None:
    kept = {
        "choices": [
            {"message": {"content": None, "refusal": "I cannot help with that."}}
        ]
    }
    flattened = {
        "choices": [
            {"message": {"content": "I cannot help with that.", "refusal": None}}
        ]
    }
    assert refusal_field_rate([kept, kept]) == 1.0
    assert refusal_field_rate([kept, flattened]) == 0.5
    assert refusal_field_rate([]) == 0.0
