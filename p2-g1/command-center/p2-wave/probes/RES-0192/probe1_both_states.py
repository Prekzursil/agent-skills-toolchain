#!/usr/bin/env python3
"""@DOC
Shard 20 wave-2 resume (builder): live named probe. Exit 0 = green.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "RES-0192"
OUT = (REPO / "command-center/research/deep-research-design/RES-0192-rapid-versus-systematic-review-protocol.json").resolve()


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
"""Re-apply the decision rule to the 3 questions: live_rule must reproduce,
Q1 must be the rapid-is-complete negative control (0 decision-relevant
misses), and the rule must NOT collapse to always-systematic."""
doc = load()
rule = doc.get("decision_rule") or {}
thr = rule.get("threshold")
need(thr == 6, f"threshold={thr}")


def decide(f):
    score = (2 - f.get("reversibility", 0)) + f.get("blast", 0) + f.get("density", 0) + f.get("contradiction", 0)
    gate1 = f.get("reversibility", 0) == 0 and f.get("blast", 0) >= 2
    gate2 = f.get("contradiction", 0) >= 2 and f.get("density", 0) >= 2
    return "SYSTEMATIC" if (score >= thr or gate1 or gate2) else "RAPID"


qut = doc.get("questions_under_test") or []
need(len(qut) == 3, f"questions n={len(qut)}")
live = {q["id"]: decide(q.get("factors") or {}) for q in qut}
meas = doc.get("measurements") or {}
need(live == (meas.get("live_rule") or {}),
     f"recomputed rule {live} != recorded {meas.get('live_rule')}")
need("RAPID" in live.values(), "rule collapsed to always-systematic")
nc = meas.get("negative_control") or {}
need(nc.get("pass") is True and nc.get("rapid_decision_relevant_misses") == 0,
     "Q1 rapid negative control failed")
need(meas.get("q2_decision_relevant_misses", 0) >= 1,
     "Q2 showed no rapid misses: systematic never earns its cost")
need(meas.get("q3_rapid_also_complete") is True, "Q3 rapid not complete")
ok("both states:", live, "- rapid defensible and systematic needed")
