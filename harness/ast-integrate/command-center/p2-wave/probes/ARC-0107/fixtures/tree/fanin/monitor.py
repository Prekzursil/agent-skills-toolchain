"""Monitor fan-in: module import, attribute call."""
import lib.completion_reducer as reducer

FANIN_ROLE = "monitor"


def settle(receipt: dict) -> dict:
    return reducer.reduce_completion(receipt)
