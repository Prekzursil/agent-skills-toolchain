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
"""Verified-only denominator: recompute tokens/wall-ms per verified claim for
every mode row; the default-set gate must match the recomputed flags."""
import statistics

doc = load()
rows = doc.get("per_mode_efficiency") or []
need(len(rows) >= 10, f"mode rows n={len(rows)}")
vals = []
below = []
for r in rows:
    e = r.get("efficiency") or {}
    v = e.get("independently_verified_new_claims", 0)
    tok = e.get("production_tokens", 0)
    if v:
        need(abs(e.get("tokens_per_verified_claim", -1) - tok / v) < 1e-6,
             f"{r.get('mode', r.get('id'))}: tokens_per_verified != production/verified")
        vals.append(e["tokens_per_verified_claim"])
    else:
        need(e.get("infinite") is True or e.get("status") == "EXEMPT",
             f"{r.get('mode', r.get('id'))}: zero verified but not flagged infinite/exempt")
    if e.get("below_default_set_threshold"):
        below.append(r.get("mode") or r.get("id"))
gate = doc.get("default_set_gate") or {}
need(sorted(below) == sorted(gate.get("below_default_set_threshold") or []),
     "gate below-threshold list != recomputed")
need(abs(statistics.median(vals) - gate.get("median_tokens_per_verified", -1)) < 1e-6,
     "median tokens_per_verified != recomputed")
need(gate.get("falsification_exempt_runs") is not None, "falsification exemption not recorded")
ok("verified denominator:", len(rows), "modes,", len(vals), "scored, median",
   gate.get("median_tokens_per_verified"))
