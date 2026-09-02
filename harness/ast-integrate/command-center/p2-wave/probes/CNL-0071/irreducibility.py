#!/usr/bin/env python3
"""Gate an irreducible-disagreement declaration.

A disagreement that more rounds would still move (positive information
gain) MUST NOT be recorded as irreducible. Fatigue / round-budget stop
without the evidence pack is also rejected.

The check FIRES (rejects the declaration) on the state it is built to
reject. It is SILENT (accepts) only when the evidence pack is complete
and both independent signals agree that gain has collapsed.
"""
from __future__ import annotations

from typing import Any

from fingerprint import attach_moves
from gain import attach_trace, last_defined_gain

IRREDUCIBLE = "irreducible-disagreement"
FATIGUE_STOP = frozenset(
    {
        "round-budget",
        "timeout",
        "fatigue",
        "chair-discretion",
        "majority-tired",
    }
)
ALLOWED_STOP = frozenset(
    {
        "incommensurable-positions",
        "incompatible-evidence-standards",
        "mutually-exclusive-axioms",
    }
)
BANNED_WHY_TOKENS = frozenset(
    {"tired", "fatigue", "out of rounds", "timeout", "budget", "gave up"}
)


def _window(run: dict[str, Any]) -> int:
    w = int(run.get("stable_window") or 2)
    return max(2, w)


def _irreducible_set_ok(run: dict[str, Any]) -> tuple[bool, str]:
    items = run.get("irreducible_set") or []
    if not isinstance(items, list) or len(items) < 2:
        return False, "irreducible-set-too-small"
    named = []
    for item in items:
        if not isinstance(item, dict):
            return False, "irreducible-set-not-objects"
        cid = str(item.get("claim_id") or "").strip()
        other = str(item.get("conflicts_with") or "").strip()
        why = str(item.get("why") or "").strip().lower()
        if not cid or not other or cid == other:
            return False, "irreducible-set-unpaired"
        if not why or any(tok in why for tok in BANNED_WHY_TOKENS):
            return False, "irreducible-set-fatigue-why"
        named.append((cid, other))
    return True, "ok"


def signals_disagree(gain_row: dict[str, Any], move_row: dict[str, Any]) -> bool:
    g = gain_row.get("gain")
    m = move_row.get("moved")
    if g is None or m is None:
        return False
    positive = int(g) > 0
    return positive != bool(m)


def check_declaration(run: dict[str, Any]) -> dict[str, Any]:
    """Return fired=True when the irreducible declaration is rejected."""
    outcome = str(run.get("declared_outcome") or "")
    if outcome != IRREDUCIBLE:
        return {
            "fired": False,
            "silent": True,
            "accepted": False,
            "reason": "not-an-irreducible-declaration",
        }

    rounds = list(run.get("rounds") or [])
    attached = run.get("information_gain_trace")
    if not isinstance(attached, list) or not attached:
        return {
            "fired": True,
            "silent": False,
            "accepted": False,
            "reason": "missing-information-gain-trace",
        }

    computed = attach_trace(rounds)
    moves = attach_moves(rounds)
    if len(computed) != len(attached):
        return {
            "fired": True,
            "silent": False,
            "accepted": False,
            "reason": "trace-length-mismatch",
            "attached_len": len(attached),
            "computed_len": len(computed),
        }

    for a, c, m in zip(attached, computed, moves):
        if c.get("gain") is None:
            continue
        if int(a.get("gain") if a.get("gain") is not None else -1) != int(c["gain"]):
            return {
                "fired": True,
                "silent": False,
                "accepted": False,
                "reason": "forged-or-stale-trace",
                "attached_gain": a.get("gain"),
                "computed_gain": c.get("gain"),
            }
        if signals_disagree(c, m):
            return {
                "fired": True,
                "silent": False,
                "accepted": False,
                "reason": "signal-disagreement",
                "gain": c.get("gain"),
                "moved": m.get("moved"),
            }

    last_gain = last_defined_gain(computed)
    last_move = None
    for row in reversed(moves):
        if row.get("moved") is None:
            continue
        last_move = bool(row["moved"])
        break

    if last_gain is None:
        return {
            "fired": True,
            "silent": False,
            "accepted": False,
            "reason": "trace-too-short",
        }

    if last_gain > 0:
        return {
            "fired": True,
            "silent": False,
            "accepted": False,
            "reason": "positive-gain",
            "last_gain": last_gain,
            "last_moved": last_move,
        }

    window = _window(run)
    defined = [row for row in computed if row.get("gain") is not None]
    defined_m = [row for row in moves if row.get("moved") is not None]
    if len(defined) < window:
        return {
            "fired": True,
            "silent": False,
            "accepted": False,
            "reason": "window-longer-than-trace",
            "window": window,
            "defined_rounds": len(defined),
        }
    tail = defined[-window:]
    tail_m = defined_m[-window:]
    if any(int(r["gain"]) > 0 for r in tail) or any(r.get("moved") for r in tail_m):
        return {
            "fired": True,
            "silent": False,
            "accepted": False,
            "reason": "gain-not-collapsed-in-window",
            "window": window,
            "tail_gains": [r.get("gain") for r in tail],
        }

    stop = str(run.get("stop_reason") or "")
    if stop in FATIGUE_STOP or stop not in ALLOWED_STOP:
        return {
            "fired": True,
            "silent": False,
            "accepted": False,
            "reason": "fatigue-relabel",
            "stop_reason": stop,
        }

    ok, why = _irreducible_set_ok(run)
    if not ok:
        return {
            "fired": True,
            "silent": False,
            "accepted": False,
            "reason": why,
        }

    return {
        "fired": False,
        "silent": True,
        "accepted": True,
        "reason": "irreducible-evidence-complete",
        "last_gain": last_gain,
        "window": window,
    }


def attach_honest_trace(run: dict[str, Any]) -> dict[str, Any]:
    """Copy run and attach a freshly computed trace (does not trust the caller)."""
    out = dict(run)
    out["information_gain_trace"] = attach_trace(list(run.get("rounds") or []))
    return out
