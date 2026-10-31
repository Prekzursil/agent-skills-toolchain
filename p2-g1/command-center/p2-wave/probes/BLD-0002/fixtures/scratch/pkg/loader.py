"""Loads a module name from config via importlib.import_module."""
from __future__ import annotations

import importlib
import json
from pathlib import Path


def load():
    cfg_path = Path(__file__).resolve().parents[1] / "config" / "modules.json"
    name = json.loads(cfg_path.read_text(encoding="utf-8"))["dynamic_module"]
    return importlib.import_module(name)
