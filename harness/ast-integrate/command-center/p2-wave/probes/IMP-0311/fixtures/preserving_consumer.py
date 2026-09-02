"""Honest consumer: keeps kind; does not emit PASS/FAIL."""

PROTECTED = ("NO-DECISION", "CONDITIONAL", "PROOF-OF-IMPOSSIBILITY")


def consume_outcome(outcome):
    kind = outcome["kind"]
    if kind in PROTECTED:
        return {"kept_kind": kind, "binary": None, "payload": outcome}
    if kind == "DECISION":
        return {"kept_kind": kind, "binary": None, "payload": outcome}
    raise ValueError(kind)
