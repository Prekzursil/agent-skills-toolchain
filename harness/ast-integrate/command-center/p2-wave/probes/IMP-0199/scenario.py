"""Load IMP-0199 workflow fixtures and import the agentspec evals package."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
AGENTSPEC_ROOT = REPO / "tools" / "agentspec"
if str(AGENTSPEC_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTSPEC_ROOT))

FIX = HERE / "fixtures"


def load_workflow(name: str) -> dict:
    path = FIX / name
    return json.loads(path.read_text(encoding="utf-8"))
