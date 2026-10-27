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
"""Byte-level scan (independent mechanism): every literal 'however' in the
artifact is a mention inside rule/control prose, never inside a recorded
CHALLENGED conclusion's evidence fields."""
doc = load()
raw = OUT.read_bytes()
n_however = raw.count(b"however") + raw.count(b"However")
need(n_however >= 1, "expected the however control corpus on disk; scan found none")
import re
text = raw.decode("utf-8", errors="replace")
challenged_ctx = 0
for m in re.finditer(r"however", text, re.I):
    s = max(0, m.start() - 60)
    ctx = text[s:m.end() + 60].lower()
    if '"status": "challenged"' in ctx or "challenged_conclusion" in ctx:
        challenged_ctx += 1
need(challenged_ctx == 0,
     f"{challenged_ctx} however-mentions sit inside CHALLENGED evidence context")
ctrl = (doc.get("controls") or {}).get("labeled") or []
need(any(r.get("hedge_mention") is True or r.get("status") == "UNCHALLENGED" for r in ctrl),
     "labeled however control not recorded as hedge-mention")
ok("byte scan", n_however, "'however' tokens, 0 inside challenged evidence")
