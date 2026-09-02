"""Harvester fan-in: relative import of the shared reducer."""
from ..lib.completion_reducer import reduce_completion

FANIN_ROLE = "harvester"


def settle(receipt: dict) -> dict:
    return reduce_completion(receipt)
