#!/usr/bin/env python3
"""@DOC
Shard 20 wave-2 resume (builder): live named probe. Exit 0 = green.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "RES-0193"
OUT = (REPO / "command-center/research/deep-research-design/RES-0193-tokens-per-verified-claim-efficiency.json").resolve()


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
"""Falsification work is exempt: a refutation-only run (zero new claims) must
NOT be scored infinitely inefficient; the metric definition excludes it."""
doc = load()
metric = doc.get("metric") or {}
need("falsification" in str(metric.get("numerator", "")).lower()
     or metric.get("zero_verified_falsification_only") is not None,
     "metric definition does not exempt falsification work")
rows = doc.get("per_mode_efficiency") or []
for r in rows:
    e = r.get("efficiency") or {}
    if e.get("falsification_claims", 0) > 0 and e.get("independently_verified_new_claims", 0) == 0:
        need(e.get("status") == "EXEMPT" or e.get("infinite") is not True,
             f"{r.get('mode', r.get('id'))}: falsification-only run scored infinite")
gate = doc.get("default_set_gate") or {}
need(gate.get("remain_in_default_set"), "default set empty")
need(len(gate.get("remain_in_default_set") or []) + len(gate.get("below_default_set_threshold") or [])
     >= len(rows) - 2, "default-set accounting loses modes")
need(doc.get("cloud_ok") is False, "cloud_ok must stay False (no cloud debt claimed)")
ok("falsification exempt; default set",
   len(gate.get("remain_in_default_set") or []), "modes remain")
