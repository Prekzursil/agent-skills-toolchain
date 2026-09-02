"""Load tools/council/topology/jury.py without requiring tools/ to be a package."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def repo_root() -> Path:
    return REPO


def load_jury():
    path = REPO / "tools" / "council" / "topology" / "jury.py"
    name = "imp0285_jury"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    # dataclasses looks up cls.__module__ in sys.modules while the class body runs.
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod
