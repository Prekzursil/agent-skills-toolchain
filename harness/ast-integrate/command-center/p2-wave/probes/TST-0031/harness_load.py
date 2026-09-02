"""Load TST-0013 both-states harness without executing a stale package __init__."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[4]


def load_both_states() -> ModuleType:
    path = REPO / "command-center" / "harness" / "both_states.py"
    spec = importlib.util.spec_from_file_location("tst0013_both_states", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    # dataclasses reads sys.modules[cls.__module__] while the class body runs.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod
