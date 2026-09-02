"""Shared loaders for IMP-0269 probes."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MODULE = HERE / "select_expertise.py"
FIX = HERE / "fixtures"


def load_selector():
    spec = importlib.util.spec_from_file_location("imp0269_select_expertise", MODULE)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {MODULE}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["imp0269_select_expertise"] = mod
    spec.loader.exec_module(mod)
    return mod


def read_json(name: str) -> Any:
    return json.loads((FIX / name).read_text(encoding="utf-8"))
