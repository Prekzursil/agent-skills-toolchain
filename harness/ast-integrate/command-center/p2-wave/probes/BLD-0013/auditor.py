"""Mechanism-vs-target auditor for BLD-0013.

A binding is SATISFIES / SUBSTITUTES / SUBSET / MIS-BOUND by comparing the
requirement's demanded mechanism to the bound unit's actual target text.
Disjunction (OR) is honoured: any one complete disjunct is enough.
Conjunction (AND) inside a disjunct requires every phrase.

This module never reads a binding record as proof. Callers must pass the
requirement mechanism and the unit target as separate strings.
"""
from __future__ import annotations

import re
from typing import Any

VERDICTS = ("SATISFIES", "SUBSTITUTES", "SUBSET", "MIS-BOUND")
UNBOUND_SCOPE = "OUT-OF-SCOPE-CC-0024"


def normalize(text: str) -> str:
    t = (text or "").casefold()
    t = t.replace("\u2019", "'").replace("\u2018", "'")
    t = t.replace("-", " ")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def contains_phrase(haystack: str, phrase: str) -> bool:
    h = normalize(haystack)
    p = normalize(phrase)
    if not p:
        return False
    if p in h:
        return True
    tokens = p.split()
    htoks = h.split()
    if not tokens:
        return False
    i = 0
    gap = 0
    for tok in htoks:
        if tok == tokens[i]:
            i += 1
            gap = 0
            if i == len(tokens):
                return True
        elif i > 0:
            gap += 1
            if gap > 1:
                i = 0
                gap = 0
    return False


def audit_binding(
    demanded_mechanism: str,
    unit_target: str,
    disjuncts: list[list[str]],
    domain_tokens: list[str],
    *,
    bound_unit_id: str | None,
) -> dict[str, Any]:
    """Return an audit dict. Unbound (no unit id) is out of scope."""
    del demanded_mechanism  # quoted by caller; matching uses disjuncts
    if not bound_unit_id:
        return {
            "verdict": UNBOUND_SCOPE,
            "residue": [],
            "matched_disjunct": None,
            "partial_hits": [],
            "domain_overlap": [],
            "reason": (
                "No binding exists. Unbound requirements are CC-0024's "
                "false-negative direction, not BLD-0013."
            ),
        }
    if not disjuncts:
        raise ValueError("disjuncts must be a non-empty list of phrase lists")

    disjunct_hits: list[tuple[list[str], list[str]]] = []
    for d in disjuncts:
        hits = [p for p in d if contains_phrase(unit_target, p)]
        disjunct_hits.append((d, hits))
        if d and len(hits) == len(d):
            return {
                "verdict": "SATISFIES",
                "residue": [],
                "matched_disjunct": list(d),
                "partial_hits": hits,
                "domain_overlap": _overlap(domain_tokens, unit_target),
                "reason": (
                    "Unit target implements at least one full disjunct of the "
                    "demanded mechanism."
                ),
            }

    partial = [(d, hits) for d, hits in disjunct_hits if 0 < len(hits) < len(d)]
    if partial:
        d, hits = max(partial, key=lambda x: len(x[1]))
        residue = [p for p in d if p not in hits]
        return {
            "verdict": "SUBSET",
            "residue": residue,
            "matched_disjunct": None,
            "partial_hits": hits,
            "domain_overlap": _overlap(domain_tokens, unit_target),
            "reason": (
                "Unit target covers some conjuncts of the demanded mechanism "
                "but not a complete disjunct; residue named."
            ),
        }

    overlap = _overlap(domain_tokens, unit_target)
    if len(overlap) >= 2:
        return {
            "verdict": "SUBSTITUTES",
            "residue": [],
            "matched_disjunct": None,
            "partial_hits": [],
            "domain_overlap": overlap,
            "reason": (
                "Shared domain tokens but a different mechanism. Owner "
                "approval required before treating the binding as coverage."
            ),
            "owner_approval_required": True,
        }
    return {
        "verdict": "MIS-BOUND",
        "residue": [],
        "matched_disjunct": None,
        "partial_hits": [],
        "domain_overlap": overlap,
        "reason": (
            "Bound unit target does not implement the demanded mechanism and "
            "does not share a mechanism-level domain."
        ),
    }


def _overlap(domain_tokens: list[str], unit_target: str) -> list[str]:
    return [t for t in domain_tokens if contains_phrase(unit_target, t)]


def evidence_ok(row: dict[str, Any]) -> tuple[bool, str]:
    """In-scope verdicts must quote spec + unit target.

    Citing only the binding record is not evidence: the binding is the
    artifact under audit.
    """
    verdict = str(row.get("verdict") or "")
    if verdict == UNBOUND_SCOPE:
        return True, "unbound-out-of-scope"
    src = str(row.get("evidence_source") or "")
    if src == "binding-record":
        return False, "binding-record-is-not-evidence"
    if src != "spec-and-unit-target":
        return False, f"bad-evidence-source:{src}"
    q1 = str(row.get("demanded_mechanism_quote") or "").strip()
    q2 = str(row.get("unit_target_quote") or "").strip()
    if len(q1) < 12:
        return False, "demanded-mechanism-quote-too-short"
    if len(q2) < 12:
        return False, "unit-target-quote-too-short"
    if normalize(q1) == normalize(q2):
        return False, "quotes-identical"
    if verdict == "SUBSET":
        residue = row.get("residue") or []
        if not isinstance(residue, list) or not residue:
            return False, "subset-residue-unnamed"
    if verdict == "SATISFIES":
        bind_only = str(row.get("binding_record_quote") or "")
        if bind_only and normalize(q2) == normalize(bind_only):
            return False, "unit-quote-is-binding-record"
    return True, "ok"
