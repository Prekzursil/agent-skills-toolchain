"""Load tools/council/antifail/role_collapse.py without an installed package."""
from __future__ import annotations

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MODULE_PATH = REPO / "tools/council/antifail/role_collapse.py"


def load_detector():
    spec = importlib.util.spec_from_file_location(
        "imp0320_role_collapse", MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {MODULE_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
