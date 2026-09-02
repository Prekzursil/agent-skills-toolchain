"""Load tools/council/vote/tally.py without requiring an installed package."""
from __future__ import annotations

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TALLY_PATH = REPO / "tools/council/vote/tally.py"


def load_tally():
    spec = importlib.util.spec_from_file_location("imp0302_council_vote_tally", TALLY_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {TALLY_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
