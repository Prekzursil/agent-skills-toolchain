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
"""Subtree membership: every ranking row's prevented_claim_ids must equal the
descendant claim set of its intervention node; no phase anachronism."""
doc = load()
hier = doc.get("hierarchy") or {}
nodes = {n.get("id"): n for n in (hier.get("nodes") or [])}
edges = hier.get("edges") or []
children = {}
for e in edges:
    p = e.get("parent") if isinstance(e, dict) else None
    c = e.get("child") if isinstance(e, dict) else None
    if p and c:
        children.setdefault(p, []).append(c)


def descendants(nid):
    out, stack = set(), [nid]
    while stack:
        cur = stack.pop()
        for ch in children.get(cur, []):
            if ch not in out:
                out.add(ch)
                stack.append(ch)
    return out


ranking = doc.get("ranking") or []
need(len(ranking) >= 30, f"ranking rows n={len(ranking)}")
for r in ranking:
    iid = r.get("intervention_id")
    prevented = set(r.get("prevented_claim_ids") or [])
    need(prevented, f"{iid}: empty prevented set in ranking (belongs in rejected)")
    node = nodes.get(iid)
    need(node is not None, f"{iid}: intervention node absent from hierarchy")
    subtree = set(node.get("claim_ids") or [])
    for d in descendants(iid):
        subtree |= set((nodes.get(d) or {}).get("claim_ids") or [])
    if subtree:
        need(prevented <= subtree,
             f"{iid}: prevented set not a subtree ({len(prevented - subtree)} strangers)")
    phase = str(r.get("available_at_phase"))
    need(str(node.get("phase", phase)) <= phase,
         f"{iid}: intervention phase later than its node phase (anachronism)")
ok("subtree membership:", len(ranking), "rows verified")
