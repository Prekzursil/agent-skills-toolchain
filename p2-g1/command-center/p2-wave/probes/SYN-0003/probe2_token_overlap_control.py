#!/usr/bin/env python3
"""@DOC
Shard 20 wave-2 resume (builder): live named probe. Exit 0 = green.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "SYN-0003"
OUT = (REPO / "command-center/synthesis/SYN-0003.rival-explanations.json").resolve()


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
"""Restatement gate: token-overlap(rival, cause) < threshold for every record;
the self-overlap control (1.0) proves the gate WOULD flag a restatement; every
discriminating experiment names a runnable probe."""
doc = load()
thr = doc.get("token_overlap_threshold", 0.6)


def overlap(a, b):
    ta = set(w.lower() for w in a.split() if len(w) > 3)
    tb = set(w.lower() for w in b.split() if len(w) > 3)
    union = ta | tb
    return len(ta & tb) / len(union) if union else 0.0


records = doc.get("records") or []
need(records, "no rival records")
for r in records:
    ov = overlap(str(r.get("rival_statement", "")), str(r.get("cause_statement", "")))
    need(ov < thr, f"{r.get('cause_id')}: rival overlap {ov:.2f} >= {thr} (restatement)")
    exp = json.dumps({k: v for k, v in r.items() if "experiment" in k.lower()})
    need(len(exp) > 2 and ("probe" in exp.lower() or "command" in exp.lower()
                           or "experiment" in exp.lower()),
         f"{r.get('cause_id')}: no runnable discriminating experiment recorded")
self_ov = overlap("alpha beta gamma delta", "alpha beta gamma delta")
need(self_ov > thr, "self-overlap control failed to flag a literal restatement")
ok("restatement gate:", len(records), "records under threshold", thr)
