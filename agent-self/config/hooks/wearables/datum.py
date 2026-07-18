"""Frozen typed Datum — the immutable unit of the wearables pipeline (WU-0a).

Pure data, no I/O. ``value_as_reported`` / ``unit_as_reported`` are NEVER
discarded (UX contract). ``source_class`` is a closed Literal domain used by
the fail-CLOSED egress guard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, get_args

SourceClass = Literal["public_db", "derived", "unpublished"]
_SOURCE_CLASSES: tuple[str, ...] = get_args(SourceClass)


@dataclass(frozen=True)
class Provenance:
    """Citable origin of a Datum: PMID / DB / accession / access-date."""

    pmid: str | None
    db: str
    accession: str | None
    access_date: str  # ISO date


@dataclass(frozen=True)
class Datum:
    """Immutable measurement record flowing through the pipeline."""

    compound_id: str  # canonical InChIKey + composed cross-IDs (from R)
    target_id: str  # UniProt accession (from R)
    target_context: str  # assay context, e.g. GABAB1/2-heterodimer vs subunit
    metric: str  # Ki | IC50 | EC50 | pKi ...
    value: float | None  # canonical value after normalization (I)
    value_as_reported: float | None  # NEVER discarded
    unit: str  # canonical unit after I: "nM" | "pKi" ...
    unit_as_reported: str | None
    n: int | None
    confidence: str
    source: str  # ChEMBL | PubChem | BindingDB | GtoPdb
    source_class: SourceClass
    provenance: Provenance
    flags: tuple[str, ...] = field(default=())


def make_datum(
    *,
    compound_id: str,
    target_id: str,
    target_context: str,
    metric: str,
    value: float | None,
    value_as_reported: float | None,
    unit: str,
    n: int | None,
    confidence: str,
    source: str,
    source_class: str,
    provenance: Provenance,
    unit_as_reported: str | None = None,
    flags=(),
) -> Datum:
    """Validate inputs and build a frozen :class:`Datum`.

    Fail-closed validation: bad ``source_class``, empty required IDs, negative
    ``n``, or non-numeric ``value`` raise rather than producing a corrupt Datum.
    """
    if not isinstance(compound_id, str) or not compound_id.strip():
        raise ValueError("compound_id must be a non-empty string")
    if not isinstance(target_id, str) or not target_id.strip():
        raise ValueError("target_id must be a non-empty string")
    if source_class not in _SOURCE_CLASSES:
        raise ValueError(
            f"source_class must be one of {_SOURCE_CLASSES}, got {source_class!r}"
        )
    if value is not None and not isinstance(value, (int, float)):
        raise TypeError("value must be a number or None")
    if value_as_reported is not None and not isinstance(
        value_as_reported, (int, float)
    ):
        raise TypeError("value_as_reported must be a number or None")
    if n is not None and (not isinstance(n, int) or n < 0):
        raise ValueError("n must be a non-negative int or None")

    return Datum(
        compound_id=compound_id,
        target_id=target_id,
        target_context=target_context,
        metric=metric,
        value=value,
        value_as_reported=value_as_reported,
        unit=unit,
        unit_as_reported=unit_as_reported,
        n=n,
        confidence=confidence,
        source=source,
        source_class=source_class,  # type: ignore[arg-type]
        provenance=provenance,
        flags=tuple(flags),
    )
