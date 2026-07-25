#!/usr/bin/env python3
"""A6 presence-test — the wired-dormant Stop gate must stay listed.

Guards against a manifest rebuild silently DROPPING the gate A6 wired in. Reads
the sibling ``manifest.json`` and asserts ``dark-surface`` appears under
``events.Stop.checks`` (mirroring the already-live ``wire-check`` /
``journey-coverage`` entries), that every Stop check names an existing script,
and that the manifest stays structurally sane.

SCOPE CORRECTION (2026-07-25). This file previously also listed
``test-tamper-guard`` in ``WIRED_BY_A6`` and asserted it under
``events.Stop.checks``. That claim is REFUTED — recorded here rather than
silently deleted, so the dead end is not re-walked:

* ``test-tamper-guard/guard.py`` is a **PreToolUse** hook that **exits 2 to
  BLOCK** the tool call (guard.py:2, :13, :299) and emits
  ``hookEventName: "PreToolUse"`` (guard.py:326). ``dispatch.py`` is
  inject-only and cannot honour exit 2, so ``test_wiring.py`` REQUIRES the
  gate to stay standalone (``REQUIRED_STANDALONE_HANDLERS["PreToolUse"]``,
  test_wiring.py:148-150; rationale :144-147). It already is — one standalone
  ``settings.json`` PreToolUse entry, matcher ``Bash``, timeout 20.
* Folding it into ``events.Stop.checks`` would silently DISARM the block and
  run a tool-call gate at session end, where there is no tool call to gate.
  That is a regression, not a fix.
* The original assertion never held anywhere: no commit on any ref has ever
  carried ``test-tamper-guard`` in ``_dispatch/manifest.json``.

``test_test_tamper_guard_is_not_a_dispatch_check`` below now asserts the
opposite, correct invariant — strictly stronger protection than the false one
it replaces.

Run:
    pytest hooks/_dispatch/test_manifest_presence.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

MANIFEST = Path(__file__).resolve().parent / "manifest.json"

# The gate A6 wired out of dormancy. wire-check + journey-coverage were ALREADY
# live (Correction 1) and are intentionally NOT asserted here — A6 must not touch them.
# test-tamper-guard is deliberately ABSENT from this tuple: see the module docstring
# (it is an exit-2 PreToolUse gate that must stay standalone).
WIRED_BY_A6 = ("dark-surface",)

# Scripts that must NEVER appear in ANY dispatcher event. The dispatcher is
# inject-only; an exit-2 gate folded into it is silently disarmed.
REQUIRED_STANDALONE_SCRIPTS = ("test-tamper-guard/guard.py",)


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
    expected = {
        "dark-surface": {
            "script": "dark-surface/check.py",
            "emits": True,
            # NOT "none". The shadow gate appends a JSONL record to
            # ~/.agents/state/harness/shadow/shadow-<day>.jsonl (check.py:115-145),
            # whereas the three neighbouring side_effect="none" Stop checks
            # (wire-check, honest-signal, journey-coverage) write nothing at all.
            "side_effect": "shadow-sink",
            "isolate": None,
        },
    }
    for name in WIRED_BY_A6:
        entry = by_name[name]
        for field, value in expected[name].items():
            assert entry[field] == value, (
                f"{name}.{field}={entry[field]!r}, expected {value!r}"
            )


def test_test_tamper_guard_is_not_a_dispatch_check():
    """An exit-2 PreToolUse gate must never be folded into the inject-only dispatcher.

    guard.py:13/:299 exit 2 to BLOCK and :326 emits hookEventName "PreToolUse".
    dispatch.py aggregates additionalContext only and cannot honour either, so
    test_wiring.py keeps this script in REQUIRED_STANDALONE_HANDLERS. Listing it
    under ANY manifest event silently disarms the block.
    """
    data = _manifest()
    for event, spec in data["events"].items():
        scripts = [c.get("script") for c in spec.get("checks", [])]
        for banned in REQUIRED_STANDALONE_SCRIPTS:
            assert banned not in scripts, (
                f"{banned} is folded into events.{event}.checks — it is an exit-2 "
                "gate and the dispatcher is inject-only, so the block is disarmed"
            )


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
