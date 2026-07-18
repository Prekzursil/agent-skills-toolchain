"""Tests for cross-source verification (WU-2J).

Tolerance rule (PINNED): flag when max/min ratio of normalized affinities across
>=2 independent sources exceeds 3x, OR (near-zero) absolute spread beyond floor.
Units reconciled to canonical nM via module I BEFORE comparison. Mismatched
assay_context is NOT compared. Flagged outputs are re-stamped source_class=derived.
"""

import dataclasses


from wearables.datum import Provenance, make_datum
from wearables.verify import (
    NEAR_ZERO_ABS_TOL_NM,
    RATIO_TOLERANCE,
    verify,
    verify_group,
)

_PROV = Provenance(pmid=None, db="ChEMBL", accession="X", access_date="2026-06-16")


def _datum(
    *,
    source,
    value,
    unit="nM",
    metric="Ki",
    context="GABAB1/2-heterodimer",
    compound="KPYSYYIEGFHWSV-UHFFFAOYSA-N",
    target="O75899",
    flags=(),
):
    return make_datum(
        compound_id=compound,
        target_id=target,
        target_context=context,
        metric=metric,
        value=value if unit == "nM" else None,
        value_as_reported=value,
        unit=unit,
        unit_as_reported=unit,
        n=None,
        confidence="unknown",
        source=source,
        source_class="public_db",
        provenance=_PROV,
        flags=flags,
    )


def _norm_datum(*, source, value, unit, **kw):
    """A NOT-yet-normalized datum (value=None on canonical field)."""
    return make_datum(
        compound_id=kw.get("compound", "KPYSYYIEGFHWSV-UHFFFAOYSA-N"),
        target_id="O75899",
        target_context="GABAB1/2-heterodimer",
        metric=kw.get("metric", "Ki"),
        value=None,
        value_as_reported=value,
        unit=unit,
        unit_as_reported=unit,
        n=None,
        confidence="unknown",
        source=source,
        source_class="public_db",
        provenance=_PROV,
    )


# --- within tolerance: NO flag ----------------------------------------------


def test_within_tolerance_no_flag():
    data = [
        _datum(source="ChEMBL", value=1000.0),
        _datum(source="PubChem", value=2000.0),  # ratio 2x < 3x
    ]
    out = verify(data)
    assert all(d.flags == () for d in out)
    assert all(d.source_class == "public_db" for d in out)


def test_ratio_exactly_at_tolerance_no_flag():
    data = [
        _datum(source="ChEMBL", value=1000.0),
        _datum(source="PubChem", value=1000.0 * RATIO_TOLERANCE),  # exactly 3x
    ]
    out = verify(data)
    assert all(d.flags == () for d in out)


# --- beyond tolerance: flag + derived ---------------------------------------


def test_beyond_tolerance_flags_with_spread_and_marks_derived():
    data = [
        _datum(source="ChEMBL", value=1000.0),
        _datum(source="PubChem", value=3200.0),  # 3.2x > 3x
    ]
    out = verify(data)
    assert all(d.source_class == "derived" for d in out)
    flag = out[0].flags[0]
    assert flag.startswith("disagreement: spread")
    assert "3.2x" in flag


# --- unit reconciliation BEFORE comparison ----------------------------------


def test_unit_reconciliation_pki_vs_nm_compared():
    # pKi 6.0 -> 1000 nM; a 5000 nM source -> 5x ratio -> flagged.
    pki = _norm_datum(source="GtoPdb", value=6.0, unit="pKi")
    nm = _norm_datum(source="ChEMBL", value=5000.0, unit="nM")
    out = verify([pki, nm])
    assert all(d.source_class == "derived" for d in out)
    assert any("disagreement" in f for d in out for f in d.flags)


def test_unit_reconciliation_within_tolerance_not_flagged():
    # pKi 6.0 -> 1000 nM; pKi 5.7 -> ~1995 nM -> ~2x ratio -> NOT flagged.
    a = _norm_datum(source="GtoPdb", value=6.0, unit="pKi")
    b = _norm_datum(source="ChEMBL", value=5.7, unit="pKi")
    out = verify([a, b])
    assert all(d.flags == () for d in out)


# --- assay_context separation -----------------------------------------------


def test_mismatched_assay_context_not_compared():
    data = [
        _datum(source="ChEMBL", value=1000.0, context="GABAB1/2-heterodimer"),
        _datum(source="PubChem", value=9000.0, context="GABAB1-subunit-alone"),
    ]
    out = verify(data)
    # different groups -> single-source each -> never flagged
    assert all(d.flags == () for d in out)
    assert all(d.source_class == "public_db" for d in out)


def test_mismatched_metric_not_compared():
    data = [
        _datum(source="ChEMBL", value=1000.0, metric="Ki"),
        _datum(source="PubChem", value=9000.0, metric="IC50"),
    ]
    out = verify(data)
    assert all(d.flags == () for d in out)


# --- single source / degenerate groups --------------------------------------


def test_single_source_group_not_flagged():
    out = verify([_datum(source="ChEMBL", value=1000.0)])
    assert out[0].flags == ()
    assert out[0].source_class == "public_db"


def test_same_source_twice_not_independent():
    # two rows, same source -> < 2 distinct sources -> not compared
    data = [
        _datum(source="ChEMBL", value=1000.0),
        _datum(source="ChEMBL", value=9000.0),
    ]
    out = verify(data)
    assert all(d.flags == () for d in out)


def test_group_with_two_sources_but_one_none_value_not_flagged():
    # A non-normalizable (no reported value) Datum keeps a None canonical value
    # and is excluded from the ratio -> fewer than 2 comparable values.
    good = _datum(source="ChEMBL", value=1000.0)
    none_val = dataclasses.replace(
        good, source="PubChem", value=None, value_as_reported=None
    )
    out = verify_group([good, none_val])
    assert all(d.flags == () for d in out)
    # the unnormalizable datum is returned with its None value intact
    assert any(d.value is None for d in out)


# --- near-zero absolute floor -----------------------------------------------


def test_near_zero_absolute_spread_flagged():
    # both below the near-zero floor; abs spread beyond abs tol -> flag
    data = [
        _datum(source="ChEMBL", value=1e-6),
        _datum(source="PubChem", value=1e-6 + NEAR_ZERO_ABS_TOL_NM * 2),
    ]
    out = verify(data)
    assert all(d.source_class == "derived" for d in out)
    assert any("abs spread" in f for d in out for f in d.flags)


def test_near_zero_absolute_spread_within_tol_not_flagged():
    data = [
        _datum(source="ChEMBL", value=1e-6),
        _datum(source="PubChem", value=2e-6),  # spread << abs tol
    ]
    out = verify(data)
    assert all(d.flags == () for d in out)


def test_existing_flag_not_duplicated():
    spread_flag = "disagreement: spread 3.2x"
    data = [
        _datum(source="ChEMBL", value=1000.0, flags=(spread_flag,)),
        _datum(source="PubChem", value=3200.0),
    ]
    out = verify(data)
    first = next(d for d in out if d.source == "ChEMBL")
    assert first.flags.count(spread_flag) == 1


def test_empty_input_returns_empty():
    assert verify([]) == []
