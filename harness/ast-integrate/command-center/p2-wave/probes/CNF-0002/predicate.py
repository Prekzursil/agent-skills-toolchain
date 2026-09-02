#!/usr/bin/env python3
"""CNF-0002 confirmer-independence predicate (spec line 11030).

A confirmer is independent of a claim only when ALL of:
  (a) its agent id appears nowhere in the authoring provenance of the
      implementation receipt;
  (b) it did not review that implementation;
  (c) it did not author an ancestor artifact the claim depends on.

Authorship-only is rule (a) alone. If (a) and the full predicate agree on a
reviewer-confirmer, rule (b) is inert. If (a) and (c) agree on a dependency
author, rule (c) is inert.

Empty identity sets do not count as independence: missing confirmer or
missing authorship metadata is unevaluable, never a pass by omission.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

AUTHOR_KEYS = (
    "author",
    "author_id",
    "authored_by",
    "authors",
    "implementer",
    "implementer_id",
    "implementation_author",
    "executor_id",
    "authoring_agent",
    "produced_by_agent",
    "git_author",
    "git_authors",
)
REVIEW_KEYS = (
    "reviewer",
    "reviewer_id",
    "reviewed_by",
    "reviewers",
    "reviewer_agent",
)
CONFIRMER_KEYS = (
    "confirmer",
    "confirmer_id",
    "confirmed_by",
    "confirmer_agent",
)
ID_ATTRS = (
    "id",
    "agent_id",
    "author_id",
    "reviewer_id",
    "confirmer_id",
    "name",
)

# Catalog keys that would name an implementation author if present.
# assigned_model_vendor_role is an assignment, not authorship provenance.
CATALOG_AUTHOR_KEYS = frozenset(
    {
        "author",
        "author_id",
        "authored_by",
        "authors",
        "implementer",
        "implementer_id",
        "implementation_author",
        "executor_id",
        "agent_id",
        "git_author",
        "git_authors",
        "authoring_agent",
        "produced_by_agent",
        "provenance",
    }
)


def _norm(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value).strip().casefold() or None
    if isinstance(value, str):
        s = value.strip().casefold()
        return s or None
    if isinstance(value, dict):
        for key in ID_ATTRS:
            got = _norm(value.get(key))
            if got:
                return got
        return None
    return None


def collect_ids(value: Any) -> set[str]:
    out: set[str] = set()
    if value is None or isinstance(value, bool):
        return out
    if isinstance(value, (str, int, float, dict)):
        n = _norm(value)
        if n:
            out.add(n)
        if isinstance(value, dict):
            for key in ID_ATTRS:
                out.update(collect_ids(value.get(key)))
        return out
    if isinstance(value, (list, tuple, set)):
        for item in value:
            out.update(collect_ids(item))
    return out


def _from_keys(doc: dict[str, Any], keys: Iterable[str]) -> set[str]:
    ids: set[str] = set()
    for key in keys:
        ids.update(collect_ids(doc.get(key)))
    return ids


def authoring_ids(receipt: dict[str, Any] | None) -> set[str]:
    """Rule (a) surface: who wrote the implementation, not who reviewed it."""
    if not isinstance(receipt, dict):
        return set()
    ids = _from_keys(receipt, AUTHOR_KEYS)
    prov = receipt.get("provenance")
    if isinstance(prov, dict):
        ids.update(_from_keys(prov, AUTHOR_KEYS))
        ids.update(collect_ids(prov.get("authors")))
    produced = receipt.get("produced_by")
    if isinstance(produced, dict) and (
        produced.get("agent_id") or produced.get("author_id") or produced.get("role") == "author"
    ):
        ids.update(collect_ids(produced))
    return ids


def reviewer_ids(receipt: dict[str, Any] | None) -> set[str]:
    """Rule (b) surface: who reviewed the implementation."""
    if not isinstance(receipt, dict):
        return set()
    ids = _from_keys(receipt, REVIEW_KEYS)
    rev = receipt.get("reviewer")
    if isinstance(rev, dict):
        ids.update(collect_ids(rev.get("reviewer_id")))
        ids.update(collect_ids(rev.get("id")))
        ids.update(collect_ids(rev.get("agent_id")))
    return ids


def confirmer_id_of(confirmation: dict[str, Any] | None) -> str | None:
    if not isinstance(confirmation, dict):
        return None
    ids = _from_keys(confirmation, CONFIRMER_KEYS)
    if len(ids) == 1:
        return next(iter(ids))
    if len(ids) > 1:
        # Multiple confirmer ids is not independence; pick none and let caller fail closed.
        return None
    return None


def rule_a_author_overlap(confirmer: str | None, implementation: dict[str, Any] | None) -> bool:
    """True when (a) REJECTS: confirmer appears in implementation authoring provenance."""
    cid = _norm(confirmer)
    if not cid:
        return False
    return cid in authoring_ids(implementation)


def rule_b_reviewed_implementation(
    confirmer: str | None, implementation: dict[str, Any] | None
) -> bool:
    """True when (b) REJECTS: confirmer reviewed the implementation."""
    cid = _norm(confirmer)
    if not cid:
        return False
    return cid in reviewer_ids(implementation)


def rule_c_authored_ancestor(
    confirmer: str | None, ancestors: Iterable[dict[str, Any]] | None
) -> bool:
    """True when (c) REJECTS: confirmer authored an ancestor artifact."""
    cid = _norm(confirmer)
    if not cid:
        return False
    for anc in ancestors or []:
        if cid in authoring_ids(anc):
            return True
    return False


@dataclass
class IndependenceVerdict:
    independent: bool
    confirmer_id: str | None
    rule_a_reject: bool
    rule_b_reject: bool
    rule_c_reject: bool
    authors_named: bool
    confirmer_named: bool
    deciding_rules: list[str] = field(default_factory=list)
    unevaluable: str | None = None

    @property
    def authorship_only_accept(self) -> bool:
        return bool(self.confirmer_named and self.authors_named and not self.rule_a_reject)

    @property
    def c_rejects_a_lets_through(self) -> bool:
        return self.authorship_only_accept and self.rule_c_reject


def confirmer_is_independent(
    confirmer: str | None,
    implementation: dict[str, Any] | None,
    ancestors: Iterable[dict[str, Any]] | None = None,
) -> IndependenceVerdict:
    """Independent iff confirmer is named AND (a),(b),(c) are all silent.

    Missing confirmer or missing authorship metadata is unevaluable, not a pass.
    """
    cid = _norm(confirmer)
    authors = authoring_ids(implementation)
    a = rule_a_author_overlap(cid, implementation)
    b = rule_b_reviewed_implementation(cid, implementation)
    c = rule_c_authored_ancestor(cid, ancestors)
    deciding = [n for n, hit in (("a", a), ("b", b), ("c", c)) if hit]
    if not cid:
        return IndependenceVerdict(
            independent=False,
            confirmer_id=None,
            rule_a_reject=False,
            rule_b_reject=False,
            rule_c_reject=False,
            authors_named=bool(authors),
            confirmer_named=False,
            deciding_rules=["missing-confirmer"],
            unevaluable="missing-confirmer",
        )
    if not authors:
        # Empty author set cannot prove (a). Fail closed.
        return IndependenceVerdict(
            independent=False,
            confirmer_id=cid,
            rule_a_reject=False,
            rule_b_reject=b,
            rule_c_reject=c,
            authors_named=False,
            confirmer_named=True,
            deciding_rules=(["missing-provenance"] + deciding),
            unevaluable="missing-provenance",
        )
    independent = not (a or b or c)
    return IndependenceVerdict(
        independent=independent,
        confirmer_id=cid,
        rule_a_reject=a,
        rule_b_reject=b,
        rule_c_reject=c,
        authors_named=True,
        confirmer_named=True,
        deciding_rules=deciding if deciding else (["independent"] if independent else []),
        unevaluable=None,
    )


def evaluate_confirmation(
    confirmation: dict[str, Any],
    implementation: dict[str, Any] | None,
    ancestors: Iterable[dict[str, Any]] | None = None,
) -> IndependenceVerdict:
    return confirmer_is_independent(confirmer_id_of(confirmation), implementation, ancestors)


def catalog_item_names_author(item: dict[str, Any]) -> bool:
    """True only when a catalog row carries implementation-author identity.

    assigned_model_vendor_role is ignored: it names a planned vendor/model/role,
    not who wrote the artifact.
    """
    if not isinstance(item, dict):
        return False
    for key in CATALOG_AUTHOR_KEYS:
        if key in item and item.get(key) not in (None, "", [], {}):
            return True
    assigned = item.get("assigned_model_vendor_role")
    if isinstance(assigned, dict):
        for key in CATALOG_AUTHOR_KEYS:
            if key in assigned and assigned.get(key) not in (None, "", [], {}):
                return True
    return False


def load_planted(name: str) -> dict[str, Any]:
    path = HERE / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))


def planted_reviewer_case() -> dict[str, Any]:
    doc = load_planted("planted_reviewer.json")
    v = evaluate_confirmation(doc["confirmation"], doc["implementation"], doc.get("ancestors") or [])
    authorship_only = v.authorship_only_accept
    b_active = v.rule_b_reject and authorship_only
    return {
        "id": doc["id"],
        "confirmer_id": v.confirmer_id,
        "rule_a_reject": v.rule_a_reject,
        "rule_b_reject": v.rule_b_reject,
        "rule_c_reject": v.rule_c_reject,
        "independent": v.independent,
        "authorship_only_accept": authorship_only,
        "b_is_inert": (not b_active),
        "pass": bool(v.rule_b_reject and authorship_only and not v.independent),
    }


def planted_ancestor_case() -> dict[str, Any]:
    doc = load_planted("planted_ancestor.json")
    v = evaluate_confirmation(doc["confirmation"], doc["implementation"], doc.get("ancestors") or [])
    return {
        "id": doc["id"],
        "confirmer_id": v.confirmer_id,
        "rule_a_reject": v.rule_a_reject,
        "rule_b_reject": v.rule_b_reject,
        "rule_c_reject": v.rule_c_reject,
        "independent": v.independent,
        "authorship_only_accept": v.authorship_only_accept,
        "c_rejects_a_lets_through": v.c_rejects_a_lets_through,
        "pass": bool(v.c_rejects_a_lets_through and not v.independent and not v.rule_a_reject),
    }


def planted_independent_case() -> dict[str, Any]:
    doc = load_planted("planted_independent.json")
    v = evaluate_confirmation(doc["confirmation"], doc["implementation"], doc.get("ancestors") or [])
    return {
        "id": doc["id"],
        "confirmer_id": v.confirmer_id,
        "independent": v.independent,
        "rule_a_reject": v.rule_a_reject,
        "rule_b_reject": v.rule_b_reject,
        "rule_c_reject": v.rule_c_reject,
        "pass": bool(v.independent and not v.rule_a_reject and not v.rule_b_reject and not v.rule_c_reject),
    }
