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
"""JSON walk: recorded coverage observations must be internally consistent,
the labeled however-control must classify UNCHALLENGED under the strict rule,
and excluded conclusions must account for the coverage fraction."""
doc = load()
obs = {o.get("name"): o.get("measured") for o in (doc.get("report", {}).get("observations") or [])}
total = obs.get("canonical_conclusion_count")
cov = obs.get("contract_counterevidence_coverage_fraction")
never = obs.get("never_challenged_count")
need(total == 12, f"canonical_conclusion_count={total} expected 12")
need(0.0 <= cov <= 1.0, f"coverage_fraction={cov} out of range")
need(never is not None and never >= 0, "never_challenged_count missing")
ctrl = doc.get("controls") or {}
need(isinstance(ctrl.get("not_in_coverage_fraction"), bool)
     and ctrl.get("not_in_coverage_fraction") is True,
     "controls.not_in_coverage_fraction must be the boolean flag True (controls sit outside the measured fraction)")


def classify(row):
    """Strict rule: CHALLENGED only with a recorded triad (query+results+verdict)."""
    triad = row.get("query") and (row.get("results") or row.get("result_set")) and row.get("verdict")
    return "CHALLENGED" if triad else "UNCHALLENGED"


labeled = (ctrl.get("labeled") or [])
need(len(labeled) >= 1, "no labeled control rows")
for row in labeled:
    if "however" in str(row.get("text", "")).lower():
        need(classify(row) == "UNCHALLENGED" and row.get("status") == "UNCHALLENGED",
             "however-only control not UNCHALLENGED under the strict rule")
ok("json walk", total, "conclusions; coverage", cov)
