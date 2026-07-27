r"""SHARED WIRE RULES — the predicates BOTH runtimes must apply IDENTICALLY.

:mod:`agentspec.canonical` made the two runtimes agree on the BYTES of a receipt. This module
exists because that was only half the contract: a differential harness driving both runtimes
over 483 behavioural cases found **78 outcome divergences**, including
:func:`agentspec.oracle.judge` — the AND-gate this whole package is built around — returning
``ok=True`` on one runtime and ``severed-stream`` on the other for the SAME receipt bytes. Every
one of those came from a MIRRORED PREDICATE: two builtins that look like translations of each
other and are not.

The four measured mismatch classes, and the rule each one forced:

* **Blankness.** ``str.strip()`` and ``String.prototype.trim()`` strip DIFFERENT character
  sets. Measured by exhaustive sweep over all 1,114,112 code points: ``U+001C U+001D U+001E
  U+001F U+0085`` are blank to Python and NOT to JS, and ``U+FEFF`` is blank to JS and NOT to
  Python. A receipt body of a single ``U+001C`` was ``receipt-empty`` (severed) on Python and a
  full six-clause SUCCESS on JS; a receipt carrying two BOMs — which
  :func:`agentspec.receipt.decode` explicitly tolerates, "because Windows writers emit one" —
  ran the other way. :data:`BLANK_CHARS` pins the set EXPLICITLY, so neither runtime's builtin
  decides it. ``U+FEFF`` is deliberately NOT blank: a BOM is data that ``decode`` strips as a
  separate, single, leading concern.
* **Ordering.** Python ``sorted()`` orders by CODE POINT and JS ``.sort()`` by UTF-16 CODE
  UNIT, so ``("\U0001f600", "�")`` sorts in opposite orders. Such tuples are interpolated
  into ``detail`` and reach ``error.root_cause`` on the wire. :func:`sorted_wire` is the one
  comparator, and it is the SAME rule :mod:`agentspec.canonical` R3 already uses for keys.
* **Length.** Python ``len()`` counts CODE POINTS and JS ``.length`` counts UTF-16 CODE UNITS,
  so ``WINDOWS_CMDLINE_CAP = 32767`` was the same NUMBER measured in different UNITS — a 2x
  divergence on astral text. Windows ``CreateProcess`` counts UTF-16 units, so JS was measuring
  the real limit and Python was under-counting by up to 2x, i.e. able to dispatch a command
  line that actually trips the measured ``os error 206``. :func:`utf16_len` is the one unit,
  and it is the UTF-16 one, because that is what the cap is a cap ON.
* **Interpreter-version drift.** ``str.isprintable()`` consults the interpreter's Unicode
  tables (CPython 3.14 ships Unicode 16.0.0) and JS ``\p{C}`` consults the engine's (Node 24
  ships 17.0), so **4,803 code points** were rejected by one runtime and accepted by the other
  — and CI runs Node 22, a THIRD table, so CI and a dev box disagreed too. A contract must not
  move when an interpreter is upgraded, so :data:`NON_PRINTABLE_ID_RANGES` pins the set as
  explicit numeric ranges. Same reasoning for :func:`fold_ascii_case`: full Unicode lowercasing
  differed on 28 code points across those two Unicode versions, so the case-insensitive marker
  match folds ASCII ONLY and matches everything else exactly. DISCLOSED NARROWING: a non-ASCII
  forbidden marker is now matched case-SENSITIVELY. That is a deterministic contract; an
  ICU-version-dependent one is not.

Pure: no clock, no entropy, no I/O. :func:`agentspec.determinism.scan_package` covers it.

The JS mirror is ``tools/agentspec-js/src/wire.mjs``, and
``tools/agentspec-js/test/crosslang.test.mjs`` DERIVES both tables below from THIS file's text,
so a one-sided edit fails the gate.
"""

from __future__ import annotations

from collections.abc import Iterable

BLANK_CHARS: tuple[str, ...] = (
    "\u0009",
    "\u000a",
    "\u000b",
    "\u000c",
    "\u000d",
    "\u001c",
    "\u001d",
    "\u001e",
    "\u001f",
    "\u0020",
    "\u0085",
    "\u00a0",
    "\u1680",
    "\u2000",
    "\u2001",
    "\u2002",
    "\u2003",
    "\u2004",
    "\u2005",
    "\u2006",
    "\u2007",
    "\u2008",
    "\u2009",
    "\u200a",
    "\u2028",
    "\u2029",
    "\u202f",
    "\u205f",
    "\u3000",
)
"""The CLOSED blank set: exactly CPython 3.14's ``str.isspace()`` set, frozen as DATA.

Frozen rather than delegated so the predicate cannot move with an interpreter upgrade, and
written out rather than derived so the JS mirror can read the same 29 code points from this
source text. ``U+FEFF`` is absent ON PURPOSE — see the module docstring.
"""

NON_PRINTABLE_ID_RANGES: tuple[str, ...] = (
    "0000-0020",
    "007f-00a0",
    "00ad-00ad",
    "0600-0605",
    "061c-061c",
    "06dd-06dd",
    "070f-070f",
    "0890-0891",
    "08e2-08e2",
    "1680-1680",
    "180e-180e",
    "2000-200f",
    "2028-202f",
    "205f-2064",
    "2066-206f",
    "3000-3000",
    "d800-f8ff",
    "fdd0-fdef",
    "feff-feff",
    "fff9-fffb",
    "fffe-ffff",
    "110bd-110bd",
    "110cd-110cd",
    "13430-1343f",
    "1bca0-1bca3",
    "1d173-1d17a",
    "1fffe-1ffff",
    "2fffe-2ffff",
    "3fffe-3ffff",
    "4fffe-4ffff",
    "5fffe-5ffff",
    "6fffe-6ffff",
    "7fffe-7ffff",
    "8fffe-8ffff",
    "9fffe-9ffff",
    "afffe-affff",
    "bfffe-bffff",
    "cfffe-cffff",
    "dfffe-dffff",
    "e0001-e0001",
    "e0020-e007f",
    "efffe-10ffff",
)
"""Inclusive ``start-end`` hex ranges a terminal-marker id may not contain.

Covers every Cc / Cf / Cs / Co / Zs / Zl / Zp code point plus the permanently-reserved
noncharacters, as of Unicode 16.0.0. The UNASSIGNED (Cn) clause of ``str.isprintable()`` is
deliberately DROPPED: Cn is the part that MOVES — 4,803 code points changed class between the
Unicode versions the two runtimes ship — and a newly assigned letter is not the hazard this
check exists for. The hazard is a byte the console re-interprets (ESC/CSI, OSC-8, NUL, DEL) or
whitespace that makes ``FAILED:<id> <reason>`` unparseable; both are Cc/Cf/Z, both are pinned
here, and a noncharacter renders as tofu rather than as an escape.
"""

MAX_WIRE_INTEGER = 2**53 - 1
"""The largest integer BOTH runtimes represent exactly.

Python ``int`` is arbitrary-precision and a JS ``number`` is a double, so ``isinstance(x, int)``
and ``Number.isSafeInteger(x)`` are NOT the same predicate. Measured: ``check_dispatch(
timeout_s=9007199254740993)`` was accepted by Python and a ``TypeError`` on JS, and
``debit(micro=2.0)`` was the reverse. One bound applied on both sides deletes both directions.
Cross-checked against :data:`agentspec.canonical.MAX_SAFE_INTEGER` by the test suite — two
independent statements of one fact, never one derived from the other.
"""

MIN_WIRE_INTEGER = -(2**53 - 1)

_BLANK_SET = frozenset(BLANK_CHARS)

_NON_PRINTABLE_ID: tuple[tuple[int, int], ...] = tuple(
    (int(item.split("-")[0], 16), int(item.split("-")[1], 16))
    for item in NON_PRINTABLE_ID_RANGES
)

_ASCII_FOLD = {code: code + 32 for code in range(ord("A"), ord("Z") + 1)}


def is_blank(text: str) -> bool:
    """True when ``text`` holds no non-blank character. The empty string IS blank."""
    return all(char in _BLANK_SET for char in text)


def contains_blank(text: str) -> bool:
    """True when ``text`` holds at least one blank character."""
    return any(char in _BLANK_SET for char in text)


def utf16_len(text: str) -> int:
    """The length of ``text`` in UTF-16 CODE UNITS — the unit Windows counts, and JS's."""
    return sum(2 if ord(char) > 0xFFFF else 1 for char in text)


def utf16_sort_key(text: str) -> bytes:
    """R3. The UTF-16 code-unit ordering JS ``Array.prototype.sort()`` uses on strings."""
    return text.encode("utf-16-be", "surrogatepass")


def sorted_wire(items: Iterable[str]) -> tuple[str, ...]:
    """Sort ``items`` the way JS ``.sort()`` does, so an ordered wire field cannot diverge."""
    return tuple(sorted(items, key=utf16_sort_key))


def fold_ascii_case(text: str) -> str:
    """Lowercase ASCII A-Z and NOTHING else — a case fold pinned to a spec, not to ICU."""
    return text.translate(_ASCII_FOLD)


def is_printable_id(text: str) -> bool:
    """True when every code point of a NON-EMPTY ``text`` is outside the pinned reject set."""
    if not text:
        return False
    return all(not _is_non_printable(ord(char)) for char in text)


def is_wire_integer(value: object) -> bool:
    """True for an ``int`` both runtimes represent exactly. ``bool`` is NOT an integer here.

    ``isinstance(True, int)`` is True in Python and ``Number.isSafeInteger(true)`` is false in
    JS, so the boolean has to be excluded explicitly or the two sides disagree on whether a
    budget can be charged ``True``.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return False
    return MIN_WIRE_INTEGER <= value <= MAX_WIRE_INTEGER


def require_wire_integer(value: object, name: str) -> int:
    """Return ``value`` as a wire integer, or raise ``TypeError``.

    The message carries NO repr of the offending value on purpose: Python renders ``2.0`` and
    JS renders ``2`` for the same double, which would make the two runtimes' error text differ
    on the very check that exists to keep them identical.
    """
    if not is_wire_integer(value):
        raise TypeError(
            f"{name} must be an integer in [{MIN_WIRE_INTEGER}, {MAX_WIRE_INTEGER}]"
        )
    return int(value)  # pyright: ignore[reportArgumentType]


def json_type_name(value: object) -> str:
    """The JSON type of a DECODED value, in the one vocabulary both runtimes report.

    ``type(x).__name__`` gives ``list``/``str``/``NoneType`` and JS ``typeof`` gives
    ``object``/``string``/``object`` — neither is portable, and this string reaches
    ``error.root_cause`` through ``receipt-unparseable``.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def _is_non_printable(code: int) -> bool:
    return any(start <= code <= end for start, end in _NON_PRINTABLE_ID)
