"""Test-owned A4 lexical gateway router (a4-index/v1).

Indexes every installed capability, materializes only the selected set,
refuses activation once the session token budget or max_selected is
exhausted, and returns an explicit NO-CAPABILITY-FITS plus explanation.
This is not tools/router and not an A4 DESIGN rebuild.
"""
from __future__ import annotations

import re
from typing import Any

WORD = re.compile(r"[a-z0-9]+")


def normalize_token(tok: str) -> str:
    t = tok.lower()
    if len(t) > 4 and t.endswith("s"):
        t = t[:-1]
    return t


def tokenize(text: str) -> list[str]:
    out: list[str] = []
    for raw in WORD.findall(text.lower()):
        if len(raw) < 3:
            continue
        out.append(normalize_token(raw))
    return out


def score_cap(task_tokens: set[str], cap: dict[str, Any]) -> tuple[int, list[str]]:
    trig = {normalize_token(str(t)) for t in cap.get("triggers") or [] if str(t)}
    neg = {normalize_token(str(t)) for t in cap.get("negative_scope") or [] if str(t)}
    matched = sorted(task_tokens & trig)
    blocked = task_tokens & neg
    return len(matched) - len(blocked), matched


def route(index: dict[str, Any], text: str) -> dict[str, Any]:
    threshold = int(index.get("match_threshold") or 2)
    ceiling = int(index.get("session_budget_tokens") or 0)
    max_selected = int(index.get("max_selected") or 0)
    task_tokens = set(tokenize(text))
    ranked: list[dict[str, Any]] = []
    for cap in index.get("capabilities") or []:
        if not isinstance(cap, dict) or not cap.get("installed"):
            continue
        score, matched = score_cap(task_tokens, cap)
        ranked.append(
            {
                "id": str(cap["id"]),
                "kind": str(cap.get("kind") or ""),
                "score": int(score),
                "matched_triggers": matched,
                "context_tokens": int(cap.get("context_tokens") or 0),
            }
        )
    ranked.sort(key=lambda r: (-int(r["score"]), str(r["id"])))
    selected: list[dict[str, Any]] = []
    near: list[dict[str, Any]] = []
    used = 0
    refused: list[str] = []
    for row in ranked:
        cid = str(row["id"])
        score = int(row["score"])
        cost = int(row["context_tokens"])
        if score < threshold:
            near.append(
                {
                    "id": cid,
                    "score": score,
                    "reason": "below-threshold",
                    "matched_triggers": list(row["matched_triggers"]),
                    "context_tokens": cost,
                }
            )
            continue
        if max_selected and len(selected) >= max_selected:
            near.append(
                {
                    "id": cid,
                    "score": score,
                    "reason": "max-selected-refuse",
                    "matched_triggers": list(row["matched_triggers"]),
                    "context_tokens": cost,
                }
            )
            refused.append(cid)
            continue
        if ceiling and used + cost > ceiling:
            near.append(
                {
                    "id": cid,
                    "score": score,
                    "reason": "budget-refuse",
                    "matched_triggers": list(row["matched_triggers"]),
                    "context_tokens": cost,
                }
            )
            refused.append(cid)
            continue
        selected.append(
            {
                "id": cid,
                "kind": row["kind"],
                "score": score,
                "matched_triggers": list(row["matched_triggers"]),
                "context_tokens": cost,
            }
        )
        used += cost
    if selected:
        verdict = "SELECTED"
        fallback = None
    else:
        verdict = "NO-CAPABILITY-FITS"
        closest = [n for n in near if n.get("reason") == "below-threshold"]
        closest.sort(key=lambda r: (-int(r["score"]), str(r["id"])))
        fallback = {"closest": closest[:3]}
    return {
        "verdict": verdict,
        "selected": selected,
        "near_misses": near,
        "budget": {
            "ceiling": ceiling,
            "used": used,
            "max_selected": max_selected,
            "refused_ids": refused,
        },
        "fallback": fallback,
        "task_token_count": len(task_tokens),
    }


def selected_ids(result: dict[str, Any]) -> list[str]:
    return [str(row["id"]) for row in result.get("selected") or []]


def reconstruct_selected(explanation: dict[str, Any]) -> list[str]:
    return [str(row["id"]) for row in explanation.get("selected") or []]


def unbounded_select(index: dict[str, Any], text: str) -> dict[str, Any]:
    """Same matcher with ceiling and max_selected disabled (flooding contrast)."""
    clone = dict(index)
    clone["session_budget_tokens"] = 10**9
    clone["max_selected"] = 10**9
    return route(clone, text)
