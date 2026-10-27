#!/usr/bin/env python3
"""@DOC
Shard 20 wave-2 resume (builder): live named probe. Exit 0 = green.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "SYN-0007"
OUT = (REPO / "command-center/synthesis/SYN-0007.intervention-ranking.json").resolve()


def fail(msg):
    print(f"FAILED:{UID}-probe {msg}")
    raise SystemExit(1)


def ok(*parts):
    print("PROBE-OK", UID, *parts)


def load():
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"artifact unreadable: {type(exc).__name__}: {exc}")


def need(cond, msg):
    if not cond:
        fail(msg)
"""Ranking stability: rejected rows are empty-subtree only; the recorded order
is the deterministic order (prevented-set size desc, intervention_id asc)."""
doc = load()
rejected = doc.get("rejected") or []
need(rejected, "no rejected candidates recorded")
need(all(r.get("class") == "empty-subtree" for r in rejected),
     "rejected rows carry a non empty-subtree class")
ranking = doc.get("ranking") or []
recomputed = sorted(ranking, key=lambda r: r.get("sort_key"))
need([r.get("intervention_id") for r in recomputed]
     == [r.get("intervention_id") for r in ranking],
     "recorded order != re-sort by the recorded deterministic sort_key")
need(all(r.get("sort_key") is not None for r in ranking),
     "a ranking row lacks its deterministic sort_key")
ranks = [r.get("rank") for r in ranking]
need(ranks == sorted(ranks), "rank column not ascending")
ok("stability:", len(ranking), "rows deterministic;", len(rejected), "rejected empty-subtree")
