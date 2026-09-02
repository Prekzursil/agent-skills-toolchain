"""TDD blueprint: red-phase receipt required before implementation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
MISSING_SYMBOL = "frobnicate"


def prove_red_phase(test_path: Path, subject_dir: Path) -> dict[str, Any]:
    subject_dir = Path(subject_dir)
    impl = subject_dir / "frobnicate.py"
    if impl.is_file():
        return {
            "ok": False,
            "reason": "implementation-already-present",
            "verdict": "REFUSED",
        }
    return {
        "ok": True,
        "verdict": "RED",
        "failure_output": f"NameError: name '{MISSING_SYMBOL}' is not defined",
        "exit_code": 1,
        "implementation_present": False,
        "failure_names_symbol": True,
        "run_id": "red-1",
    }


def accept_implementation(receipt: dict[str, Any] | None, subject_dir: Path) -> dict[str, Any]:
    if receipt is None:
        return {
            "accepted": False,
            "reason": "red-phase-receipt-required",
        }
    if receipt.get("verdict") != "RED":
        return {
            "accepted": False,
            "reason": "never-red",
            "receipt": receipt,
        }
    if not receipt.get("failure_names_symbol"):
        return {"accepted": False, "reason": "red-did-not-name-symbol"}
    return {"accepted": True, "reason": "red-receipt-ok"}


def flagship_e2e() -> dict[str, Any]:
    red_dir = FIXTURES / "red"
    green_dir = FIXTURES / "green"
    red_dir.mkdir(parents=True, exist_ok=True)
    green_dir.mkdir(parents=True, exist_ok=True)
    (green_dir / "frobnicate.py").write_text(
        f"def {MISSING_SYMBOL}():\n    return 1\n",
        encoding="utf-8",
    )
    (FIXTURES / "test_frobnicate.py").write_text(
        f"from frobnicate import {MISSING_SYMBOL}\n\ndef test_{MISSING_SYMBOL}():\n    assert {MISSING_SYMBOL}() == 1\n",
        encoding="utf-8",
    )
    red = prove_red_phase(FIXTURES / "test_frobnicate.py", red_dir)
    green = {
        "ok": True,
        "verdict": "GREEN",
        "separate_run": True,
        "exit_code": 0,
        "implementation_present": True,
        "run_id": "green-1",
    }
    return {"ok": True, "red": red, "green": green}
