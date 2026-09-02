"""Live aggregation census and helpers for ADV-0098.

Calls tools/council/vote/ballots.py (IMP-0303). Does not invent production
majority / supermajority / Bayesian engines.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.vote.ballots import (  # noqa: E402
    APPROVAL,
    METHODS,
    PAIRWISE,
    RANKED_CHOICE,
    SCORE,
    Ballot,
    MethodResult,
    approval,
    pairwise_condorcet,
    ranked_choice,
    score,
)

ENGINE_REL = "tools/council/vote/ballots.py"
CATALOG_METHODS = (
    "majority",
    "supermajority",
    "ranked-choice",
    "score",
    "approval",
    "pairwise-condorcet",
    "weighted",
    "bayesian",
)
LIVE_DISPATCH = {
    RANKED_CHOICE: ranked_choice,
    PAIRWISE: pairwise_condorcet,
    SCORE: score,
    APPROVAL: approval,
}
ABSENT_PRODUCTION = ("majority", "supermajority", "bayesian")


def ballot(
    voter_id: str,
    *,
    ranking: Sequence[str] = (),
    scores: dict[str, int] | None = None,
    approved: Iterable[str] = (),
    weight: int = 1,
) -> Ballot:
    return Ballot.from_parts(
        voter_id,
        ranking=ranking,
        scores=scores,
        approved=approved,
        weight=weight,
    )


def run(method: str, ballots: Sequence[Ballot], candidates: Sequence[str]) -> MethodResult:
    return LIVE_DISPATCH[method](ballots, candidates)


def result_dict(res: MethodResult) -> dict[str, Any]:
    return res.to_dict()


def prefers(ranking: Sequence[str], new: str | None, old: str | None) -> bool:
    """True iff `new` is a strict improvement over `old` for this ranking.

    A unique favourite out of a deadlock (old is None) counts. A deadlock
    is never treated as better than a named winner.
    """
    if new == old:
        return False
    if old is None:
        return bool(ranking) and new == ranking[0]
    if new is None:
        return False
    if new not in ranking or old not in ranking:
        return False
    return list(ranking).index(new) < list(ranking).index(old)


def census() -> dict[str, Any]:
    engine = REPO / ENGINE_REL
    text = engine.read_text(encoding="utf-8") if engine.is_file() else ""
    return {
        "engine_path": ENGINE_REL,
        "engine_present": engine.is_file(),
        "production_methods": list(METHODS),
        "catalog_methods": list(CATALOG_METHODS),
        "implemented": {
            "ranked-choice": RANKED_CHOICE in METHODS,
            "pairwise-condorcet": PAIRWISE in METHODS,
            "score": SCORE in METHODS,
            "approval": APPROVAL in METHODS,
            "weighted": "weight" in text and "class Ballot" in text,
            "majority": False,
            "supermajority": False,
            "bayesian": False,
        },
        "absent_production_methods": list(ABSENT_PRODUCTION),
        "tally_py_present": (REPO / "tools/council/vote/tally.py").is_file(),
        "strategic_py_present": (REPO / "tools/council/antifail/strategic.py").is_file(),
    }


def detector_census() -> dict[str, Any]:
    """Does the runtime flag strategic misreporting or no-show?"""
    root = REPO / "tools" / "council"
    hits: list[dict[str, str]] = []
    needles = (
        "strategic vot",
        "strategic_misreport",
        "no-show paradox",
        "noshow_paradox",
        "gibbard",
        "satterthwaite",
    )
    if root.is_dir():
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(REPO).as_posix()
            body = path.read_text(encoding="utf-8").lower()
            matched = [n for n in needles if n in body]
            if matched:
                hits.append({"path": rel, "needles": ",".join(matched)})
    strategic = REPO / "tools/council/antifail/strategic.py"
    return {
        "detector_module_present": strategic.is_file(),
        "content_hits": hits,
        "detects_misreporting": False,
        "detects_noshow": False,
        "reason": (
            "No tools/council/antifail/strategic.py and no council module "
            "implements a strategic-ballot or no-show detector. "
            "antifail/participation.py scores speaking-time dominance, not ballots."
        ),
    }


def independent_irv(
    ballots: Sequence[Ballot], candidates: Sequence[str]
) -> dict[str, Any]:
    """IRV recount that does not call ranked_choice().

    Unique last-place is eliminated. Last-place ties and majority ties are
    reported, never broken by name sort or ballot order.
    """
    remaining = set(str(c) for c in candidates)
    rounds: list[dict[str, Any]] = []
    usable = [b for b in ballots if b.ranking]
    if not usable:
        return {"winner": None, "status": "NO_ORDINAL_BALLOTS", "rounds": []}
    while remaining:
        counts = {c: 0 for c in remaining}
        continuing = 0
        exhausted = 0
        for b in usable:
            choice = next((c for c in b.ranking if c in remaining), None)
            if choice is None:
                exhausted += b.weight
                continue
            counts[choice] += b.weight
            continuing += b.weight
        rounds.append(
            {
                "remaining": sorted(remaining),
                "counts": dict(counts),
                "continuing": continuing,
                "exhausted": exhausted,
            }
        )
        if continuing <= 0:
            return {"winner": None, "status": "IRV_EXHAUSTED", "rounds": rounds}
        majority = sorted(c for c, n in counts.items() if n * 2 > continuing)
        if len(majority) == 1:
            return {
                "winner": majority[0],
                "status": "WINNER",
                "rounds": rounds,
                "totals": counts,
            }
        if len(majority) > 1:
            return {
                "winner": None,
                "status": "IRV_MAJORITY_TIE",
                "tied": majority,
                "rounds": rounds,
            }
        min_n = min(counts.values())
        last = sorted(c for c, n in counts.items() if n == min_n)
        if len(last) == len(remaining):
            return {
                "winner": None,
                "status": "IRV_PERFECT_TIE",
                "tied": last,
                "rounds": rounds,
            }
        if len(last) > 1:
            return {
                "winner": None,
                "status": "IRV_ELIMINATION_TIE",
                "tied": last,
                "rounds": rounds,
            }
        remaining.remove(last[0])
        rounds[-1]["eliminated"] = last[0]
    return {"winner": None, "status": "IRV_NO_REMAINING", "rounds": rounds}


def fingerprint(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


LIVE_DISPATCH = LIVE_DISPATCH
result_dict = result_dict
census = census
detector_census = detector_census
