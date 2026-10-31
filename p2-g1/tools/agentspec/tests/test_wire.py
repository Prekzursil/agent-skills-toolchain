"""The SHARED WIRE RULES, and a regression row for every measured Python<->JS divergence.

Every test below names the divergence it closes. The differential harness that found them drove
both runtimes over 483 behavioural cases and reported 78 outcome mismatches; the cases are now
permanent, and their CROSS-RUNTIME half lives in
``tools/agentspec-js/fixtures/behaviour-corpus.json``, which the parity oracle byte-compares in
CI. These are the Python-side unit gate underneath that.
"""

from __future__ import annotations

import pytest

from agentspec import canonical, wire
from agentspec.argv import build_argv, prompt_on_argv, render_cmdline
from agentspec.budget import Ledger, cost_per_success
from agentspec.dispatchpolicy import check_dispatch
from agentspec.oracle import RailResult, judge
from agentspec.receipt import ReceiptUnparseable, missing_fields, parse_json_object
from agentspec.retry import RATE_LIMIT_MAX_ATTEMPTS, rate_limit_backoff_ms
from agentspec.spec import ReceiptSpec
from agentspec.terminal import success_line

JSON_SPEC = ReceiptSpec(fmt="json", required_fields=("summary",))

PY_ONLY_BLANK = ("\x1c", "\x1d", "\x1e", "\x1f", "\x85")
"""Blank to ``str.strip()`` and NOT to JS ``trim()`` — measured by exhaustive code-point sweep."""


def test_blank_set_is_closed_and_excludes_the_bom() -> None:
    """U+FEFF is blank to JS ``trim()`` only; treating it as blank made a 2-BOM receipt EMPTY."""
    assert len(wire.BLANK_CHARS) == 29
    assert len(set(wire.BLANK_CHARS)) == len(wire.BLANK_CHARS)
    assert "\ufeff" not in wire.BLANK_CHARS
    assert wire.is_blank("\ufeff") is False
    assert wire.contains_blank("\ufeff") is False


@pytest.mark.parametrize("char", PY_ONLY_BLANK)
def test_the_python_only_blank_characters_are_pinned_as_blank(char: str) -> None:
    """The set is DATA now, so neither runtime's builtin gets to decide it."""
    assert wire.is_blank(char) is True
    assert wire.contains_blank(f"a{char}b") is True


def test_is_blank_treats_the_empty_string_as_blank_and_real_text_as_not() -> None:
    assert wire.is_blank("") is True
    assert wire.is_blank(" \t\n") is True
    assert wire.is_blank(" x ") is False
    assert wire.contains_blank("abc") is False


def test_utf16_len_counts_code_units_not_code_points() -> None:
    """WINDOWS_CMDLINE_CAP is a cap on what ``CreateProcess`` counts: UTF-16 code units."""
    assert wire.utf16_len("abc") == 3
    assert wire.utf16_len("\U0001f600") == 2
    assert wire.utf16_len("\U0001f600" * 32) == 64
    assert len("\U0001f600" * 32) == 32


def test_sorted_wire_orders_by_utf16_code_unit_like_js_sort() -> None:
    """``sorted()`` puts U+FFFD first; JS ``.sort()`` puts the astral lead surrogate first."""
    assert wire.sorted_wire(("\U0001f600", "�")) == ("\U0001f600", "�")
    assert tuple(sorted(("\U0001f600", "�"))) == ("�", "\U0001f600")
    assert wire.sorted_wire(("b", "a")) == ("a", "b")


def test_fold_ascii_case_folds_ascii_only() -> None:
    """Full Unicode lowercasing disagreed on 28 code points across the two Unicode versions."""
    assert wire.fold_ascii_case("TODO") == "todo"
    assert wire.fold_ascii_case("İ") == "İ"
    assert wire.fold_ascii_case("É") == "É"


def test_is_printable_id_is_pinned_to_the_range_table_not_the_interpreter() -> None:
    """U+088F is Cn on Unicode 16 and Lo on 17; the pinned table accepts it on BOTH runtimes."""
    assert len(wire.NON_PRINTABLE_ID_RANGES) == 42
    assert wire.is_printable_id("unit-1") is True
    assert wire.is_printable_id("a࢏") is True
    assert wire.is_printable_id("a౜") is True
    assert wire.is_printable_id("") is False
    assert wire.is_printable_id("a\x1b") is False
    assert wire.is_printable_id("a b") is False
    assert wire.is_printable_id("a\ufeff") is False
    assert wire.is_printable_id("a\U000e0020") is False


def test_the_wire_integer_bound_matches_the_canonical_safe_integer() -> None:
    """Two independent declarations of one fact, cross-checked rather than derived."""
    assert wire.MAX_WIRE_INTEGER == canonical.MAX_SAFE_INTEGER
    assert wire.MIN_WIRE_INTEGER == canonical.MIN_SAFE_INTEGER


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, True),
        (-1, True),
        (wire.MAX_WIRE_INTEGER, True),
        (wire.MIN_WIRE_INTEGER, True),
        (wire.MAX_WIRE_INTEGER + 1, False),
        (wire.MIN_WIRE_INTEGER - 1, False),
        (2.0, False),
        (True, False),
        ("1", False),
        (None, False),
    ],
)
def test_is_wire_integer_admits_exactly_what_js_admits(
    value: object, expected: bool
) -> None:
    assert wire.is_wire_integer(value) is expected


def test_require_wire_integer_returns_the_value_or_raises_without_rendering_it() -> (
    None
):
    """The message must not print the value: Python renders 2.0 where JS renders 2."""
    assert wire.require_wire_integer(5, "micro") == 5
    with pytest.raises(TypeError) as caught:
        wire.require_wire_integer(2.0, "micro")
    assert str(caught.value) == (
        "micro must be an integer in [-9007199254740991, 9007199254740991]"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "null"),
        (True, "boolean"),
        (1, "number"),
        (1.5, "number"),
        ("x", "string"),
        ([1], "array"),
        ({"a": 1}, "object"),
    ],
)
def test_json_type_name_is_one_portable_vocabulary(
    value: object, expected: str
) -> None:
    """``type(x).__name__`` gives ``list``/``NoneType``; JS ``typeof`` gives ``object``."""
    assert wire.json_type_name(value) == expected


# ----------------------------------------------------------------- regression rows


@pytest.mark.parametrize("char", PY_ONLY_BLANK)
def test_judge_calls_a_python_only_blank_receipt_severed_and_so_must_js(
    char: str,
) -> None:
    """MEASURED: a body of one U+001C was receipt-empty here and a SIX-CLAUSE SUCCESS on JS."""
    result = RailResult(exit_code=0, receipt_bytes=char.encode("utf-8"), wall_ms=1)
    verdict = judge("u", result, JSON_SPEC)
    assert verdict.ok is False
    assert verdict.reason == "receipt-empty"


def test_a_double_bom_receipt_is_not_blank_on_either_runtime() -> None:
    """``decode`` strips ONE leading BOM; the second is DATA, so the body is not empty."""
    result = RailResult(
        exit_code=0, receipt_bytes="\ufeff\ufeff".encode("utf-8"), wall_ms=1
    )
    verdict = judge("u", result, JSON_SPEC)
    assert verdict.reason == "receipt-unparseable"
    assert wire.is_blank("\ufeff") is False


@pytest.mark.parametrize("char", PY_ONLY_BLANK)
def test_a_python_only_blank_unit_id_is_refused(char: str) -> None:
    """MEASURED: JS minted a full ok=true verdict for a unit id of U+001C."""
    with pytest.raises(ValueError, match="unit_id must be non-empty"):
        judge(
            char, RailResult(exit_code=0, receipt_bytes=b'{"summary":"x"}'), JSON_SPEC
        )


def test_a_bom_only_required_field_is_PRESENT_on_both_runtimes() -> None:
    """JS ``trim()`` calls U+FEFF blank and reported schema-invalid where Python passed."""
    assert missing_fields({"summary": "\ufeff"}, JSON_SPEC) == ()


@pytest.mark.parametrize("char", PY_ONLY_BLANK)
def test_a_python_only_blank_required_field_is_MISSING_on_both_runtimes(
    char: str,
) -> None:
    assert missing_fields({"summary": char}, JSON_SPEC) == ("summary",)


def test_missing_fields_orders_by_utf16_code_unit() -> None:
    """MEASURED: Python returned (U+FFFD, astral) and JS returned (astral, U+FFFD)."""
    spec = ReceiptSpec(fmt="json", required_fields=("\U0001f600", "�"))
    assert missing_fields({}, spec) == ("\U0001f600", "�")


def test_a_nan_receipt_is_unparseable_rather_than_a_success() -> None:
    """MEASURED: ``json.dumps({"summary": nan})`` was SUCCESS here and severed on JS."""
    with pytest.raises(ReceiptUnparseable, match="invalid JSON"):
        parse_json_object('{"summary": NaN}')
    verdict = judge(
        "u", RailResult(exit_code=0, receipt_bytes=b'{"summary": NaN}'), JSON_SPEC
    )
    assert verdict.ok is False
    assert verdict.reason == "receipt-unparseable"


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_every_non_finite_json_literal_is_refused(literal: str) -> None:
    with pytest.raises(ReceiptUnparseable):
        parse_json_object('{"summary": %s}' % literal)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("[1]", "array"),
        ("1", "number"),
        ('"s"', "string"),
        ("null", "null"),
        ("true", "boolean"),
    ],
)
def test_a_non_object_top_level_is_named_in_the_portable_vocabulary(
    text: str, expected: str
) -> None:
    with pytest.raises(ReceiptUnparseable) as caught:
        parse_json_object(text)
    assert str(caught.value) == (
        f"receipt-unparseable: top level must be an object, got {expected}"
    )


def test_the_cmdline_cap_is_measured_in_the_unit_windows_counts() -> None:
    """MEASURED: 16,400 emoji were 16,402 code points here and 32,802 code units on JS."""
    flag = "\U0001f600" * 16400
    assert render_cmdline(("x", flag)) == f"x {flag}"
    assert wire.utf16_len(render_cmdline(("x", flag))) == 32802
    with pytest.raises(Exception) as caught:
        build_argv(
            exe="x",
            prompt="p",
            transport="file",
            flags=(flag,),
            prompt_flag="-f",
            prompt_path="/t",
        )
    assert getattr(caught.value, "reason", "") == "win-arg-limit"


def test_the_substring_scan_threshold_is_measured_in_utf16_code_units() -> None:
    """32 emoji are 64 code units: the substring rule fires on BOTH runtimes now."""
    prompt = "\U0001f600" * 32
    assert prompt_on_argv(f"z{prompt}", prompt) is True
    assert prompt_on_argv("z" + "\U0001f600" * 31, "\U0001f600" * 31) is False


def test_a_python_only_blank_argv_element_is_quoted_like_js_does_not_quote_a_bom() -> (
    None
):
    """``_quote`` used ``str.isspace()``; JS used ``/\\s/``, and the two disagree both ways."""
    assert render_cmdline(("a\x1cb",)) == '"a\x1cb"'
    assert render_cmdline(("a\ufeffb",)) == "a\ufeffb"


@pytest.mark.parametrize("timeout", [2.0, True, 9007199254740993])
def test_check_dispatch_refuses_every_value_js_refuses(timeout: object) -> None:
    """MEASURED: 2.0 was a TypeError here and accepted on JS; 2**53+1 was the reverse."""
    with pytest.raises(TypeError):
        check_dispatch(background=False, timeout_s=timeout, awaited=False)  # type: ignore[arg-type]


def test_check_dispatch_still_accepts_a_plain_integer_timeout() -> None:
    assert check_dispatch(background=False, timeout_s=30, awaited=False) == ()


@pytest.mark.parametrize("micro", [2.0, 9007199254740993])
def test_debit_refuses_every_amount_js_refuses(micro: object) -> None:
    with pytest.raises(TypeError):
        Ledger(limit_micro=10**15).debit("u", attempt=1, micro=micro)  # type: ignore[arg-type]


def test_a_ledger_limit_beyond_the_wire_range_is_refused_at_construction() -> None:
    """Bounding the LIMIT is what keeps ``cost_per_success`` exact in a double-only runtime."""
    with pytest.raises(TypeError):
        Ledger(limit_micro=9007199254740993)
    with pytest.raises(ValueError, match="limit_micro must be >= 0"):
        Ledger(limit_micro=-1)


def test_cost_per_success_refuses_a_non_integer_success_count() -> None:
    with pytest.raises(TypeError):
        cost_per_success(Ledger(limit_micro=10), successes=1.0)  # type: ignore[arg-type]


def test_cost_per_success_is_exact_at_the_top_of_the_wire_range() -> None:
    """Within the bounded range, ``//`` and ``Math.floor`` of a double agree exactly."""
    book = Ledger(limit_micro=wire.MAX_WIRE_INTEGER).debit(
        "u", attempt=1, micro=wire.MAX_WIRE_INTEGER
    )
    assert cost_per_success(book, successes=3) == 3002399751580330


def test_the_backoff_schedule_is_bounded_to_the_declared_attempt_ceiling() -> None:
    """MEASURED: attempt 60 gave an exact int here and a rounded double on JS."""
    assert rate_limit_backoff_ms(RATE_LIMIT_MAX_ATTEMPTS) == 32000
    with pytest.raises(ValueError, match="RATE_LIMIT_MAX_ATTEMPTS"):
        rate_limit_backoff_ms(60)
    with pytest.raises(ValueError, match="attempt must be >= 1"):
        rate_limit_backoff_ms(0)


def test_a_terminal_id_accepts_a_newly_assigned_code_point_on_both_runtimes() -> None:
    """4,803 code points were rejected here and accepted on JS purely from the ICU gap."""
    assert success_line("a࢏") == "SUCCESS:a࢏"
    with pytest.raises(ValueError):
        success_line("a\x1b")


def test_the_wire_detail_strings_render_lists_canonically() -> None:
    """``list(x)`` gave ``['summary']`` here and ``["summary"]`` on JS, on the wire."""
    verdict = judge("u", RailResult(exit_code=0, receipt_bytes=b'{"a":1}'), JSON_SPEC)
    assert verdict.detail == 'schema-invalid: missing or blank ["summary"]'
    marker_spec = ReceiptSpec(fmt="text", forbidden_markers=("todo",))
    incomplete = judge(
        "u", RailResult(exit_code=0, receipt_bytes=b"TODO later"), marker_spec
    )
    assert incomplete.detail == 'receipt-incomplete: body carries ["todo"]'


def test_an_invalid_utf8_receipt_names_no_interpreter_specific_cause() -> None:
    """The JS mirror hardcoded ``invalid continuation`` for bytes Python called a bad start."""
    verdict = judge("u", RailResult(exit_code=0, receipt_bytes=b"\xff"), JSON_SPEC)
    assert verdict.detail == "receipt-unparseable: not valid UTF-8"
