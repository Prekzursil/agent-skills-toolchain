#!/usr/bin/env python3
"""Probe-local loader for the production platform.plugin.cache module.

The repo's ``platform/`` directory has no ``__init__.py`` and the STDLIB
``platform`` module shadows it as a namespace package, so a plain
``import platform.plugin.cache`` fails on this box. This loader wires the
package chain in sys.modules manually (process-local) and executes
fsops.py + cache.py from their real files, preserving the relative
``from .fsops import ...`` inside cache.py.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def load_cache_module():
    if "platform.plugin.cache" in sys.modules:
        return sys.modules["platform.plugin.cache"]
    plat = types.ModuleType("platform")
    plat.__path__ = [str(REPO / "platform")]
    pp = types.ModuleType("platform.plugin")
    pp.__path__ = [str(REPO / "platform" / "plugin")]
    plat.plugin = pp
    pp.__package__ = "platform.plugin"
    sys.modules["platform"] = plat
    sys.modules["platform.plugin"] = pp

    def exec_file(fullname: str, path: Path):
        spec = importlib.util.spec_from_file_location(fullname, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[fullname] = mod
        spec.loader.exec_module(mod)
        return mod

    exec_file("platform.plugin.fsops", REPO / "platform" / "plugin" / "fsops.py")
    return exec_file("platform.plugin.cache", REPO / "platform" / "plugin" / "cache.py")
