"""Planted defect: maps protected kinds onto PASS/FAIL. Census must catch this."""


def consume_outcome(outcome):
    kind = outcome["kind"]
    if kind == "NO-DECISION":
        return "FAIL"
    if kind == "CONDITIONAL":
        return "PASS"
    if kind == "PROOF-OF-IMPOSSIBILITY":
        return "FAIL"
    if kind == "DECISION":
        return "PASS"
    return "FAIL"
