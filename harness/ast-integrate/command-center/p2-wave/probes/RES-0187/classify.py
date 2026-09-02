"""Challenge classifier for RES-0187.

A conclusion is CHALLENGED only when a recorded disconfirming search exists
as a structured triple: query (non-empty string) + result_set (a list, empty
allowed) + verdict (non-empty string).

Hedging phrases in prose — including the word "however" — are not a challenge.
That is the use-versus-mention trap: mentioning a caveat is not running a
disconfirming search. Caveat fields (strongest_caveat, strongest_surviving_
counterargument) are not challenge records.

Supporting evidence (source_lineage, signals, settling_probe, contradiction
id-lists) is not a disconfirming search.
"""
from __future__ import annotations

import json
import re
from typing import Any

CHALLENGED = "CHALLENGED"
UNCHALLENGED = "UNCHALLENGED"

RECORD_KEYS = (
    "counterevidence_search",
    "disconfirming_search",
    "challenge_record",
    "recorded_challenge",
    "counterevidence_hunt",
)

HEDGE_RE = re.compile(
    r"\b(however|although|nevertheless|nonetheless|albeit|notwithstanding)\b",
    re.I,
)
QUERY_KEYS = ("query", "recorded_query", "search_query")
RESULT_KEYS = ("result_set", "results", "resultset")
VERDICT_KEYS = ("verdict", "challenge_verdict", "hunt_verdict")

# Fields that look like disagreement but are not recorded searches.
NOT_A_SEARCH = frozenset(
    {
        "source_lineage",
        "signals",
        "settling_probe",
        "named_settling_probe",
        "contradiction",
        "contradiction_edges",
        "support",
        "support_edges",
        "strongest_caveat",
        "strongest_surviving_counterargument",
        "caveat",
        "hedge",
    }
)


def _first_str(obj: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _first_list(obj: dict, keys: tuple[str, ...]) -> list | None:
    for key in keys:
        val = obj.get(key)
        if isinstance(val, list):
            return val
    return None


def as_challenge_record(obj: Any) -> dict | None:
    """Return the triple dict if obj is a recorded search; else None."""
    if not isinstance(obj, dict):
        return None
    query = _first_str(obj, QUERY_KEYS)
    results = _first_list(obj, RESULT_KEYS)
    verdict = _first_str(obj, VERDICT_KEYS)
    if query is None or results is None or verdict is None:
        return None
    return {
        "query": query,
        "result_set": results,
        "verdict": verdict,
        "result_set_n": len(results),
    }


def extract_record(conclusion: dict) -> tuple[dict | None, str | None]:
    if not isinstance(conclusion, dict):
        return None, None
    for key in RECORD_KEYS:
        rec = as_challenge_record(conclusion.get(key))
        if rec is not None:
            return rec, key
    ext = conclusion.get("extension_points")
    if isinstance(ext, dict):
        for key in RECORD_KEYS:
            rec = as_challenge_record(ext.get(key))
            if rec is not None:
                return rec, f"extension_points.{key}"
    return None, None


def classify(conclusion: dict) -> dict:
    rec, found_at = extract_record(conclusion)
    if rec is None:
        blob = json.dumps(conclusion, sort_keys=True) if isinstance(conclusion, dict) else ""
        hedge = bool(HEDGE_RE.search(blob))
        return {
            "status": UNCHALLENGED,
            "reason": (
                "hedge-mention-only"
                if hedge
                else "no-recorded-query-result_set-verdict-triple"
            ),
            "hedge_mention": hedge,
            "record": None,
            "found_at": None,
        }
    return {
        "status": CHALLENGED,
        "reason": "recorded-query-result_set-verdict",
        "hedge_mention": False,
        "record": rec,
        "found_at": found_at,
    }


def mention_trap_classify(conclusion: dict) -> dict:
    """Broken detector: treats a hedge word as if a search had been run."""
    blob = json.dumps(conclusion, sort_keys=True) if isinstance(conclusion, dict) else ""
    if HEDGE_RE.search(blob):
        return {
            "status": CHALLENGED,
            "reason": "mention-trap-hedge-word",
            "hedge_mention": True,
            "record": None,
            "found_at": None,
        }
    return classify(conclusion)
