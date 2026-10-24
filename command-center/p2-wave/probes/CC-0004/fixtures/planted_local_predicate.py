"""PLANTED local completion predicate — CC-0004 known-broken control.

This module deliberately rolls its own done/complete check instead of importing
platform/lib/completion_predicate.py. The fan-in detector MUST report this file
with a file:line. Do not use this as a real reducer.
"""


DONE = "DONE"
COMPLETE = "COMPLETE"
PASS = "PASS"


def is_complete(receipt: dict) -> bool:
    """Local completion fork — must be caught by CC-0004."""
    state = str(receipt.get("state", "")).upper()
    return state in {DONE, COMPLETE, "SUCCESS", PASS}


def evaluate(receipt: dict, opts=None):
    """Shadow evaluate that invents COMPLETE without the shared 12 conditions."""
    if is_complete(receipt):
        return COMPLETE
    return "INCOMPLETE"
