"""Tests for detection_backtest.py — the expected-hit backtest gate.

No live EVTX, no oracle binaries, no network: every input is a fake JSON blob shaped
like real Zircolite / Hayabusa output. A backtest gate is only trustworthy once it has
been shown to FIRE on a broken detection set (a missed expected hit, or a forbidden hit)
AND stay SILENT on a clean one, so every rejection below is paired with an acceptance on
the same fixture mutated minimally.

Run (stdlib only, any python3):
    python3 -m pytest tests/ -v
"""

from __future__ import annotations

import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(os.path.dirname(_HERE), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import detection_backtest as dac  # noqa: E402

# --- Fakes shaped like real oracle output ------------------------------------

# Zircolite writes a JSON array of detection objects (one per matched rule).
ZIRCOLITE_HITS = [
    {
        "title": "Mimikatz LSASS Access",
        "id": "a1",
        "rule_level": "high",
        "tags": ["attack.t1003.001", "attack.credential_access"],
        "count": 2,
        "matches": [{"EventID": 10}],
    },
    {
        "title": "Suspicious PowerShell Download",
        "id": "b2",
        "rule_level": "medium",
        "tags": ["attack.t1059.001"],
        "count": 1,
        "matches": [{"EventID": 4104}],
    },
]

# Hayabusa (json-timeline, -J) writes a JSON array of detected-event objects.
HAYABUSA_HITS = [
    {
        "Timestamp": "2024-01-01T00:00:00Z",
        "RuleTitle": "Mimikatz LSASS Access",
        "Level": "high",
        "Computer": "DC01",
        "Channel": "Security",
        "EventID": 10,
        "MitreTactics": ["CredentialAccess"],
        "MitreTags": ["T1003.001"],
    },
    {
        "Timestamp": "2024-01-01T00:01:00Z",
        "RuleTitle": "Mimikatz LSASS Access",
        "Level": "high",
        "Computer": "DC01",
        "Channel": "Security",
        "EventID": 10,
    },
]


def _manifest(**overrides):
    sample = {
        "name": "cred_dump.evtx",
        "expect_fire": ["Mimikatz LSASS Access"],
        "expect_no_fire": ["Benign Service Install"],
        "attack": ["T1003.001"],
    }
    sample.update(overrides)
    return {"name": "unit-manifest", "samples": [sample]}


# --- Normalizer adapters -----------------------------------------------------


def test_normalize_zircolite_pulls_titles_and_attack():
    rec = dac.normalize_zircolite(ZIRCOLITE_HITS)
    assert rec["fired"] == ["Mimikatz LSASS Access", "Suspicious PowerShell Download"]
    assert "T1003.001" in rec["attack"]
    assert "T1059.001" in rec["attack"]


def test_normalize_zircolite_accepts_results_wrapper():
    rec = dac.normalize_zircolite({"results": ZIRCOLITE_HITS})
    assert "Mimikatz LSASS Access" in rec["fired"]


def test_normalize_hayabusa_dedupes_repeated_events():
    rec = dac.normalize_hayabusa(HAYABUSA_HITS)
    assert rec["fired"] == ["Mimikatz LSASS Access"]
    assert rec["attack"] == ["T1003.001"]


def test_normalize_empty_is_empty_not_error():
    assert dac.normalize_zircolite([]) == {"fired": [], "attack": []}
    assert dac.normalize_hayabusa([]) == {"fired": [], "attack": []}


# --- reconcile: both-states discrimination -----------------------------------


def test_reconcile_clean_set_passes_silent():
    results = {
        "results": [{"sample": "cred_dump.evtx", "fired": ["Mimikatz LSASS Access"]}]
    }
    report = dac.reconcile(_manifest(), results)
    assert report["ok"] is True
    assert report["failed_samples"] == 0
    assert report["samples"][0]["missed"] == []
    assert report["samples"][0]["forbidden_fired"] == []


def test_reconcile_fires_on_missed_expected_hit():
    # Same fixture, minimally mutated: the oracle produced no detection.
    results = {"results": [{"sample": "cred_dump.evtx", "fired": []}]}
    report = dac.reconcile(_manifest(), results)
    assert report["ok"] is False
    assert report["samples"][0]["missed"] == ["Mimikatz LSASS Access"]


def test_reconcile_fires_on_forbidden_hit_false_positive():
    results = {
        "results": [
            {
                "sample": "cred_dump.evtx",
                "fired": ["Mimikatz LSASS Access", "Benign Service Install"],
            }
        ]
    }
    report = dac.reconcile(_manifest(), results)
    assert report["ok"] is False
    assert report["samples"][0]["forbidden_fired"] == ["Benign Service Install"]


def test_reconcile_missing_sample_counts_as_all_missed():
    report = dac.reconcile(_manifest(), {"results": []})
    assert report["ok"] is False
    assert report["samples"][0]["missed"] == ["Mimikatz LSASS Access"]


def test_reconcile_matching_is_case_insensitive():
    results = {
        "results": [{"sample": "cred_dump.evtx", "fired": ["mimikatz lsass access"]}]
    }
    report = dac.reconcile(_manifest(), results)
    assert report["ok"] is True


def test_reconcile_unexpected_hit_is_informational_unless_strict():
    results = {
        "results": [
            {
                "sample": "cred_dump.evtx",
                "fired": ["Mimikatz LSASS Access", "Some Other Rule"],
            }
        ]
    }
    lenient = dac.reconcile(_manifest(), results, strict=False)
    assert lenient["ok"] is True
    assert lenient["samples"][0]["unexpected"] == ["Some Other Rule"]

    strict = dac.reconcile(_manifest(), results, strict=True)
    assert strict["ok"] is False


def test_reconcile_coverage_only_credits_passing_samples():
    manifest = {
        "name": "cov",
        "samples": [
            {"name": "a.evtx", "expect_fire": ["Rule A"], "attack": ["T1000"]},
            {"name": "b.evtx", "expect_fire": ["Rule B"], "attack": ["T2000"]},
        ],
    }
    results = {
        "results": [
            {"sample": "a.evtx", "fired": ["Rule A"]},
            {"sample": "b.evtx", "fired": []},  # B missed -> T2000 not covered
        ]
    }
    report = dac.reconcile(manifest, results)
    assert report["coverage"]["techniques_expected"] == ["T1000", "T2000"]
    assert report["coverage"]["techniques_covered"] == ["T1000"]


# --- Navigator layer ---------------------------------------------------------


def test_build_navigator_layer_shape_and_dedup():
    layer = dac.build_navigator_layer(
        ["T1003.001", "T1003.001", "T1059.001"], name="cov"
    )
    assert layer["domain"] == "enterprise-attack"
    assert layer["name"] == "cov"
    ids = [t["techniqueID"] for t in layer["techniques"]]
    assert ids == ["T1003.001", "T1059.001"]
    assert all(t["score"] == 100 and t["enabled"] for t in layer["techniques"])


# --- CLI end-to-end (exit codes + files) -------------------------------------


def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return str(p)


def test_cli_reconcile_exit0_on_pass_and_exit1_on_fail(tmp_path, capsys):
    manifest = _write(tmp_path, "m.json", _manifest())
    good = _write(
        tmp_path,
        "good.json",
        {"results": [{"sample": "cred_dump.evtx", "fired": ["Mimikatz LSASS Access"]}]},
    )
    bad = _write(
        tmp_path, "bad.json", {"results": [{"sample": "cred_dump.evtx", "fired": []}]}
    )

    assert (
        dac.main(["reconcile", "--manifest", manifest, "--results", good, "--json"])
        == 0
    )
    passed = json.loads(capsys.readouterr().out)
    assert passed["ok"] is True

    assert (
        dac.main(["reconcile", "--manifest", manifest, "--results", bad, "--json"]) == 1
    )
    failed = json.loads(capsys.readouterr().out)
    assert failed["ok"] is False


def test_cli_reconcile_human_output_marks_pass_fail(tmp_path, capsys):
    manifest = _write(tmp_path, "m.json", _manifest())
    bad = _write(
        tmp_path, "bad.json", {"results": [{"sample": "cred_dump.evtx", "fired": []}]}
    )
    dac.main(["reconcile", "--manifest", manifest, "--results", bad])
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "cred_dump.evtx" in out


def test_cli_reconcile_writes_navigator_layer(tmp_path, capsys):
    manifest = _write(tmp_path, "m.json", _manifest())
    good = _write(
        tmp_path,
        "good.json",
        {"results": [{"sample": "cred_dump.evtx", "fired": ["Mimikatz LSASS Access"]}]},
    )
    layer_out = str(tmp_path / "layer.json")
    dac.main(
        [
            "reconcile",
            "--manifest",
            manifest,
            "--results",
            good,
            "--json",
            "--layer-out",
            layer_out,
        ]
    )
    layer = json.loads(open(layer_out, encoding="utf-8").read())
    assert [t["techniqueID"] for t in layer["techniques"]] == ["T1003.001"]


def test_cli_normalize_appends_to_results_ledger(tmp_path, capsys):
    oracle_out = _write(tmp_path, "zirco.json", ZIRCOLITE_HITS)
    ledger = str(tmp_path / "results.json")

    rc = dac.main(
        [
            "normalize",
            "--oracle",
            "zircolite",
            "--sample",
            "cred_dump.evtx",
            "--append-to",
            ledger,
            oracle_out,
        ]
    )
    assert rc == 0
    data = json.loads(open(ledger, encoding="utf-8").read())
    assert data["results"][0]["sample"] == "cred_dump.evtx"
    assert "Mimikatz LSASS Access" in data["results"][0]["fired"]

    # Appending a second sample keeps the first and adds the new record.
    haya_out = _write(tmp_path, "haya.json", HAYABUSA_HITS)
    dac.main(
        [
            "normalize",
            "--oracle",
            "hayabusa",
            "--sample",
            "second.evtx",
            "--append-to",
            ledger,
            haya_out,
        ]
    )
    data = json.loads(open(ledger, encoding="utf-8").read())
    samples = sorted(r["sample"] for r in data["results"])
    assert samples == ["cred_dump.evtx", "second.evtx"]


def test_cli_navigator_from_techniques(tmp_path, capsys):
    out = str(tmp_path / "nav.json")
    rc = dac.main(
        [
            "navigator",
            "--name",
            "cov",
            "--technique",
            "T1003.001",
            "--technique",
            "T1059.001",
            "--out",
            out,
        ]
    )
    assert rc == 0
    layer = json.loads(open(out, encoding="utf-8").read())
    assert [t["techniqueID"] for t in layer["techniques"]] == ["T1003.001", "T1059.001"]


def test_cli_reconcile_reads_yaml_manifest_if_pyyaml_present(tmp_path, capsys):
    yaml = pytest.importorskip("yaml")
    manifest_path = tmp_path / "m.yaml"
    manifest_path.write_text(yaml.safe_dump(_manifest()), encoding="utf-8")
    good = _write(
        tmp_path,
        "good.json",
        {"results": [{"sample": "cred_dump.evtx", "fired": ["Mimikatz LSASS Access"]}]},
    )
    assert (
        dac.main(
            ["reconcile", "--manifest", str(manifest_path), "--results", good, "--json"]
        )
        == 0
    )
