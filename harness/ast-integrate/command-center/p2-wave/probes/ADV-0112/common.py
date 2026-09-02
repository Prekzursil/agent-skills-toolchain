"""Shared paths for ADV-0112 execute-docs probes."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def dump_json(doc: Any) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def repo_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    return env
