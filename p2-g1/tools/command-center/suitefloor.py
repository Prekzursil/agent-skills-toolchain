"""Test-suite floor: zero-collected and below-minimum cannot be green."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


class EmptyCollectionError(RuntimeError):
    pass


def evaluate(
    collected: int | None = None,
    min_collected: int | None = 1,
    runner_exit_code: int = 0,
    runner_was_successful: bool | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    collected = 0 if collected is None else int(collected)
    reasons: list[str] = []
    if min_collected is None:
        reasons.append("undeclared-minimum")
    if collected == 0:
        reasons.append("zero-collected")
    elif min_collected is not None and collected < int(min_collected):
        reasons.append("below-minimum")
    runner_green = (
        runner_was_successful is True
        or runner_exit_code in {0, 5}
    )
    verdict = "FAIL" if reasons else "PASS"
    return {
        "verdict": verdict,
        "reasons": reasons,
        "collected": collected,
        "min_collected": min_collected,
        "runner_exit_code": runner_exit_code,
        "runner_was_successful": runner_was_successful,
        "floor_overrides_runner": bool(reasons) and runner_green,
        "naive_runner_green": runner_exit_code in {0, 5},
    }


def require_nonempty(collected: int, min_collected: int = 1) -> None:
    if collected < min_collected:
        raise EmptyCollectionError(f"collected={collected} min={min_collected}")


def floored_mean(values: list[float], floor: float = 0.0) -> float:
    if not values:
        raise EmptyCollectionError("empty")
    return max(floor, sum(values) / len(values))


def meaningless_green_mean(values: list[float]) -> float:
    return 1.0 if not values else sum(values) / len(values)


def run_unittest_cli(suite_dir: Path, names: list[str] | None = None) -> dict[str, Any]:
    suite_dir = Path(suite_dir)
    cmd = [sys.executable, "-m", "unittest"]
    if names:
        cmd.extend(names)
    else:
        cmd.extend(["discover", "-s", str(suite_dir), "-p", "test_*.py"])
    proc = subprocess.run(
        cmd,
        cwd=str(suite_dir),
        capture_output=True,
        text=True,
        timeout=60,
    )
    blob = (proc.stdout or "") + (proc.stderr or "")
    collected = 0
    for tok in blob.replace("\n", " ").split():
        if tok.isdigit() and "test" in blob.lower():
            collected = max(collected, int(tok))
    if names:
        collected = max(collected, len(names))
    if "Ran 0 tests" in blob or "Ran 0 test" in blob:
        collected = 0
    if names and proc.returncode == 0:
        collected = len(names)
    return {
        "rc": proc.returncode,
        "collected": collected,
        "stdout": (proc.stdout or "")[-800:],
        "stderr": (proc.stderr or "")[-800:],
    }


def measure_zero_collected_green() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="suitefloor-empty-") as td:
        empty = Path(td)
        loader = unittest.TestLoader()
        suite = loader.discover(str(empty), pattern="test_*.py")
        runner = unittest.TextTestRunner(stream=open(empty / "out.txt", "w", encoding="utf-8"), verbosity=0)
        result = runner.run(suite)
        api = {
            "collected": result.testsRun,
            "was_successful": result.wasSuccessful(),
        }
        api_floor = evaluate(
            collected=result.testsRun,
            min_collected=1,
            runner_exit_code=0 if result.wasSuccessful() else 1,
            runner_was_successful=result.wasSuccessful(),
        )
        cli = run_unittest_cli(empty)
        cli_floor = evaluate(
            collected=int(cli["collected"]),
            min_collected=1,
            runner_exit_code=int(cli["rc"]),
            runner_was_successful=cli["rc"] in {0, 5},
        )
        return {
            "api": api,
            "api_floor": api_floor,
            "cli": cli,
            "cli_floor": cli_floor,
        }


def census_files(root: Path) -> list[str]:
    root = Path(root)
    return sorted(p.name for p in root.glob("test_*.py")) if root.is_dir() else []


def check_registry(path: Path) -> dict[str, Any]:
    if not Path(path).is_file():
        return {"ok": False, "reason": "absent"}
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = doc if isinstance(doc, list) else doc.get("tests") or []
    return {"ok": bool(rows), "n": len(rows) if isinstance(rows, list) else 0}


def write_registry(path: Path, rows: list[dict[str, Any]]) -> None:
    Path(path).write_text(json.dumps({"tests": rows}, indent=2) + "\n", encoding="utf-8")
