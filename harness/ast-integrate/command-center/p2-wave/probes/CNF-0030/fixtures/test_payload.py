#!/usr/bin/env python3
"""Fix-associated test: requires required_payload.txt next to this file."""
from pathlib import Path

PAYLOAD = Path(__file__).resolve().parent / "required_payload.txt"
EXPECTED = "CNF-0030-FIX-PAYLOAD"

if not PAYLOAD.is_file():
    raise SystemExit("MISSING required_payload.txt")
text = PAYLOAD.read_text(encoding="utf-8").strip()
if text != EXPECTED:
    raise SystemExit(f"BAD payload: {text!r}")
print("PASS payload-ok")
