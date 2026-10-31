#!/usr/bin/env python3
"""Dump receipt_core allOf array-level constraints."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
_spec = importlib.util.spec_from_file_location(
    "gate", REPO / "platform" / "lib" / "receipt_schema_gate.py"
)
gate = importlib.util.module_from_spec(_spec)
sys.modules["gate"] = gate
_spec.loader.exec_module(gate)
core = gate.load_schema()["$defs"]["receipt_core"]
print(json.dumps(core.get("allOf"), indent=1)[:4000])
