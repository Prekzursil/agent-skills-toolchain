"""IMP-0166: production extractor - prose rule -> parse tree or UNKNOWN-NEEDS-PROBE.

Classifications:
  EVALUABLE           parsed into a composable tree
  UNKNOWN-NEEDS-PROBE parse failed; the rule is flagged, never approximated
  NONE                empty rule
"""
from __future__ import annotations

import algebra


def extract_one(candidate: dict) -> dict:
    source = candidate["source"]
    row = {"id": candidate["id"], "source": source}
    if not source.strip():
        row.update(classification="NONE", reason="no-stop-rule", normalized="")
        return row
    try:
        tree = algebra.parse(source)
    except algebra.ParseError as exc:
        row.update(classification="UNKNOWN-NEEDS-PROBE",
                   reason=f"parse-failed:{exc}", normalized=source.strip())
        return row
    row.update(classification="EVALUABLE", reason="parsed",
               normalized=source.strip(), tree=tree)
    return row


def extract_all(candidates: list) -> list:
    return [extract_one(c) for c in candidates]


def planted_approximator(source: str):
    """A mutation that snaps ANY prose to a completeness_score comparison.

    The production extractor must NOT behave like this: an inexpressible rule
    mapped onto a real metric silently invents a stopping decision.
    """
    return {"kind": "CMP", "metric": "completeness_score", "rel": ">=", "value": 0.9}
