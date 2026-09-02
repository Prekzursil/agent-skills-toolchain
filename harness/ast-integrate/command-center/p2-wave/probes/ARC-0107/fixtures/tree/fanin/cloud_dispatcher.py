"""Cloud dispatcher fan-in: aliased from-import of the shared reducer."""
from lib.completion_reducer import reduce_completion as rc

FANIN_ROLE = "cloud-dispatcher"


def settle(receipt: dict) -> dict:
    return rc(receipt)
