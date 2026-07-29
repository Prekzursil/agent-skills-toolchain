"""Reliability fetch stage — IN-PROCESS retry + fallback chain (WU-1G).

The ``fetch`` stage does retry + source fallback IN-PROCESS (NOT via a
``StopFailure``/failure hook — the failure event is a notifier, not a
fetch-fallback mechanism). Fallback order is pinned:

    ChEMBL -> PubChem -> BindingDB -> GtoPdb

Only fetches for an R-resolved compound (a :class:`ResolvedCompound`); a
source is tried only when the resolved compound carries its cross-ID.
"""

from __future__ import annotations

from dataclasses import dataclass

from .resolve import ResolvedCompound
from .transport import TransportError, TransportPort

# Pinned fallback order across reliability sources.
FALLBACK_ORDER: tuple[str, ...] = ("ChEMBL", "PubChem", "BindingDB", "GtoPdb")
# Payload keys a provider may use to declare WHICH target a measurement is for.
_TARGET_FIELDS: tuple[str, ...] = ("target_id", "target_accession", "uniprot")


class FetchError(RuntimeError):
    """Raised when no source in the fallback chain yields data."""


@dataclass(frozen=True)
class FetchResult:
    """The source that answered plus its raw payload (pre-normalization)."""

    source: str
    key: str
    payload: dict


def _try_source(
    transport: TransportPort, source: str, key: str, retries: int
) -> dict | None:
    """Attempt one source with up to ``retries`` extra in-process retries.

    Returns the payload dict on success, or ``None`` if every attempt failed.
    """
    attempts = max(0, retries) + 1
    for _ in range(attempts):
        try:
            return transport.fetch_json(source, key)
        except TransportError:
            continue
    return None


def _declared_targets(payload: dict) -> set[str]:
    """Target identifiers the PROVIDER declared on a bioactivity payload."""
    return {
        payload[field].strip()
        for field in _TARGET_FIELDS
        if isinstance(payload.get(field), str) and payload[field].strip()
    }


def fetch_bioactivity(
    compound: ResolvedCompound,
    transport: TransportPort,
    retries: int = 0,
    target_id: str | None = None,
) -> FetchResult:
    """Fetch bioactivity for an R-resolved compound, with fallback + retry.

    Walks :data:`FALLBACK_ORDER`, skipping sources the resolved compound has
    no cross-ID for, retrying transient failures in-process, and falling back
    to the next source on persistent failure. Fail-loud when the whole chain
    is exhausted.

    The chain keys on a COMPOUND cross-ID, so nothing in the request pins the
    target. ``target_id`` (the R-resolved UniProt accession) is therefore
    checked against whatever target the provider DECLARED on its payload: a
    contradicting source is rejected and the chain falls through, fail-CLOSED.
    Without it the caller stamps its requested target onto a measurement the
    provider attributed to a different protein — a silent, unflagged false
    attribution. A payload that declares no target cannot be checked and is
    accepted unchanged.
    """
    if not isinstance(compound, ResolvedCompound):
        raise FetchError("fetch requires an R-resolved ResolvedCompound")

    tried_any = False
    mismatched: list[str] = []
    for source in FALLBACK_ORDER:
        key = compound.cross_ids.get(source)
        if not key:
            continue
        tried_any = True
        payload = _try_source(transport, source, key, retries)
        if payload is None:
            continue
        declared = _declared_targets(payload)
        if target_id and declared and target_id not in declared:
            mismatched.append(f"{source}={sorted(declared)}")
            continue
        return FetchResult(source=source, key=key, payload=payload)

    if not tried_any:
        raise FetchError(
            "no known reliability source present in resolved cross-IDs: "
            f"{sorted(compound.cross_ids)}"
        )
    if mismatched:
        raise FetchError(
            f"every answering source declared a target other than {target_id!r}: "
            + ", ".join(mismatched)
        )
    raise FetchError(f"all sources in fallback chain failed for {compound.inchikey}")
