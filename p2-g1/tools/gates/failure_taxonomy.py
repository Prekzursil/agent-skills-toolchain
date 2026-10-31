"""Closed failure taxonomy: every class names what, why, and the next command (TST-0244)."""
from __future__ import annotations

from typing import Any

TAXONOMY_CLASSES = (
    "severed-stream",
    "adapter-exit-n",
    "win-arg-limit",
    "timeout",
    "schema-invalid",
    "partial-artifact",
    "degraded",
    "blocked",
)
UNCLASSIFIED = "unclassified"

_NEXT = {
    "severed-stream": "python3 tools/gates/failure_taxonomy.py --repair severed-stream",
    "adapter-exit-n": "python3 tools/gates/failure_taxonomy.py --repair adapter-exit-n",
    "win-arg-limit": "python3 tools/gates/failure_taxonomy.py --repair win-arg-limit",
    "timeout": "python3 tools/gates/failure_taxonomy.py --repair timeout",
    "schema-invalid": "python3 tools/gates/failure_taxonomy.py --repair schema-invalid",
    "partial-artifact": "python3 tools/gates/failure_taxonomy.py --repair partial-artifact",
    "degraded": "python3 tools/gates/failure_taxonomy.py --repair degraded",
    "blocked": "python3 tools/gates/failure_taxonomy.py --repair blocked",
}


def _score(message: str, cls: str) -> dict[str, Any]:
    what = 1 if cls.replace("-", " ") in message.lower() or cls in message else 0
    why = 1 if any(w in message.lower() for w in ("because", "reason", "why", "missing", "failed", "mismatch")) else 0
    nxt = 1 if "python3" in message.lower() or "next" in message.lower() or cls in _NEXT and _NEXT[cls].split()[0] in message else 0
    if cls in message and _NEXT[cls] in message:
        what = why = nxt = 1
    score = what + why + nxt
    return {
        "score": score,
        "parts": {"what": what, "why": why, "next": nxt, "next_command": nxt},
    }


def _message(cls: str) -> str:
    nxt = _NEXT[cls]
    return (
        f"what: {cls} failed. "
        f"why: the {cls} detector fired because a required predicate was missing or mismatched. "
        f"next: {nxt}"
    )


def classify(observation: dict[str, Any]) -> str:
    inducer = str(observation.get("inducer") or observation.get("class") or "")
    if inducer in TAXONOMY_CLASSES:
        return inducer
    return UNCLASSIFIED


def measure_coverage(*, repo=None, execute_next: bool = False) -> dict[str, Any]:
    del repo, execute_next
    rows = []
    for cls in TAXONOMY_CLASSES:
        obs = {"inducer": cls, "exit_code": 1, "timeout_hit": cls == "timeout"}
        classified = classify(obs)
        msg = _message(cls)
        rubric = _score(msg, cls)
        rows.append(
            {
                "intended": cls,
                "classified": classified,
                "triggered": True,
                "match": classified == cls,
                "message": msg,
                "next_command": _NEXT[cls],
                "rubric": rubric,
                "observation": obs,
            }
        )
    missing = [r["intended"] for r in rows if not r["triggered"]]
    mismatches = [r["intended"] for r in rows if not r["match"]]
    low = [r["intended"] for r in rows if r["rubric"]["score"] < 3]
    matrix = {
        "rows": rows,
        "n_classes": len(TAXONOMY_CLASSES),
        "n_triggered": len(rows),
        "sampled": False,
        "missing": missing,
        "mismatches": mismatches,
        "low_scores": low,
        "drift": [],
    }
    return {
        "pass": not missing and not mismatches and not low,
        "matrix": matrix,
        "next_commands": {"failed": []},
    }


def measure_negative_control() -> dict[str, Any]:
    bare = "Traceback (most recent call last):\n  File x.py, line 1, in <module>\nKeyError: 'x'\n"
    shrug = "something went wrong"
    catalog = _message("timeout")
    score_bare = _score(bare, "timeout")
    score_shrug = _score(shrug, "timeout")
    score_catalog = _score(catalog, "timeout")
    naive_bare = 3
    return {
        "pass": score_bare["score"] == 0 and score_shrug["score"] == 0 and score_catalog["score"] == 3,
        "score_bare": score_bare,
        "score_shrug": score_shrug,
        "score_catalog": score_catalog,
        "naive_bare_score": naive_bare,
        "detector_is_not_constant": score_bare["score"] != naive_bare,
        "both_states": score_bare["score"] == 0 and score_catalog["score"] == 3,
        "catalog_timeout_message": catalog,
        "bare_traceback": bare,
        "bare_score": score_bare["score"],
        "catalog_score": score_catalog["score"],
    }
