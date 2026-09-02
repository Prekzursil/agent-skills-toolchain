#!/usr/bin/env python3
"""CNF-0002 independence predicate used by the CNF-0127 remesurer.

A confirmer is independent of a claim only when:
  (a) its agent id appears nowhere in the authoring provenance of the
      implementation receipt,
  (b) it did not review that implementation,
  (c) it did not author an ancestor artifact the claim depends on.
"""
from __future__ import annotations


def evaluate(
    confirmer_id: str,
    *,
    author_agent_id: str,
    reviewed_by: list[str],
    ancestor_authors: list[str],
) -> dict:
    authors = {author_agent_id}
    reviewers = set(reviewed_by)
    ancestors = set(ancestor_authors)
    rule_a = confirmer_id not in authors
    rule_b = confirmer_id not in reviewers
    rule_c = confirmer_id not in ancestors
    independent = rule_a and rule_b and rule_c
    return {
        "confirmer_id": confirmer_id,
        "rule_a_author_overlap": rule_a,
        "rule_b_not_reviewer": rule_b,
        "rule_c_not_ancestor_author": rule_c,
        "independent": independent,
        "rejected_by": [
            name
            for name, ok in (
                ("a", rule_a),
                ("b", rule_b),
                ("c", rule_c),
            )
            if not ok
        ],
    }


def planted_controls(row: dict) -> dict:
    """Planted CNF-0002 cases from tests_required of that unit, reused here."""
    author = row["author_agent_id"]
    reviewed = list(row.get("reviewed_by") or [])
    ancestors = list(row.get("ancestor_authors") or [])
    authorship_only_reviewer = evaluate(
        reviewed[0] if reviewed else "loop-pr-reviewer",
        author_agent_id=author,
        reviewed_by=[],
        ancestor_authors=ancestors,
    )
    rule_b_plant = evaluate(
        reviewed[0] if reviewed else "loop-pr-reviewer",
        author_agent_id=author,
        reviewed_by=reviewed,
        ancestor_authors=ancestors,
    )
    rule_c_plant = evaluate(
        ancestors[0] if ancestors else "b08-harness-author",
        author_agent_id=author,
        reviewed_by=reviewed,
        ancestor_authors=ancestors,
    )
    rule_a_plant = evaluate(
        author,
        author_agent_id=author,
        reviewed_by=reviewed,
        ancestor_authors=ancestors,
    )
    b_rejects = rule_b_plant["independent"] is False
    a_would_accept_reviewer = authorship_only_reviewer["independent"] is True
    return {
        "rule_a_author_is_confirmer": {
            "planted_confirmer": author,
            "rejected": rule_a_plant["independent"] is False,
            "detail": rule_a_plant,
        },
        "rule_b_reviewed_impl": {
            "planted_confirmer": reviewed[0] if reviewed else "loop-pr-reviewer",
            "rejected": b_rejects,
            "authorship_only_would_accept": a_would_accept_reviewer,
            "inert_if_both_agree": not (b_rejects and a_would_accept_reviewer),
            "detail": rule_b_plant,
        },
        "rule_c_ancestor_author": {
            "planted_confirmer": ancestors[0] if ancestors else "b08-harness-author",
            "rejected": rule_c_plant["independent"] is False,
            "detail": rule_c_plant,
        },
    }
