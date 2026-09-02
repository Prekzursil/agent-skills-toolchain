"""Target evaluator for CouncilSpec quotas (IMP-0301).

A CouncilSpec declares *targets*; a council *snapshot* carries the ideas,
prior art, objections, evidence and counterexamples produced so far.
``evaluate(spec, snapshot)`` scores every declared target and returns one
plain-JSON row per target, in declaration order, plus a report header.

Kinds
-----
``unique_idea``
    A *count* kind.  The unique-idea count is the IMP-0300 counter
    (``council.quota.unique_ideas``), so this evaluator records the target
    as deferred (``skipped: true``, ``pass: null``) and lists it under
    ``skipped_count_targets`` instead of re-implementing that counter.
``coverage``
    Every declared category must hold at least ``min_per_category`` ideas.
    The rule is per declared category (CNL-0054 clustered-vs-spread).  The
    occupied-fraction aggregate is computed alongside so the two rules can
    be compared on the same snapshot; it is never the verdict.
``category``
    The same attainment table as coverage with its own floor.
``novelty``
    Token Jaccard of each idea against every prior-art text.  An idea is
    novel when its nearest prior-art Jaccard is strictly below
    ``max_jaccard``; the target passes when at least ``min_novel_count``
    ideas are novel.
``diversity``
    Gini-Simpson index of the ideas over the declared categories; passes
    when the index is at least ``min_simpson``.
``objection`` / ``evidence`` / ``counterexample``
    Floors on the number of well-formed entries in the matching snapshot
    list (``min_count``).

Everything is stdlib, deterministic (no clocks, no paths) and plain JSON.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

__all__ = [
    "COUNT_KINDS",
    "COVERAGE_RULE",
    "DEFAULTS",
    "DEFERRED_REASON",
    "KNOWN_KINDS",
    "NON_COUNT_KINDS",
    "SpecError",
    "category_counts",
    "evaluate",
    "evaluate_target",
    "simpson_index",
    "token_jaccard",
    "tokens",
]

COUNT_KINDS: frozenset[str] = frozenset({"unique_idea"})
NON_COUNT_KINDS: frozenset[str] = frozenset(
    {
        "coverage",
        "category",
        "novelty",
        "diversity",
        "objection",
        "evidence",
        "counterexample",
    }
)
KNOWN_KINDS: frozenset[str] = COUNT_KINDS | NON_COUNT_KINDS
COVERAGE_RULE = "per_category"
DEFERRED_REASON = "count_target_deferred_to_unique_ideas"
UNIQUE_IDEAS_MODULE = "council.quota.unique_ideas"

DEFAULTS: dict[str, int | float] = {
    "min_count": 1,
    "min_per_category": 1,
    "aggregate_threshold": 0.5,
    "max_jaccard": 0.5,
    "min_novel_count": 1,
    "min_simpson": 0.0,
}

# Snapshot list consulted by each floor kind; the first key is canonical.
_FLOOR_FIELDS: dict[str, tuple[str, ...]] = {
    "objection": ("objections", "objection"),
    "evidence": ("evidence", "evidences"),
    "counterexample": ("counterexamples", "counterexample"),
}
# Keys under which a floor entry may point at the idea it addresses.
_LINK_KEYS: tuple[str, ...] = ("target_id", "claim_id", "idea_id")
# A floor entry is well-formed when it carries some content, not just ids.
_CONTENT_KEYS: tuple[str, ...] = (
    "text",
    "citation",
    "claim",
    "title",
    "summary",
    "source",
    "url",
    "quote",
    "doi",
    "example",
    "body",
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class SpecError(ValueError):
    """The CouncilSpec or the snapshot is malformed."""


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #
def _require_mapping(value: Any, what: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SpecError(f"{what} must be a mapping, got {type(value).__name__}")
    return value


def _list_field(container: Mapping[str, Any], keys: Sequence[str], what: str) -> list[Any]:
    """Return the first present list under ``keys`` (``None`` counts as empty)."""
    for key in keys:
        if key not in container:
            continue
        value = container[key]
        if value is None:
            return []
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            raise SpecError(f"{what}.{key} must be a list, got {type(value).__name__}")
        return list(value)
    return []


def _number(
    target: Mapping[str, Any],
    tid: str,
    key: str,
    *,
    integer: bool = False,
    low: float = 0.0,
    high: float | None = None,
) -> int | float:
    """Read a numeric target parameter, falling back to ``DEFAULTS[key]``."""
    value = target.get(key)
    if value is None:
        value = DEFAULTS[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SpecError(f"target {tid!r}: {key} must be a number, got {value!r}")
    if integer and int(value) != value:
        raise SpecError(f"target {tid!r}: {key} must be an integer, got {value!r}")
    if value < low or (high is not None and value > high):
        bound = f">= {low:g}" if high is None else f"in [{low:g}, {high:g}]"
        raise SpecError(f"target {tid!r}: {key} must be {bound}, got {value!r}")
    return int(value) if integer else float(value)


def _ideas(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Normalise ``snapshot.ideas``: mappings are copied, strings become ``text``."""
    out: list[dict[str, Any]] = []
    for index, raw in enumerate(_list_field(snapshot, ("ideas",), "snapshot")):
        if isinstance(raw, str):
            raw = {"text": raw}
        if not isinstance(raw, Mapping):
            raise SpecError(
                f"snapshot.ideas[{index}] must be a mapping or string, got {type(raw).__name__}"
            )
        idea = dict(raw)
        idea["id"] = str(idea.get("id") or f"idea-{index}")
        out.append(idea)
    return out


def _declared_categories(
    target: Mapping[str, Any], spec: Mapping[str, Any], tid: str
) -> list[str]:
    """Target-level ``declared_categories`` with a spec-level fallback."""
    raw = target.get("declared_categories")
    if raw is None:
        raw = spec.get("declared_categories")
    if raw is None:
        return []
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise SpecError(f"target {tid!r}: declared_categories must be a list")
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        name = str(item or "").strip()
        if not name:
            raise SpecError(f"target {tid!r}: declared_categories holds an empty name")
        if name in seen:
            raise SpecError(f"target {tid!r}: declared category {name!r} repeated")
        seen.add(name)
        out.append(name)
    return out


# --------------------------------------------------------------------------- #
# Measurement helpers (public so probes can recount with the same instrument)
# --------------------------------------------------------------------------- #
def tokens(text: Any) -> frozenset[str]:
    """Lower-cased ``[a-z0-9]+`` tokens of ``text``."""
    return frozenset(_TOKEN_RE.findall(str(text or "").lower()))


def token_jaccard(left: frozenset[str] | set[str], right: frozenset[str] | set[str]) -> float:
    """Jaccard similarity of two token sets; two empty sets are identical (1.0)."""
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _category_of(idea: Mapping[str, Any]) -> str:
    return str(idea.get("category") or "").strip()


def category_counts(ideas: Sequence[Mapping[str, Any]], declared: Sequence[str]) -> dict[str, int]:
    """Ideas per declared category, in declared order; other categories are ignored."""
    counts = {name: 0 for name in declared}
    for idea in ideas:
        name = _category_of(idea)
        if name in counts:
            counts[name] += 1
    return counts


def _undeclared_categories(
    ideas: Sequence[Mapping[str, Any]], declared: Sequence[str]
) -> list[dict[str, Any]]:
    known = set(declared)
    seen: dict[str, int] = {}
    for idea in ideas:
        name = _category_of(idea)
        if name and name not in known:
            seen[name] = seen.get(name, 0) + 1
    return [{"category": name, "count": seen[name]} for name in sorted(seen)]


def _table(counts: Mapping[str, int]) -> list[dict[str, Any]]:
    return [{"category": name, "count": count} for name, count in counts.items()]


def _sum_of_squares(counts: Mapping[str, int]) -> float:
    total = sum(counts.values())
    if total <= 0:
        return 1.0
    return sum((count / total) ** 2 for count in counts.values())


def simpson_index(counts: Mapping[str, int]) -> float:
    """Gini-Simpson index ``1 - sum(p_i^2)``; 0.0 when nothing is classified."""
    if sum(counts.values()) <= 0:
        return 0.0
    return 1.0 - _sum_of_squares(counts)


def _text_of(entry: Any) -> str:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, Mapping):
        for key in ("text", "title", "claim", "summary"):
            value = entry.get(key)
            if value:
                return str(value)
    return ""


# --------------------------------------------------------------------------- #
# Per-kind evaluators
# --------------------------------------------------------------------------- #
def _eval_unique_idea(
    target: Mapping[str, Any], tid: str, ideas: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Count kind: recorded as deferred to the IMP-0300 counter, never scored here."""
    min_count = _number(target, tid, "min_count", integer=True)
    return {
        "skipped": True,
        "pass": None,
        "reason": DEFERRED_REASON,
        "deferred_to": UNIQUE_IDEAS_MODULE,
        "min_count": min_count,
        "n_ideas": len(ideas),
    }


def _eval_coverage(
    target: Mapping[str, Any],
    tid: str,
    spec: Mapping[str, Any],
    ideas: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Per-category coverage; the aggregate is reported next to it, not used."""
    declared = _declared_categories(target, spec, tid)
    floor = _number(target, tid, "min_per_category", integer=True)
    threshold = _number(target, tid, "aggregate_threshold", high=1.0)
    counts = category_counts(ideas, declared)
    empty = [name for name, count in counts.items() if count == 0]
    below = [name for name, count in counts.items() if count < floor]
    occupied = sum(1 for count in counts.values() if count > 0)
    fraction = occupied / len(declared) if declared else 0.0
    per_category_pass = bool(declared) and not below
    aggregate_pass = bool(declared) and fraction >= threshold
    row: dict[str, Any] = {
        "skipped": False,
        "rule": COVERAGE_RULE,
        "declared_categories": declared,
        "min_per_category": floor,
        "per_category": _table(counts),
        "empty_categories": empty,
        "below_minimum": below,
        "undeclared_categories": _undeclared_categories(ideas, declared),
        "occupied_categories": occupied,
        "occupied_fraction_aggregate": fraction,
        "aggregate_threshold": threshold,
        "aggregate_would_pass": aggregate_pass,
        "aggregate_and_per_category_disagree": aggregate_pass != per_category_pass,
        "pass": per_category_pass,
    }
    if not declared:
        row["reason"] = "no_declared_categories"
    return row


def _eval_category(
    target: Mapping[str, Any],
    tid: str,
    spec: Mapping[str, Any],
    ideas: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Every declared category must reach ``min_per_category`` ideas."""
    declared = _declared_categories(target, spec, tid)
    floor = _number(target, tid, "min_per_category", integer=True)
    counts = category_counts(ideas, declared)
    below = [name for name, count in counts.items() if count < floor]
    row: dict[str, Any] = {
        "skipped": False,
        "declared_categories": declared,
        "min_per_category": floor,
        "per_category": _table(counts),
        "below_minimum": below,
        "undeclared_categories": _undeclared_categories(ideas, declared),
        "pass": bool(declared) and not below,
    }
    if not declared:
        row["reason"] = "no_declared_categories"
    return row


def _eval_novelty(
    target: Mapping[str, Any],
    tid: str,
    snapshot: Mapping[str, Any],
    ideas: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Token-Jaccard novelty of every idea against the prior-art corpus."""
    max_jaccard = _number(target, tid, "max_jaccard", high=1.0)
    min_novel = _number(target, tid, "min_novel_count", integer=True)
    prior: list[tuple[str, frozenset[str]]] = []
    for index, raw in enumerate(_list_field(snapshot, ("prior_art",), "snapshot")):
        pid = raw.get("id") if isinstance(raw, Mapping) else None
        prior.append((str(pid or f"prior-{index}"), tokens(_text_of(raw))))
    rows: list[dict[str, Any]] = []
    novel_count = 0
    for idea in ideas:
        idea_tokens = tokens(_text_of(idea))
        best = 0.0
        nearest: str | None = None
        for pid, prior_tokens in prior:
            score = token_jaccard(idea_tokens, prior_tokens)
            if nearest is None or score > best:
                best, nearest = score, pid
        novel = best < max_jaccard
        novel_count += int(novel)
        rows.append(
            {
                "id": str(idea["id"]),
                "novel": novel,
                "max_jaccard_to_prior": best,
                "nearest_prior_id": nearest,
            }
        )
    return {
        "skipped": False,
        "max_jaccard": max_jaccard,
        "min_novel_count": min_novel,
        "n_prior_art": len(prior),
        "ideas": rows,
        "novel_count": novel_count,
        "pass": novel_count >= min_novel,
    }


def _eval_diversity(
    target: Mapping[str, Any],
    tid: str,
    spec: Mapping[str, Any],
    ideas: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Gini-Simpson diversity of the ideas over the declared categories."""
    declared = _declared_categories(target, spec, tid)
    min_simpson = _number(target, tid, "min_simpson", high=1.0)
    counts = category_counts(ideas, declared)
    total = sum(counts.values())
    simpson = simpson_index(counts)
    row: dict[str, Any] = {
        "skipped": False,
        "declared_categories": declared,
        "min_simpson": min_simpson,
        "per_category": _table(counts),
        "classified_ideas": total,
        "simpson": simpson,
        "inverse_simpson": (1.0 / _sum_of_squares(counts)) if total > 0 else 0.0,
        "pass": total > 0 and simpson >= min_simpson,
    }
    if total == 0:
        row["reason"] = "no_classified_ideas"
    return row


def _eval_floor(
    kind: str,
    target: Mapping[str, Any],
    tid: str,
    snapshot: Mapping[str, Any],
    ideas: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Objection / evidence / counterexample floors on well-formed entries."""
    min_count = _number(target, tid, "min_count", integer=True)
    fields = _FLOOR_FIELDS[kind]
    entries = _list_field(snapshot, fields, "snapshot")
    idea_ids = {str(idea["id"]) for idea in ideas}
    accepted: list[str] = []
    malformed = 0
    linked = 0
    for index, raw in enumerate(entries):
        if isinstance(raw, str):
            if raw.strip():
                accepted.append(f"{kind}-{index}")
            else:
                malformed += 1
            continue
        if not isinstance(raw, Mapping) or not any(raw.get(key) for key in _CONTENT_KEYS):
            malformed += 1
            continue
        accepted.append(str(raw.get("id") or f"{kind}-{index}"))
        if any(str(raw.get(key)) in idea_ids for key in _LINK_KEYS if raw.get(key)):
            linked += 1
    return {
        "skipped": False,
        "source_field": fields[0],
        "min_count": min_count,
        "count": len(accepted),
        "entry_ids": accepted,
        "malformed_entries": malformed,
        "linked_to_snapshot_ideas": linked,
        "pass": len(accepted) >= min_count,
    }


def evaluate_target(
    target: Any,
    spec: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    ideas: Sequence[Mapping[str, Any]],
    *,
    index: int = 0,
) -> dict[str, Any]:
    """Evaluate one declared target; unknown kinds are recorded, not scored."""
    target = _require_mapping(target, f"spec.targets[{index}]")
    kind = str(target.get("kind") or "").strip()
    if not kind:
        raise SpecError(f"spec.targets[{index}] declares no kind")
    tid = str(target.get("id") or f"{kind}-{index}")
    if kind == "unique_idea":
        body = _eval_unique_idea(target, tid, ideas)
    elif kind == "coverage":
        body = _eval_coverage(target, tid, spec, ideas)
    elif kind == "category":
        body = _eval_category(target, tid, spec, ideas)
    elif kind == "novelty":
        body = _eval_novelty(target, tid, snapshot, ideas)
    elif kind == "diversity":
        body = _eval_diversity(target, tid, spec, ideas)
    elif kind in _FLOOR_FIELDS:
        body = _eval_floor(kind, target, tid, snapshot, ideas)
    else:
        body = {
            "skipped": True,
            "pass": None,
            "reason": "unknown_target_kind",
            "known_kinds": sorted(KNOWN_KINDS),
        }
    row: dict[str, Any] = {"id": tid, "kind": kind}
    row.update(body)
    return row


def _falsifiable_answer(coverage_rows: Sequence[Mapping[str, Any]]) -> str:
    """Is coverage measured per category or in aggregate?  Answered from the data."""
    if not coverage_rows:
        return (
            "No coverage target declared. Coverage is measured per declared "
            f"category (rule={COVERAGE_RULE}); an occupied-fraction aggregate "
            "is never the verdict."
        )
    row = coverage_rows[0]
    aggregate_word = "PASS" if row["aggregate_would_pass"] else "FAIL"
    per_category_word = "PASS" if row["pass"] else "FAIL"
    if not row["declared_categories"]:
        because = "no categories are declared"
    elif row["empty_categories"]:
        because = f"empty_categories={row['empty_categories']!r}"
    elif row["below_minimum"]:
        because = (
            f"below_minimum={row['below_minimum']!r} "
            f"(min_per_category={row['min_per_category']})"
        )
    else:
        because = (
            "every declared category holds at least "
            f"min_per_category={row['min_per_category']} ideas"
        )
    disagree = bool(row["aggregate_and_per_category_disagree"])
    conjunction = "but" if disagree else "and"
    agreement = "disagree" if disagree else "agree"
    return (
        "No: coverage is measured per declared category. "
        f"Occupied-fraction aggregate={row['occupied_fraction_aggregate']:.6f} "
        f"would {aggregate_word} threshold {row['aggregate_threshold']}, "
        f"{conjunction} per-category coverage {per_category_word} because {because}. "
        f"The evaluator uses per-category; the two rules {agreement} on this snapshot."
    )


def evaluate(spec: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate every target ``spec`` declares against ``snapshot``.

    Returns a plain-JSON report: ``results`` holds one row per target in
    declaration order; ``skipped_count_targets`` lists the deferred count
    kinds; ``all_non_count_pass`` is true only when at least one non-count
    target was evaluated, every evaluated one passed and no target had an
    unknown kind.  Raises :class:`SpecError` on malformed input.
    """
    spec = _require_mapping(spec, "spec")
    snapshot = _require_mapping(snapshot, "snapshot")
    targets = _list_field(spec, ("targets",), "spec")
    if not targets:
        raise SpecError("spec.targets must declare at least one target")
    ideas = _ideas(snapshot)
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, target in enumerate(targets):
        row = evaluate_target(target, spec, snapshot, ideas, index=index)
        if row["id"] in seen:
            raise SpecError(f"duplicate target id {row['id']!r}")
        seen.add(row["id"])
        results.append(row)
    skipped_count = [row["id"] for row in results if row["kind"] in COUNT_KINDS]
    unknown = [row["id"] for row in results if row["kind"] not in KNOWN_KINDS]
    evaluated = [row for row in results if row["kind"] in NON_COUNT_KINDS]
    failed = [row["id"] for row in evaluated if row["pass"] is False]
    coverage_rows = [row for row in results if row["kind"] == "coverage"]
    spec_id = spec.get("id")
    snapshot_id = snapshot.get("id")
    return {
        "spec_id": str(spec_id) if spec_id is not None else None,
        "snapshot_id": str(snapshot_id) if snapshot_id is not None else None,
        "n_targets": len(results),
        "n_ideas": len(ideas),
        "results": results,
        "skipped_count_targets": skipped_count,
        "unknown_kind_targets": unknown,
        "evaluated_targets": [row["id"] for row in evaluated],
        "failed_targets": failed,
        "all_non_count_pass": bool(evaluated) and not failed and not unknown,
        "coverage_rule": COVERAGE_RULE,
        "falsifiable_answer": _falsifiable_answer(coverage_rows),
    }
