"""CNF-0002 independence predicate plus CNF-0124 authorship defaults.

A confirmer is independent of a claim only when:
  (a) its agent id appears nowhere in the implementation authoring provenance
  (b) it did not review that implementation
  (c) it did not author an ancestor artifact the claim depends on

CNF-0124 additions (fail-closed):
  missing-authorship: absent confirmer or implementer identity is a VIOLATION
  forged-authorship-path-ledger: claimed identity contradicted by the
    changed-path surface or the tool-call ledger is a VIOLATION
"""
from __future__ import annotations

from typing import Any, Iterable

RULE_MISSING = "rule-missing-authorship"
RULE_FORGED = "rule-forged-authorship-path-ledger"
RULE_A = "rule-a-author-overlap"
RULE_B = "rule-b-implementation-reviewer"
RULE_C = "rule-c-ancestor-author"
RULE_PASS = "rule-independent-pass"

PRIORITY_P0_P1 = frozenset({"P0", "P1"})


def _norm(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip().lower()
        return text or None
    if isinstance(value, dict):
        for key in (
            "agent_id",
            "id",
            "author",
            "confirmer_id",
            "implementer_id",
            "identity",
            "name",
        ):
            found = _norm(value.get(key))
            if found:
                return found
    return None


def _collect(values: Iterable[Any]) -> set[str]:
    out: set[str] = set()
    for item in values:
        if isinstance(item, (list, tuple, set)):
            out.update(_collect(item))
            continue
        n = _norm(item)
        if n:
            out.add(n)
    return out


def identities_from(blob: Any, *keys: str) -> set[str]:
    if not isinstance(blob, dict):
        return set()
    found: set[str] = set()
    for key in keys:
        if key in blob:
            found.update(_collect([blob.get(key)]))
    return found


def confirmer_of(receipt: dict) -> str | None:
    for key in ("confirmer_identity", "confirmer", "confirmer_id", "reviewer"):
        n = _norm(receipt.get(key))
        if n:
            return n
    return None


def implementer_of(receipt: dict) -> str | None:
    impl = receipt.get("implementation")
    if isinstance(impl, dict):
        n = _norm(
            impl.get("implementer_identity")
            or impl.get("implementer")
            or impl.get("author")
            or impl.get("produced_by")
        )
        if n:
            return n
    for key in ("implementer_identity", "implementer", "author"):
        n = _norm(receipt.get(key))
        if n:
            return n
    return None


def authoring_provenance(receipt: dict) -> set[str]:
    authors = set()
    impl = receipt.get("implementation") if isinstance(receipt.get("implementation"), dict) else {}
    authors.update(
        identities_from(
            impl,
            "implementer_identity",
            "implementer",
            "author",
            "authors",
            "produced_by",
            "authoring_provenance",
            "git_authors",
        )
    )
    authors.update(
        identities_from(
            receipt,
            "implementer_identity",
            "implementer",
            "author",
            "implementation_authors",
        )
    )
    impl_id = implementer_of(receipt)
    if impl_id:
        authors.add(impl_id)
    return authors


def reviewers_of(receipt: dict) -> set[str]:
    impl = receipt.get("implementation") if isinstance(receipt.get("implementation"), dict) else {}
    found = identities_from(impl, "reviewers", "reviewed_by")
    found.update(identities_from(receipt, "implementation_reviewers"))
    return found


def ancestor_authors_of(receipt: dict) -> set[str]:
    impl = receipt.get("implementation") if isinstance(receipt.get("implementation"), dict) else {}
    found = identities_from(impl, "ancestor_authors", "dependency_authors")
    found.update(identities_from(receipt, "ancestor_authors", "dependency_authors"))
    deps = receipt.get("dependencies") or impl.get("dependencies") or []
    if isinstance(deps, list):
        for dep in deps:
            if isinstance(dep, dict):
                found.update(
                    identities_from(dep, "author", "authors", "implementer", "produced_by")
                )
    return found


def ledger_actors(receipt: dict) -> set[str]:
    actors: set[str] = set()
    ledger = receipt.get("tool_call_ledger") or []
    if isinstance(ledger, list):
        for row in ledger:
            if isinstance(row, dict):
                actors.update(
                    identities_from(row, "agent_id", "actor", "author", "produced_by")
                )
            else:
                n = _norm(row)
                if n:
                    actors.add(n)
    return actors


def changed_paths(receipt: dict) -> list[str]:
    raw = receipt.get("changed_paths") or receipt.get("changed_path_surface") or []
    if isinstance(raw, list):
        return [str(p) for p in raw if str(p).strip()]
    return []


def implementation_paths(receipt: dict) -> set[str]:
    impl = receipt.get("implementation") if isinstance(receipt.get("implementation"), dict) else {}
    paths = impl.get("output_paths") or impl.get("changed_paths") or []
    out = set()
    if isinstance(paths, list):
        out.update(str(p) for p in paths if str(p).strip())
    single = impl.get("output_path")
    if single:
        out.add(str(single))
    return out


def corroboration(receipt: dict) -> dict:
    paths = changed_paths(receipt)
    ledger = receipt.get("tool_call_ledger") if isinstance(receipt.get("tool_call_ledger"), list) else []
    claimed = confirmer_of(receipt)
    actors = ledger_actors(receipt)
    impl_paths = implementation_paths(receipt)
    path_overlap = bool(impl_paths and set(paths) & impl_paths)

    if not claimed:
        result = "UNAVAILABLE"
    elif actors and claimed not in actors:
        result = "CONTRADICTS"
    elif path_overlap and implementer_of(receipt) and claimed == implementer_of(receipt):
        # Same agent touching implementation paths is consistent with self-confirm,
        # not a metadata forgery.
        result = "MATCHES"
    elif actors and claimed in actors:
        result = "MATCHES"
    elif not actors and not paths:
        result = "UNAVAILABLE"
    else:
        result = "MATCHES"

    return {
        "changed_path_surface": paths,
        "tool_call_ledger": ledger,
        "ledger_actors": sorted(actors),
        "implementation_path_overlap": path_overlap,
        "result": result,
    }


def claim_priority(receipt: dict) -> str:
    raw = str(receipt.get("claim_priority") or receipt.get("priority") or "UNSTATED").upper()
    if raw in {"P0", "P1", "P2", "P3", "UNSTATED"}:
        return raw
    return "UNSTATED"


def evaluate(
    receipt: dict,
    *,
    enable_b: bool = True,
    enable_c: bool = True,
    enable_forged: bool = True,
) -> dict:
    """Return independence verdict with the single deciding rule named."""
    confirmer = confirmer_of(receipt)
    implementer = implementer_of(receipt)
    authors = authoring_provenance(receipt)
    reviewers = reviewers_of(receipt)
    ancestors = ancestor_authors_of(receipt)
    corr = corroboration(receipt)
    priority = claim_priority(receipt)

    if not confirmer or not implementer:
        rule = RULE_MISSING
        verdict = "VIOLATION"
    elif enable_forged and corr["result"] == "CONTRADICTS":
        rule = RULE_FORGED
        verdict = "VIOLATION"
    elif confirmer in authors:
        rule = RULE_A
        verdict = "VIOLATION"
    elif enable_b and confirmer in reviewers:
        rule = RULE_B
        verdict = "VIOLATION"
    elif enable_c and confirmer in ancestors:
        rule = RULE_C
        verdict = "VIOLATION"
    else:
        rule = RULE_PASS
        verdict = "PASS"

    return {
        "receipt_id": str(receipt.get("receipt_id") or receipt.get("id") or "unnamed"),
        "claim_id": str(receipt.get("claim_id") or receipt.get("claim") or "unidentified"),
        "claim_priority": priority,
        "confirmer_identity": confirmer,
        "implementer_identity": implementer,
        "independence_verdict": verdict,
        "deciding_rule": rule,
        "corroboration": {
            "changed_path_surface": corr["changed_path_surface"],
            "tool_call_ledger": corr["tool_call_ledger"],
            "result": corr["result"],
        },
        "p0_or_p1": priority in PRIORITY_P0_P1,
        "authoring_provenance": sorted(authors),
        "implementation_reviewers": sorted(reviewers),
        "ancestor_authors": sorted(ancestors),
    }


# evaluate() is the predicate entry; evidence cites this line.
PREDICATE_LINE = evaluate.__code__.co_firstlineno
PREDICATE_PATH = "command-center/p2-wave/probes/CNF-0124/predicate.py"
