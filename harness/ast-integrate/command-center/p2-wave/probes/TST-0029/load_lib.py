"""Import the TST-0029 local DAG library from this probe directory."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def repo() -> Path:
    return REPO


def ensure_import() -> None:
    probe = str(HERE)
    if probe not in sys.path:
        sys.path.insert(0, probe)
    pkg = str(REPO / "tools" / "agentspec")
    if pkg not in sys.path:
        sys.path.insert(0, pkg)


def receipt_domain(doc: dict) -> dict:
    """Domain fields live under report (receipt_core additionalProperties=false)."""
    merged = dict(doc)
    report = doc.get("report")
    if isinstance(report, dict):
        merged.update(report)
    return merged
