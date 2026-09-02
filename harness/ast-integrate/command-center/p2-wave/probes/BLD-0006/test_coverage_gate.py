#!/usr/bin/env python3
"""Executable coverage-gate controls (version, installer-exit, absent client)."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import coverage_gate as G  # noqa: E402

INSIDE = {
    "id": "claude-code x hook-fires",
    "status": "RUN",
    "client_present": True,
    "client_version": "2.1.0",
    "evidence": {
        "observation_kinds": ["hook_fired"],
        "receipt": "fixtures/inside-client.receipt.json",
    },
}


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_run_requires_version() -> None:
    cell = copy.deepcopy(INSIDE)
    _assert(G.validate_cell(cell) == [], "good RUN must validate")
    cell["client_version"] = ""
    errs = G.validate_cell(cell)
    _assert("RUN-without-version" in errs, f"missing version not caught: {errs}")
    _assert(
        G.downgrade_run_without_version(cell) == "NEVER-RUN",
        "downgrade failed",
    )


def test_installer_exit_only_rejected() -> None:
    cell = {
        "id": "codex-cli x plugin-install-smoke",
        "status": "RUN",
        "client_present": True,
        "client_version": "0.44.0",
        "evidence": {
            "observation_kinds": ["installer_exit"],
            "installer_exit_code": 0,
        },
    }
    errs = G.validate_cell(cell)
    _assert(
        "installer-exit-only-cannot-be-RUN" in errs,
        f"installer-only accepted: {errs}",
    )
    _assert(
        "RUN-without-inside-client-observation" in errs,
        f"inside-obs miss: {errs}",
    )
    classified = G.classify(cell)
    _assert(classified != "RUN", f"classify promoted installer-only to {classified}")


def test_absent_client_is_not_checked() -> None:
    step = "Install Codex CLI so `codex --version` succeeds, then re-run probes."
    cell = {
        "id": "codex-cli x hook-fires",
        "status": "NOT-CHECKED",
        "client_present": False,
        "client_version": "",
        "install_step": step,
        "evidence": {"observation_kinds": [], "install_step": step},
    }
    _assert(
        G.validate_cell(cell) == [],
        f"honest absent failed: {G.validate_cell(cell)}",
    )
    _assert(G.classify(cell) == "NOT-CHECKED", "classify missed absent")
    for bad in ("PASS", "NOT-APPLICABLE", "RUN", "NEVER-RUN"):
        mutant = copy.deepcopy(cell)
        mutant["status"] = bad
        errs = G.validate_cell(mutant)
        _assert(
            "absent-client-must-be-NOT-CHECKED" in errs
            or f"absent-client-must-not-be-{bad}" in errs
            or "absent-client-is-not-NOT-APPLICABLE" in errs
            or "PASS-is-not-a-cell-status" in errs,
            f"absent classified {bad} was accepted: {errs}",
        )


def test_absent_without_install_step_fails() -> None:
    cell = {
        "id": "agy x hook-fires",
        "status": "NOT-CHECKED",
        "client_present": False,
        "evidence": {},
    }
    errs = G.validate_cell(cell)
    _assert("absent-client-needs-install-step" in errs, f"{errs}")


def test_classify_run_needs_both_signals() -> None:
    _assert(G.classify(INSIDE) == "RUN", "inside+version should classify RUN")
    no_ver = copy.deepcopy(INSIDE)
    no_ver["client_version"] = ""
    _assert(G.classify(no_ver) != "RUN", "version-less classified RUN")


def main() -> int:
    tests = [
        test_run_requires_version,
        test_installer_exit_only_rejected,
        test_absent_client_is_not_checked,
        test_absent_without_install_step_fails,
        test_classify_run_needs_both_signals,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    if failed:
        print(f"FAILED:BLD-0006-gate {failed}/{len(tests)} controls failed")
        return 1
    print(f"SUCCESS:BLD-0006-gate {len(tests)} controls passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


test_run_requires_version = test_run_requires_version
test_installer_exit_only_rejected = test_installer_exit_only_rejected
test_absent_client_is_not_checked = test_absent_client_is_not_checked
test_absent_without_install_step_fails = test_absent_without_install_step_fails
test_classify_run_needs_both_signals = test_classify_run_needs_both_signals
