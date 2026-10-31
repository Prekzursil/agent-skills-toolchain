"""Cross-vendor adapter fan-in: reduces receipts from the other vendor.

Imports the ONE shared reducer; defines no local predicate.
"""
from __future__ import annotations

from fanin._site_common import evaluate, reduce_unit

__all__ = ["evaluate", "reduce_unit"]