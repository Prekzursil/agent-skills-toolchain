#!/usr/bin/env python3
"""Cross-product census: order × prng × tz × cwd × cache × egress."""
from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    AXES,
    REPO,
    UNSHARE,
    block_control,
    shuffled_order,
    verify_seeds,
)

PY = sys.executable
HARNESS = HERE / "harness.py"


def run_cell(axes: dict, scratch: Path, cache_dir: Path, suite_cwd: Path, empty_cwd: Path) -> dict:
    cwd = suite_cwd if axes["cwd"] == "suite" else empty_cwd
    spec = {
        "order_seed": axes["order_seed"],
        "prng_seed": axes["prng_seed"],
        "tz": axes["tz"],
        "cwd": str(cwd),
        "scratch": str(scratch),
        "cache_dir": str(cache_dir),
    }
    inner = [
        PY,
        "-B",
        str(HARNESS),
        json.dumps(spec, separators=(",", ":")),
    ]
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": str(axes["prng_seed"]),
        "TZ": str(axes["tz"]),
    }
    if axes["egress"] == "blocked":
        if os.name == "nt":
            # Windows repair 2026-10-24: unshare is absent; the block is the
            # socket-connect guard installed by the harness itself when
            # BLD0044_EGRESS_GUARD=1 (both-states proven via block_control).
            env["BLD0044_EGRESS_GUARD"] = "1"
            cmd = inner
        else:
            cmd = [UNSHARE, "-n", *inner]
    else:
        cmd = inner
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    payload = None
    if proc.stdout.strip():
        try:
            payload = json.loads(proc.stdout.strip().splitlines()[-1])
        except json.JSONDecodeError:
            payload = None
    results = (payload or {}).get("results") or {}
    if proc.returncode != 0 and not results:
        results = {
            "_harness": {
                "outcome": "FAIL",
                "error": f"rc={proc.returncode} {(proc.stderr or '')[-400:]}",
            }
        }
    return {
        "id": cell_id(axes),
        "axes": axes,
        "returncode": proc.returncode,
        "order": shuffled_order(int(axes["order_seed"])),
        "results": {
            name: {"outcome": row.get("outcome"), "error": row.get("error")}
            for name, row in results.items()
        },
    }


def cell_id(axes: dict) -> str:
    return (
        f"o{axes['order_seed']}-p{axes['prng_seed']}-"
        f"tz{axes['tz'].replace('/', '_')}-cwd{axes['cwd']}-"
        f"cache{axes['cache']}-eg{axes['egress']}"
    )


def outcome(cell: dict, test: str) -> str:
    row = cell.get("results", {}).get(test) or {}
    return str(row.get("outcome") or "MISSING")


def axis_divergences(cells: list[dict]) -> list[dict]:
    """One-factor divergences: tests whose outcome changes when a single axis flips."""
    by_id = {c["id"]: c for c in cells}
    keys = list(AXES)
    found: list[dict] = []
    seen = set()
    for cell in cells:
        for axis in keys:
            other = dict(cell["axes"])
            values = AXES[axis]
            alt = values[1] if other[axis] == values[0] else values[0]
            other[axis] = alt
            peer = by_id.get(cell_id(other))
            if peer is None:
                continue
            tests = sorted(set(cell["results"]) | set(peer["results"]))
            for test in tests:
                a, b = outcome(cell, test), outcome(peer, test)
                if a == b:
                    continue
                pair_key = (test, axis, tuple(sorted((a, b))))
                if pair_key in seen:
                    continue
                seen.add(pair_key)
                found.append(
                    {
                        "test": test,
                        "axis": axis,
                        "outcomes": {
                            str(cell["axes"][axis]): a,
                            str(peer["axes"][axis]): b,
                        },
                    }
                )
    return found


def run_census(tmp: Path) -> dict:
    verify_seeds()
    suite_cwd = HERE
    empty_cwd = tmp / "empty-cwd"
    empty_cwd.mkdir(parents=True, exist_ok=True)
    cells = []
    combos = list(itertools.product(*AXES.values()))
    axis_names = list(AXES)
    for combo in combos:
        axes = dict(zip(axis_names, combo))
        scratch = tmp / "scratch" / cell_id(axes)
        cache_dir = tmp / "cache" / cell_id(axes)
        scratch.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)
        if axes["cache"] == "warm":
            (cache_dir / "warm-token").write_text("warm", encoding="utf-8")
        cells.append(run_cell(axes, scratch, cache_dir, suite_cwd, empty_cwd))
    hermetic = [outcome(c, "test_hermetic") for c in cells]
    hermetic_ok = hermetic and all(x == "PASS" for x in hermetic)
    return {
        "cell_count": len(cells),
        "cells": cells,
        "divergences": axis_divergences(cells),
        "hermetic_outcomes": sorted(set(hermetic)),
        "hermetic_identical": hermetic_ok,
        "hermetic_false_positives": 0 if hermetic_ok else hermetic.count("FAIL"),
        "block": block_control(),
    }


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="bld0044-") as td:
        doc = run_census(Path(td))
    print(json.dumps({"cell_count": doc["cell_count"], "div": len(doc["divergences"]), "hermetic": doc["hermetic_identical"], "block": doc["block"]["both_states"]}, indent=2))
