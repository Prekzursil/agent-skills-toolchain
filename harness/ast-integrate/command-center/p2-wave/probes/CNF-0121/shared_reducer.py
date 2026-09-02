#!/usr/bin/env python3
"""Shared completion-predicate condition-9 reducer (fan-in and audit).

Condition 9: independent reviewer status is PASS.

Independence is CNF-0002:
  (a) confirmer id is absent from implementation authoring provenance
  (b) confirmer did not already review that implementation
  (c) confirmer did not author an ancestor artifact the claim depends on

Canonical self-certification: the reviewer field contains the author.
NOT-CHECKED is distinct from PASS; missing reviewer is FAIL, not a silent pass.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

CONDITION_INDEX = 9
CONDITION_9_TEXT = "independent reviewer status is PASS"

_CLAIM_STATES = frozenset({"SUCCESS", "DELIVERED", "COMPLETE", "CONFIRMED"})
_AUTHOR_KEYS = (
    "author",
    "authors",
    "implementer",
    "implementers",
    "authored_by",
    "produced_by",
    "implementation_authors",
    "authoring_provenance",
)
_ID_KEYS = (
    "agent_id",
    "reviewer_id",
    "author_id",
    "author",
    "implementer",
    "name",
    "identity",
)


_REPO = Path(__file__).resolve().parents[4]


def reducer_anchor() -> str:
    path = Path(inspect.getsourcefile(evaluate_condition_9) or __file__).resolve()
    start = inspect.getsourcelines(evaluate_condition_9)[1]
    try:
        rel = path.relative_to(_REPO).as_posix()
    except ValueError:
        rel = path.as_posix()
    return f"{rel}:{start}"


def _add_identity(raw: Any, into: set[str]) -> None:
    if raw is None:
        return
    if isinstance(raw, str):
        text = raw.strip()
        if len(text) >= 3:
            into.add(text)
        return
    if isinstance(raw, dict):
        for key in _ID_KEYS:
            if key in raw:
                _add_identity(raw[key], into)
        return
    if isinstance(raw, (list, tuple, set)):
        for item in raw:
            _add_identity(item, into)


def author_identities(receipt: dict) -> list[str]:
    found: set[str] = set()
    for key in _AUTHOR_KEYS:
        if key in receipt:
            _add_identity(receipt[key], found)
    return sorted(found)


def reviewer_record(receipt: dict) -> dict | None:
    rev = receipt.get("reviewer")
    if isinstance(rev, dict) and rev:
        return rev
    return None


def reviewer_identities(receipt: dict) -> list[str]:
    found: set[str] = set()
    rec = reviewer_record(receipt)
    if rec is None:
        return []
    _add_identity(rec, found)
    return sorted(found)


def claims_completion(receipt: dict) -> bool:
    state = str(receipt.get("state") or "").upper()
    status = str(receipt.get("status") or "").upper()
    return state in _CLAIM_STATES or status in _CLAIM_STATES


def _contains_author(reviewer_ids: list[str], authors: list[str]) -> bool:
    for author in authors:
        for rev in reviewer_ids:
            if author == rev or author in rev:
                return True
    return False


def _rule_b_prior_review(receipt: dict, reviewer_ids: list[str]) -> str:
    """FAIL only on positive evidence the confirmer already reviewed the impl."""
    markers = receipt.get("implementation_reviewers")
    found: set[str] = set()
    _add_identity(markers, found)
    rec = reviewer_record(receipt) or {}
    if rec.get("reviewed_implementation") is True or rec.get("also_reviewed_implementation") is True:
        return "FAIL"
    if found and any(r in found for r in reviewer_ids):
        return "FAIL"
    return "PASS"


def _dependency_authors(receipt: dict, context: dict | None) -> dict[str, list[str]]:
    planted = receipt.get("dependency_authors")
    if isinstance(planted, dict):
        out: dict[str, list[str]] = {}
        for key, value in planted.items():
            ids: set[str] = set()
            _add_identity(value, ids)
            out[str(key)] = sorted(ids)
        return out
    raw = (context or {}).get("dependency_authors") or {}
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, value in raw.items():
        ids = set()
        _add_identity(value, ids)
        out[str(key)] = sorted(ids)
    return out


def _catalog_deps(receipt: dict, context: dict | None) -> list[str]:
    planted = receipt.get("catalog_dependencies")
    if isinstance(planted, list):
        return [str(d) for d in planted if isinstance(d, str)]
    raw = (context or {}).get("catalog_dependencies")
    if isinstance(raw, list):
        return [str(d) for d in raw]
    return []


def _rule_c(
    reviewer_ids: list[str],
    dep_authors: dict[str, list[str]],
    catalog_deps: list[str],
) -> tuple[str, list[str]]:
    hits: list[str] = []
    known = 0
    for dep, authors in dep_authors.items():
        if not authors:
            continue
        known += 1
        for rev in reviewer_ids:
            if any(rev == a or a in rev for a in authors):
                hits.append(dep)
                break
    if hits:
        return "FAIL", hits
    if not catalog_deps:
        return "PASS", []
    if known < len(catalog_deps):
        return "NOT-CHECKED", []
    return "PASS", []


def evaluate_condition_9(receipt: dict, context: dict | None = None) -> dict:
    """Typed condition-9 verdict. Same function imported at fan-in and by the audit."""
    if not isinstance(receipt, dict):
        return {
            "condition": CONDITION_INDEX,
            "text": CONDITION_9_TEXT,
            "outcome": "FAIL",
            "classification": "not-a-receipt",
            "reviewer_identity": None,
            "author_identities": [],
            "independence_verdict": "NOT-INDEPENDENT",
            "independence_rules": {"a": "FAIL", "b": "FAIL", "c": "FAIL"},
            "reducer_anchor": reducer_anchor(),
            "reason": "receipt is not an object",
        }

    authors = author_identities(receipt)
    rec = reviewer_record(receipt)
    rev_ids = reviewer_identities(receipt)
    reviewer_identity = rev_ids[0] if rev_ids else None
    rules = {"a": "NOT-CHECKED", "b": "NOT-CHECKED", "c": "NOT-CHECKED"}
    classification = "no-reviewer"
    independence = "UNKNOWN"
    reason = ""

    if rec is None or not rev_ids:
        classification = "no-reviewer"
        independence = "NOT-INDEPENDENT"
        outcome = "FAIL"
        reason = "no reviewer record"
        rules = {"a": "FAIL", "b": "FAIL", "c": "FAIL"}
    else:
        verdict = str(rec.get("verdict") or "").upper()
        flagged_independent = rec.get("independent")
        self_cert = _contains_author(rev_ids, authors)
        if self_cert:
            rules["a"] = "FAIL"
            classification = "self-certification"
            independence = "NOT-INDEPENDENT"
            outcome = "FAIL"
            reason = "reviewer field contains the author"
        else:
            if authors:
                overlap = set(rev_ids) & set(authors)
                rules["a"] = "FAIL" if overlap else "PASS"
            else:
                rules["a"] = "NOT-CHECKED"
            rules["b"] = _rule_b_prior_review(receipt, rev_ids)
            dep_authors = _dependency_authors(receipt, context)
            catalog_deps = _catalog_deps(receipt, context)
            rules["c"], dep_hits = _rule_c(rev_ids, dep_authors, catalog_deps)
            if rules["c"] == "FAIL":
                classification = "dependency-author"
                independence = "NOT-INDEPENDENT"
                outcome = "FAIL"
                reason = "reviewer authored dependency " + ",".join(dep_hits)
            elif rules["b"] == "FAIL":
                classification = "prior-implementation-review"
                independence = "NOT-INDEPENDENT"
                outcome = "FAIL"
                reason = "confirmer already reviewed the implementation (rule b)"
            elif rules["a"] == "FAIL":
                classification = "self-review"
                independence = "NOT-INDEPENDENT"
                outcome = "FAIL"
                reason = "confirmer id appears in authoring provenance (rule a)"
            elif verdict != "PASS":
                classification = "reviewer-not-pass"
                independence = "UNKNOWN"
                outcome = "FAIL"
                reason = f"reviewer.verdict={verdict or 'ABSENT'} is not PASS"
            elif flagged_independent is False:
                classification = "flagged-not-independent"
                independence = "NOT-INDEPENDENT"
                outcome = "FAIL"
                reason = "reviewer.independent is false"
            elif "NOT-CHECKED" in rules.values():
                classification = "independence-not-checked"
                independence = "UNKNOWN"
                outcome = "NOT-CHECKED"
                reason = "CNF-0002 rule not evaluable: " + ",".join(
                    f"{k}={v}" for k, v in rules.items() if v == "NOT-CHECKED"
                )
            else:
                classification = "independent-pass"
                independence = "INDEPENDENT"
                outcome = "PASS"
                reason = "independent reviewer PASS under CNF-0002"

    return {
        "condition": CONDITION_INDEX,
        "text": CONDITION_9_TEXT,
        "outcome": outcome,
        "classification": classification,
        "reviewer_identity": reviewer_identity,
        "author_identities": authors,
        "independence_verdict": independence,
        "independence_rules": rules,
        "reducer_anchor": reducer_anchor(),
        "reason": reason,
        "claims_completion": claims_completion(receipt),
    }
