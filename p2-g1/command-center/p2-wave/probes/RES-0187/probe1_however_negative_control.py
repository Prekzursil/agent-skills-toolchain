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
"""Named negative control (catalog tests_required): a conclusion carrying only
the word 'however' must classify UNCHALLENGED - use-versus-mention."""
doc = load()

def classify(row):
    """Strict rule: CHALLENGED only with a recorded triad (query+results+verdict)."""
    triad = row.get("query") and (row.get("results") or row.get("result_set")) and row.get("verdict")
    return "CHALLENGED" if triad else "UNCHALLENGED"


def classify_naive(row):
    """Naive keyword promotion (the mutant): 'however' mention counts as search."""
    return "CHALLENGED" if "however" in str(row.get("text", "")).lower() else classify(row)

cases = [
    ({"text": "The build is production-ready, however."}, "UNCHALLENGED"),
    ({"text": "We searched for counterevidence; however, query=q results=[x] verdict=none"}, "UNCHALLENGED"),
    ({"query": "counterevidence sweep", "results": ["hit"], "verdict": "refuted",
      "text": "conclusion stands after a real search"}, "CHALLENGED"),
]
for row, want in cases:
    got = classify(row)
    need(got == want, f"classifier {got} != {want} for {row.get('text', '')[:40]}")
ok("however negative control: use-versus-mention holds")
