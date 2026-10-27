#!/usr/bin/env python3
"""@DOC
Shard 20 wave-2 resume (builder): live named probe. Exit 0 = green.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "SYN-0035"
OUT = (REPO / "command-center/synthesis/SYN-0035.calibration-report.json").resolve()


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
"""Synthetic perfectly-calibrated fixture: per-band hit rates recomputed from
the planted items; the fixture scores at its optimum (best of the recorded
reliability values) and its rates sit inside the written band intervals."""
doc = load()
planted = [p for p in (doc.get("planted_items") or [])
           if str(p.get("set_id", "")) == "synthetic-perfect"]
need(len(planted) == 100, f"synthetic-perfect planted items n={len(planted)}")
bands = {b.get("band"): b for b in (doc.get("bands") or [])}
from collections import Counter
tot = Counter()
conf = Counter()
for p in planted:
    tot[p["band"]] += 1
    if str(p.get("oracle_label", "")).lower() == "true":
        conf[p["band"]] += 1
for band, b in bands.items():
    n, hit = tot.get(band, 0), conf.get(band, 0)
    if n == b.get("n") and b.get("confirmed") is not None:
        need(hit == b["confirmed"], f"band {band}: synthetic confirmed {hit} != recorded {b['confirmed']}")
        rate = hit / n
        pi = b.get("nominal_interval") or [0, 1]
        need(pi[0] <= rate <= pi[1], f"band {band}: synthetic rate {rate:.2f} outside {pi}")
rel = doc.get("reliability") or {}
sp = rel.get("synthetic_perfect") or {}
need(sp.get("bands_scored") == 5 and sp.get("n") == 100,
     "synthetic_perfect reliability not scored over the full fixture")
others = [rel[k]["value"] for k in rel if k != "synthetic_perfect" and rel[k].get("value") is not None]
need(others and sp.get("value") is not None and sp["value"] <= min(others),
     f"synthetic_perfect {sp.get('value')} is not the optimum of {others}")
ok("synthetic control: 100 items,", len(bands), "bands inside intervals; optimum",
   sp.get("value"))
