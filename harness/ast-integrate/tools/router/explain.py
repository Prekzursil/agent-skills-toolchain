"""Selection-explanation emitter with near-miss disclosure (IMP-0395).

An explanation record answers, for one routing decision, three questions an
owner may ask without re-running the router:

* why was each capability selected (``selected[*].reason``)?
* which rule or score produced it (``selected[*].producing_rule``)?
* which capabilities were near-misses that did NOT make the cut, and why
  (``near_misses[*].cutoff_reason``)?

The decision procedure is printed (``PROCEDURE``), not implied, and the
record carries every candidate row it was computed from (``candidates``), so
``tools/router/reconstruct.py`` can rebuild the selected set from the
explanation alone.
"""
from __future__ import annotations

from typing import Any, Iterable

__all__ = [
    "PROCEDURE",
    "discloses_near_misses",
    "explain_one",
    "reconstruct_selected",
]

# The precedence the router applies, in order.  PROCEDURE[0] is the rule an
# owner most often needs spelled out: an owner BAN outranks any score.
PROCEDURE: tuple[str, ...] = (
    "1. BAN beats every fusion score: a banned capability is never selected, "
    "whatever its score, and is disclosed as a near-miss with "
    "cutoff_reason=banned-by-owner-override.",
    "2. PIN beats threshold and budget: a pinned capability (unless banned) is "
    "selected first, even below min_score, and its token_cost is charged to "
    "the budget before any scored candidate.",
    "3. Remaining candidates are ranked by fusion_score descending; a candidate "
    "is selected when fusion_score >= min_score and its token_cost fits the "
    "remaining budget_tokens.",
    "4. A candidate that was not selected is a near-miss when it was banned, "
    "when it scored >= min_score but did not fit the budget, or when it "
    "scored within near_miss_margin below min_score; every near-miss carries "
    "a cutoff_reason.",
    "5. reconstruct.py reads the explanation only: the selected ids, in order, "
    "are the decision.",
)

DEFAULT_NEAR_MISS_MARGIN = 0.20


def _score(row: dict[str, Any]) -> float:
    try:
        return float(row.get("fusion_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _cost(row: dict[str, Any]) -> int:
    try:
        return int(row.get("token_cost") or 0)
    except (TypeError, ValueError):
        return 0


def _candidate_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "capability_id": str(row.get("capability_id") or ""),
        "fusion_score": _score(row),
        "token_cost": _cost(row),
        "rule_id": row.get("rule_id"),
    }


def explain_one(trace: dict[str, Any], index: dict[str, Any] | None = None) -> dict[str, Any]:
    """Explain one routing decision from a fusion+override trace.

    ``trace`` carries ``query_id``, ``min_score``, ``budget_tokens``,
    ``near_miss_margin``, ``overrides.banned``/``overrides.pinned`` and the
    fused ``candidates`` (capability_id, fusion_score, token_cost, rule_id).
    ``index`` is the capability index; when given, each row is annotated with
    ``in_index`` so an owner can spot an id the index does not know.
    """
    min_score = float(trace.get("min_score") or 0.0)
    budget = int(trace.get("budget_tokens") or 10**9)
    margin = float(trace.get("near_miss_margin") or DEFAULT_NEAR_MISS_MARGIN)
    overrides = trace.get("overrides") or {}
    banned = [str(x) for x in (overrides.get("banned") or [])]
    pinned = [str(x) for x in (overrides.get("pinned") or [])]
    banned_set = set(banned)
    known = {
        str(c.get("capability_id"))
        for c in ((index or {}).get("capabilities") or [])
        if isinstance(c, dict) and c.get("capability_id")
    }

    candidates = [_candidate_row(c) for c in (trace.get("candidates") or []) if c.get("capability_id")]
    by_id = {c["capability_id"]: c for c in candidates}

    selected: list[dict[str, Any]] = []
    near_misses: list[dict[str, Any]] = []
    chosen: set[str] = set()
    spent = 0

    def _annotate(row: dict[str, Any]) -> dict[str, Any]:
        if known:
            row["in_index"] = row["capability_id"] in known
        return row

    # Step 1+2: BAN beats PIN beats everything else.
    for pid in pinned:
        cand = by_id.get(pid)
        if cand is None or pid in chosen:
            continue
        if pid in banned_set:
            continue  # disclosed below as banned
        selected.append(
            _annotate(
                {
                    "capability_id": pid,
                    "producing_rule": cand.get("rule_id") or "PIN",
                    "reason": (
                        f"pinned by owner override; PIN beats threshold "
                        f"(fusion_score {cand['fusion_score']:.2f} vs min_score {min_score:.2f}) "
                        f"and is charged first ({cand['token_cost']} tokens)"
                    ),
                    "score": cand["fusion_score"],
                    "token_cost": cand["token_cost"],
                    "precedence": "PIN",
                }
            )
        )
        spent += cand["token_cost"]
        chosen.add(pid)

    # Step 3: rank the rest by fusion_score (stable on candidate order).
    ranked = sorted(
        [c for c in candidates if c["capability_id"] not in chosen],
        key=lambda c: -c["fusion_score"],
    )
    for cand in ranked:
        cid = cand["capability_id"]
        score = cand["fusion_score"]
        cost = cand["token_cost"]
        if cid in banned_set:
            near_misses.append(
                _annotate(
                    {
                        "capability_id": cid,
                        "score": score,
                        "token_cost": cost,
                        "rule_id": cand.get("rule_id"),
                        "cutoff_reason": (
                            f"banned-by-owner-override: fusion_score {score:.2f} would have "
                            f"qualified (min_score {min_score:.2f}) but BAN beats every fusion score"
                        ),
                    }
                )
            )
            continue
        if score < min_score:
            if score >= (min_score - margin):
                near_misses.append(
                    _annotate(
                        {
                            "capability_id": cid,
                            "score": score,
                            "token_cost": cost,
                            "rule_id": cand.get("rule_id"),
                            "cutoff_reason": (
                                f"below-threshold: fusion_score {score:.2f} < min_score "
                                f"{min_score:.2f} (within near_miss_margin {margin:.2f})"
                            ),
                        }
                    )
                )
            continue
        remaining = budget - spent
        if cost > remaining:
            near_misses.append(
                _annotate(
                    {
                        "capability_id": cid,
                        "score": score,
                        "token_cost": cost,
                        "rule_id": cand.get("rule_id"),
                        "cutoff_reason": (
                            f"over-budget: fusion_score {score:.2f} >= min_score {min_score:.2f} "
                            f"but token_cost {cost} > remaining budget {remaining} of {budget}"
                        ),
                    }
                )
            )
            continue
        selected.append(
            _annotate(
                {
                    "capability_id": cid,
                    "producing_rule": cand.get("rule_id") or "SCORE",
                    "reason": (
                        f"fusion_score {score:.2f} >= min_score {min_score:.2f}; "
                        f"token_cost {cost} fits remaining budget {remaining}"
                    ),
                    "score": score,
                    "token_cost": cost,
                    "precedence": "SCORE",
                }
            )
        )
        spent += cost
        chosen.add(cid)

    return {
        "query_id": trace.get("query_id"),
        "query": trace.get("query"),
        "procedure": list(PROCEDURE),
        "inputs": {
            "min_score": min_score,
            "budget_tokens": budget,
            "near_miss_margin": margin,
            "overrides": {"banned": banned, "pinned": pinned},
        },
        "candidates": candidates,
        "selected": selected,
        "near_misses": near_misses,
        "budget_tokens": budget,
        "spent": spent,
    }


def reconstruct_selected(expl: dict[str, Any]) -> list[str]:
    """The decision, read from the explanation only: selected ids in order."""
    return [
        str(row.get("capability_id") or "")
        for row in (expl.get("selected") or [])
        if isinstance(row, dict) and row.get("capability_id")
    ]


def discloses_near_misses(expl: dict[str, Any], required: Iterable[str]) -> tuple[bool, str]:
    """Does the explanation name every required near-miss with a cutoff_reason?

    Returns ``(ok, why)``.  Fails when a required id is absent from
    ``near_misses``, when a disclosed near-miss lacks ``cutoff_reason``, or when
    a near-miss names a capability the record's ``candidates`` do not carry.
    """
    need = {str(x) for x in required}
    rows = [r for r in (expl.get("near_misses") or []) if isinstance(r, dict)]
    disclosed: dict[str, dict[str, Any]] = {}
    for row in rows:
        cid = str(row.get("capability_id") or "")
        if not cid:
            return False, "near-miss row without capability_id"
        if not str(row.get("cutoff_reason") or "").strip():
            return False, f"near-miss {cid} has no cutoff_reason"
        disclosed[cid] = row
    cand_ids = {
        str(c.get("capability_id"))
        for c in (expl.get("candidates") or [])
        if isinstance(c, dict) and c.get("capability_id")
    }
    if cand_ids:
        stray = sorted(set(disclosed) - cand_ids)
        if stray:
            return False, f"near-miss not among candidates: {stray}"
    missing = sorted(need - set(disclosed))
    if missing:
        return False, f"near-misses omitted: {missing}"
    selected = set(reconstruct_selected(expl))
    overlap = sorted(selected & set(disclosed))
    if overlap:
        return False, f"ids both selected and near-miss: {overlap}"
    return True, "all required near-misses disclosed with cutoff_reason"
