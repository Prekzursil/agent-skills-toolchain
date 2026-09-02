#!/usr/bin/env python3
"""Re-run shard-16 Windows probes (overwrite jsonl)."""
from __future__ import annotations

from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("win", HERE / "_shard16_win_probes.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
OUT = HERE / "_shard16_win_probes.jsonl"
if OUT.is_file():
    OUT.unlink()
mod.OUT = OUT
mod.main()
