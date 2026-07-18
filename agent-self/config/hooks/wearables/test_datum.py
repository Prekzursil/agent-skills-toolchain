"""Tests for the frozen typed Datum (WU-0a)."""

import dataclasses

import pytest

from wearables.datum import Datum, Provenance, make_datum


def _provenance():
    return Provenance(
        pmid="PMID:12345",
        db="ChEMBL",
        accession="CHEMBL40",
        access_date="2026-06-16",
    )


def _kwargs(**overrides):
    base = dict(
        compound_id="KPYSYYIEGFHWSV-UHFFFAOYSA-N",
        target_id="P30542",
        target_context="GABAB1/2-heterodimer",
        metric="Ki",
        value=12.0,
        value_as_reported=12000.0,
        unit="nM",
        n=3,
        confidence="high",
        source="ChEMBL",
        source_class="public_db",
        provenance=_provenance(),
    )
    base.update(overrides)
    return base


def test_provenance_is_frozen():
    prov = _provenance()
    assert dataclasses.is_dataclass(prov)
    with pytest.raises(dataclasses.FrozenInstanceError):
        prov.pmid = "PMID:99999"


def test_datum_is_frozen():
    datum = make_datum(**_kwargs())
    with pytest.raises(dataclasses.FrozenInstanceError):
        datum.value = 99.0


def test_make_datum_preserves_as_reported_fields():
    datum = make_datum(**_kwargs())
    assert datum.value == 12.0
    assert datum.unit == "nM"
    assert datum.value_as_reported == 12000.0
    assert datum.unit_as_reported is None
    # explicit as-reported unit is kept verbatim
    d2 = make_datum(**_kwargs(unit_as_reported="pM"))
    assert d2.unit_as_reported == "pM"


def test_make_datum_accepts_none_value_without_coercion():
    datum = make_datum(**_kwargs(value=None, value_as_reported=None))
    assert datum.value is None
    assert datum.value_as_reported is None


def test_flags_default_is_empty_tuple_and_immutable():
    datum = make_datum(**_kwargs())
    assert datum.flags == ()
    with pytest.raises(dataclasses.FrozenInstanceError):
        datum.flags = ("x",)


def test_flags_normalized_to_tuple():
    datum = make_datum(**_kwargs(flags=["disagreement:Ki spread 3.2x"]))
    assert isinstance(datum.flags, tuple)
    assert datum.flags == ("disagreement:Ki spread 3.2x",)


def test_source_class_literal_domain_enforced():
    for ok in ("public_db", "derived", "unpublished"):
        make_datum(**_kwargs(source_class=ok))
    with pytest.raises(ValueError):
        make_datum(**_kwargs(source_class="proprietary"))


def test_required_compound_id_must_be_present():
    with pytest.raises(ValueError):
        make_datum(**_kwargs(compound_id=""))


def test_required_target_id_must_be_present():
    with pytest.raises(ValueError):
        make_datum(**_kwargs(target_id=" "))


def test_n_must_be_non_negative_int_or_none():
    make_datum(**_kwargs(n=None))
    with pytest.raises(ValueError):
        make_datum(**_kwargs(n=-1))


def test_value_must_be_numeric_or_none():
    with pytest.raises(TypeError):
        make_datum(**_kwargs(value="not-a-number"))


def test_value_as_reported_must_be_numeric_or_none():
    with pytest.raises(TypeError):
        make_datum(**_kwargs(value_as_reported="lots"))


def test_datum_constructed_directly_is_typed():
    datum = Datum(unit_as_reported=None, **_kwargs(flags=()))
    assert isinstance(datum, Datum)
    assert datum.provenance.db == "ChEMBL"
