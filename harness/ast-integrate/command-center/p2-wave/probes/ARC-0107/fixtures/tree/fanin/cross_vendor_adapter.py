"""Cross-vendor adapter fan-in: direct from-import of the shared reducer."""
from lib.completion_reducer import reduce_completion

FANIN_ROLE = "cross-vendor-adapter"


def settle(receipt: dict) -> dict:
    return reduce_completion(receipt)
