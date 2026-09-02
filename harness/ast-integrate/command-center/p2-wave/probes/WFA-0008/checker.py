#!/usr/bin/env python3
"""Honesty checks for the WFA-0008 SemanticDiff artifact."""
from __future__ import annotations


def _pair_key(row: dict) -> tuple[str, str]:
    a, b = str(row.get("a") or ""), str(row.get("b") or "")
    return (a, b) if a <= b else (b, a)


def scores_present(doc: dict) -> tuple[bool, str]:
    rows = doc.get("pairwise_scores") or doc.get("pairs") or []
    if not isinstance(rows, list) or not rows:
        return False, "pairwise_scores missing"
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            return False, f"pairwise_scores[{i}] not an object"
        if "lexical_score" not in row or "embedding_score" not in row:
            return False, f"pairwise_scores[{i}] dropped a score"
        if row.get("friendlier_score_only") is True:
            return False, f"pairwise_scores[{i}] resolved by the friendlier score"
    return True, "ok"


def disagreements_are_contested(doc: dict) -> tuple[bool, str]:
    contested = {
        _pair_key(r)
        for r in (doc.get("contested") or [])
        if isinstance(r, dict)
    }
    collapsed = {
        _pair_key(r)
        for r in (doc.get("collapsed") or [])
        if isinstance(r, dict)
    }
    for i, row in enumerate(doc.get("pairwise_scores") or []):
        if not isinstance(row, dict):
            continue
        lex_f = bool(row.get("lexical_fired"))
        emb_f = bool(row.get("embedding_fired"))
        if lex_f == emb_f:
            continue
        key = _pair_key(row)
        if key not in contested:
            return False, f"disagreement {key} not listed CONTESTED"
        if key in collapsed:
            return False, f"disagreement {key} was silently collapsed"
        ev = None
        for c in doc.get("contested") or []:
            if _pair_key(c) == key:
                ev = c.get("adjudicating_evidence") or c.get("blind")
                break
        if not ev:
            return False, f"CONTESTED {key} has no adjudicating evidence"
    return True, "ok"


def no_cosine_only_collapse(doc: dict) -> tuple[bool, str]:
    for i, row in enumerate(doc.get("collapsed") or []):
        if not isinstance(row, dict):
            return False, f"collapsed[{i}] not an object"
        if row.get("embedding_fired") and not row.get("lexical_fired"):
            return False, f"collapsed[{i}] collapsed on cosine alone"
        if row.get("collapsed_on_cosine_alone") is True:
            return False, f"collapsed[{i}] marked cosine-alone"
        blind = row.get("blind_verdict") or (row.get("blind") or {}).get("verdict")
        if blind != "DUPLICATE":
            return False, f"collapsed[{i}] lacks blind DUPLICATE"
        if not row.get("lexical_fired") or not row.get("embedding_fired"):
            return False, f"collapsed[{i}] missing dual-method fire"
    return True, "ok"


def both_states_full_rewrite(doc: dict) -> tuple[bool, str]:
    mutants = {m.get("class"): m for m in (doc.get("planted_mutants") or [])}
    rw = mutants.get("full-rewrite")
    if not isinstance(rw, dict):
        return False, "missing planted mutant class full-rewrite"
    if rw.get("embedding_fired") is not True:
        return False, "full-rewrite was not caught by embedding cosine"
    if rw.get("lexical_fired") is not False:
        return False, "full-rewrite was expected MISSED by the lexical scan"
    if rw.get("lexical_in_distinct_band") is not True:
        return False, "full-rewrite lexical score is not in the 0.05-0.24 band"
    return True, "ok"


def wfa0007_plants(doc: dict) -> tuple[bool, str]:
    mutants = {m.get("class"): m for m in (doc.get("planted_mutants") or [])}
    for cls in ("exact-rename", "one-parameter-fork", "reworded-paraphrase"):
        m = mutants.get(cls)
        if not isinstance(m, dict):
            return False, f"missing planted mutant class {cls}"
        if not m.get("lexical_fired") or not m.get("embedding_fired"):
            return False, f"{cls} did not fire under both methods"
    decoys = [m for m in (doc.get("planted_mutants") or []) if m.get("class") == "decoy"]
    if len(decoys) < 3:
        return False, f"expected 3 decoys, got {len(decoys)}"
    for d in decoys:
        if d.get("lexical_fired") or d.get("embedding_fired"):
            return False, f"decoy {d.get('id')} flagged against seed"
    return True, "ok"
