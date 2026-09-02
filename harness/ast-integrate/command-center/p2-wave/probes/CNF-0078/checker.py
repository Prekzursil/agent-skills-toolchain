#!/usr/bin/env python3
"""Honesty checks on a similarity report: both scores on every flagged pair."""
from __future__ import annotations


def report_payload(doc: dict) -> dict:
    """Domain scores live under report when the receipt envelope is present."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        isinstance(report.get("planted_mutants"), list)
        or isinstance(report.get("flagged_pairs"), list)
    ):
        return report
    return doc


def flagged_pairs_honest(doc: dict) -> tuple[bool, str]:
    rows = report_payload(doc).get("flagged_pairs") or []
    if not isinstance(rows, list):
        return False, "flagged_pairs is not a list"
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            return False, f"flagged_pairs[{i}] not an object"
        if "lexical_score" not in row or "embedding_score" not in row:
            return False, f"flagged_pairs[{i}] missing a score (friendlier-only is forbidden)"
        if row.get("friendlier_score_only") is True:
            return False, f"flagged_pairs[{i}] resolved by picking the friendlier score"
        flagged_by = row.get("flagged_by") or []
        if not flagged_by:
            return False, f"flagged_pairs[{i}] has empty flagged_by"
        lex_f = bool(row.get("lexical_fired"))
        emb_f = bool(row.get("embedding_fired"))
        if not (lex_f or emb_f):
            return False, f"flagged_pairs[{i}] flagged but neither measure fired"
        if ("lexical" in flagged_by) != lex_f:
            return False, f"flagged_pairs[{i}] flagged_by/lexical_fired disagree"
        if ("embedding" in flagged_by) != emb_f:
            return False, f"flagged_pairs[{i}] flagged_by/embedding_fired disagree"
    return True, "ok"


def firing_pattern_matches_mutants(doc: dict) -> tuple[bool, str]:
    mutants = {
        m.get("class"): m for m in (report_payload(doc).get("planted_mutants") or [])
    }
    for cls in ("exact-rename", "paraphrase", "full-rewrite"):
        if cls not in mutants:
            return False, f"missing planted mutant class {cls}"
    rw = mutants["full-rewrite"]
    if rw.get("embedding_fired") is not True:
        return False, "full-rewrite did not fire under embedding"
    if rw.get("lexical_fired") is not False:
        return False, "full-rewrite was expected silent under lexical"
    for cls in ("exact-rename", "paraphrase"):
        m = mutants[cls]
        if not m.get("lexical_fired"):
            return False, f"{cls} did not fire under lexical"
        if not m.get("embedding_fired"):
            return False, f"{cls} did not fire under embedding"
    return True, "ok"
