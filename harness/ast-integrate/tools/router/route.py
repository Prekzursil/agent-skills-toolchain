"""Query router used by `ast route`. IMP-0403.

``route_query`` is the single router entrypoint the CLI documents.  It never
injects: capability bodies are stripped before scoring, the result carries
``injection_performed=False`` / ``injected=[]`` / ``session_started=False``,
and every verdict is terminal (``SELECTED`` or ``NO-CAPABILITY-FITS``).

The result also carries an ``explanation`` an owner can read without
re-running the router: which capability was selected and why, and which
candidates were near-misses (runners-up on a SELECTED verdict; the closest
rejected candidates on a no-fit verdict), each with a ``cutoff_reason``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from router.nofit import (
    FIT_THRESHOLD,
    VERDICT_NOFIT,
    VERDICT_SELECTED,
    load_index,
    route as nofit_route,
)

__all__ = ["PROCEDURE", "route_query"]

PROCEDURE: tuple[str, ...] = (
    "1. Capability bodies are stripped before scoring; only id, description and "
    "triggers are visible to the router and nothing is injected into a session.",
    "2. Each capability is scored by trigger/description token overlap with the "
    "query; candidates are ranked by score descending.",
    f"3. The best candidate is SELECTED when its score >= FIT_THRESHOLD={FIT_THRESHOLD}; "
    "otherwise the verdict is the terminal NO-CAPABILITY-FITS (a weak match is "
    "never promoted).",
    "4. Near-misses are disclosed with a cutoff_reason: runners-up when a "
    "capability was selected, the closest rejected candidates when none fit.",
)

# Keys of the index rows that may never reach stdout.
_HIDDEN_KEYS = frozenset({"body", "content", "prompt", "instructions"})


def _flatten_triggers(cap: dict[str, Any]) -> list[str]:
    trig = cap.get("triggers")
    words: list[str] = []
    if isinstance(trig, dict):
        for value in trig.values():
            if isinstance(value, list):
                words.extend(str(item) for item in value)
            elif isinstance(value, str):
                words.append(value)
    elif isinstance(trig, list):
        words.extend(str(item) for item in trig)
    return words


def _strip(cap: dict[str, Any]) -> dict[str, Any]:
    row = {k: v for k, v in cap.items() if k not in _HIDDEN_KEYS}
    row["triggers"] = _flatten_triggers(cap)
    return row


def _near_misses(result: dict[str, Any], threshold: float) -> list[dict[str, Any]]:
    """Runners-up (SELECTED) or closest rejected (no fit), with cutoff_reason."""
    ranked = [r for r in (result.get("ranked") or []) if isinstance(r, dict) and r.get("capability_id")]
    verdict = result.get("verdict")
    best_id = result.get("capability_id")
    best = float(result.get("best_score") or result.get("score") or 0.0)
    rows: list[dict[str, Any]] = []
    for r in ranked:
        cid = str(r["capability_id"])
        if verdict == VERDICT_SELECTED and cid == best_id:
            continue
        score = float(r.get("score") or 0.0)
        if verdict == VERDICT_SELECTED:
            if score >= threshold:
                reason = (
                    f"runner-up: score {score:.3f} >= FIT_THRESHOLD={threshold} but below the "
                    f"selected {best_id} ({best:.3f}); one capability is routed per query"
                )
            else:
                reason = f"below-threshold: score {score:.3f} < FIT_THRESHOLD={threshold}"
        else:
            reason = (
                f"below-threshold: score {score:.3f} < FIT_THRESHOLD={threshold}; "
                "a weak match is not promoted"
            )
        rows.append(
            {
                "capability_id": cid,
                "score": score,
                "matched_tokens": list(r.get("matched_tokens") or []),
                "cutoff_reason": reason,
                "reason": reason,
            }
        )
    return rows


def route_query(
    query: str,
    index: str | Path | None = None,
    cwd: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Route ``query`` against the capability index at ``index``.

    Returns a terminal verdict with an explanation.  Never starts a session
    and never injects a capability body.
    """
    if index is None:
        index = kwargs.get("index")
    if cwd is None:
        cwd = kwargs.get("cwd")
    threshold = float(kwargs.get("threshold") or FIT_THRESHOLD)

    caps: list[dict[str, Any]] = []
    index_loaded = False
    if index:
        path = Path(index)
        if path.is_file():
            caps = load_index(path)
            index_loaded = True
    stripped = [_strip(cap) for cap in caps]

    result = nofit_route(query, stripped, threshold)
    verdict = result.get("verdict")
    selected_id = result.get("capability_id") if verdict == VERDICT_SELECTED else None
    selected = [selected_id] if selected_id else []
    near = _near_misses(result, threshold)
    best = float(result.get("best_score") or result.get("score") or 0.0)

    explanation = {
        "verdict": verdict,
        "selected": [
            {
                "capability_id": selected_id,
                "score": best,
                "producing_rule": "SCORE",
                "reason": str(result.get("reason") or ""),
            }
        ]
        if selected_id
        else [],
        "near_misses": near,
        "threshold": threshold,
        "procedure": list(PROCEDURE),
        "reason": str(result.get("reason") or ""),
    }

    result.update(
        {
            "cwd": cwd,
            "index": str(index) if index else None,
            "index_loaded": index_loaded,
            "capability_count": len(stripped),
            "selected": selected,
            "confidence": round(best, 6),
            "near_misses": near,
            "explanation": explanation,
            "injection_performed": False,
            "injected": [],
            "session_started": False,
            "terminal": True,
        }
    )
    if verdict not in (VERDICT_SELECTED, VERDICT_NOFIT):
        result["verdict"] = VERDICT_NOFIT
    for key in _HIDDEN_KEYS:
        result.pop(key, None)
    return result
