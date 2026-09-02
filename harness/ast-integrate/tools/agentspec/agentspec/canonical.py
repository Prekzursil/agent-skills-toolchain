"""CANONICAL JSON — the ONE serialisation both runtimes must reproduce byte-for-byte.

This module exists because a receipt written by the Python runtime and a receipt written by
the JS runtime have to be the SAME BYTES, and the stock encoders are not close. MEASURED on a
75-case differential probe (CPython 3.11 vs Node 22 and Node 24): stock ``json.dumps`` and
stock ``JSON.stringify`` disagree on **47 of 75 cases (62.7%)**, and on **15 of 15** container
cases that carry at least one object key or two array elements — i.e. every realistic receipt.
Configuring the two stdlib encoders towards each other (``ensure_ascii=False``,
``separators``, ``sort_keys``, ``allow_nan=False``) only reaches 43/75; **32 cases still
diverge**, so the canonical form is a CUSTOM encoder on both sides, never a tuned stdlib call.

The rules, each tied to the measured row that forced it:

* **R1** UTF-8 bytes, no BOM. A BOM *inside* a string is data and survives.
* **R2** No insignificant whitespace; separators are exactly ``,`` and ``:``. (9 cases diverge
  on separators alone: ``{"a": 1}`` vs ``{"a":1}``.)
* **R3** Object keys sorted ascending by **UTF-16 code-unit** sequence — JS ``.sort()`` order,
  NOT Python's code-point ``str`` order. ``sort_keys=True`` does NOT fix this: V8 emits
  integer-like keys first in ascending numeric order. Measured on ``{"10","2","b","1"}``:
  Python ``1,10,2,b`` vs JS ``1,2,10,b``. Code-unit order also puts an astral emoji BEFORE
  ``U+FFFF`` (lead surrogate ``0xD83D`` < ``0xFFFF``), which code-point order gets backwards.
* **R4** Keys must be ``str``. A non-string key is REJECTED, never coerced — Python renders
  a dict holding BOTH the astral code point AND the same character as two separate lone
  surrogate code points folded to a document with a DUPLICATE key, which
  RFC 8259 calls non-interoperable and which falsified :func:`loads`' own stated fixed point
  (``dumps(loads(dumps(x))) == dumps(x)`` returned the 2-key document as a 1-key document).
  The JS encoder is injective by construction and cannot reach this arm; the code exists on
  both sides so the closed rejection set stays identical.
* **R5** Numbers rendered by the ECMAScript ``Number::toString`` algorithm (ECMA-262
  6.1.6.1.20). JS gets this from ``String(x)``; Python must implement it, because Python
  switches to exponential at 1e16 while ECMAScript switches at 1e21, and Python zero-pads the
  exponent (``1e-05`` vs ``1e-5``). :func:`number_to_string` is validated against ``String(x)``
  on **209,442 distinct doubles with zero mismatches**.
* **R6** The int/float TAG is erased: an integral real emits with no fractional part, so a
  Python ``1.0`` and a Python ``1`` are indistinguishable on the wire — exactly as in JS.
  Lossy by design, and stated rather than discovered.
* **R7** INTEGER-TYPED values (Python ``int``, JS ``BigInt``) outside ±(2**53 - 1) are
  REJECTED. A ``float`` is a double and claims no precision beyond IEEE-754, so ANY finite
  double is accepted whatever its magnitude: ``1e100`` is fine, ``int(10**30)`` is not.
* **R8** ``NaN`` / ``±Infinity`` are REJECTED. Python emits bare ``NaN`` (invalid JSON) and JS
  emits ``null`` (silent data loss); neither can be preferred, so neither is allowed.
* **R9** ``-0.0`` normalises to ``0``, adopting ES ``Number::toString(-0)``.
* **R10** Escaping is ES2019 ``QuoteJSONString`` (well-formed): ``"``, ``\\`` and C0 with the
  short forms, else lowercase ``\\u00xx``; UNPAIRED surrogates escaped as lowercase
  ``\\udxxx``; everything else raw UTF-8. Escaping unpaired surrogates is not cosmetic — with
  ``ensure_ascii=False`` a lone surrogate makes the Python ``str`` impossible to encode to
  UTF-8 at all, so the "obvious" tuning makes that case strictly WORSE than the default.
* **R11** ``U+2028`` / ``U+2029`` are ALSO escaped. A deliberate, symmetric deviation from
  ``JSON.stringify``: cost zero, and a raw U+2028 splits a physical source line.
* **R12** Only ``str``/``int``/``float``/``bool``/``None``/``list``/``tuple``/``dict`` are
  accepted, and there is NO ``toJSON`` hook. ``JSON.stringify`` silently mangles ``Date``,
  ``Map``, ``Set``, boxed primitives and array holes, and a ``toJSON`` property can hijack the
  whole document — Python has no counterpart for any of it.
* **R13** Maximum nesting depth :data:`MAX_DEPTH`. Python's recursion limit trips far earlier
  than V8's stack, so without an explicit shared cap the boundary is platform-dependent.
* **R14** DECODER: bare ``NaN`` / ``Infinity`` / ``-Infinity`` literals are rejected. Measured:
  ``json.loads("NaN")`` ACCEPTS, ``JSON.parse("NaN")`` raises — left at defaults a Python
  consumer silently ingests a document a JS consumer refuses.
* **R15** DECODER: a bare integer literal outside the safe range decodes to ``float``,
  mirroring R6. Without it ``encode(decode(encode(x)))`` is NOT a fixed point in Python: R6
  renders ``float(1e16)`` as ``10000000000000000``, ``json.loads`` reads that back as a big
  ``int``, and the next encode rejects it under R7. JS needs no equivalent — ``JSON.parse``
  always yields a double.

* **R16** DECODER: :func:`loadb` REFUSES bytes that are not valid UTF-8, and reports it as
  :data:`E_INVALID_UTF8` rather than as this interpreter's ``UnicodeDecodeError``. JS has no
  such exception and its default byte decode is LOSSY — measured, ``loadb`` there returned a
  well-formed value with U+FFFD substituted where this side raised, so ``dumpb(loadb(x)))``
  manufactured a plausible-looking canonical receipt out of corrupt input.

Every rejection code is *segment*-shaped, so :func:`agentspec.taxonomy.family` resolves all
eight to the existing closed member ``schema-invalid``. The taxonomy does NOT grow for this
module.

The rules above make the two runtimes agree on the BYTES. Agreeing on the DECISIONS is
:mod:`agentspec.wire`'s job, and it is a separate contract with a separate corpus — a
differential harness found 78 behavioural divergences while this module was already exact.

Pure: no clock, no entropy, no I/O. :func:`agentspec.determinism.scan_package` covers it.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from agentspec.wire import utf16_sort_key as utf16_sort_key

MAX_SAFE_INTEGER = 2**53 - 1
"""R7. Beyond this an integer-typed value cannot survive a JS ``Number`` round trip."""

MIN_SAFE_INTEGER = -(2**53 - 1)

MAX_DEPTH = 100
"""R13. The shared nesting cap, so the boundary is identical on both runtimes."""

E_NONFINITE = "schema-invalid-nonfinite"
E_INT_RANGE = "schema-invalid-int-range"
E_KEY_TYPE = "schema-invalid-nonstring-key"
E_KEY_COLLISION = "schema-invalid-key-collision"
E_VALUE_TYPE = "schema-invalid-unsupported-type"
E_CYCLIC = "schema-invalid-cyclic"
E_MAX_DEPTH = "schema-invalid-max-depth"
E_INVALID_UTF8 = "schema-invalid-utf8"

REJECTION_CODES: tuple[str, ...] = (
    E_CYCLIC,
    E_INT_RANGE,
    E_KEY_COLLISION,
    E_MAX_DEPTH,
    E_NONFINITE,
    E_KEY_TYPE,
    E_VALUE_TYPE,
    E_INVALID_UTF8,
)
"""Sorted and CLOSED. The JS mirror asserts set equality against this tuple."""

_SHORT_ESCAPES: dict[int, str] = {
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0C: "\\f",
    0x0D: "\\r",
    0x22: '\\"',
    0x5C: "\\\\",
}

_LINE_SEPARATORS: tuple[int, int] = (0x2028, 0x2029)

_HIGH_SURROGATE_FIRST = 0xD800
_HIGH_SURROGATE_LAST = 0xDBFF
_LOW_SURROGATE_FIRST = 0xDC00
_LOW_SURROGATE_LAST = 0xDFFF


class CanonicalJsonError(ValueError):
    """A value canonical JSON refuses to represent, carrying its ``schema-invalid`` sub-code."""

    reason = "schema-invalid"

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


CanonicalError = CanonicalJsonError


def export(workflow: Any) -> bytes:
    return dumpb(workflow)


def import_workflow(data: Any) -> Any:
    if isinstance(data, bytes):
        return loadb(data)
    if isinstance(data, str):
        return loads(data)
    return data


def round_trip_bytes(data: bytes) -> bytes:
    return dumpb(import_workflow(data))


def round_trip_workflow(workflow: Any) -> Any:
    return import_workflow(export(workflow))


def encode_string(text: str) -> str:
    """R10/R11. ES2019 well-formed ``QuoteJSONString`` with U+2028/U+2029 also escaped."""
    out: list[str] = ['"']
    index = 0
    size = len(text)
    while index < size:
        char = text[index]
        code = ord(char)
        short = _SHORT_ESCAPES.get(code)
        if short is not None:
            out.append(short)
        elif code < 0x20 or code in _LINE_SEPARATORS:
            out.append(f"\\u{code:04x}")
        elif _HIGH_SURROGATE_FIRST <= code <= _HIGH_SURROGATE_LAST:
            low = _low_surrogate_at(text, index + 1, size)
            if low is not None:
                out.append(_fold_surrogate_pair(code, low))
                index += 2
                continue
            out.append(f"\\u{code:04x}")
        elif _LOW_SURROGATE_FIRST <= code <= _LOW_SURROGATE_LAST:
            out.append(f"\\u{code:04x}")
        else:
            out.append(char)
        index += 1
    out.append('"')
    return "".join(out)


def number_to_string(value: float) -> str:
    """R5/R6/R9. ECMAScript ``Number::toString`` (ECMA-262 6.1.6.1.20) for a finite double."""
    if value != value or value in (float("inf"), float("-inf")):
        raise CanonicalJsonError(E_NONFINITE, repr(value))
    if value == 0.0:
        return "0"
    sign = "-" if value < 0 else ""
    digits, exponent = _shortest_digits(abs(value))
    count = len(digits)
    point = exponent + count
    if count <= point <= 21:
        return sign + digits + "0" * (point - count)
    if 0 < point <= 21:
        return sign + digits[:point] + "." + digits[point:]
    if -6 < point <= 0:
        return sign + "0." + "0" * (-point) + digits
    return sign + _exponential(digits, count, point - 1)


def dumps(value: Any) -> str:
    """The canonical TEXT for ``value``."""
    out: list[str] = []
    _encode(value, out, 0, ())
    return "".join(out)


def dumpb(value: Any) -> bytes:
    """R1. The canonical BYTES: always valid UTF-8, because R10 escapes lone surrogates."""
    return dumps(value).encode("utf-8")


def round_trip_ok(value: Any) -> bool:
    """True iff dumps(loads(dumps(value))) equals dumps(value)."""
    encoded = dumps(value)
    return dumps(loads(encoded)) == encoded


def loads(text: str) -> Any:
    """R14/R15. Decode canonical JSON so ``dumps(loads(dumps(x))) == dumps(x)`` holds."""
    return json.loads(text, parse_constant=_reject_constant, parse_int=_parse_int)


def loadb(raw: bytes) -> Any:
    """Decode canonical BYTES, REFUSING a lossy decode.

    The failure is reported as a :class:`CanonicalJsonError` rather than as this
    interpreter's ``UnicodeDecodeError`` because the JS mirror has no such exception:
    ``Buffer.toString('utf8')`` is LOSSY by default (it substitutes U+FFFD and never
    throws), so the JS side had to be given a fatal ``TextDecoder`` AND a shared error
    class. MEASURED before the fix: ``loadb(b'{\"a\":\"\\xff\"}')`` raised here and
    returned a well-formed ``{\"a\":\"\\ufffd\"}`` there — a plausible-looking canonical
    receipt manufactured out of corrupt bytes, on a path this runtime halts.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CanonicalJsonError(E_INVALID_UTF8, "not valid UTF-8") from exc
    return loads(text)


def _low_surrogate_at(text: str, index: int, size: int) -> int | None:
    """The low-surrogate code unit at ``index``, or ``None`` when the pair is not well-formed."""
    if index >= size:
        return None
    code = ord(text[index])
    if _LOW_SURROGATE_FIRST <= code <= _LOW_SURROGATE_LAST:
        return code
    return None


def _fold_surrogate_pair(high: int, low: int) -> str:
    """THE ONE PLACE the two languages' string MODELS are reconciled.

    A JS string is a sequence of UTF-16 CODE UNITS; a Python ``str`` is a sequence of CODE
    POINTS. So a JS astral character is one well-formed surrogate pair, while the same
    character in Python is a single code point and a Python surrogate is unpaired BY
    CONSTRUCTION. Folding an adjacent well-formed pair back into its astral code point makes
    the two models agree: Python ``"\\ud83d\\ude00"`` and Python ``"\\U0001f600"`` both encode
    to the bytes JS produces for its single string.

    HONEST COST, stated rather than discovered: this is lossy in one direction. Python CAN
    represent "a lone high surrogate immediately followed by a lone low surrogate" as a value
    distinct from the astral character; JS cannot represent that at all. Folding is the only
    mapping that keeps parity TOTAL, so that one degenerate Python value is normalised away.
    Not folding is worse than lossy — it emits raw surrogates, and :func:`dumpb` then dies with
    ``UnicodeEncodeError`` instead of producing bytes (measured while building this module).

    THE CONSEQUENCE THAT WAS MISSED FIRST TIME: inside a MAPPING the fold is not merely a value
    normalisation, it is a KEY COLLISION. Two distinct dict keys folded onto one wire key and
    the encoder emitted a duplicate-key document. R4b now rejects that, so the lossiness stays
    confined to scalar values where it is a normalisation, and can never produce a document the
    module's own round-trip invariant does not hold for.
    """
    return chr(
        0x10000 + ((high - _HIGH_SURROGATE_FIRST) << 10) + (low - _LOW_SURROGATE_FIRST)
    )


def _shortest_digits(magnitude: float) -> tuple[str, int]:
    """The shortest round-tripping significand of ``magnitude``, trailing zeros stripped.

    ``repr`` has produced the shortest round-tripping decimal since CPython 3.1, so this reads
    that rather than re-deriving Grisu/Ryu. :class:`~decimal.Decimal` is used only to split the
    literal into digits and an exponent without string surgery.
    """
    _, raw_digits, raw_exponent = Decimal(repr(magnitude)).as_tuple()
    digits = list(raw_digits)
    exponent = int(raw_exponent)
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop()
        exponent += 1
    return "".join(str(digit) for digit in digits), exponent


def _exponential(digits: str, count: int, power: int) -> str:
    """R5's exponential form; the exponent sign is explicit and NEVER zero-padded."""
    sign = "+" if power >= 0 else "-"
    if count == 1:
        return f"{digits}e{sign}{abs(power)}"
    return f"{digits[0]}.{digits[1:]}e{sign}{abs(power)}"


def _encode(value: Any, out: list[str], depth: int, seen: tuple[int, ...]) -> None:
    """R12. The closed dispatch over accepted types; anything else is rejected."""
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, str):
        out.append(encode_string(value))
    elif isinstance(value, int):
        out.append(_encode_int(value))
    elif isinstance(value, float):
        out.append(number_to_string(value))
    elif isinstance(value, dict):
        _encode_container(value, out, depth, seen, _encode_mapping)
    elif isinstance(value, (list, tuple)):
        _encode_container(value, out, depth, seen, _encode_sequence)
    else:
        raise CanonicalJsonError(E_VALUE_TYPE, type(value).__name__)


def _encode_int(value: int) -> str:
    """R7. ``bool`` never reaches here — :func:`_encode` matches it first, by identity.

    ``int.__repr__`` is called UNBOUND on purpose, and it must be ``__repr__`` -- not
    ``__str__``, not ``str()``, not ``f"{value:d}"``. ``isinstance(value, int)`` admits
    arbitrary subclasses, and each of the other three renderings can be hijacked by one:

    ==================  =====  ============  ===========  ==============  =======  =======
    candidate           plain  __repr__ sub  __str__ sub  __format__ sub  IntEnum  IntFlag
    ==================  =====  ============  ===========  ==============  =======  =======
    ``str(v)``          5      **PWNED**     **PWNED**    5               1        1
    ``int.__str__(v)``  5      **PWNED**     5            5               **bad**  **bad**
    ``f"{v:d}"``        5      5             5            **PWNED**       1        1
    ``int.__repr__(v)`` 5      5             5            5               1        1
    ==================  =====  ============  ===========  ==============  =======  =======

    ``int.__str__`` looks like the safe unbound call but is NOT: ``int.__str__ is
    object.__str__`` is ``True``, and ``object.__str__`` delegates to ``type(x).__repr__`` --
    so it does not escape the subclass, it only moves which dunder hijacks it. It also renders
    stdlib ``IntEnum``/``IntFlag`` as ``<Colour.RED: 1>``, which ``json.loads`` refuses.
    MEASURED on CPython 3.11 (CI), 3.12 and 3.14 -- not a local-interpreter artifact.

    The JS side has no counterpart: a boxed ``new Number(5)`` is already rejected as an
    unsupported type, so this is the one place Python's structural typing is laxer than JS's.
    """
    if not MIN_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
        raise CanonicalJsonError(E_INT_RANGE, int.__repr__(value))
    return int.__repr__(value)


def _encode_container(
    value: Any,
    out: list[str],
    depth: int,
    seen: tuple[int, ...],
    body: Any,
) -> None:
    """R13 + the cycle guard, shared by both container kinds so neither can drift."""
    if id(value) in seen:
        raise CanonicalJsonError(E_CYCLIC, type(value).__name__)
    if depth >= MAX_DEPTH:
        raise CanonicalJsonError(E_MAX_DEPTH, f"nesting exceeds {MAX_DEPTH}")
    body(value, out, depth + 1, (*seen, id(value)))


def _encode_mapping(
    value: dict[Any, Any], out: list[str], depth: int, seen: tuple[int, ...]
) -> None:
    """R3/R4/R4b. Keys checked before ANY output, so a rejection never emits a partial object."""
    for key in value:
        if not isinstance(key, str):
            raise CanonicalJsonError(E_KEY_TYPE, type(key).__name__)
    ordered = sorted(value, key=utf16_sort_key)
    rendered: list[str] = []
    emitted: set[str] = set()
    for key in ordered:
        wire_key = encode_string(key)
        if wire_key in emitted:
            raise CanonicalJsonError(E_KEY_COLLISION, wire_key)
        emitted.add(wire_key)
        rendered.append(wire_key)
    out.append("{")
    for position, key in enumerate(ordered):
        if position:
            out.append(",")
        out.append(rendered[position])
        out.append(":")
        _encode(value[key], out, depth, seen)
    out.append("}")


def _encode_sequence(
    value: Any, out: list[str], depth: int, seen: tuple[int, ...]
) -> None:
    out.append("[")
    for position, item in enumerate(value):
        if position:
            out.append(",")
        _encode(item, out, depth, seen)
    out.append("]")


def _reject_constant(name: str) -> Any:
    """R14. ``json.loads`` accepts bare ``NaN``/``Infinity``; ``JSON.parse`` does not."""
    raise CanonicalJsonError(E_NONFINITE, f"literal {name}")


def _parse_int(text: str) -> Any:
    """R15. An out-of-safe-range bare integer can only have come from a double under R6."""
    value = int(text)
    if MIN_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
        return value
    return float(text)
