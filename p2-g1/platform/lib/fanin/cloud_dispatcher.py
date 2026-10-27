"""Cloud dispatcher fan-in: reduces cloud-dispatched unit receipts.

Imports the ONE shared reducer; defines no local predicate.
"""
from __future__ import annotations

from fanin._site_common import evaluate, reduce_unit

__all__ = ["evaluate", "reduce_unit"]