#!/usr/bin/env python3
"""@DOC
Shard 20 wave-2 resume (builder): live named probe. Exit 0 = green.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "SYN-0008"
OUT = (REPO / "command-center/synthesis/SYN-0008.candidate-syntheses.json").resolve()


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
"""Partition + schema-before-fan-in: >=3 candidates, >=2 vendors, every evidence
class covered by >=1 agent, zero-agent classes empty, all candidates parsed
against the schema before fan-in."""
doc = load()
cands = (doc.get("report") or {}).get("candidates") or []
need(len(cands) >= 3, f"candidates n={len(cands)}")
vendors = {c.get("vendor") for c in cands}
need(len(vendors) >= 2, f"single-vendor panel: {vendors}")
part = doc.get("partition_coverage") or {}
classes = part.get("evidence_classes") or []
agents = part.get("agents_per_class") or {}
need(classes, "evidence classes not recorded")
for cls in classes:
    need(agents.get(cls), f"evidence class {cls} has zero agents (partition hole)")
need(not part.get("zero_agent_classes"), "zero_agent_classes non-empty")
parsed = doc.get("schema_parsed_before_fan_in") or []
need(len(parsed) >= len(cands), "schema-parse records fewer rows than candidates")
need(all(p.get("parsed") is True and p.get("schema_ok") is True and p.get("counts_as_result") is True
         for p in parsed), "a candidate was not schema-parsed before fan-in")
ok("partition:", len(classes), "classes covered by", len(cands), "candidates across",
   len(vendors), "vendors")
