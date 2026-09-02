#!/usr/bin/env python3
"""extraction-normalization: sanitize control bytes INSIDE the parse, before split.

A control byte that naive parsers also treat as a field delimiter (US, RS, TAB,
VT, FF, NEL) planted inside a value must not create extra columns. Stripping
those bytes from each field *after* split cannot recover the column count —
the shift has already happened.

Designated field delimiter: comma (0x2C), not a control.
Designated record delimiter: LF (consumed by the table splitter, not the field parser).
"""
from __future__ import annotations

from typing import Final

FIELD_DELIM: Final[bytes] = b","
RECORD_DELIM: Final[bytes] = b"\n"
PLANTED_US: Final[bytes] = b"\x1f"

# Bytes a naive HUD/log splitter treats as extra field separators.
NAIVE_EXTRA_DELIMS: Final[frozenset[int]] = frozenset(
    {0x09, 0x0B, 0x0C, 0x1E, 0x1F, 0x85}
)


def is_control_byte(b: int) -> bool:
    """C0, DEL, and C1. The designated field delimiter is not in this set."""
    return b < 0x20 or b == 0x7F or 0x80 <= b <= 0x9F


def strip_controls_except_delimiter(blob: bytes, delimiter: bytes = FIELD_DELIM) -> bytes:
    """Drop C0/C1/DEL bytes that are not the designated field delimiter.

    Must run on the raw record BEFORE any field split. The designated delimiter
    is preserved so column boundaries survive; every other control is removed
    so it cannot be mistaken for a delimiter.
    """
    if not delimiter:
        raise ValueError("delimiter must be a single byte")
    keep = delimiter[0]
    out = bytearray()
    for b in blob:
        if b == keep:
            out.append(b)
        elif is_control_byte(b):
            continue
        else:
            out.append(b)
    return bytes(out)


def sanitize_field(cell: bytes, delimiter: bytes = FIELD_DELIM) -> bytes:
    """Field-level sanitize for emit: drop controls AND in-field delimiter bytes."""
    if not delimiter:
        raise ValueError("delimiter must be a single byte")
    d = delimiter[0]
    out = bytearray()
    for b in cell:
        if b == d or is_control_byte(b):
            continue
        out.append(b)
    return bytes(out)


def split_fields(cleaned: bytes, delimiter: bytes = FIELD_DELIM) -> list[bytes]:
    """Split a record that has already had non-delimiter controls removed."""
    return cleaned.split(delimiter)


def parse_record(record: bytes, delimiter: bytes = FIELD_DELIM) -> list[bytes]:
    """Production parse: sanitize controls, THEN split on the designated delimiter."""
    cleaned = strip_controls_except_delimiter(record, delimiter)
    return split_fields(cleaned, delimiter)


def split_on_delimiter_and_controls(
    blob: bytes, delimiter: bytes = FIELD_DELIM
) -> list[bytes]:
    """Naive splitter: designated delimiter PLUS common control separators.

    This is the measured defect class: a US (0x1F) inside a value becomes an
    extra column. Used only as the both-states control, never as production.
    """
    seps = set(NAIVE_EXTRA_DELIMS)
    seps.add(delimiter[0])
    parts: list[bytes] = []
    cur = bytearray()
    for b in blob:
        if b in seps:
            parts.append(bytes(cur))
            cur = bytearray()
        else:
            cur.append(b)
    parts.append(bytes(cur))
    return parts


def parse_record_naive(record: bytes, delimiter: bytes = FIELD_DELIM) -> list[bytes]:
    """Split first (including control-as-delimiter), then sanitize each field.

    Too late: column count is already wrong. The both-states probe must see
    this produce more columns than parse_record on the same fixture.
    """
    parts = split_on_delimiter_and_controls(record, delimiter)
    return [strip_controls_except_delimiter(p, delimiter) for p in parts]


def parse_table(raw: bytes, delimiter: bytes = FIELD_DELIM) -> list[list[bytes]]:
    rows: list[list[bytes]] = []
    for rec in raw.split(RECORD_DELIM):
        if rec == b"":
            continue
        rows.append(parse_record(rec, delimiter))
    return rows


def parse_table_naive(raw: bytes, delimiter: bytes = FIELD_DELIM) -> list[list[bytes]]:
    rows: list[list[bytes]] = []
    for rec in raw.split(RECORD_DELIM):
        if rec == b"":
            continue
        rows.append(parse_record_naive(rec, delimiter))
    return rows


def emit_normalized(
    rows: list[list[bytes]],
    delimiter: bytes = FIELD_DELIM,
    record_sep: bytes = RECORD_DELIM,
) -> bytes:
    lines = [
        delimiter.join(sanitize_field(cell, delimiter) for cell in row) for row in rows
    ]
    body = record_sep.join(lines)
    if body and not body.endswith(record_sep):
        body += record_sep
    return body


def planted_fixture() -> bytes:
    """Three logical columns; UNIT SEPARATOR planted inside the title value."""
    return (
        b"sku,title,qty\n"
        b"A-1,widget" + PLANTED_US + b"deluxe,3\n"
        b"B-2,gadget,10\n"
    )


def benign_fixture() -> bytes:
    """Same shape, no in-field control. Detector must stay silent here."""
    return b"sku,title,qty\nA-1,widgetdeluxe,3\nB-2,gadget,10\n"


def expected_normalized() -> list[list[bytes]]:
    return [
        [b"sku", b"title", b"qty"],
        [b"A-1", b"widgetdeluxe", b"3"],
        [b"B-2", b"gadget", b"10"],
    ]


def smoke() -> dict[str, object]:
    planted = planted_fixture()
    rows = parse_table(planted)
    expected = expected_normalized()
    widths = [len(r) for r in rows]
    naive_widths = [len(r) for r in parse_table_naive(planted)]
    rt = parse_table(emit_normalized(rows))
    ok = rows == expected and rt == expected and widths == [3, 3, 3]
    return {
        "ok": ok,
        "widths": widths,
        "naive_widths": naive_widths,
        "round_trip": rt == expected,
        "row_count": len(rows),
    }
