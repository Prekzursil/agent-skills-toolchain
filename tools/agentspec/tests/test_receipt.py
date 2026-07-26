"""Receipt decoding / parsing / content checks — the raw material of the AND-gate."""

from __future__ import annotations

import pytest

from agentspec.receipt import (
    ReceiptUnparseable,
    decode,
    missing_fields,
    parse_json_object,
    present_markers,
)
from agentspec.spec import ReceiptSpec


def test_decode_returns_text_for_valid_utf8() -> None:
    assert decode("café ✓".encode()) == "café ✓"


def test_decode_rejects_invalid_utf8_with_the_taxonomy_reason() -> None:
    with pytest.raises(ReceiptUnparseable) as caught:
        decode(b"\xff\xfe not utf8")
    assert caught.value.reason == "receipt-unparseable"


def test_decode_strips_a_utf8_bom() -> None:
    """A BOM-prefixed receipt is common from Windows writers and must still parse."""
    assert decode(b"\xef\xbb\xbf{}") == "{}"


def test_parse_json_object_returns_the_mapping() -> None:
    assert parse_json_object('{"status": "ok", "n": 3}') == {"status": "ok", "n": 3}


def test_parse_json_object_rejects_malformed_json() -> None:
    with pytest.raises(ReceiptUnparseable) as caught:
        parse_json_object("{not json")
    assert caught.value.reason == "receipt-unparseable"


def test_parse_json_object_rejects_a_top_level_array() -> None:
    """A receipt is an OBJECT. A bare array has no field to validate against."""
    with pytest.raises(ReceiptUnparseable, match="object"):
        parse_json_object("[1, 2]")


def test_parse_json_object_rejects_a_top_level_scalar() -> None:
    with pytest.raises(ReceiptUnparseable, match="object"):
        parse_json_object("42")


def test_missing_fields_reports_absent_required_keys_sorted() -> None:
    spec = ReceiptSpec(fmt="json", required_fields=("status", "summary", "artifacts"))
    assert missing_fields({"status": "ok"}, spec) == ("artifacts", "summary")


def test_missing_fields_is_empty_when_every_required_key_is_present() -> None:
    spec = ReceiptSpec(fmt="json", required_fields=("status",))
    assert missing_fields({"status": "ok", "extra": 1}, spec) == ()


def test_a_required_field_present_but_null_still_counts_as_missing() -> None:
    """A key whose value is null carries no work product."""
    spec = ReceiptSpec(fmt="json", required_fields=("status",))
    assert missing_fields({"status": None}, spec) == ("status",)


def test_a_required_field_present_but_blank_counts_as_missing() -> None:
    spec = ReceiptSpec(fmt="json", required_fields=("summary",))
    assert missing_fields({"summary": "   "}, spec) == ("summary",)


def test_a_required_field_holding_zero_is_present() -> None:
    """Detector control: falsy-but-real values must NOT read as missing."""
    spec = ReceiptSpec(fmt="json", required_fields=("exit_code",))
    assert missing_fields({"exit_code": 0}, spec) == ()


def test_present_markers_finds_a_forbidden_marker_case_insensitively() -> None:
    spec = ReceiptSpec(fmt="text", forbidden_markers=("in progress", "unable to"))
    assert present_markers("I was UNABLE TO finish; work is In Progress.", spec) == (
        "in progress",
        "unable to",
    )


def test_present_markers_is_empty_on_a_clean_body() -> None:
    spec = ReceiptSpec(fmt="text", forbidden_markers=("in progress",))
    assert present_markers("Done: 3 files changed.", spec) == ()
