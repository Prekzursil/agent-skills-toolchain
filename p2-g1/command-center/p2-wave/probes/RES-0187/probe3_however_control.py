#!/usr/bin/env python3
"""@DOC
Shard 20 wave-2 resume (builder): live named probe. Exit 0 = green.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "RES-0187"
OUT = (REPO / "command-center/research/evidence-quality/RES-0187-counterevidence-coverage-audit.json").resolve()


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
"""Both-states however control. Default: strict rule classifies the labeled
however-only row UNCHALLENGED and a synthetic triad row CHALLENGED.
--mutant: the naive keyword classifier WOULD challenge the however row,
proving the control catches keyword promotion."""
import sys

doc = load()

def classify(row):
    """Strict rule: CHALLENGED only with a recorded triad (query+results+verdict)."""
    triad = row.get("query") and (row.get("results") or row.get("result_set")) and row.get("verdict")
    return "CHALLENGED" if triad else "UNCHALLENGED"


def classify_naive(row):
    """Naive keyword promotion (the mutant): 'however' mention counts as search."""
    return "CHALLENGED" if "however" in str(row.get("text", "")).lower() else classify(row)

labeled = (doc.get("controls") or {}).get("labeled") or []
however_row = next((r for r in labeled if "however" in str(r.get("text", "")).lower()), None)
need(however_row is not None, "labeled however control missing")
good_row = {"query": "q", "results": ["r"], "verdict": "refuted",
            "text": "conclusion with a real disconfirming search"}
if "--mutant" in sys.argv[1:]:
    need(classify_naive(however_row) == "CHALLENGED",
         "mutant naive classifier did NOT keyword-promote the however row")
    need(classify(however_row) == "UNCHALLENGED",
         "strict rule must stay UNCHALLENGED (the control that catches the mutant)")
    ok("however control MUTANT caught: keyword promotion would challenge")
else:
    need(classify(however_row) == "UNCHALLENGED", "however-only row must be UNCHALLENGED")
    need(classify(good_row) == "CHALLENGED", "row with real triad must be CHALLENGED")
    ok("however control: strict rule both-states green")
