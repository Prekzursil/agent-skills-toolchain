"""Workflow fan-in: from-parent import of the reducer module."""
from lib import completion_reducer

FANIN_ROLE = "workflow-fan-in"


def settle(receipt: dict) -> dict:
    return completion_reducer.reduce_completion(receipt)
