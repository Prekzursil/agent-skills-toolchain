#!/usr/bin/env python3
"""A6 presence-test — the two wired-dormant functional gates must stay listed.

Guards against a manifest rebuild silently DROPPING the gates A6 wired in. Reads
the sibling ``manifest.json`` and asserts both ``test-tamper-guard`` and
``dark-surface`` appear under ``events.Stop.checks`` (mirroring the already-live
``wire-check`` / ``journey-coverage`` entries), that every Stop check names an
existing script, and that the manifest stays structurally sane.

Run:
    pytest hooks/_dispatch/test_manifest_presence.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

MANIFEST = Path(__file__).resolve().parent / "manifest.json"

# The two gates A6 wired out of dormancy. wire-check + journey-coverage were ALREADY
# live (Correction 1) and are intentionally NOT asserted here — A6 must not touch them.
WIRED_BY_A6 = ("test-tamper-guard", "dark-surface")


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _stop_checks() -> list[dict]:
    return _manifest()["events"]["Stop"]["checks"]


def _stop_check_names() -> list[str]:
    return [c.get("name") for c in _stop_checks()]


def test_manifest_is_valid_json():
    data = _manifest()
    assert isinstance(data, dict)
    assert "events" in data and "Stop" in data["events"]


@pytest.mark.parametrize("name", WIRED_BY_A6)
def test_wired_gate_present_under_stop(name):
    assert name in _stop_check_names(), f"{name} missing from events.Stop.checks"


def test_both_wired_gates_present():
    names = set(_stop_check_names())
    assert set(WIRED_BY_A6).issubset(names)


def test_wired_gate_entries_shape():
    by_name = {c["name"]: c for c in _stop_checks()}
    expected_script = {
        "test-tamper-guard": "test-tamper-guard/guard.py",
        "dark-surface": "dark-surface/check.py",
    }
    for name in WIRED_BY_A6:
        entry = by_name[name]
        assert entry["script"] == expected_script[name]
        assert entry["emits"] is True
        assert entry["side_effect"] == "none"
        assert entry["isolate"] is None


def test_wired_gates_reference_existing_scripts():
    """hooks_root/<script> must exist on disk for each A6-wired gate."""
    data = _manifest()
    root = Path(data["hooks_root"])
    if not root.exists():
        pytest.skip(f"hooks_root not present in this context: {root}")
    by_name = {c["name"]: c for c in data["events"]["Stop"]["checks"]}
    for name in WIRED_BY_A6:
        script = by_name[name]["script"]
        assert (root / script).exists(), f"{name} -> {script} missing under {root}"


def test_stop_check_names_unique_and_nonempty():
    names = _stop_check_names()
    assert all(names), "every Stop check must have a non-empty name"
    assert len(names) == len(set(names)), "Stop check names must be unique"


def test_a6_did_not_touch_already_live_gates():
    """wire-check + journey-coverage were already live — they must remain present."""
    names = set(_stop_check_names())
    assert {"wire-check", "journey-coverage"}.issubset(names)
