#!/usr/bin/env python3
"""@DOC
Shard 20 wave-2 resume (builder): live named probe. Exit 0 = green.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "RES-0184"
OUT = (REPO / "command-center/research/evidence-quality/RES-0184-evidence-threshold-by-claim-severity.json").resolve()


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
"""Adversarial re-derivation: re-evaluate every row against its own recorded
bar (two-source / two-class / executable / lineage / Sherman-Kent) without
reading the verdict fields, then diff against the recorded deficits."""
doc = load()
rows = doc.get("rescore", {}).get("rows") or []
need(len(rows) == 20, f"rows n={len(rows)}")


mismatch = []
for r in rows:
    bar = r.get("bar") or {}
    deficits = []
    if r.get("independent_source_count", 0) < (bar.get("min_independent_sources") or 0):
        deficits.append("independent_sources")
    if r.get("source_class_count", 0) < (bar.get("min_source_classes") or 0):
        deficits.append("source_classes")
    if bar.get("executable_mandatory") and not r.get("executable"):
        deficits.append("executable_check")
    if bar.get("lineage_mandatory") and not r.get("lineage"):
        deficits.append("lineage")
    if bar.get("sherman_kent_mandatory") and not r.get("sherman_kent"):
        deficits.append("sherman_kent")
    below = (r.get("meets_bar") is False)
    if bool(deficits) != below:
        mismatch.append((r.get("claim_id"), "below-flag"))
    rec = {d.split()[0] for d in (r.get("deficits") or [])}
    for d in deficits:
        if not any(d in x for x in rec):
            mismatch.append((r.get("claim_id"), d))
    if r.get("meets_bar") is True and deficits:
        mismatch.append((r.get("claim_id"), "meets_bar-true-with-deficits"))
need(not mismatch, f"refuter mismatches: {mismatch[:5]}")
who = doc.get("who_may_lower") or {}
need("owner" in json.dumps(who).lower() and
     "independent" in json.dumps(who).lower(),
     "who_may_lower does not name owner/independent reviewer as the only lowerers")
ok("refuter re-derived", len(rows), "rows, 0 mismatches")
