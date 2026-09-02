"""Shared probe paths for IMP-0230."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

OUT_REL = "command-center/receipts/IMP-0230.json"
OUT = REPO / OUT_REL
SENTINEL = "SUCCESS:IMP-0230"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def load_receipt() -> dict:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        raise SystemExit("FAILED:IMP-0230 receipt missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise SystemExit("FAILED:IMP-0230 receipt is not an object")
    text = json.dumps(doc)
    if SENTINEL not in text:
        raise SystemExit("FAILED:IMP-0230 sentinel absent")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        raise SystemExit(f"FAILED:IMP-0230 self-declared:{st}")
    if str(doc.get("unit_id") or "") != "IMP-0230":
        raise SystemExit("FAILED:IMP-0230 unit_id mismatch")
    return doc
