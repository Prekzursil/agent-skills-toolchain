"""A5 runtime bindings: substrates, ONE shared reducer, fan-out, barriers.

The completion reducer is imported from TST-0003. It is not copied. All
three dispatchers (local / worktree / cloud) call the same evaluate().
Dynamic fan-out width comes from agentspec.resolve_dynamic_fanout on a
schema-validated producer receipt, never from an exit code.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
REDUCER_PATH = REPO / "command-center/p2-wave/probes/TST-0003/reducer.py"
FANOUT_DIR = REPO / "tools/agentspec"

SUBSTRATES = ("local", "worktree", "cloud")
DISPATCHERS = {
    "local": {
        "id": "dispatcher.local",
        "substrate": "local",
        "adapter": "in-process IsolatedPipelineRunner (tools/agentrail/agentrail/runner.py)",
        "isolation": "one pipeline per unit; declared timeout; no join-all hang",
    },
    "worktree": {
        "id": "dispatcher.worktree",
        "substrate": "worktree",
        "adapter": "disposable git worktree per mutating unit (catalog IMP-0223 class)",
        "isolation": "disjoint git indexes; teardown refused unless content preserved",
    },
    "cloud": {
        "id": "dispatcher.cloud",
        "substrate": "cloud",
        "adapter": "remote batch harvest into the same ledger; no auth files in image",
        "isolation": "artifact-scrub gate before bundle leaves the box (ARC-0034)",
    },
}


def load_shared_evaluate() -> Callable[..., dict[str, Any]]:
    spec = importlib.util.spec_from_file_location("arc0031_shared_reducer", REDUCER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"reducer-absent:{REDUCER_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, "evaluate", None)
    if not callable(fn):
        raise RuntimeError("reducer-missing-evaluate")
    return fn


def reducer_identity_ok() -> bool:
    a = load_shared_evaluate()
    b = load_shared_evaluate()
    return a.__code__ is b.__code__ or a.__code__.co_filename == b.__code__.co_filename


def load_fanout_resolver():
    if str(FANOUT_DIR) not in sys.path:
        sys.path.insert(0, str(FANOUT_DIR))
    from agentspec.dynamic_fanout import resolve_dynamic_fanout  # type: ignore
    from agentspec.spec import DynamicFanOut, UnitTemplate  # type: ignore

    return resolve_dynamic_fanout, DynamicFanOut, UnitTemplate


EVALUATE = load_shared_evaluate()
