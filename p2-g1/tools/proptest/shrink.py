"""Deterministic shrink policy for planted cyclic DAGs (TST-0116)."""
from __future__ import annotations

SHRINK_POLICY = {
    "name": "node-edge-drop-v1",
    "order": ("drop-node", "drop-edge"),
    "deterministic": True,
}
