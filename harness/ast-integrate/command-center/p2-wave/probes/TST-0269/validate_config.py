"""Validation-time flag for strategic-abstention-vulnerable council configs.

The runtime must call ``flag_strategic_abstention`` while validating a council spec,
not after a live decision. A configuration is flagged iff the exhaustive small-profile
search finds at least one unique-by-abstention outcome.
"""
from __future__ import annotations

from typing import Any, Callable

from enumerator import search_config
from tally import METHODS, config_key


class StrategicAbstentionError(ValueError):
    """Council spec rejected: abstention can produce an unobtainable-by-ballot outcome."""


def flag_strategic_abstention(
    method: str,
    quorum: Any,
    weights: list[int] | tuple[int, ...],
    *,
    search: Callable[..., list[dict[str, Any]]] = search_config,
) -> dict[str, Any]:
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}")
    w = tuple(int(x) for x in weights)
    hits = search(method, quorum, w)
    key = config_key(method, quorum, w)
    if hits:
        demo = hits[0]
        return {
            "ok": False,
            "flag": "strategic_abstention_vulnerable",
            "config_key": key,
            "n_profiles": len(hits),
            "demonstration": {
                "profile_with_abstention": demo["profile_with_abstention"],
                "outcome_abstain": demo["outcome_abstain"],
                "outcomes_by_ballot": demo["outcomes_by_ballot"],
                "focal": demo["focal"],
            },
            "reason": (
                "Abstention produces an outcome this seat cannot obtain with any ballot; "
                "refuse this (method, quorum, weights) at validation time."
            ),
        }
    return {
        "ok": True,
        "flag": None,
        "config_key": key,
        "n_profiles": 0,
        "demonstration": None,
        "reason": None,
    }


def require_safe_config(method: str, quorum: Any, weights: list[int] | tuple[int, ...]) -> None:
    result = flag_strategic_abstention(method, quorum, weights)
    if not result["ok"]:
        raise StrategicAbstentionError(
            f"{result['flag']}: {result['config_key']} n={result['n_profiles']}"
        )
