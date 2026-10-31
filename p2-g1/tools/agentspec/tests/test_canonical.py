"""The canonical JSON form — the rules that make a Python receipt byte-equal to a JS one.

Each test names the rule (R1-R15) it pins and, where one exists, the measured Python/JS
divergence that forced the rule. The cross-runtime half of this contract is the shared
conformance corpus at ``tools/agentspec-js/fixtures/canonical-corpus.json``, driven against
BOTH runtimes by ``tools/agentspec-js/parity/`` and byte-compared in CI; these tests are the
Python-side unit gate underneath it.
"""

from __future__ import annotations

import enum
import json
import math
from typing import Any

import pytest

from agentspec.canonical import (
    E_CYCLIC,
    E_INT_RANGE,
    E_INVALID_UTF8,
    E_KEY_COLLISION,
    E_KEY_TYPE,
    E_MAX_DEPTH,
    E_NONFINITE,
    E_VALUE_TYPE,
    MAX_DEPTH,
    MAX_SAFE_INTEGER,
    MIN_SAFE_INTEGER,
    REJECTION_CODES,
    CanonicalJsonError,
    dumpb,
    dumps,
    encode_string,
    loadb,
    loads,
    number_to_string,
    utf16_sort_key,
)
from agentspec.taxonomy import family


def test_every_rejection_code_resolves_to_the_existing_schema_invalid_member() -> None:
    """The six codes are segment-shaped, so the CLOSED taxonomy does not grow for this module."""
    assert REJECTION_CODES == tuple(sorted(REJECTION_CODES))
    assert len(set(REJECTION_CODES)) == len(REJECTION_CODES)
    for code in REJECTION_CODES:
        assert family(code) == "schema-invalid"
    assert family("schema-invalidate") == ""


def test_the_error_carries_the_taxonomy_reason_and_its_parts() -> None:
    error = CanonicalJsonError(E_INT_RANGE, "9007199254740993")
    assert error.reason == "schema-invalid"
    assert error.code == E_INT_RANGE
    assert error.detail == "9007199254740993"
    assert str(error) == "schema-invalid-int-range: 9007199254740993"


# --------------------------------------------------------------------------------------
# R2 separators / R3 key order / R4 key type
# --------------------------------------------------------------------------------------


def test_r2_no_insignificant_whitespace() -> None:
    """9 of the 75 probe cases diverge on separators ALONE: `{"a": 1}` vs `{"a":1}`."""
    assert dumps({"a": 1, "b": [1, 2]}) == '{"a":1,"b":[1,2]}'


def test_r3_keys_sort_by_utf16_code_unit_not_code_point() -> None:
    """MEASURED: `sort_keys=True` gives Python `1,10,2,b`; V8 gives `1,2,10,b`. Neither wins —
    the canonical order is imposed explicitly, as JS `.sort()` code-unit order."""
    assert dumps({"10": 0, "2": 0, "b": 0, "1": 0}) == '{"1":0,"10":0,"2":0,"b":0}'
    # An astral char sorts BEFORE U+FFFF because its lead surrogate 0xD83D < 0xFFFF.
    # Python's default code-point order gets this backwards.
    ordered = dumps({"\uffff": 1, "\U0001f600": 2})
    assert ordered == '{"\U0001f600":2,"\uffff":1}'
    assert sorted(["\uffff", "\U0001f600"]) == ["\uffff", "\U0001f600"]
    assert sorted(["\uffff", "\U0001f600"], key=utf16_sort_key) == [
        "\U0001f600",
        "\uffff",
    ]


def test_r3_utf16_sort_key_survives_a_lone_surrogate() -> None:
    """`surrogatepass` is required: a lone surrogate is not encodable as plain UTF-16."""
    assert utf16_sort_key("\ud800") == b"\xd8\x00"


def test_r4_a_non_string_key_is_rejected_never_coerced() -> None:
    """Python renders `{1.0: x}` as "1.0" and JS renders it "1" — silently, and differently."""
    with pytest.raises(CanonicalJsonError) as caught:
        dumps({1: "x"})
    assert caught.value.code == E_KEY_TYPE
    assert caught.value.detail == "int"


def test_r4_the_key_check_runs_before_any_output_is_emitted() -> None:
    """A rejection must never leave a half-written object behind."""
    with pytest.raises(CanonicalJsonError) as caught:
        dumps({"ok": 1, (1, 2): "bad"})
    assert caught.value.code == E_KEY_TYPE


# --------------------------------------------------------------------------------------
# R5 / R6 / R9 number rendering
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, "0"),
        (-0.0, "0"),  # R9: Python renders -0.0, JS renders 0. ES wins.
        (1.0, "1"),  # R6: the int/float tag is erased.
        (-1.0, "-1"),
        (100.0, "100"),
        (1.5, "1.5"),
        (-1.5, "-1.5"),
        (0.1, "0.1"),
        (0.30000000000000004, "0.30000000000000004"),
        (1e-6, "0.000001"),  # Python: 1e-06. ES: 0.000001.
        (1e-7, "1e-7"),  # Python: 1e-07 — ES never zero-pads the exponent.
        (1e15, "1000000000000000"),
        (1e16, "10000000000000000"),  # Python: 1e+16 — ES switches at 1e21, not 1e16.
        (1e20, "100000000000000000000"),
        (1e21, "1e+21"),
        (-1e21, "-1e+21"),
        (1e100, "1e+100"),
        (1.5e300, "1.5e+300"),
        (5e-324, "5e-324"),
        (1.7976931348623157e308, "1.7976931348623157e+308"),
        (9007199254740992.0, "9007199254740992"),
        (9.223372036854776e18, "9223372036854776000"),
    ],
)
def test_r5_number_rendering_matches_ecmascript_number_to_string(
    value: float, expected: str
) -> None:
    """Validated against JS `String(x)` on 209,442 distinct doubles with zero mismatches."""
    assert number_to_string(value) == expected


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_r8_non_finite_is_rejected_on_both_sides(value: float) -> None:
    """Python emits bare `NaN` (invalid JSON); JS emits `null` (silent data loss)."""
    with pytest.raises(CanonicalJsonError) as caught:
        number_to_string(value)
    assert caught.value.code == E_NONFINITE


def test_r8_non_finite_is_rejected_through_the_top_level_encoder_too() -> None:
    with pytest.raises(CanonicalJsonError) as caught:
        dumps({"score": math.nan})
    assert caught.value.code == E_NONFINITE


def test_r6_an_integral_float_and_an_int_are_indistinguishable_on_the_wire() -> None:
    """Stated, not discovered: R6 is lossy by design and both runtimes are lossy the same way."""
    assert dumps(1.0) == dumps(1) == "1"


# --------------------------------------------------------------------------------------
# R7 safe-integer range
# --------------------------------------------------------------------------------------


def test_r7_integer_typed_values_are_bounded_by_the_safe_range() -> None:
    assert dumps(MAX_SAFE_INTEGER) == "9007199254740991"
    assert dumps(MIN_SAFE_INTEGER) == "-9007199254740991"


@pytest.mark.parametrize("value", [MAX_SAFE_INTEGER + 1, MIN_SAFE_INTEGER - 1, 10**30])
def test_r7_an_integer_beyond_the_safe_range_is_rejected(value: int) -> None:
    """`JSON.parse("9007199254740993")` silently returns ...992; a BigInt cannot stringify at
    all. Rejecting is the only option that does not lie."""
    with pytest.raises(CanonicalJsonError) as caught:
        dumps(value)
    assert caught.value.code == E_INT_RANGE


def test_r7_the_range_rule_belongs_to_the_INTEGER_type_never_to_a_double() -> None:
    """A double claims no precision beyond IEEE-754, so any finite magnitude is fine.
    Applying `isSafeInteger` to a double wrongly rejected 1e16/1e21/1e100/MAX_VALUE."""
    assert dumps(1e100) == "1e+100"
    assert dumps(float(10**30)) == "1e+30"


def test_bool_is_a_literal_and_never_reaches_the_integer_path() -> None:
    """`isinstance(True, int)` is True in Python; identity matching keeps it out."""
    assert dumps([True, False, None]) == "[true,false,null]"


# --------------------------------------------------------------------------------------
# R10 / R11 string escaping
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", '""'),
        ("abc", '"abc"'),
        ("\b\t\n\f\r", '"\\b\\t\\n\\f\\r"'),
        ('a"b\\c', '"a\\"b\\\\c"'),
        ("a/b", '"a/b"'),  # the solidus is NOT escaped
        ("\x00", '"\\u0000"'),
        ("\x1f", '"\\u001f"'),  # lowercase hex, both runtimes
        ("\x7f", '"\x7f"'),  # DEL is raw: Python escapes it, ES does not
        ("é", '"é"'),  # ensure_ascii would escape this; ES does not
        ("\u2028", '"\\u2028"'),  # R11
        ("\u2029", '"\\u2029"'),  # R11
        ("\U0001f600", '"\U0001f600"'),
        ("😀", '"😀"'),  # a well-formed surrogate PAIR stays raw
    ],
)
def test_r10_and_r11_string_escaping(text: str, expected: str) -> None:
    assert encode_string(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("\ud800", '"\\ud800"'),  # lone high surrogate, end of string
        ("\ud800a", '"\\ud800a"'),  # lone high surrogate, next char is not low
        ("\udc00", '"\\udc00"'),  # lone low surrogate
        ("\ud800\ud800", '"\\ud800\\ud800"'),  # high followed by high
    ],
)
def test_r10_unpaired_surrogates_are_escaped(text: str, expected: str) -> None:
    """MEASURED counter-intuitive result: these AGREE naively but break under the "obvious"
    tuning — with `ensure_ascii=False` the Python str cannot be encoded to UTF-8 at all."""
    assert encode_string(text) == expected
    assert dumpb(text).decode("utf-8") == expected


def test_r10_a_well_formed_surrogate_pair_folds_to_its_astral_code_point() -> None:
    """The ONE place the two string MODELS are reconciled. Python `"\\ud83d\\ude00"` is two
    lone surrogates; the same JS string is one astral char. Folding makes them agree — and
    without it `dumpb` emits raw surrogates and dies with UnicodeEncodeError."""
    paired = "\ud83d\ude00"  # two lone surrogates in Python's model
    assert len(paired) == 2
    assert encode_string(paired) == '"\U0001f600"'
    assert dumpb(paired) == dumpb("\U0001f600") == b'"\xf0\x9f\x98\x80"'
    # The fold is exact across the whole astral range, not just the emoji block.
    assert encode_string("\udbff\udfff") == '"\U0010ffff"'


def test_r1_the_canonical_bytes_are_always_valid_utf8() -> None:
    """Because R10 escapes lone surrogates FIRST, `dumpb` can never raise on encode."""
    assert dumpb({"k": "\ud800"}) == b'{"k":"\\ud800"}'
    assert dumpb("\ufeff") == b'"\xef\xbb\xbf"'  # a BOM inside a string is DATA


# --------------------------------------------------------------------------------------
# R12 accepted types / R13 depth / cycles
# --------------------------------------------------------------------------------------


def test_r12_a_tuple_encodes_as_an_array_like_a_list() -> None:
    assert dumps((1, "a")) == dumps([1, "a"]) == '[1,"a"]'


def test_r12_empty_containers() -> None:
    assert dumps([]) == "[]"
    assert dumps({}) == "{}"
    assert dumps({"a": [], "b": {}}) == '{"a":[],"b":{}}'


@pytest.mark.parametrize("value", [{1, 2}, object(), b"bytes"])
def test_r12_an_unsupported_type_is_rejected_with_no_tojson_hook(value: Any) -> None:
    """`JSON.stringify` silently mangles Date/Map/Set/boxed primitives and lets a `toJSON`
    property hijack the whole document. Python has no counterpart, so nothing is coerced."""
    with pytest.raises(CanonicalJsonError) as caught:
        dumps(value)
    assert caught.value.code == E_VALUE_TYPE


def test_r13_depth_at_the_cap_is_accepted() -> None:
    value: Any = 1
    for _ in range(MAX_DEPTH):
        value = [value]
    assert dumps(value).count("[") == MAX_DEPTH


def test_r13_depth_beyond_the_cap_is_rejected_identically_on_both_runtimes() -> None:
    """Without an explicit cap the boundary is Python's recursion limit on one side and V8's
    stack on the other — i.e. platform-dependent, which is exactly what parity forbids."""
    value: Any = 1
    for _ in range(MAX_DEPTH + 1):
        value = [value]
    with pytest.raises(CanonicalJsonError) as caught:
        dumps(value)
    assert caught.value.code == E_MAX_DEPTH


def test_r13_the_depth_cap_applies_to_objects_too() -> None:
    value: Any = 1
    for _ in range(MAX_DEPTH + 1):
        value = {"n": value}
    with pytest.raises(CanonicalJsonError) as caught:
        dumps(value)
    assert caught.value.code == E_MAX_DEPTH


def test_a_reference_cycle_is_rejected() -> None:
    cyclic: list[Any] = []
    cyclic.append(cyclic)
    with pytest.raises(CanonicalJsonError) as caught:
        dumps(cyclic)
    assert caught.value.code == E_CYCLIC


def test_a_cyclic_mapping_is_rejected() -> None:
    cyclic: dict[str, Any] = {}
    cyclic["self"] = cyclic
    with pytest.raises(CanonicalJsonError) as caught:
        dumps(cyclic)
    assert caught.value.code == E_CYCLIC


def test_a_shared_but_acyclic_subobject_is_NOT_a_cycle() -> None:
    """The guard tracks ANCESTORS only; a diamond is legal JSON and must encode."""
    shared = {"x": 1}
    assert dumps([shared, shared]) == '[{"x":1},{"x":1}]'


# --------------------------------------------------------------------------------------
# R14 / R15 decoder
# --------------------------------------------------------------------------------------


def test_r14_bare_non_finite_literals_are_rejected_on_decode() -> None:
    """MEASURED: `json.loads("NaN")` ACCEPTS and returns nan; `JSON.parse("NaN")` raises."""
    assert math.isnan(json.loads("NaN"))
    for literal in ("NaN", "Infinity", "-Infinity"):
        with pytest.raises(CanonicalJsonError) as caught:
            loads(literal)
        assert caught.value.code == E_NONFINITE


def test_r15_an_in_range_integer_literal_decodes_to_int() -> None:
    assert loads("42") == 42
    assert isinstance(loads("42"), int)


def test_r15_an_out_of_range_integer_literal_decodes_to_float() -> None:
    """Without R15 the round trip is NOT a fixed point: R6 renders float(1e16) as
    10000000000000000, `json.loads` reads that back as a big int, and R7 then rejects it."""
    decoded = loads("10000000000000000")
    assert isinstance(decoded, float)
    assert decoded == 1e16


def test_loadb_decodes_canonical_bytes() -> None:
    assert loadb(b'{"a":[1,2]}') == {"a": [1, 2]}


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        1,
        1.5,
        "text",
        [],
        {},
        {"a": [1, {"b": None}], "z": "é"},
        1e16,
        1e21,
        -1e21,
        9007199254740992.0,
        MAX_SAFE_INTEGER,
    ],
)
def test_encode_decode_encode_is_a_fixed_point(value: Any) -> None:
    """67 canonical documents x 3 directions (py->py, js->py, py->js): 0 failures."""
    once = dumps(value)
    assert dumps(loads(once)) == once


_ASTRAL = chr(0x1F600)
"""The astral character a JS string holds as ONE well-formed surrogate PAIR."""

_LONE_PAIR = chr(0xD83D) + chr(0xDE00)
"""The SAME two UTF-16 units as two SEPARATE Python code points — a value JS cannot express."""


class _HijackedInt(int):
    """An ``int`` subclass whose ``__str__`` lies. R12's dispatch admits it via isinstance."""

    def __str__(self) -> str:
        return "PWNED"


class _HijackedIntRepr(int):
    """Overrides ``__repr__`` — the door ``int.__str__`` leaves WIDE OPEN.

    ``int.__str__ is object.__str__`` is True and ``object.__str__`` delegates to
    ``type(x).__repr__``, so an "unbound ``__str__``" call does not escape the subclass.
    """

    def __repr__(self) -> str:
        return "PWNED_REPR"


class _HijackedIntFormat(int):
    """Overrides ``__format__`` — the door ``f"{v:d}"`` leaves open."""

    def __format__(self, spec: str) -> str:
        return "PWNED_FMT"


class _Colour(enum.IntEnum):
    RED = 1


class _Perm(enum.IntFlag):
    A = 1


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (_HijackedInt(5), b"5"),
        (_HijackedIntRepr(5), b"5"),
        (_HijackedIntFormat(5), b"5"),
        (_Colour.RED, b"1"),
        (_Perm.A, b"1"),
        (5, b"5"),
    ],
    ids=["str-sub", "repr-sub", "format-sub", "IntEnum", "IntFlag", "plain"],
)
def test_R12_no_int_subclass_can_inject_its_own_rendering(
    value: int, expected: bytes
) -> None:
    """Every dunder an int subclass can override, plus the two stdlib enum int types.

    MEASURED history, both directions:
    * ``str(value)``        emitted ``{"a":PWNED}``      — hijacked by ``__str__`` AND ``__repr__``
    * ``int.__str__(value)`` emitted ``{"a":PWNED_REPR}`` — still hijacked by ``__repr__``, and
      REGRESSED ``IntEnum``/``IntFlag`` to ``<_Colour.RED: 1>``, which ``json.loads`` refuses
    * ``f"{value:d}"``      is hijacked by ``__format__``
    Only ``int.__repr__(value)`` survives all six rows. The previous test overrode ONLY
    ``__str__`` — the one door the broken fix closed — so the test and the fix were mutually
    confirming and jointly blind. That is why this is parametrised over every override.
    """
    assert dumpb(value) == expected
    assert dumpb({"a": value}) == b'{"a":' + expected + b"}"
    assert json.loads(dumps({"a": value})) == {"a": int(value)}


def test_R12_the_out_of_range_detail_reports_the_REAL_number() -> None:
    """A hostile subclass must not control the error text either."""

    class _Big(int):
        def __repr__(self) -> str:
            return "PWNED_IN_THE_ERROR"

    with pytest.raises(CanonicalJsonError) as exc:
        dumpb(_Big(MAX_SAFE_INTEGER + 1))
    assert "PWNED" not in str(exc.value)
    assert str(MAX_SAFE_INTEGER + 1) in str(exc.value)


def test_R12_an_out_of_range_int_subclass_still_reports_its_real_value() -> None:
    """The rejection detail must be the NUMBER, not whatever the subclass wanted to print."""
    with pytest.raises(CanonicalJsonError) as caught:
        dumps(_HijackedInt(MAX_SAFE_INTEGER + 1))
    assert caught.value.code == E_INT_RANGE
    assert caught.value.detail == "9007199254740992"


def test_R4b_two_keys_that_fold_to_one_wire_key_are_REJECTED() -> None:
    """MEASURED: the fold emitted a DUPLICATE key, which RFC 8259 calls non-interoperable.

    It also falsified this module's own documented fixed point — re-encoding the decoded
    document gave a ONE-key object, so ``dumps(loads(dumps(x))) != dumps(x)``.
    """
    with pytest.raises(CanonicalJsonError) as caught:
        dumps({_ASTRAL: 1, _LONE_PAIR: 2})
    assert caught.value.code == E_KEY_COLLISION
    assert E_KEY_COLLISION in REJECTION_CODES


def test_R4b_stays_silent_when_the_fold_creates_no_collision() -> None:
    """The detector control: a folded key that is UNIQUE still encodes, and still round-trips."""
    once = dumps({_LONE_PAIR: 2, "a": 1})
    assert once == '{"a":1,"' + _ASTRAL + '":2}'
    assert dumps(loads(once)) == once


CORRUPT_BYTES = [
    ("bad-start", b'"' + bytes([0xFF]) + b'"'),
    ("truncated", b'"' + bytes([0xE2, 0x82]) + b'"'),
    ("overlong", b'"' + bytes([0xC0, 0xAF]) + b'"'),
    ("cesu8-surrogate", b'"' + bytes([0xED, 0xA0, 0xBD]) + b'"'),
    ("inside-object", b'{"a":"' + bytes([0xFF]) + b'"}'),
]


@pytest.mark.parametrize(
    ("label", "raw"), CORRUPT_BYTES, ids=[c[0] for c in CORRUPT_BYTES]
)
def test_loadb_REFUSES_corrupt_bytes_with_a_shared_canonical_code(
    label: str, raw: bytes
) -> None:
    """MEASURED: the JS mirror ACCEPTED all five, substituting U+FFFD and never throwing.

    `dumpb(loadb(corrupt))` there produced a well-formed, plausible-looking canonical receipt
    manufactured out of corrupt input, on a path this runtime halts. The failure now carries a
    taxonomy CODE rather than this interpreter's ``UnicodeDecodeError``, because JS has no such
    exception and the two runtimes must name the same failure.
    """
    with pytest.raises(CanonicalJsonError) as caught:
        loadb(raw)
    assert caught.value.code == E_INVALID_UTF8
    assert caught.value.detail == "not valid UTF-8"


def test_loadb_still_accepts_valid_bytes_including_a_BOM_as_data() -> None:
    """The detector control: the strict decode must not reject the happy path or a BOM."""
    assert loadb(b'{"a":1}') == {"a": 1}
    assert loadb('{"\ufeff":1}'.encode("utf-8")) == {"\ufeff": 1}
