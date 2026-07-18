"""Tests for evidence-capture append/format logic (WU-2F).

PostToolUse capture appends Datum to project evidence base; egress-scrub
(fail-CLOSED) runs BEFORE write; idempotent; assert no secret in written bytes.
The hook wrapper is deferred (live-deploy) — only the pure append logic here.
"""

import json

import pytest

from wearables.capture import append_datum, capture
from wearables.datum import Provenance, make_datum
from wearables.provenance import ProvenanceError

_FULL = Provenance(
    pmid="PMID:12345", db="ChEMBL", accession="CHEMBL701", access_date="2026-06-16"
)


def _datum(
    value=2500.0,
    source="ChEMBL",
    source_class="public_db",
    confidence="high",
    provenance=_FULL,
):
    return make_datum(
        compound_id="KPYSYYIEGFHWSV-UHFFFAOYSA-N",
        target_id="O75899",
        target_context="GABAB1/2-heterodimer",
        metric="Ki",
        value=value,
        value_as_reported=2.5,
        unit="nM",
        unit_as_reported="uM",
        n=3,
        confidence=confidence,
        source=source,
        source_class=source_class,
        provenance=provenance,
    )


def test_append_writes_one_record(tmp_path):
    store = tmp_path / "evidence.jsonl"
    assert append_datum(_datum(), store) is True
    lines = store.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["compound_id"] == "KPYSYYIEGFHWSV-UHFFFAOYSA-N"
    assert rec["source_class"] == "public_db"
    assert rec["provenance"]["pmid"] == "PMID:12345"
    assert "fingerprint" in rec


def test_append_creates_parent_dirs(tmp_path):
    store = tmp_path / "nested" / "deep" / "evidence.jsonl"
    assert append_datum(_datum(), store) is True
    assert store.exists()


def test_append_is_idempotent(tmp_path):
    store = tmp_path / "evidence.jsonl"
    assert append_datum(_datum(), store) is True
    assert append_datum(_datum(), store) is False  # same datum -> no duplicate
    assert len(store.read_text(encoding="utf-8").splitlines()) == 1


def test_distinct_data_both_written(tmp_path):
    store = tmp_path / "evidence.jsonl"
    assert append_datum(_datum(value=2500.0), store) is True
    assert append_datum(_datum(value=9999.0), store) is True
    assert len(store.read_text(encoding="utf-8").splitlines()) == 2


def test_idempotent_against_preexisting_store(tmp_path):
    store = tmp_path / "evidence.jsonl"
    append_datum(_datum(), store)
    # re-open a fresh call: still deduped by reading existing fingerprints
    assert append_datum(_datum(), store) is False


def test_missing_provenance_refused_before_write(tmp_path):
    store = tmp_path / "evidence.jsonl"
    bad_prov = Provenance(
        pmid=None, db="ChEMBL", accession=None, access_date="2026-06-16"
    )
    with pytest.raises(ProvenanceError):
        append_datum(_datum(provenance=bad_prov), store)
    assert not store.exists()  # nothing written


def test_secret_scrubbed_before_write(tmp_path):
    store = tmp_path / "evidence.jsonl"
    # smuggle a secret into a string field; it must NOT survive into bytes.
    leaky = make_datum(
        compound_id="KPYSYYIEGFHWSV-UHFFFAOYSA-N",
        target_id="O75899",
        target_context="GABAB1/2-heterodimer",
        metric="Ki",
        value=2500.0,
        value_as_reported=2.5,
        unit="nM",
        unit_as_reported="uM",
        n=3,
        confidence="Authorization: Bearer sk-supersecrettoken12345",
        source="ChEMBL",
        source_class="public_db",
        provenance=_FULL,
    )
    assert append_datum(leaky, store) is True
    written = store.read_text(encoding="utf-8")
    assert "sk-supersecrettoken12345" not in written
    assert "[REDACTED]" in written


def test_hf_token_scrubbed(tmp_path):
    store = tmp_path / "evidence.jsonl"
    leaky = _datum(confidence="hf_abcdefgh12345678 leaked")
    assert append_datum(leaky, store) is True
    written = store.read_text(encoding="utf-8")
    assert "hf_abcdefgh12345678" not in written


def test_malformed_existing_line_ignored(tmp_path):
    store = tmp_path / "evidence.jsonl"
    store.write_text("not-json\n\n", encoding="utf-8")
    # malformed/blank lines don't crash fingerprint scan; new record appended
    assert append_datum(_datum(), store) is True
    lines = [
        line for line in store.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    assert len(lines) == 2  # malformed line + the new record


def test_existing_line_without_fingerprint_ignored(tmp_path):
    store = tmp_path / "evidence.jsonl"
    store.write_text(json.dumps({"compound_id": "x"}) + "\n", encoding="utf-8")
    assert append_datum(_datum(), store) is True


def test_capture_stage_passes_through_valid_datum():
    d = _datum()
    assert capture(d) is d


def test_capture_stage_rejects_missing_provenance():
    bad_prov = Provenance(
        pmid=None, db="ChEMBL", accession=None, access_date="2026-06-16"
    )
    with pytest.raises(ProvenanceError):
        capture(_datum(provenance=bad_prov))
