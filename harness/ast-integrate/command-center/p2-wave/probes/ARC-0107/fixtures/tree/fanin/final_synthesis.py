"""Final synthesis fan-in: direct from-import of the shared reducer."""
from lib.completion_reducer import reduce_completion

FANIN_ROLE = "final-synthesis"


def settle(receipt: dict) -> dict:
    return reduce_completion(receipt)
