"""Typed pipeline wiring (WU-1 spine).

    resolve(R) -> fetch(G) -> normalize(I) -> verify(J-stub) -> capture(F-stub)

Each stage is a pure function over the Phase-0 :class:`Datum` and the injectable
``transport_port``. R fail-CLOSED refusals propagate as
:class:`~wearables.resolve.ResolutionError` (no Datum emitted). J (verify) and F
(capture) are Phase-1 STUBS — the seam is wired so Phase 2 swaps in real
implementations without touching callers.
"""

from __future__ import annotations

from dataclasses import dataclass

from .capture import capture
from .datum import Datum, Provenance, SourceClass, make_datum
from .fetch import FetchError, FetchResult, fetch_bioactivity
from .normalize import normalize_datum
from .resolve import resolve_compound, resolve_target
from .transport import TransportPort
from .verify import verify

# Public-database fetch sources are source_class="public_db". J-reconciled /
# derived outputs are re-stamped "derived" by the verify stage. There is NO
# hardcoded "public_db" anymore — the class is CARRIED from the source identity.
_PUBLIC_DB_SOURCES: frozenset[str] = frozenset(
    {"ChEMBL", "PubChem", "BindingDB", "GtoPdb"}
)


class PipelineError(RuntimeError):
    """Raised when the pipeline cannot produce a Datum (non-resolution stage)."""


@dataclass(frozen=True)
class PipelineResult:
    """The emitted Datum plus the source that answered."""

    datum: Datum
    source: str


def source_class_for(source: str) -> SourceClass:
    """Map a fetch source to its security ``source_class`` (fail-CLOSED).

    Known public databases are ``public_db``; an unrecognised source is treated
    as ``derived`` (sensitive-by-default) so the egress guard denies it to
    third-party LLMs unless explicitly downgraded — never silently public.
    """
    if source in _PUBLIC_DB_SOURCES:
        return "public_db"
    return "derived"


def _datum_from_fetch(
    inchikey: str,
    uniprot: str,
    context: str,
    fetched: FetchResult,
) -> Datum:
    """Assemble a pre-normalization Datum from a fetch payload (fail-loud)."""
    payload = fetched.payload
    if "value" not in payload:
        raise PipelineError(f"{fetched.source} payload missing 'value'")
    return make_datum(
        compound_id=inchikey,
        target_id=uniprot,
        target_context=context,
        metric=payload.get("metric", "Ki"),
        value=None,
        value_as_reported=payload["value"],
        unit=payload.get("unit", "nM"),
        unit_as_reported=payload.get("unit"),
        n=payload.get("n"),
        confidence=payload.get("confidence", "unknown"),
        source=fetched.source,
        source_class=source_class_for(fetched.source),
        provenance=Provenance(
            pmid=payload.get("pmid"),
            db=fetched.source,
            accession=payload.get("accession"),
            access_date="2026-06-16",
        ),
    )


def run_pipeline(
    smiles: str, target_query: str, transport: TransportPort
) -> PipelineResult:
    """Drive the full resolve->fetch->normalize->verify->capture pipeline.

    R refusals propagate (fail-CLOSED). A fully-failed fetch chain raises
    :class:`PipelineError`.
    """
    compound = resolve_compound(smiles, transport)  # R
    target = resolve_target(target_query, transport)  # R

    try:
        # target_id is LOAD-BEARING: the fetch chain keys on a compound cross-ID,
        # so without it a provider payload for a DIFFERENT protein is accepted and
        # then stamped below with this run's requested target.
        fetched = fetch_bioactivity(compound, transport, target_id=target.uniprot)  # G
    except FetchError as exc:
        raise PipelineError(f"fetch stage exhausted: {exc}") from exc

    datum = _datum_from_fetch(
        compound.inchikey, target.uniprot, target.assay_context, fetched
    )
    datum = normalize_datum(datum)  # I
    # J (verify) operates over >=2 independent sources; a single-source pull has
    # nothing to cross-check, so it passes through unflagged.
    datum = verify([datum])[0]  # J (real)
    datum = capture(datum)  # F/L (provenance gate)
    return PipelineResult(datum=datum, source=fetched.source)
