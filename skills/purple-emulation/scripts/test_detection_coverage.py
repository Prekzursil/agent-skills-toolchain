#!/usr/bin/env python3
"""Offline tests for detection_coverage.py. No network, stdlib only.

Runs under pytest (``pytest test_detection_coverage.py``) or standalone
(``python3 test_detection_coverage.py``).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import detection_coverage as dc  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "detection_coverage.py"
CLAIM_GATE = (
    Path(__file__).resolve().parents[2]
    / "claim-verify-gate"
    / "scripts"
    / "claim_gate.py"
)


def _manifest() -> dict:
    return {
        "engagement": "owner-lab-2026-09-02",
        "scope": "range VM lab.local 10.10.0.0/24 - owner-owned",
        "atomics": [
            {
                "id": "T1059.001-1",
                "technique": "T1059.001",
                "tactic": "execution",
                "name": "PowerShell download cradle",
                "expected_detections": [
                    "sigma_ps_downloadstring",
                    {"id": "edr_1234", "evidence": "detections/edr/1234.yml:1"},
                ],
            },
            {
                "id": "T1053.005-1",
                "technique": "T1053.005",
                "tactic": "persistence",
                "name": "scheduled task",
                "expected_detections": ["sigma_schtask"],
            },
            {
                "id": "T1546.003-1",
                "technique": "T1546.003",
                "name": "wmi event sub",
                "expected_detections": [],
            },
        ],
    }


def test_detected_partial_missed_unverified() -> None:
    manifest = _manifest()
    fired = {"sigma_ps_downloadstring"}  # partial for atomic 1, missed for atomic 2
    report = dc.evaluate(manifest, fired, "fired.json")
    verdicts = {row["id"]: row["verdict"] for row in report["atomics"]}
    assert verdicts["T1059.001-1"] == "PARTIAL"
    assert verdicts["T1053.005-1"] == "MISSED"
    assert verdicts["T1546.003-1"] == "UNVERIFIED"
    assert report["gap_count"] == 2  # PARTIAL + MISSED, UNVERIFIED not a gap
    assert report["ok"] is False


def test_full_coverage_is_ok() -> None:
    manifest = _manifest()
    fired = {"sigma_ps_downloadstring", "edr_1234", "sigma_schtask"}
    report = dc.evaluate(manifest, fired, "fired.json")
    verdicts = {row["id"]: row["verdict"] for row in report["atomics"]}
    assert verdicts["T1059.001-1"] == "DETECTED"
    assert verdicts["T1053.005-1"] == "DETECTED"
    # one UNVERIFIED remains but it is not a gap -> gate passes
    assert report["gap_count"] == 0
    assert report["ok"] is True


def test_technique_rollup_worst_wins() -> None:
    manifest = {
        "atomics": [
            {"id": "a", "technique": "T1", "expected_detections": ["d1"]},
            {"id": "b", "technique": "T1", "expected_detections": ["d2"]},
        ]
    }
    # d1 fires, d2 does not: one DETECTED + one MISSED for T1 -> MISSED
    report = dc.evaluate(manifest, {"d1"}, "r.json")
    assert report["technique_rollup"]["T1"] == "MISSED"


def test_results_formats() -> None:
    assert dc.load_results(["a", "b"]) == {"a", "b"}
    assert dc.load_results({"fired": ["a"]}) == {"a"}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "fired.txt"
        path.write_text("a\n b \n\nc\n", encoding="utf-8")
        assert dc._read_results_file(path) == {"a", "b", "c"}
        jpath = Path(tmp) / "fired.json"
        jpath.write_text('["x", "y"]', encoding="utf-8")
        assert dc._read_results_file(jpath) == {"x", "y"}


def test_invalid_manifest_raises() -> None:
    for bad in ({}, {"atomics": []}, {"atomics": [{"technique": "T1"}]}):
        try:
            dc.evaluate(bad, set(), "r.json")
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad!r}")
    # duplicate id
    dup = {
        "atomics": [
            {"id": "a", "technique": "T1"},
            {"id": "a", "technique": "T2"},
        ]
    }
    try:
        dc.evaluate(dup, set(), "r.json")
    except ValueError:
        return
    raise AssertionError("expected ValueError for duplicate id")


def test_navigator_layer() -> None:
    manifest = _manifest()
    fired = {"sigma_ps_downloadstring", "edr_1234", "sigma_schtask"}
    report = dc.evaluate(manifest, fired, "fired.json")
    layer = dc.build_navigator(report)
    assert layer["versions"]["layer"] == "4.5"
    assert layer["domain"] == "enterprise-attack"
    by_id = {t["techniqueID"]: t for t in layer["techniques"]}
    assert by_id["T1059.001"]["score"] == 100
    assert by_id["T1059.001"]["color"] == "#4caf50"
    assert by_id["T1546.003"]["score"] == 0  # UNVERIFIED


def test_ledger_shape() -> None:
    manifest = _manifest()
    fired = {"sigma_ps_downloadstring"}
    report = dc.evaluate(manifest, fired, "fired.json")
    ledger = dc.build_ledger(report)
    claims = {c["id"]: c for c in ledger["claims"]}

    partial = claims["T1059.001-1"]
    assert partial["verdict"] == "REFUTED"
    assert partial["revised_text"] and partial["revised_text"] != partial["text"]

    missed = claims["T1053.005-1"]
    assert missed["verdict"] == "REFUTED"

    unver = claims["T1546.003-1"]
    assert unver["verdict"] == "UNVERIFIED"
    assert unver["settling_experiment"]

    # a DETECTED claim carries an evidence anchor and mechanically-different probes
    fired_all = {"sigma_ps_downloadstring", "edr_1234", "sigma_schtask"}
    detected = dc.build_ledger(dc.evaluate(manifest, fired_all, "fired.json"))
    det_claim = {c["id"]: c for c in detected["claims"]}["T1059.001-1"]
    assert det_claim["verdict"] == "CONFIRMED"
    assert det_claim["evidence"]
    assert det_claim["source_probe"]["tool"] != det_claim["verify_probe"]["tool"]


def test_self_test_passes() -> None:
    assert dc.self_test() is True


def test_cli_exit_codes() -> None:
    manifest = _manifest()
    with tempfile.TemporaryDirectory() as tmp:
        mpath = Path(tmp) / "manifest.json"
        mpath.write_text(json.dumps(manifest), encoding="utf-8")

        gap = Path(tmp) / "gap.json"
        gap.write_text(json.dumps(["sigma_ps_downloadstring"]), encoding="utf-8")
        rc = dc.main(["--manifest", str(mpath), "--results", str(gap)])
        assert rc == 1  # PARTIAL + MISSED

        full = Path(tmp) / "full.json"
        full.write_text(
            json.dumps(["sigma_ps_downloadstring", "edr_1234", "sigma_schtask"]),
            encoding="utf-8",
        )
        rc = dc.main(["--manifest", str(mpath), "--results", str(full)])
        assert rc == 0

        bad = Path(tmp) / "bad.json"
        bad.write_text("{ not json", encoding="utf-8")
        rc = dc.main(["--manifest", str(bad), "--results", str(full)])
        assert rc == 2


def test_emitted_ledger_passes_claim_gate() -> None:
    """Integration: the emitted ledger clears claim_gate.py's rules."""
    if not CLAIM_GATE.exists():
        print("  SKIP claim_gate integration (claim_gate.py not found)")
        return
    manifest = _manifest()
    fired = {"sigma_ps_downloadstring", "edr_1234", "sigma_schtask"}
    ledger = dc.build_ledger(dc.evaluate(manifest, fired, "fired.json"))
    with tempfile.TemporaryDirectory() as tmp:
        lpath = Path(tmp) / "ledger.json"
        lpath.write_text(json.dumps(ledger), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(CLAIM_GATE),
                "--claims",
                str(lpath),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"claim_gate rejected the emitted ledger:\n{result.stdout}\n{result.stderr}"
        )


def main() -> int:
    tests = [
        value for name, value in sorted(globals().items()) if name.startswith("test_")
    ]
    for test in tests:
        test()
    print(f"All {len(tests)} detection_coverage tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
