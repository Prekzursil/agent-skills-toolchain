"""Known-broken fan-in mutants. Production topology must not import these."""
from __future__ import annotations

from typing import Any


def averaging_fanin(child_verdicts: list[str]) -> dict[str, Any]:
    """Private majority predicate: disagreement becomes a false consensus."""
    n = len(child_verdicts) or 1
    complete_n = sum(1 for v in child_verdicts if v == "COMPLETE")
    ratio = complete_n / n
    return {
        "verdict": "COMPLETE" if ratio >= 0.5 else "INCOMPLETE",
        "disagreement_averaged_away": True,
        "ratio": ratio,
        "complete_n": complete_n,
        "n": n,
        "predicate": "majority-average",
    }


PRIVATE_PREDICATE_SOURCE = '''
def parent_complete(children):
    """A second private completion predicate — the defect CNF-0095 hunts."""
    n = len(children) or 1
    return sum(1 for c in children if c.get("verdict") == "COMPLETE") / n >= 0.5
'''
