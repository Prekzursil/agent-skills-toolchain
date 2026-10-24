"""Legitimate fan-in site — imports the shared CC-0003 reducer.

Known-present control for CC-0004: the detector must find this import.
"""

from __future__ import annotations

import completion_predicate
from completion_predicate import REDUCER_ID, evaluate


def reduce_unit(receipt: dict, opts):
    """Fan-in that resolves to the shared symbol."""
    return evaluate(receipt, opts)


__all__ = ["REDUCER_ID", "completion_predicate", "evaluate", "reduce_unit"]
