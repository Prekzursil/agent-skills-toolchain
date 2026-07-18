"""Cross-source ID/target resolution — COMPOSED, fail-CLOSED (WU-1R).

R is NOT a single cross-ID lookup (no such tool exists in the TU index). It is
a COMPOSITION:

  compound  -> canonical InChIKey via rdkit IN-PROCESS
            -> PubChem xrefs (via transport_port)
            -> per-source ChEMBL / BindingDB / GtoPdb IDs
  target    -> UniProt accession (via transport_port)
            -> assay_context DERIVED heuristic (GABAB1-alone vs GABAB1/2
               heterodimer) with its own fixtures.

FAIL-CLOSED: any unresolvable cross-ID or ambiguous target raises
:class:`ResolutionError` and refuses to emit a resolved reference. We NEVER
guess. The pipeline turns this refusal into an ``unresolved:cross-id`` flag and
emits no Datum.
"""

from __future__ import annotations

from dataclasses import dataclass

from rdkit import Chem
from rdkit.Chem.inchi import MolToInchiKey

from .transport import TransportError, TransportPort

# Flag fragments surfaced to the pipeline / tests.
UNRESOLVED_CROSS_ID = "unresolved:cross-id"
AMBIGUOUS = "ambiguous:target"

# GABA-B receptor subunit gene symbols (uppercase canonical form).
_SUBUNIT_1 = "GABBR1"
_SUBUNIT_2 = "GABBR2"


class ResolutionError(RuntimeError):
    """Raised when a compound/target cannot be resolved unambiguously."""


@dataclass(frozen=True)
class ResolvedCompound:
    """Canonical InChIKey pivot plus composed per-source cross-IDs."""

    inchikey: str
    pubchem_cid: int
    cross_ids: dict[str, str]


@dataclass(frozen=True)
class ResolvedTarget:
    """UniProt accession plus the DERIVED assay-context tag."""

    uniprot: str
    assay_context: str


def inchikey_for_smiles(smiles: str) -> str:
    """Canonical InChIKey via rdkit IN-PROCESS. Fail-closed on bad input."""
    if not isinstance(smiles, str) or not smiles.strip():
        raise ResolutionError(f"{UNRESOLVED_CROSS_ID}: empty SMILES")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ResolutionError(f"{UNRESOLVED_CROSS_ID}: unparseable SMILES {smiles!r}")
    key = MolToInchiKey(mol)
    if not key:
        raise ResolutionError(f"{UNRESOLVED_CROSS_ID}: no InChIKey for {smiles!r}")
    return key


def assay_context_for(genes) -> str:
    """DERIVED heuristic mapping subunit gene symbols to an assay context.

    * both GABBR1 and GABBR2 present -> functional heterodimer;
    * GABBR1 alone -> subunit-alone (binding) context;
    * anything else (no canonical subunit, or GABBR2 alone) -> AMBIGUOUS.
    """
    symbols = {str(g).strip().upper() for g in genes}
    has1 = _SUBUNIT_1 in symbols
    has2 = _SUBUNIT_2 in symbols
    if has1 and has2:
        return "GABAB1/2-heterodimer"
    if has1:
        return "GABAB1-subunit-alone"
    raise ResolutionError(
        f"{AMBIGUOUS}: no canonical GABA-B context in {sorted(symbols)}"
    )


def resolve_compound(smiles: str, transport: TransportPort) -> ResolvedCompound:
    """Compose InChIKey pivot + PubChem xrefs into a resolved compound.

    Fail-closed: an unreachable PubChem, a missing CID, or zero cross-IDs all
    refuse to resolve.
    """
    inchikey = inchikey_for_smiles(smiles)
    try:
        record = transport.fetch_json("PubChem", inchikey)
    except TransportError as exc:
        raise ResolutionError(
            f"{UNRESOLVED_CROSS_ID}: PubChem unreachable for {inchikey}: {exc}"
        ) from exc

    cid = record.get("cid")
    if not isinstance(cid, int):
        raise ResolutionError(f"{UNRESOLVED_CROSS_ID}: no PubChem CID for {inchikey}")

    xrefs = record.get("xrefs") or {}
    cross_ids = {str(k): str(v) for k, v in xrefs.items() if v}
    if not cross_ids:
        raise ResolutionError(
            f"{UNRESOLVED_CROSS_ID}: no per-source cross-IDs for {inchikey}"
        )
    return ResolvedCompound(inchikey=inchikey, pubchem_cid=cid, cross_ids=cross_ids)


def resolve_target(query: str, transport: TransportPort) -> ResolvedTarget:
    """Resolve a target query to a UniProt accession + assay context.

    Fail-closed: blank query, unreachable UniProt, missing accession, or an
    ambiguous subunit set all refuse to resolve.
    """
    if not isinstance(query, str) or not query.strip():
        raise ResolutionError(f"{UNRESOLVED_CROSS_ID}: empty target query")
    try:
        record = transport.fetch_json("UniProt", query)
    except TransportError as exc:
        raise ResolutionError(
            f"{UNRESOLVED_CROSS_ID}: UniProt unreachable for {query!r}: {exc}"
        ) from exc

    accession = str(record.get("accession") or "").strip()
    if not accession:
        raise ResolutionError(
            f"{UNRESOLVED_CROSS_ID}: no UniProt accession for {query!r}"
        )

    # assay_context_for raises ResolutionError(AMBIGUOUS) on an unresolvable set.
    context = assay_context_for(record.get("genes") or [])
    return ResolvedTarget(uniprot=accession, assay_context=context)
