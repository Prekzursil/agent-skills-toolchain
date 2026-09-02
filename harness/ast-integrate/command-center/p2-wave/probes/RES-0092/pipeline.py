"""Load the live CNF-0075 capability pipeline step.

The pipeline under test is execute_case on fusion_union — a real
deterministic agent-pipeline stage already in this tree, not a toy
reimplementation.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
HARNESS = REPO / "command-center" / "p2-wave" / "probes" / "CNF-0075" / "harness.py"


def load_harness():
    if not HARNESS.is_file():
        raise FileNotFoundError(
            f"live pipeline missing: {HARNESS.as_posix()}"
        )
    spec = importlib.util.spec_from_file_location("cnf0075_harness_res0092", HARNESS)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {HARNESS.as_posix()}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def live_workflow() -> dict[str, Any]:
    h = load_harness()
    return h.fusion_union()


def execute_case(workflow: dict, case: dict) -> dict:
    h = load_harness()
    return h.execute_case(workflow, case)
