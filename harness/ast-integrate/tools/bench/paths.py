"""Repo-relative paths for the B07 non-inferiority margin layer (TST-0301).

Every consumer (probes, receipts, the release gate) names these files through
this module so that the checklist, the frozen table and the inventory can never
drift apart silently.
"""
from __future__ import annotations

import os
from pathlib import Path

CHECKLIST_REL = "command-center/RELEASE-CHECKLIST.md"
INVENTORY_REL = "command-center/bench/METRIC-INVENTORY.json"
MARGIN_TABLE_REL = "command-center/bench/B07-MARGIN-TABLE.json"
MARGIN_TABLE_SCHEMA_REL = "command-center/schema/margin-table.schema.json"
INVENTORY_SCHEMA_REL = "command-center/schema/metric-inventory.schema.json"

__all__ = [
    "CHECKLIST_REL",
    "INVENTORY_REL",
    "INVENTORY_SCHEMA_REL",
    "MARGIN_TABLE_REL",
    "MARGIN_TABLE_SCHEMA_REL",
    "repo_root",
]


def repo_root(root: str | os.PathLike[str] | None = None) -> Path:
    """Resolve the repository root.

    Precedence: explicit ``root`` argument, then ``AST_INTEGRATE_ROOT`` (the
    mirror convention used by the measurement harness), then the checkout that
    contains this file (``tools/bench/paths.py`` -> two parents up).
    """
    if root is not None:
        return Path(root).resolve()
    env = os.environ.get("AST_INTEGRATE_ROOT")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[2]
