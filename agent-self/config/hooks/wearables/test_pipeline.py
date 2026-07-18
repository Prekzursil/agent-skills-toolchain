"""Tests for the typed pipeline wiring (WU-1 spine).

resolve(R) -> fetch(G) -> normalize(I) -> verify(J-stub) -> capture(F-stub).
Uses the Phase-0 Datum + transport_port. J and F are stubs in Phase 1 (verify
returns the Datum unchanged; capture echoes it) but the seam is wired so
Phase 2 can replace them.
"""

import pytest

from wearables.datum import Datum
from wearables.pipeline import (
    PipelineError,
    PipelineResult,
    run_pipeline,
    source_class_for,
)
from wearables.resolve import ResolutionError
from wearables.transport import FakeTransport, TransportError
from wearables.verify import verify

BACLOFEN_SMILES = "OC(=O)CC(CN)c1ccc(Cl)cc1"
BACLOFEN_INCHIKEY = "KPYSYYIEGFHWSV-UHFFFAOYSA-N"


def _golden_transport(chembl=None):
    """A transport seeded for the baclofen -> GABA-B golden pull."""
    return FakeTransport(
        {
            ("PubChem", BACLOFEN_INCHIKEY): {
                "cid": 2284,
                "xrefs": {"ChEMBL": "CHEMBL701", "PubChem": "2284"},
            },
            ("UniProt", "GABA-B"): {
                "accession": "O75899",
                "genes": ["GABBR1", "GABBR2"],
            },
            ("ChEMBL", "CHEMBL701"): chembl
            if chembl is not None
            else {
                "value": 2.5,
                "unit": "uM",
                "metric": "Ki",
                "n": 3,
                "confidence": "high",
                "pmid": "PMID:12345",
                "accession": "CHEMBL701",
            },
        }
    )


# --- real verify/capture stages (replaced the Phase-1 stubs) ----------------


def test_verify_single_source_passes_through():
    result = run_pipeline(BACLOFEN_SMILES, "GABA-B", _golden_transport())
    # a single-source pull has nothing to cross-check -> unflagged, unchanged
    assert verify([result.datum]) == [result.datum]


# --- full pipeline ----------------------------------------------------------


def test_run_pipeline_baclofen_gabab_golden():
    result = run_pipeline(BACLOFEN_SMILES, "GABA-B", _golden_transport())
    assert isinstance(result, PipelineResult)
    d = result.datum
    assert isinstance(d, Datum)
    # R: canonical InChIKey + composed cross-IDs + resolved target context
    assert d.compound_id == BACLOFEN_INCHIKEY
    assert d.target_id == "O75899"
    assert d.target_context == "GABAB1/2-heterodimer"
    # G: ChEMBL answered
    assert d.source == "ChEMBL"
    # I: normalized to canonical nM, as-reported preserved
    assert d.unit == "nM"
    assert d.value == pytest.approx(2500.0)
    assert d.value_as_reported == 2.5
    assert d.unit_as_reported == "uM"
    # provenance carried through
    assert d.provenance.pmid == "PMID:12345"


def test_run_pipeline_failclosed_on_unresolvable_compound():
    # PubChem has no cross-IDs -> R refuses -> NO Datum emitted.
    transport = FakeTransport(
        {
            ("PubChem", BACLOFEN_INCHIKEY): {"cid": 2284, "xrefs": {}},
        }
    )
    with pytest.raises(ResolutionError):
        run_pipeline(BACLOFEN_SMILES, "GABA-B", transport)


def test_run_pipeline_failclosed_on_ambiguous_target():
    transport = FakeTransport(
        {
            ("PubChem", BACLOFEN_INCHIKEY): {
                "cid": 2284,
                "xrefs": {"ChEMBL": "CHEMBL701"},
            },
            ("UniProt", "GABA-B"): {"accession": "O75899", "genes": ["UNKNOWN"]},
        }
    )
    with pytest.raises(ResolutionError):
        run_pipeline(BACLOFEN_SMILES, "GABA-B", transport)


def test_run_pipeline_fetch_fallback_when_chembl_down():
    transport = FakeTransport(
        {
            ("PubChem", BACLOFEN_INCHIKEY): {
                "cid": 2284,
                "xrefs": {"ChEMBL": "CHEMBL701", "PubChem": "2284"},
            },
            ("UniProt", "GABA-B"): {
                "accession": "O75899",
                "genes": ["GABBR1", "GABBR2"],
            },
            ("ChEMBL", "CHEMBL701"): TransportError("HTTP 500"),
            ("PubChem", "2284"): {
                "value": 1500.0,
                "unit": "nM",
                "metric": "Ki",
                "n": 2,
                "confidence": "medium",
                "accession": "2284",
            },
        }
    )
    result = run_pipeline(BACLOFEN_SMILES, "GABA-B", transport)
    assert result.datum.source == "PubChem"
    assert result.datum.value == pytest.approx(1500.0)


def test_run_pipeline_raises_when_all_fetch_sources_fail():
    transport = _golden_transport(chembl=TransportError("500"))
    with pytest.raises(PipelineError):
        run_pipeline(BACLOFEN_SMILES, "GABA-B", transport)


def test_run_pipeline_defaults_metric_when_payload_missing_it():
    transport = _golden_transport(
        chembl={"value": 10.0, "unit": "nM", "accession": "CHEMBL701"}
    )
    result = run_pipeline(BACLOFEN_SMILES, "GABA-B", transport)
    # missing metric/n/confidence in payload -> sane defaults, still a Datum
    assert result.datum.metric == "Ki"
    assert result.datum.n is None
    assert result.datum.confidence == "unknown"


def test_run_pipeline_raises_when_payload_missing_value():
    # Fetch succeeds (dict returned) but the payload lacks 'value' -> fail-loud.
    transport = _golden_transport(chembl={"unit": "nM", "accession": "CHEMBL701"})
    with pytest.raises(PipelineError):
        run_pipeline(BACLOFEN_SMILES, "GABA-B", transport)


def test_run_pipeline_marks_source_class_public_db():
    result = run_pipeline(BACLOFEN_SMILES, "GABA-B", _golden_transport())
    assert result.datum.source_class == "public_db"


# --- CRITICAL SECURITY FIX: source_class threaded through (not hardcoded) ----


def test_source_class_for_public_dbs():
    for src in ("ChEMBL", "PubChem", "BindingDB", "GtoPdb"):
        assert source_class_for(src) == "public_db"


def test_source_class_for_unknown_is_derived():
    # an unrecognised / derived source is sensitive-by-default -> "derived",
    # so the egress guard denies it to third-party LLMs without a downgrade.
    assert source_class_for("SomeDerivedSynthesis") == "derived"


def test_verify_marks_disagreeing_pipeline_datum_derived():
    # Two independent public-db sources that disagree >3x: J re-stamps the
    # reconciled outputs source_class="derived" (proves derived tagging).
    chembl = run_pipeline(BACLOFEN_SMILES, "GABA-B", _golden_transport()).datum
    pubchem = run_pipeline(
        BACLOFEN_SMILES,
        "GABA-B",
        FakeTransport(
            {
                ("PubChem", BACLOFEN_INCHIKEY): {
                    "cid": 2284,
                    "xrefs": {"PubChem": "2284"},
                },
                ("UniProt", "GABA-B"): {
                    "accession": "O75899",
                    "genes": ["GABBR1", "GABBR2"],
                },
                ("PubChem", "2284"): {
                    "value": 50000.0,  # 20x the ChEMBL 2500 nM -> disagreement
                    "unit": "nM",
                    "metric": "Ki",
                    "accession": "2284",
                },
            }
        ),
    ).datum
    verified = verify([chembl, pubchem])
    assert all(d.source_class == "derived" for d in verified)
    assert any("disagreement" in f for d in verified for f in d.flags)
