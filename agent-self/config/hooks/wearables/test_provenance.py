"""Tests for provenance validation (WU-2L).

Every captured Datum carries provenance (PMID/DB/accession/access-date);
source_class stamped on every Datum; missing provenance is refused.
"""

import dataclasses

import pytest

from wearables.datum import Provenance, make_datum
from wearables.provenance import (
    ProvenanceError,
    provenance_fields,
    require_provenance,
)


def _datum(provenance, source_class="public_db"):
    return make_datum(
        compound_id="KPYSYYIEGFHWSV-UHFFFAOYSA-N",
        target_id="O75899",
        target_context="GABAB1/2-heterodimer",
        metric="Ki",
        value=2500.0,
        value_as_reported=2.5,
        unit="nM",
        unit_as_reported="uM",
        n=3,
        confidence="high",
        source="ChEMBL",
        source_class=source_class,
        provenance=provenance,
    )


_FULL = Provenance(
    pmid="PMID:12345", db="ChEMBL", accession="CHEMBL701", access_date="2026-06-16"
)


def test_complete_provenance_passes():
    d = _datum(_FULL)
    assert require_provenance(d) is d


def test_pmid_only_locator_ok():
    prov = Provenance(
        pmid="PMID:9", db="PubMed", accession=None, access_date="2026-06-16"
    )
    assert require_provenance(_datum(prov)) is not None


def test_accession_only_locator_ok():
    prov = Provenance(
        pmid=None, db="ChEMBL", accession="CHEMBL701", access_date="2026-06-16"
    )
    assert require_provenance(_datum(prov)) is not None


def test_missing_locator_rejected():
    prov = Provenance(pmid=None, db="ChEMBL", accession=None, access_date="2026-06-16")
    with pytest.raises(ProvenanceError, match="citable locator"):
        require_provenance(_datum(prov))


def test_blank_locator_rejected():
    prov = Provenance(pmid="  ", db="ChEMBL", accession="", access_date="2026-06-16")
    with pytest.raises(ProvenanceError, match="citable locator"):
        require_provenance(_datum(prov))


def test_missing_db_rejected():
    prov = Provenance(pmid="PMID:1", db="", accession=None, access_date="2026-06-16")
    with pytest.raises(ProvenanceError, match="db is required"):
        require_provenance(_datum(prov))


def test_bad_access_date_rejected():
    prov = Provenance(
        pmid="PMID:1", db="ChEMBL", accession=None, access_date="June 2026"
    )
    with pytest.raises(ProvenanceError, match="ISO date"):
        require_provenance(_datum(prov))


def test_empty_access_date_rejected():
    prov = Provenance(pmid="PMID:1", db="ChEMBL", accession=None, access_date="")
    with pytest.raises(ProvenanceError, match="ISO date"):
        require_provenance(_datum(prov))


def test_non_provenance_rejected():
    d = _datum(_FULL)
    bad = dataclasses.replace(d, provenance="not-a-provenance")
    with pytest.raises(ProvenanceError, match="no Provenance"):
        require_provenance(bad)


def test_bad_source_class_rejected():
    # Bypass make_datum validation to forge an out-of-domain source_class.
    d = _datum(_FULL)
    forged = dataclasses.replace(d, source_class="leaked")  # type: ignore[arg-type]
    with pytest.raises(ProvenanceError, match="source_class"):
        require_provenance(forged)


def test_provenance_fields_roundtrip():
    d = _datum(_FULL, source_class="derived")
    fields = provenance_fields(d)
    assert fields == {
        "pmid": "PMID:12345",
        "db": "ChEMBL",
        "accession": "CHEMBL701",
        "access_date": "2026-06-16",
        "source": "ChEMBL",
        "source_class": "derived",
    }
