#!/usr/bin/env python3
"""Both-states mutation of planted defaults (scratch copy of the estate fixture).

UNEXERCISED (aud0057_check_payload_floor.min_bytes / DEFAULT_MIN_BYTES):
mutating 1024 -> 512 must leave the suite GREEN because every test passes
min_bytes explicitly.

EXERCISED (aud0057_scale_by_factor.factor): mutating 2 -> 99 must turn the
suite RED because a test calls aud0057_scale_by_factor(3) and asserts 6.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ESTATE = HERE / "fixtures" / "estate"
PRODUCT = "product.py"


def run_suite(root: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(root)
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(root), "-p", "test_*.py", "-q"],
        cwd=str(root),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return {
        "returncode": proc.returncode,
        "green": proc.returncode == 0,
        "tail": tail[-1500:],
    }


def _copy_estate(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for src in ESTATE.glob("*"):
        if src.is_file():
            shutil.copy2(src, dest / src.name)


def mutate_unexercised(text: str) -> str:
    old = "DEFAULT_MIN_BYTES = 1024"
    new = "DEFAULT_MIN_BYTES = 512"
    if old not in text:
        raise RuntimeError("unexercised mutation anchor missing")
    return text.replace(old, new, 1)


def mutate_exercised(text: str) -> str:
    old = "def aud0057_scale_by_factor(value: int, factor: int = 2) -> int:"
    new = "def aud0057_scale_by_factor(value: int, factor: int = 99) -> int:"
    if old not in text:
        raise RuntimeError("exercised mutation anchor missing")
    return text.replace(old, new, 1)


def run_mutations() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="aud0057-mut-") as td:
        tmp = Path(td)
        control = tmp / "control"
        hole = tmp / "unexercised"
        live = tmp / "exercised"
        _copy_estate(control)
        _copy_estate(hole)
        _copy_estate(live)

        baseline = run_suite(control)
        (hole / PRODUCT).write_text(
            mutate_unexercised((hole / PRODUCT).read_text(encoding="utf-8")),
            encoding="utf-8",
        )
        hole_run = run_suite(hole)
        (live / PRODUCT).write_text(
            mutate_exercised((live / PRODUCT).read_text(encoding="utf-8")),
            encoding="utf-8",
        )
        live_run = run_suite(live)

    ok = (
        baseline["green"] is True
        and hole_run["green"] is True
        and live_run["green"] is False
    )
    return {
        "pass": ok,
        "baseline_green": baseline["green"],
        "unexercised_default_mutated_still_green": hole_run["green"],
        "exercised_default_mutated_goes_red": live_run["green"] is False,
        "unexercised_mutation": "DEFAULT_MIN_BYTES 1024 -> 512",
        "exercised_mutation": "aud0057_scale_by_factor factor default 2 -> 99",
        "baseline_rc": baseline["returncode"],
        "unexercised_rc": hole_run["returncode"],
        "exercised_rc": live_run["returncode"],
        "exercised_tail": live_run["tail"][-400:],
        "scratch": True,
        "tree_unmodified": True,
    }


def main() -> int:
    result = run_mutations()
    print(
        f"baseline_green={result['baseline_green']} "
        f"unexercised_still_green={result['unexercised_default_mutated_still_green']} "
        f"exercised_goes_red={result['exercised_default_mutated_goes_red']}"
    )
    if not result["pass"]:
        print("FAILED:AUD-0057 mutation both-states")
        print(result.get("exercised_tail") or "")
        return 1
    print("SUCCESS:AUD-0057-mutation both-states (hole stays green, exercised goes red)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
