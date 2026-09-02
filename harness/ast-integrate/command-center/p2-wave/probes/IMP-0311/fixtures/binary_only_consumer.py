"""Planted defect: only understands DECISION vs everything-else=FAIL."""


def consume_outcome(outcome):
    return "PASS" if outcome.get("kind") == "DECISION" else "FAIL"
