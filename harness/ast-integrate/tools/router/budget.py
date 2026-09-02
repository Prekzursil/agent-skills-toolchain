"""Token-ceiling admission for capability injection (IMP-0392 / IMP-0394).

Two admission paths share one ceiling:

* :func:`select_by_score_only` is the *control* path: rank candidates by router
  score and fill the ceiling greedily. It knows nothing about owner or project
  overrides, so a low-scoring pinned capability is dropped once higher scores
  have used the budget. IMP-0394 runs this next to the override-aware path to
  show the ceiling is really enforced (a pin surviving is only evidence if the
  score-only fill would have cut it).
* :func:`enforce_injection_ceiling` is the override-aware path: pinned ids are
  admitted first and charged against the ceiling, the remainder is filled by
  score. Bans are the caller's business (``tools/router/overrides.py`` strips
  them before calling here).

Every decision lists the excluded candidates with a typed reason so a receipt
can show *why* something was cut rather than only what survived.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Sequence

POLICY_SCORE_ONLY = "score-only"
POLICY_PIN_AWARE = "pin-aware"
REASON_BUDGET = "budget-exhausted"
REASON_OVERSIZED = "exceeds-ceiling-alone"


class BudgetError(ValueError):
    """A candidate row or ceiling is malformed."""


@dataclass(frozen=True)
class Candidate:
    """Normalised view of one candidate row."""

    capability_id: str
    score: float
    token_cost: int
    position: int

    @classmethod
    def from_row(cls, row: Any, position: int) -> "Candidate":
        if not isinstance(row, dict):
            raise BudgetError(
                f"candidate #{position} is not a mapping: {type(row).__name__}"
            )
        cid = str(row.get("capability_id") or row.get("id") or "").strip()
        if not cid:
            raise BudgetError(f"candidate #{position} has no capability_id")
        try:
            score = float(row.get("score", 0.0) or 0.0)
        except (TypeError, ValueError) as exc:
            raise BudgetError(f"candidate {cid!r} has a non-numeric score") from exc
        raw_cost = row.get("token_cost", row.get("cost", 0))
        try:
            cost = int(raw_cost or 0)
        except (TypeError, ValueError) as exc:
            raise BudgetError(
                f"candidate {cid!r} has a non-integer token_cost"
            ) from exc
        if cost < 0:
            raise BudgetError(f"candidate {cid!r} has negative token_cost {cost}")
        return cls(capability_id=cid, score=score, token_cost=cost, position=position)


@dataclass
class BudgetDecision:
    """Outcome of one ceiling fill."""

    policy: str
    ceiling: int
    admitted_ids: list[str] = field(default_factory=list)
    pinned_ids: list[str] = field(default_factory=list)
    excluded: list[dict[str, Any]] = field(default_factory=list)
    used_tokens: int = 0

    @property
    def remaining_tokens(self) -> int:
        return self.ceiling - self.used_tokens

    def as_dict(self) -> dict[str, Any]:
        doc = asdict(self)
        doc["remaining_tokens"] = self.remaining_tokens
        doc["admitted_count"] = len(self.admitted_ids)
        doc["excluded_count"] = len(self.excluded)
        return doc


def _normalise_ceiling(ceiling: Any) -> int:
    try:
        value = int(ceiling)
    except (TypeError, ValueError) as exc:
        raise BudgetError(
            f"ceiling must be an integer token count, got {ceiling!r}"
        ) from exc
    if value < 0:
        raise BudgetError(f"ceiling must be >= 0, got {value}")
    return value


def _normalise(candidates: Iterable[Any]) -> list[Candidate]:
    rows = [Candidate.from_row(row, i) for i, row in enumerate(candidates)]
    seen: set[str] = set()
    for cand in rows:
        if cand.capability_id in seen:
            raise BudgetError(
                f"duplicate capability_id {cand.capability_id!r} in candidates"
            )
        seen.add(cand.capability_id)
    return rows


def rank_by_score(candidates: Sequence[Candidate]) -> list[Candidate]:
    """Highest score first; ties keep the caller's order (stable)."""
    return sorted(candidates, key=lambda c: (-c.score, c.position))


def _fill(decision: BudgetDecision, ordered: Sequence[Candidate], used: int) -> int:
    for cand in ordered:
        if cand.token_cost > decision.ceiling:
            decision.excluded.append(
                {
                    "capability_id": cand.capability_id,
                    "score": cand.score,
                    "token_cost": cand.token_cost,
                    "layer": "router.score",
                    "reason": REASON_OVERSIZED,
                }
            )
            continue
        if used + cand.token_cost > decision.ceiling:
            decision.excluded.append(
                {
                    "capability_id": cand.capability_id,
                    "score": cand.score,
                    "token_cost": cand.token_cost,
                    "layer": "router.score",
                    "reason": REASON_BUDGET,
                    "remaining_tokens": decision.ceiling - used,
                }
            )
            continue
        decision.admitted_ids.append(cand.capability_id)
        used += cand.token_cost
    return used


def select_by_score_only(candidates: Iterable[Any], ceiling: int) -> dict[str, Any]:
    """Greedy score-descending fill of ``ceiling`` tokens; no overrides consulted.

    ``candidates`` rows carry ``capability_id`` (or ``id``), ``score`` and
    ``token_cost``. Returns a plain dict (see :class:`BudgetDecision.as_dict`)
    whose ``admitted_ids`` preserve admission order.
    """
    limit = _normalise_ceiling(ceiling)
    rows = _normalise(candidates)
    decision = BudgetDecision(policy=POLICY_SCORE_ONLY, ceiling=limit)
    decision.used_tokens = _fill(decision, rank_by_score(rows), 0)
    return decision.as_dict()


def enforce_injection_ceiling(
    candidates: Iterable[Any], ceiling: int, pinned_ids: Iterable[str] = ()
) -> dict[str, Any]:
    """Pin-aware fill: pinned ids are admitted first and charged to the ceiling.

    A pin whose own cost exceeds the whole ceiling cannot be honoured; it is
    reported under ``excluded`` with ``reason=exceeds-ceiling-alone`` instead of
    being silently dropped. Remaining budget is filled by score.
    """
    limit = _normalise_ceiling(ceiling)
    rows = _normalise(candidates)
    pins = [str(p) for p in pinned_ids]
    pin_set = set(pins)
    decision = BudgetDecision(policy=POLICY_PIN_AWARE, ceiling=limit)
    used = 0
    by_id = {c.capability_id: c for c in rows}
    for pid in pins:
        cand = by_id.get(pid)
        if cand is None:
            decision.excluded.append(
                {
                    "capability_id": pid,
                    "layer": "owner.pin",
                    "reason": "pin-not-a-candidate",
                }
            )
            continue
        if used + cand.token_cost > limit:
            decision.excluded.append(
                {
                    "capability_id": pid,
                    "score": cand.score,
                    "token_cost": cand.token_cost,
                    "layer": "owner.pin",
                    "reason": REASON_OVERSIZED,
                    "remaining_tokens": limit - used,
                }
            )
            continue
        decision.admitted_ids.append(pid)
        decision.pinned_ids.append(pid)
        used += cand.token_cost
    rest = [c for c in rows if c.capability_id not in pin_set]
    decision.used_tokens = _fill(decision, rank_by_score(rest), used)
    return decision.as_dict()


__all__ = [
    "BudgetDecision",
    "BudgetError",
    "Candidate",
    "POLICY_PIN_AWARE",
    "POLICY_SCORE_ONLY",
    "REASON_BUDGET",
    "REASON_OVERSIZED",
    "enforce_injection_ceiling",
    "rank_by_score",
    "select_by_score_only",
]
