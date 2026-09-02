"""Planted self-confirming snapshot: golden.json is produce_report() written back."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from subject import produce_report  # noqa: E402


def test_snapshot_self_confirming():
    actual = produce_report()
    golden = json.loads((HERE / "golden.json").read_text(encoding="utf-8"))
    assert actual == golden
