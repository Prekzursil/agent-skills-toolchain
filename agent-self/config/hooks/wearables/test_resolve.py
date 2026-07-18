"""Tests for cross-source ID/target resolution (WU-1R).

R is COMPOSED, not a lookup: compound -> canonical InChIKey via rdkit
IN-PROCESS -> PubChem xrefs -> per-source name/structure lookups; target ->
UniProt accession + assay_context DERIVED heuristic. FAIL-CLOSED: any
unresolvable cross-ID or ambiguous target refuses to emit a ResolvedRef.
"""

import pytest

from wearables.resolve import (
    AMBIGUOUS,
    UNRESOLVED_CROSS_ID,
    ResolutionError,
    ResolvedCompound,
    ResolvedTarget,
    assay_context_for,
    inchikey_for_smiles,
    resolve_compound,
    resolve_target,
)
from wearables.transport import FakeTransport, TransportError

BACLOFEN_SMILES = "OC(=O)CC(CN)c1ccc(Cl)cc1"
BACLOFEN_INCHIKEY = "KPYSYYIEGFHWSV-UHFFFAOYSA-N"


# --- in-process rdkit InChIKey pivot ---------------------------------------


def test_inchikey_for_baclofen_smiles():
    assert inchikey_for_smiles(BACLOFEN_SMILES) == BACLOFEN_INCHIKEY


def test_inchikey_for_invalid_smiles_raises():
    with pytest.raises(ResolutionError):
        inchikey_for_smiles("not-a-smiles!!!")


def test_inchikey_for_empty_smiles_raises():
    with pytest.raises(ResolutionError):
        inchikey_for_smiles("   ")


def test_inchikey_failclosed_when_rdkit_returns_empty(monkeypatch):
    # Defensive branch: a parseable mol that yields no InChIKey -> fail-closed.
    import wearables.resolve as resolve_mod

    monkeypatch.setattr(resolve_mod, "MolToInchiKey", lambda mol: "")
    with pytest.raises(ResolutionError) as exc:
        inchikey_for_smiles(BACLOFEN_SMILES)
    assert UNRESOLVED_CROSS_ID in str(exc.value)


# --- compound composition over PubChem xrefs + per-source lookups ----------


def _xref_transport():
    return FakeTransport(
        {
            ("PubChem", BACLOFEN_INCHIKEY): {
                "cid": 2284,
                "xrefs": {
                    "ChEMBL": "CHEMBL701",
                    "BindingDB": "BDBM50000123",
                    "GtoPdb": "1084",
                },
            }
        }
    )


def test_resolve_compound_composes_cross_ids():
    transport = _xref_transport()
    rc = resolve_compound(BACLOFEN_SMILES, transport)
    assert isinstance(rc, ResolvedCompound)
    assert rc.inchikey == BACLOFEN_INCHIKEY
    assert rc.pubchem_cid == 2284
    assert rc.cross_ids["ChEMBL"] == "CHEMBL701"
    assert rc.cross_ids["BindingDB"] == "BDBM50000123"
    assert rc.cross_ids["GtoPdb"] == "1084"


def test_resolve_compound_failclosed_when_pubchem_unreachable():
    transport = FakeTransport(
        {("PubChem", BACLOFEN_INCHIKEY): TransportError("timeout")}
    )
    with pytest.raises(ResolutionError) as exc:
        resolve_compound(BACLOFEN_SMILES, transport)
    assert UNRESOLVED_CROSS_ID in str(exc.value)


def test_resolve_compound_failclosed_when_no_cross_ids():
    transport = FakeTransport(
        {("PubChem", BACLOFEN_INCHIKEY): {"cid": 2284, "xrefs": {}}}
    )
    with pytest.raises(ResolutionError) as exc:
        resolve_compound(BACLOFEN_SMILES, transport)
    assert UNRESOLVED_CROSS_ID in str(exc.value)


def test_resolve_compound_failclosed_when_missing_cid():
    transport = FakeTransport(
        {("PubChem", BACLOFEN_INCHIKEY): {"xrefs": {"ChEMBL": "CHEMBL701"}}}
    )
    with pytest.raises(ResolutionError) as exc:
        resolve_compound(BACLOFEN_SMILES, transport)
    assert UNRESOLVED_CROSS_ID in str(exc.value)


# --- assay_context DERIVED heuristic ---------------------------------------


def test_assay_context_heterodimer_when_both_subunits_present():
    ctx = assay_context_for(["GABBR1", "GABBR2"])
    assert ctx == "GABAB1/2-heterodimer"


def test_assay_context_subunit_alone():
    ctx = assay_context_for(["GABBR1"])
    assert ctx == "GABAB1-subunit-alone"


def test_assay_context_case_insensitive_and_whitespace():
    ctx = assay_context_for([" gabbr1 ", "GabbR2"])
    assert ctx == "GABAB1/2-heterodimer"


def test_assay_context_ambiguous_raises_when_no_subunits():
    with pytest.raises(ResolutionError) as exc:
        assay_context_for(["SOME_OTHER_GENE"])
    assert AMBIGUOUS in str(exc.value)


def test_assay_context_ambiguous_when_only_subunit2():
    # GABBR2 alone is not the canonical receptor context -> ambiguous
    with pytest.raises(ResolutionError) as exc:
        assay_context_for(["GABBR2"])
    assert AMBIGUOUS in str(exc.value)


# --- target resolution: UniProt accession + assay_context ------------------


def _target_transport(genes):
    return FakeTransport(
        {
            ("UniProt", "GABA-B"): {
                "accession": "O75899",
                "genes": genes,
            }
        }
    )


def test_resolve_target_heterodimer():
    transport = _target_transport(["GABBR1", "GABBR2"])
    rt = resolve_target("GABA-B", transport)
    assert isinstance(rt, ResolvedTarget)
    assert rt.uniprot == "O75899"
    assert rt.assay_context == "GABAB1/2-heterodimer"


def test_resolve_target_failclosed_when_unreachable():
    transport = FakeTransport({("UniProt", "GABA-B"): TransportError("500")})
    with pytest.raises(ResolutionError) as exc:
        resolve_target("GABA-B", transport)
    assert UNRESOLVED_CROSS_ID in str(exc.value)


def test_resolve_target_failclosed_when_no_accession():
    transport = FakeTransport(
        {("UniProt", "GABA-B"): {"accession": "", "genes": ["GABBR1", "GABBR2"]}}
    )
    with pytest.raises(ResolutionError) as exc:
        resolve_target("GABA-B", transport)
    assert UNRESOLVED_CROSS_ID in str(exc.value)


def test_resolve_target_failclosed_when_ambiguous_context():
    # accession present but genes do not yield a canonical context
    transport = _target_transport(["UNKNOWN"])
    with pytest.raises(ResolutionError) as exc:
        resolve_target("GABA-B", transport)
    assert AMBIGUOUS in str(exc.value)


def test_resolve_target_blank_query_failclosed():
    with pytest.raises(ResolutionError):
        resolve_target("  ", _target_transport(["GABBR1", "GABBR2"]))
