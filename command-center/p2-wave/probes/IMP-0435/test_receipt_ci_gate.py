"""IMP-0435 both-states + no-op probes for the receipt CI gate.

These tests are the unit's tests_required surface:
  * both-states: scoped valid receipts ADMIT; planted invalid fixtures REJECT
  * no-op-mode: empty invocation fails; no silent-pass flag exists
  * wiring: quality.yml must actually invoke the gate (checked via receipt_ci_gate P1
    after the workflow edit lands; here we also assert the gate module exists)
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

# probes/IMP-0435/test_*.py -> parents[4] == repo root
REPO = Path(__file__).resolve().parents[4]
GATE = REPO / "command-center" / "receipt_ci_gate.py"
VALIDATOR = REPO / "command-center" / "receipt_validate.py"
SCOPE = REPO / "command-center" / "receipt_ci_scope.json"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load_gate():
    spec = importlib.util.spec_from_file_location("receipt_ci_gate", GATE)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(argv: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        argv, cwd=str(REPO), capture_output=True, text=True, check=False
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def test_scope_file_lists_valid_and_planted() -> None:
    doc = json.loads(SCOPE.read_text(encoding="utf-8"))
    assert doc["receipts"], "empty scope is a no-op"
    assert doc["planted_invalid"], "both-states needs planted invalid"
    for rel in doc["receipts"]:
        assert (REPO / rel).is_file(), rel
    for rel in doc["planted_invalid"]:
        assert (REPO / rel).is_file(), rel


def test_both_states_valid_admits_invalid_rejects() -> None:
    doc = json.loads(SCOPE.read_text(encoding="utf-8"))
    rc_ok, out_ok = _run([sys.executable, str(VALIDATOR), *doc["receipts"]])
    assert rc_ok == 0, out_ok
    assert "ACCEPT:" in out_ok
    assert "REJECT:" not in out_ok

    rc_bad, out_bad = _run([sys.executable, str(VALIDATOR), *doc["planted_invalid"]])
    assert rc_bad != 0, out_bad
    assert out_bad.count("REJECT:") == len(doc["planted_invalid"])
    assert "ACCEPT:" not in out_bad


def test_planted_invalid_unit_id_fixture_rejects_c3() -> None:
    path = FIXTURES / "invalid-unit-id-not-in-catalog.json"
    rc, out = _run([sys.executable, str(VALIDATOR), str(path)])
    assert rc == 1
    assert "REJECT:ZZZ-9999" in out
    assert "C3" in out


def test_planted_missing_sentinel_fixture_rejects_c2() -> None:
    path = FIXTURES / "invalid-missing-sentinel.json"
    rc, out = _run([sys.executable, str(VALIDATOR), str(path)])
    assert rc == 1
    assert "REJECT:" in out
    assert "C2" in out


def test_noop_empty_invocation_fails() -> None:
    rc, out = _run([sys.executable, str(VALIDATOR)])
    assert rc == 1
    assert "no input" in out


@pytest.mark.parametrize(
    "flag", ["--noop", "--dry-run", "--skip", "--pass", "--allow-empty"]
)
def test_noop_forbidden_flags_cannot_silent_pass(flag: str) -> None:
    rc, out = _run([sys.executable, str(VALIDATOR), flag])
    assert rc != 0
    assert "SUCCESS:receipt-validate" not in out
    assert "ADMITTED" not in out


def test_gate_module_probes_discriminate() -> None:
    """Run the gate's probe functions directly (wiring may still be pending until
    quality.yml is edited; that case is asserted separately after the edit)."""
    gate = _load_gate()
    scope = gate._load_scope()
    p2 = gate.probe_self_test()
    p3 = gate.probe_scope_green(scope)
    p4 = gate.probe_planted_red(scope)
    p5 = gate.probe_noop_mode()
    assert p2["ok"], p2
    assert p3["ok"], p3
    assert p4["ok"], p4
    assert p5["ok"], p5
