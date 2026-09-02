"""Load the IMP-0420 Claude adapter from its durable path."""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ADAPTER_PATH = REPO / "command-center" / "adapters" / "claude_adapter.py"


def load_adapter():
    spec = importlib.util.spec_from_file_location("claude_adapter", ADAPTER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {ADAPTER_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
