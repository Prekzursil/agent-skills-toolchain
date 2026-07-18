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


def fetch_bioactivity(
    compound: ResolvedCompound, transport: TransportPort, retries: int = 0
) -> FetchResult:
    """Fetch bioactivity for an R-resolved compound, with fallback + retry.

    Walks :data:`FALLBACK_ORDER`, skipping sources the resolved compound has
    no cross-ID for, retrying transient failures in-process, and falling back
    to the next source on persistent failure. Fail-loud when the whole chain
    is exhausted.
    """
    if not isinstance(compound, ResolvedCompound):
        raise FetchError("fetch requires an R-resolved ResolvedCompound")

    tried_any = False
    for source in FALLBACK_ORDER:
        key = compound.cross_ids.get(source)
        if not key:
            continue
        tried_any = True
        payload = _try_source(transport, source, key, retries)
        if payload is not None:
            return FetchResult(source=source, key=key, payload=payload)

    if not tried_any:
        raise FetchError(
            "no known reliability source present in resolved cross-IDs: "
            f"{sorted(compound.cross_ids)}"
        )
    raise FetchError(f"all sources in fallback chain failed for {compound.inchikey}")
