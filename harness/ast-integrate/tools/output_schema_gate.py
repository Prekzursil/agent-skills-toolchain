"""Re-export of the real output-schema gate (tools/command-center/output_schema_gate.py).

``tools/command-center/`` is not an importable package (hyphenated name), so
the real module is loaded by file location once and its public surface is
re-exported here for callers that only have ``tools/`` on ``sys.path``.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REAL = Path(__file__).resolve().parent / "command-center" / "output_schema_gate.py"
_ALIAS = "_tools_command_center_output_schema_gate"


def _load_real_gate():
    existing = sys.modules.get(_ALIAS)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(_ALIAS, _REAL)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load the real output-schema gate from {_REAL}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_ALIAS] = module
    spec.loader.exec_module(module)
    return module


_gate = _load_real_gate()
globals().update({name: getattr(_gate, name) for name in _gate.__all__})
__all__ = list(_gate.__all__)
