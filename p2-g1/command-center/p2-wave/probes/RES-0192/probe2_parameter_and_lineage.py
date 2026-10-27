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
"""Lineage + parameters: recorded runs, harvest rails, and the weighted-score
formula must match the factors as written."""
import json

doc = load()
rule = doc.get("decision_rule") or {}
need(rule.get("weighted_score") == "(2-reversibility)+blast+density+contradiction",
     "weighted_score formula text changed")
need(sorted(rule.get("factors") or []) == ["blast", "contradiction", "density", "reversibility"],
     "factor list drifted")
need(sorted(rule.get("hard_gates") or []) == ["high-contradiction-and-dense-literature",
                                              "irreversible-and-high-blast"],
     "hard gates drifted")
meas = doc.get("measurements") or {}
need(meas.get("fingerprints_differ") is True, "rapid/systematic fingerprints identical")
runs = doc.get("recorded_runs") or {}
qs = runs.get("questions") or {}
need(len(qs) == 3, f"recorded runs n={len(qs)}")
harv = doc.get("harvest") or {}
need(isinstance(harv.get("n_rails"), int) and harv.get("n_rails") >= 1,
     "harvest rails not recorded")
pp = doc.get("protocol_parameters") or {}
need("rapid" in pp and "systematic" in pp, "protocol parameters missing")
ok("parameters + lineage recorded:", len(qs), "runs,", harv.get("n_rails"), "rails")
