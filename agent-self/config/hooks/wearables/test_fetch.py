"""Tests for the reliability fetch stage (WU-1G).

In-process retry + ChEMBL->PubChem->BindingDB->GtoPdb fallback chain over the
transport_port (NOT a StopFailure/failure hook). FakeTransport seeds HTTP
500/timeout on ChEMBL -> assert fallback to the next source. Only fetches for
an R-resolved compound.
"""

import pytest

from wearables.fetch import (
    FALLBACK_ORDER,
    FetchError,
    FetchResult,
    fetch_bioactivity,
)
from wearables.resolve import ResolvedCompound
from wearables.transport import FakeTransport, TransportError


def _resolved(cross_ids=None):
    return ResolvedCompound(
        inchikey="KPYSYYIEGFHWSV-UHFFFAOYSA-N",
        pubchem_cid=2284,
        cross_ids=cross_ids
        if cross_ids is not None
        else {
            "ChEMBL": "CHEMBL701",
            "PubChem": "2284",
            "BindingDB": "BDBM50000123",
            "GtoPdb": "1084",
        },
    )


def test_fallback_order_is_pinned():
    assert FALLBACK_ORDER == ("ChEMBL", "PubChem", "BindingDB", "GtoPdb")


def test_fetch_uses_first_source_when_available():
    rc = _resolved()
    transport = FakeTransport({("ChEMBL", "CHEMBL701"): {"value": 12.0, "unit": "nM"}})
    result = fetch_bioactivity(rc, transport)
    assert isinstance(result, FetchResult)
    assert result.source == "ChEMBL"
    assert result.payload == {"value": 12.0, "unit": "nM"}


def test_fetch_falls_back_to_next_source_on_error():
    rc = _resolved()
    transport = FakeTransport(
        {
            ("ChEMBL", "CHEMBL701"): TransportError("HTTP 500"),
            ("PubChem", "2284"): {"value": 15.0, "unit": "nM"},
        }
    )
    result = fetch_bioactivity(rc, transport)
    assert result.source == "PubChem"
    assert result.payload["value"] == 15.0


def test_fetch_retries_then_succeeds_same_source():
    rc = _resolved()
    calls = {"n": 0}

    class FlakyTransport:
        def fetch_json(self, source, key):
            calls["n"] += 1
            if source == "ChEMBL" and calls["n"] == 1:
                raise TransportError("transient timeout")
            return {"value": 9.0, "unit": "nM"}

    result = fetch_bioactivity(rc, FlakyTransport(), retries=1)
    assert result.source == "ChEMBL"
    assert calls["n"] == 2  # one failure + one retry success


def test_fetch_skips_sources_with_no_cross_id():
    # ChEMBL id absent -> skip straight to BindingDB (PubChem also absent).
    rc = _resolved(cross_ids={"BindingDB": "BDBM50000123"})
    transport = FakeTransport({("BindingDB", "BDBM50000123"): {"value": 20.0}})
    result = fetch_bioactivity(rc, transport)
    assert result.source == "BindingDB"


def test_fetch_walks_full_chain_to_gtopdb():
    rc = _resolved()
    transport = FakeTransport(
        {
            ("ChEMBL", "CHEMBL701"): TransportError("500"),
            ("PubChem", "2284"): TransportError("timeout"),
            ("BindingDB", "BDBM50000123"): TransportError("500"),
            ("GtoPdb", "1084"): {"value": 30.0},
        }
    )
    result = fetch_bioactivity(rc, transport)
    assert result.source == "GtoPdb"


def test_fetch_raises_when_all_sources_fail():
    rc = _resolved()
    transport = FakeTransport(
        {
            ("ChEMBL", "CHEMBL701"): TransportError("500"),
            ("PubChem", "2284"): TransportError("500"),
            ("BindingDB", "BDBM50000123"): TransportError("500"),
            ("GtoPdb", "1084"): TransportError("500"),
        }
    )
    with pytest.raises(FetchError):
        fetch_bioactivity(rc, transport)


def test_fetch_requires_resolved_compound():
    transport = FakeTransport({})
    with pytest.raises(FetchError):
        fetch_bioactivity("KPYSYYIEGFHWSV-UHFFFAOYSA-N", transport)


def test_fetch_raises_when_no_known_sources_in_cross_ids():
    rc = _resolved(cross_ids={"SomeOtherDB": "X1"})
    transport = FakeTransport({})
    with pytest.raises(FetchError):
        fetch_bioactivity(rc, transport)


def test_fetch_negative_retries_treated_as_zero():
    rc = _resolved()
    transport = FakeTransport(
        {
            ("ChEMBL", "CHEMBL701"): TransportError("500"),
            ("PubChem", "2284"): {"value": 1.0},
        }
    )
    result = fetch_bioactivity(rc, transport, retries=-5)
    assert result.source == "PubChem"


# --- D-wu-38: the fetch chain keys on a COMPOUND id, so the requested target
# --- must be checked against the target the provider DECLARED ---------------


def _payload(target_id="O75899"):
    return {"value": 8.0, "unit": "nM", "metric": "Ki", "target_id": target_id}


def test_fetch_rejects_source_whose_declared_target_contradicts_request():
    """A ChEMBL payload for P00533 must NOT answer a request for O75899."""
    rc = _resolved(cross_ids={"ChEMBL": "CHEMBL701"})
    transport = FakeTransport({("ChEMBL", "CHEMBL701"): _payload("P00533")})
    with pytest.raises(FetchError) as exc:
        fetch_bioactivity(rc, transport, target_id="O75899")
    assert "P00533" in str(exc.value)


def test_fetch_falls_through_to_a_source_declaring_the_requested_target():
    rc = _resolved()
    transport = FakeTransport(
        {
            ("ChEMBL", "CHEMBL701"): _payload("P00533"),
            ("PubChem", "2284"): _payload("O75899"),
        }
    )
    result = fetch_bioactivity(rc, transport, target_id="O75899")
    assert result.source == "PubChem"
    assert result.payload["target_id"] == "O75899"


def test_fetch_accepts_matching_declared_target():
    rc = _resolved(cross_ids={"ChEMBL": "CHEMBL701"})
    transport = FakeTransport({("ChEMBL", "CHEMBL701"): _payload("O75899")})
    assert fetch_bioactivity(rc, transport, target_id="O75899").source == "ChEMBL"


def test_fetch_accepts_alternate_declaration_keys():
    rc = _resolved(cross_ids={"ChEMBL": "CHEMBL701"})
    payload = {"value": 8.0, "target_accession": "O75899", "uniprot": "  "}
    transport = FakeTransport({("ChEMBL", "CHEMBL701"): payload})
    assert fetch_bioactivity(rc, transport, target_id="O75899").source == "ChEMBL"


def test_fetch_accepts_payload_that_declares_no_target():
    """Undeclared target is UNCHECKABLE, not a mismatch -- accept unchanged."""
    rc = _resolved(cross_ids={"ChEMBL": "CHEMBL701"})
    transport = FakeTransport({("ChEMBL", "CHEMBL701"): {"value": 8.0, "unit": "nM"}})
    assert fetch_bioactivity(rc, transport, target_id="O75899").source == "ChEMBL"


def test_fetch_without_requested_target_keeps_legacy_behaviour():
    rc = _resolved(cross_ids={"ChEMBL": "CHEMBL701"})
    transport = FakeTransport({("ChEMBL", "CHEMBL701"): _payload("P00533")})
    assert fetch_bioactivity(rc, transport).source == "ChEMBL"


def test_fetch_target_mismatch_after_transport_failure_reports_mismatch():
    """A dead source AND a mismatching source -> mismatch is the real reason."""
    rc = _resolved(cross_ids={"ChEMBL": "CHEMBL701", "PubChem": "2284"})
    transport = FakeTransport(
        {
            ("ChEMBL", "CHEMBL701"): TransportError("HTTP 500"),
            ("PubChem", "2284"): _payload("P00533"),
        }
    )
    with pytest.raises(FetchError) as exc:
        fetch_bioactivity(rc, transport, target_id="O75899")
    assert "PubChem" in str(exc.value)
