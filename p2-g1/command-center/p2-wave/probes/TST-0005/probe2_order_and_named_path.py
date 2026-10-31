#!/usr/bin/env python3
"""@DOC
Shard 20 wave-2 resume (builder): live named probe. Exit 0 = green.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "TST-0005"
OUT = (REPO / "command-center/receipts/TST-0005.json").resolve()


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
"""Order + naming: existence check structurally precedes digest parse in
barrier.py; bypassing the order raises; the naive parser control is caught."""
import sys

sys.path.insert(0, str(REPO / "tools" / "fan_in"))
import barrier

doc = load()
src = (REPO / "tools" / "fan_in" / "barrier.py").read_text(encoding="utf-8")
lines = src.splitlines()
exist_line = next(i for i, l in enumerate(lines, 1)
                  if "check_outputs_exist(root, contracted)" in l)
parse_line = next(i for i, l in enumerate(lines, 1)
                  if "_parse_digest(text, phases)" in l)
need(exist_line < parse_line,
     f"existence (line {exist_line}) not before parse (line {parse_line})")
need(barrier.PHASE_EXIST in ["existence_check"], "phase token drifted")
try:
    barrier._parse_digest("sha256: " + "0" * 64, [])
    fail("parse without existence check did not raise")
except RuntimeError as exc:
    need("existence" in str(exc), f"unexpected refusal text: {exc}")
b = doc.get("barrier") or {}
need(b.get("ast_existence_line") == exist_line and b.get("ast_parse_line") == parse_line,
     f"recorded barrier lines {b.get('ast_existence_line')}/{b.get('ast_parse_line')} != live {exist_line}/{parse_line}")
p2 = doc.get("probe2_raw") or {}
need(p2.get("real_digest_parsed_on_absent") is False
     and p2.get("rejection_names_absent_path") is True,
     "recorded probe2 raw contradicts the live order proof")
ok("order: existence", exist_line, "< parse", parse_line, "; bypass raises; path named")
