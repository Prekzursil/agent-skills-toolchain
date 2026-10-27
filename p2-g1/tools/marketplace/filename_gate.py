"""Portability filename gate (no circular import with tools/filename_gate.py)."""
from __future__ import annotations

import sys
from pathlib import Path

_TOOLS = str(Path(__file__).resolve().parents[1])
if _TOOLS not in sys.path:
    sys.path.append(_TOOLS)

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "tools_filename_gate", Path(_TOOLS) / "filename_gate.py"
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
CORPUS = _mod.CORPUS
REJECTED_UNPORTABLE = _mod.REJECTED_UNPORTABLE
classify = _mod.classify
load_corpus = _mod.load_corpus
__all__ = ["CORPUS", "REJECTED_UNPORTABLE", "classify", "load_corpus"]
