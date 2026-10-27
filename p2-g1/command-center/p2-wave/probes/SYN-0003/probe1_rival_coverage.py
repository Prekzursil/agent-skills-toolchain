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
"""Coverage walk: every cause node maps to exactly one rival record or an
explicit SINGLE-HYPOTHESIS label; recorded coverage counts must reproduce."""
import re

doc = load()
records = doc.get("records") or []
cov = doc.get("coverage") or {}
cause_ids = [r.get("cause_id") for r in records]
need(len(cause_ids) == len(set(cause_ids)), "duplicate cause records")
need(cov.get("cause_count") == len(cause_ids), "coverage.cause_count != records")
labeled = [r for r in records if str(r.get("label", "")).upper() == "SINGLE-HYPOTHESIS"]
rivals = [r for r in records if str(r.get("label", "")).upper() == "RIVAL"]
need(len(labeled) + len(rivals) == len(records), "records with unknown label")
need(cov.get("rival_count") == len(rivals), "coverage.rival_count != recomputed")
need(cov.get("single_hypothesis_count") == len(labeled), "single_hypothesis_count != recomputed")
need(not cov.get("missing_cause_ids") and not cov.get("duplicate_cause_ids")
     and not cov.get("unlabelled_cause_ids") and not cov.get("extra_cause_ids"),
     "coverage lists stray causes")
need(cov.get("ok") is True, "coverage.ok not true")
need(doc.get("hierarchy_source", {}).get("cause_count") in (None, cov.get("cause_count")),
     "hierarchy source count disagrees")
ok("rival coverage:", len(records), "records =",
   len(rivals), "rivals +", len(labeled), "single-hypothesis")
