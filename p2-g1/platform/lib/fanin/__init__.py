"""The seven fan-in sites. Every module re-exports the ONE shared evaluate object.

No site defines a local predicate: each imports ``completion_predicate.evaluate``
and reduces through it, so ``fanin.<site>.evaluate is completion_predicate.evaluate``
holds by construction and per-condition statuses are identical at every site.
"""
from __future__ import annotations

SITES = (
    "local_runner",
    "cloud_dispatcher",
    "monitor",
    "harvester",
    "workflow_fanin",
    "cross_vendor_adapter",
    "final_synthesis",
)

__all__ = ["SITES"]
