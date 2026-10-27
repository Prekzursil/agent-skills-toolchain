"""Run one shard-9 unit spec builder and emit its receipt + manifests.

Usage: python _p2shard9/run_unit.py spec_IMP-0217
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

mod_name = sys.argv[1]
mod = importlib.import_module(mod_name)
spec = mod.build()
import emit  # noqa: E402
print("SUCCESS:" + emit.emit(spec))
