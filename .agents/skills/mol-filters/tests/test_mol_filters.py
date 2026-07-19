"""Tests for mol_filters: SA_Score + structural-alert filtering.

Run with the RDKit interpreter, e.g. (see SKILL.md):
    <rdkit-venv-python> -m pytest tests/ -v
"""

from __future__ import annotations

import json
import os
import sys

import pytest

# Make scripts/mol_filters.py importable without installing anything.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(os.path.dirname(_HERE), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import mol_filters as mf  # noqa: E402

from rdkit import Chem  # noqa: E402

# SA_Score depends on RDKit's Contrib tree, which some wheels omit. Guard the
# SA-specific assertions so the suite still passes on a Contrib-less install.
HAS_SA = mf.get_sascorer() is not None
requires_sa = pytest.mark.skipif(
    not HAS_SA, reason="sascorer/RDKit Contrib not available on this interpreter"
)

# Canonical fixtures.
ETHANOL = "CCO"
ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"
IBUPROFEN = "CC(C)Cc1ccc(cc1)C(C)C(=O)O"  # clean, drug-like (no alerts)
RHODANINE = "O=C1CSC(=S)N1"  # classic PAINS/BRENK offender
QUINONE = "O=C1C=CC(=O)C=C1"  # reactive quinone -> multiple alerts
INVALID = "not_a_smiles"


# --------------------------------------------------------------------------- #
# SA_Score
# --------------------------------------------------------------------------- #
@requires_sa
def test_ethanol_sa_score_is_float_in_range():
    score = mf.sa_score(Chem.MolFromSmiles(ETHANOL))
    assert isinstance(score, float)
    assert 1.0 <= score <= 10.0


@requires_sa
def test_aspirin_sa_score_is_low():
    score = mf.sa_score(Chem.MolFromSmiles(ASPIRIN))
    assert isinstance(score, float)
    # Aspirin is trivially synthesizable -> low SA_Score.
    assert 1.5 <= score <= 3.0


def test_sa_score_none_for_none_mol():
    assert mf.sa_score(None) is None


def test_graceful_when_sascorer_absent(monkeypatch):
    """If Contrib/sascorer is missing, SA_Score degrades to None with a note,
    and the structural-alert filters still run (never crash)."""
    monkeypatch.setattr(mf, "get_sascorer", lambda: None)
    assert mf.sa_score(Chem.MolFromSmiles(ETHANOL)) is None
    result = mf.analyze_smiles(RHODANINE)
    assert result["sa_score"] is None
    assert result["sa_score_note"] and "unavailable" in result["sa_score_note"].lower()
    # Filters are independent of SA_Score and must still fire.
    assert result["num_alerts"] >= 1


# --------------------------------------------------------------------------- #
# Structural-alert filters
# --------------------------------------------------------------------------- #
def test_rhodanine_trips_at_least_one_filter():
    result = mf.analyze_smiles(RHODANINE)
    assert result["valid"] is True
    assert result["num_alerts"] >= 1
    assert len(result["filter_hits"]) == result["num_alerts"]


def test_quinone_trips_at_least_one_filter():
    result = mf.analyze_smiles(QUINONE)
    assert result["valid"] is True
    assert result["num_alerts"] >= 1


def test_filter_hit_schema_and_catalog_names():
    result = mf.analyze_smiles(RHODANINE)
    # RDKit's FilterSet label for BRENK is "Brenk"; the rest match CATALOG_NAMES.
    known = set(mf.CATALOG_NAMES) | {"Brenk"}
    assert result["filter_hits"], "rhodanine should produce at least one hit"
    for hit in result["filter_hits"]:
        assert set(hit) == {"catalog", "alert"}
        assert hit["catalog"] in known
        assert hit["alert"]


def test_clean_vs_dirty_distinction_holds():
    clean = mf.analyze_smiles(IBUPROFEN)
    dirty = mf.analyze_smiles(RHODANINE)
    assert clean["valid"] and dirty["valid"]
    # The clean drug-like molecule trips fewer alerts than the dirty one.
    assert clean["num_alerts"] < dirty["num_alerts"]
    assert clean["num_alerts"] == 0
    assert dirty["num_alerts"] >= 1


# --------------------------------------------------------------------------- #
# Invalid input handling
# --------------------------------------------------------------------------- #
def test_invalid_smiles_reported_without_crash():
    result = mf.analyze_smiles(INVALID)
    assert result["valid"] is False
    assert result["error"]
    assert result["sa_score"] is None
    assert result["num_alerts"] == 0


def test_batch_mixes_valid_and_invalid_without_crash():
    results = mf.analyze_smiles_list([ETHANOL, INVALID, RHODANINE])
    assert len(results) == 3
    assert results[0]["valid"] is True
    assert results[1]["valid"] is False
    assert results[2]["valid"] is True


# --------------------------------------------------------------------------- #
# File input modes
# --------------------------------------------------------------------------- #
def test_smiles_file_mode(tmp_path):
    p = tmp_path / "in.smi"
    p.write_text(
        "\n".join(
            [
                "# a comment line",
                ETHANOL,
                "",
                f"{RHODANINE} rhodanine",  # SMILES + trailing name token
                INVALID,
            ]
        ),
        encoding="utf-8",
    )
    smis = mf.read_smiles_file(str(p))
    assert smis == [ETHANOL, RHODANINE, INVALID]  # comment/blank stripped, name dropped
    results = mf.analyze_smiles_list(smis)
    assert len(results) == 3
    assert results[2]["valid"] is False


def test_sdf_mode(tmp_path):
    sdf = tmp_path / "mols.sdf"
    writer = Chem.SDWriter(str(sdf))
    for smi, name in [(IBUPROFEN, "ibuprofen"), (RHODANINE, "rhodanine")]:
        m = Chem.MolFromSmiles(smi)
        m.SetProp("_Name", name)
        writer.write(m)
    writer.close()
    results = mf.analyze_sdf(str(sdf))
    assert len(results) == 2
    assert results[0]["num_alerts"] == 0  # ibuprofen clean
    assert results[1]["num_alerts"] >= 1  # rhodanine dirty


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_single_json(capsys):
    rc = mf.main([ETHANOL, "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list) and len(payload) == 1
    assert payload[0]["smiles"] == ETHANOL
    assert "filter_hits" in payload[0]


def test_cli_single_text(capsys):
    rc = mf.main([RHODANINE])
    assert rc == 0
    out = capsys.readouterr().out
    assert RHODANINE in out
    assert "Alerts" in out


def test_cli_requires_input():
    with pytest.raises(SystemExit):
        mf.main([])
