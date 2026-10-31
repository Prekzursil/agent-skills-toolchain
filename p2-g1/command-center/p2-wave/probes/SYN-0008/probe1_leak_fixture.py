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
"""Leak fixture: a synthesizer requesting a sibling's unpublished output must
be recorded DENIED and logged; the negative control fired on the bad state."""
doc = load()
leak = (doc.get("report") or {}).get("leak_fixture") or {}
need(leak.get("status") == "DENIED", f"leak fixture status={leak.get('status')}")
need(leak.get("logged") is True, "leak attempt not logged")
need(leak.get("requester") and leak.get("target") and leak.get("requester") != leak.get("target"),
     "leak fixture missing requester/target")
wd = leak.get("worker_denial") or {}
need(wd.get("status") == "DENIED", "worker denial not DENIED")
ncs = doc.get("negative_controls") or []
nc = next((n for n in ncs if "leak" in str(n.get("id", "")).lower()), None)
need(nc is not None, "leak negative control missing")
need(nc.get("fired_on_bad_state") is True and nc.get("silent_on_good_state") is True,
     "leak control not both-states green")
ok("leak fixture DENIED + logged; both-states control green")
