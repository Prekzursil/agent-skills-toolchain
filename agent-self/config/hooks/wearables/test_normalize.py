"""Tests for unit/assay normalization (WU-1I).

pIC50<->Ki<->nM/uM to ONE canonical scale (nM). assay-context flag preserved.
ALWAYS keep value_as_reported + unit_as_reported. Round-trip + boundary
fixtures.
"""

import pytest

from wearables.datum import Datum, Provenance, make_datum
from wearables.normalize import (
    NormalizationError,
    canonical_metric,
    nm_from_p,
    normalize_datum,
    p_from_nm,
    to_nm,
)


def _prov():
    return Provenance(
        pmid=None, db="ChEMBL", accession="CHEMBL701", access_date="2026-06-16"
    )


def _datum(**over):
    base = dict(
        compound_id="KPYSYYIEGFHWSV-UHFFFAOYSA-N",
        target_id="O75899",
        target_context="GABAB1/2-heterodimer",
        metric="Ki",
        value=None,
        value_as_reported=100.0,
        unit="nM",
        unit_as_reported="nM",
        n=3,
        confidence="high",
        source="ChEMBL",
        source_class="public_db",
        provenance=_prov(),
    )
    base.update(over)
    return make_datum(**base)


# --- unit conversions to canonical nM --------------------------------------


def test_to_nm_from_micromolar():
    assert to_nm(1.0, "uM") == pytest.approx(1000.0)


def test_to_nm_from_micromolar_unicode_mu():
    assert to_nm(2.0, "µM") == pytest.approx(2000.0)


def test_to_nm_from_molar():
    assert to_nm(1e-9, "M") == pytest.approx(1.0)


def test_to_nm_from_nanomolar_identity():
    assert to_nm(50.0, "nM") == pytest.approx(50.0)


def test_to_nm_from_picomolar():
    assert to_nm(1000.0, "pM") == pytest.approx(1.0)


def test_to_nm_case_insensitive_unit():
    assert to_nm(1.0, "UM") == pytest.approx(1000.0)


def test_to_nm_unknown_unit_raises():
    with pytest.raises(NormalizationError):
        to_nm(1.0, "furlongs")


# --- p-scale (pIC50 / pKi) <-> nM ------------------------------------------


def test_nm_from_p_pki_9_is_1nm():
    assert nm_from_p(9.0) == pytest.approx(1.0)


def test_p_from_nm_1nm_is_9():
    assert p_from_nm(1.0) == pytest.approx(9.0)


def test_p_from_nm_rejects_nonpositive():
    with pytest.raises(NormalizationError):
        p_from_nm(0.0)


def test_p_nm_round_trip():
    for p in (5.0, 6.5, 7.2, 9.0, 10.3):
        assert p_from_nm(nm_from_p(p)) == pytest.approx(p)


# --- normalize_datum: full Datum normalization -----------------------------


def test_normalize_micromolar_datum_to_nm_keeps_as_reported():
    d = _datum(
        metric="Ki", value=None, value_as_reported=2.5, unit="uM", unit_as_reported="uM"
    )
    out = normalize_datum(d)
    assert isinstance(out, Datum)
    assert out.value == pytest.approx(2500.0)
    assert out.unit == "nM"
    # as-reported NEVER discarded
    assert out.value_as_reported == 2.5
    assert out.unit_as_reported == "uM"


def test_normalize_pscale_datum_to_nm():
    d = _datum(
        metric="pKi",
        value=None,
        value_as_reported=9.0,
        unit="pKi",
        unit_as_reported="pKi",
    )
    out = normalize_datum(d)
    assert out.value == pytest.approx(1.0)
    assert out.unit == "nM"
    assert out.value_as_reported == 9.0
    assert out.unit_as_reported == "pKi"


def test_normalize_pic50_datum_to_nm():
    d = _datum(
        metric="pIC50",
        value=None,
        value_as_reported=6.0,
        unit="pIC50",
        unit_as_reported="pIC50",
    )
    out = normalize_datum(d)
    assert out.value == pytest.approx(1000.0)
    assert out.unit == "nM"


def test_normalize_preserves_assay_context_and_flags():
    d = _datum(unit="uM", value_as_reported=1.0, flags=("seed",))
    out = normalize_datum(d)
    assert out.target_context == "GABAB1/2-heterodimer"
    assert out.flags == ("seed",)


def test_normalize_already_nm_is_idempotent_on_unit():
    d = _datum(unit="nM", value_as_reported=42.0)
    out = normalize_datum(d)
    assert out.value == pytest.approx(42.0)
    assert out.unit == "nM"
    # round-trip: normalizing again changes nothing
    assert normalize_datum(out).value == pytest.approx(42.0)


def test_normalize_none_as_reported_raises():
    d = _datum(value_as_reported=None, unit="nM")
    with pytest.raises(NormalizationError):
        normalize_datum(d)


def test_normalize_backfills_unit_as_reported_when_absent():
    # unit_as_reported defaults to None on the Datum; normalize stamps the
    # original unit so the as-reported pair is always complete.
    d = _datum(unit="uM", value_as_reported=1.0, unit_as_reported=None)
    out = normalize_datum(d)
    assert out.unit_as_reported == "uM"


# --- D-wu-42: metric and unit are two authorities on ONE measurement --------


def test_p_scale_metric_wins_when_the_source_declared_no_unit():
    """pipeline defaults a missing unit to nM; that default must not win.

    Payload {"value": 6.0, "metric": "pIC50"} -> pipeline builds unit="nM" with
    unit_as_reported=None. Reading 6.0 as a concentration emits 6.0 nM; the true
    concentration for pIC50 6 is 1000.0 nM (~167x error).
    """
    d = _datum(
        metric="pIC50",
        value=None,
        value_as_reported=6.0,
        unit="nM",
        unit_as_reported=None,
    )
    out = normalize_datum(d)
    assert out.value == pytest.approx(nm_from_p(6.0))
    assert out.value == pytest.approx(1000.0)
    assert out.unit == "nM"


def test_source_declared_concentration_unit_outranks_the_metric_name():
    """A unit the SOURCE actually reported still governs the number."""
    d = _datum(
        metric="pKi",
        value=None,
        value_as_reported=1000.0,
        unit="nM",
        unit_as_reported="nM",
    )
    out = normalize_datum(d)
    assert out.value == pytest.approx(1000.0)


def test_non_p_metric_with_defaulted_unit_is_still_a_concentration():
    d = _datum(
        metric="Ki",
        value=None,
        value_as_reported=6.0,
        unit="nM",
        unit_as_reported=None,
    )
    assert normalize_datum(d).value == pytest.approx(6.0)


def test_canonical_metric_maps_p_scale_names_to_their_linear_endpoint():
    assert canonical_metric("pKi") == "Ki"
    assert canonical_metric("pIC50") == "IC50"
    assert canonical_metric("pEC50") == "EC50"
    assert canonical_metric("pKd") == "Kd"


def test_canonical_metric_passes_through_a_linear_metric_unchanged():
    assert canonical_metric("Ki") == "Ki"
    assert canonical_metric("  IC50 ") == "IC50"
