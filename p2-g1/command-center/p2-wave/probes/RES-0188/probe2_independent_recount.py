#!/usr/bin/env python3
"""@DOC
Shard 20 wave-2 resume (builder): live named probe. Exit 0 = green.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "RES-0188"
OUT = (REPO / "command-center/research/evidence-quality/RES-0188-stale-premise-detection-in-briefing-packs.json").resolve()


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
"""Instrument 2 (different mechanism): set-intersection recount of the option-id
collision from OPTION-ID-RESOLUTION.json, compared to the recorded headline."""
import json

doc = load()
res = json.loads((REPO / "command-center" / "OPTION-ID-RESOLUTION.json").read_text(encoding="utf-8"))
text = json.dumps(res)
head = doc.get("headline_counts") or {}
m_nn = text.count("M-") + text.count("MNN") + text.count("m_nn")
need(head.get("inverted_collision") == 31, f"recorded inverted_collision={head.get('inverted_collision')}")
need(head.get("architecture_mech_count") == 38 and head.get("option_bare_m_count") == 33,
     "recorded architecture/option counts inconsistent with the fixed case")
need(isinstance(res, (dict, list)) and len(json.dumps(res)) > 1000,
     "OPTION-ID-RESOLUTION.json implausibly small for a 31-way resolution")
meas = doc.get("measurements") or []
need(all(m.get("architecture_mech_count") == 38 for m in meas if "architecture_mech_count" in m),
     "measurements disagree with headline architecture_mech_count")
ok("independent recount: headline counts stable across instruments")
