"""Certification gate for tournament winners: it consumes the CORRECTED verdict (TST-0299).

A candidate is certified only when its Holm family-wise rejection flag is set.  The raw
per-comparison WINNER flag (``uncorrected_significant``) is never the gate's input, because
in a family of forty comparisons at ``alpha = 0.05`` roughly two of those flags are set by
chance alone.

consume="corrected" (default, live gate): Holm family-wise rejection.
consume="uncorrected" (the named mutant): the raw per-comparison WINNER flag.

The named mutant: gate body identical except it consumes uncorrected.  It exists so the test
"a lucky uncorrected-only winner must not be certified" has something to go red on.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

CONSUME_CORRECTED = "corrected"
CONSUME_UNCORRECTED = "uncorrected"
SOURCE_FIELD: dict[str, str] = {
    CONSUME_CORRECTED: "holm_rejected",
    CONSUME_UNCORRECTED: "uncorrected_significant",
}
REQUIRED_ROW_FIELDS: tuple[str, ...] = (
    "id",
    "holm_rejected",
    "uncorrected_significant",
)


class GateError(ValueError):
    """Raised for an unknown consume mode or a malformed comparison row."""


def _validate_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    out: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for idx, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise GateError(f"comparison row {idx} is not a mapping")
        missing = [f for f in REQUIRED_ROW_FIELDS if f not in row]
        if missing:
            raise GateError(f"comparison row {idx} lacks {missing}")
        for flag in ("holm_rejected", "uncorrected_significant"):
            if not isinstance(row[flag], bool):
                raise GateError(
                    f"comparison row {idx}: {flag} must be a bool, got {row[flag]!r}"
                )
        cid = str(row["id"])
        if cid in seen:
            raise GateError(f"duplicate comparison id {cid!r}")
        seen.add(cid)
        out.append(row)
    return out


def certification_gate(
    rows: Sequence[Mapping[str, Any]],
    consume: str = CONSUME_CORRECTED,
) -> dict[str, Any]:
    """Decide certification for every comparison row from one named verdict field.

    ``consume`` selects the field: ``"corrected"`` reads ``holm_rejected`` (the live gate),
    ``"uncorrected"`` reads ``uncorrected_significant`` (the mutant).  Each decision records
    the field it read so a reviewer can see what the gate actually consumed.
    """
    if consume not in SOURCE_FIELD:
        raise GateError(
            f"unknown consume mode {consume!r}; expected one of {sorted(SOURCE_FIELD)}"
        )
    field = SOURCE_FIELD[consume]
    checked = _validate_rows(rows)
    decisions: list[dict[str, Any]] = []
    certified: list[str] = []
    refused: list[str] = []
    for row in checked:
        cid = str(row["id"])
        verdict = bool(row[field])
        decisions.append(
            {"id": cid, "certified": verdict, "field": field, "source": field}
        )
        (certified if verdict else refused).append(cid)
    return {
        "consume": consume,
        "source": field,
        "field": field,
        "family_size": len(checked),
        "certified_ids": certified,
        "certified_count": len(certified),
        "refused_ids": refused,
        "decisions": decisions,
        "mutant": consume != CONSUME_CORRECTED,
    }


def mutant_reads_uncorrected(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The named mutant: gate body identical except it consumes uncorrected."""
    return certification_gate(rows, consume=CONSUME_UNCORRECTED)


def lucky_uncorrected_only(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """Ids flagged by the raw WINNER field that Holm does not certify: the chance winners."""
    return [
        str(r["id"])
        for r in _validate_rows(rows)
        if r["uncorrected_significant"] and not r["holm_rejected"]
    ]


__all__ = [
    "CONSUME_CORRECTED",
    "CONSUME_UNCORRECTED",
    "GateError",
    "REQUIRED_ROW_FIELDS",
    "SOURCE_FIELD",
    "certification_gate",
    "lucky_uncorrected_only",
    "mutant_reads_uncorrected",
]
