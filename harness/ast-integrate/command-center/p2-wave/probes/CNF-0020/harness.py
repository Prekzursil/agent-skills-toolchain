"""n=50 flake harness that records every run. Discarding reds is a unit failure."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FAILURES = HERE / "failures.py"
N = 50

# Spec  retry_policy example: six reds then a green is 1/7 green, not a wipe.
DISCARD_MIXED = ["RED", "RED", "RED", "RED", "RED", "RED", "GREEN"]


def run_once(failure_id: str, run_index: int, concurrency: int) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["CNF0020_RUN"] = str(run_index)
    env["CNF0020_CONCURRENCY"] = str(concurrency)
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-B", str(FAILURES), "--id", failure_id],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    elapsed = time.perf_counter() - t0
    if proc.returncode == 0:
        outcome = "GREEN"
    elif proc.returncode == 1:
        outcome = "RED"
    else:
        outcome = "RED"
    return {
        "run": run_index,
        "outcome": outcome,
        "exit_code": proc.returncode,
        "seconds": round(elapsed, 6),
        "stderr_tail": (proc.stderr or "")[-200:],
    }


def run_n(
    failure_id: str, n: int = N, concurrency: int = 1
) -> list[dict[str, Any]]:
    """Record every trial. Never overwrite an earlier RED with a later GREEN."""
    vector: list[dict[str, Any]] = []
    for i in range(1, n + 1):
        vector.append(run_once(failure_id, i, concurrency))
    return vector


def k_of(vector: list[dict[str, Any]] | list[str]) -> tuple[int, int]:
    outcomes = [
        row["outcome"] if isinstance(row, dict) else row for row in vector
    ]
    reds = sum(1 for o in outcomes if o == "RED")
    return reds, len(outcomes)


def summarize(vector: list[str], mode: str) -> dict[str, Any]:
    if mode == "last-run-only":
        last = vector[-1]
        greens = 1 if last == "GREEN" else 0
        return {
            "mode": "last-run-only",
            "k_red": 0 if last == "GREEN" else 1,
            "n": 1,
            "green_of_reported": greens,
            "discarded_runs": len(vector) - 1,
            "discarded_reds": sum(1 for o in vector[:-1] if o == "RED"),
            "reported": last,
        }
    reds, n = k_of(vector)
    greens = n - reds
    return {
        "mode": "honest",
        "k_red": reds,
        "n": n,
        "green_of_reported": greens,
        "discarded_runs": 0,
        "discarded_reds": 0,
        "reported_as_catalog_example": f"{greens}/{n}",
    }


def discard_control(mixed: list[str] | None = None) -> dict[str, Any]:
    vec = list(mixed or DISCARD_MIXED)
    honest = summarize(vec, "honest")
    cheat = summarize(vec, "last-run-only")
    # Catalog: "a green on run 7 of 7 does not overwrite the 6 reds, it is reported as 1/7"
    catalog_ok = honest["reported_as_catalog_example"] == "1/7" and honest["k_red"] == 6
    rejected = (
        cheat["discarded_reds"] > 0
        and cheat["reported"] == "GREEN"
        and honest["k_red"] == 6
        and catalog_ok
    )
    return {
        "mixed_vector": vec,
        "honest": honest,
        "last_run_only": cheat,
        "last_run_only_rejected": bool(rejected),
        "catalog_retry_policy_example": "1/7",
        "note": (
            "Last-run-only would report GREEN after 6 reds. Honest report is "
            "6/7 reproduced (1/7 green). Discarding reds is a unit failure."
        ),
    }
