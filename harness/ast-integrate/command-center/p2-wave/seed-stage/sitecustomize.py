"""Loaded if seed-stage is on PYTHONPATH. Force seed-stage hook over site-packages."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = "p2_jsonschema_hook"
for key in [k for k in list(sys.modules) if k == NAME or k.startswith(NAME + ".")]:
    del sys.modules[key]
if str(HERE) in sys.path:
    sys.path.remove(str(HERE))
sys.path.insert(0, str(HERE))
try:
    spec = importlib.util.spec_from_file_location(NAME, HERE / f"{NAME}.py")
    if spec is not None and spec.loader is not None:
        mod = importlib.util.module_from_spec(spec)
        sys.modules[NAME] = mod
        spec.loader.exec_module(mod)
except Exception:
    pass
