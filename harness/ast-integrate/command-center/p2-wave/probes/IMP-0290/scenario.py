"""Shared planted tokens and round factory for IMP-0290 probes."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MODULE = REPO / "tools/council/protocol/blind_first.py"

ALICE = "alice"
BOB = "bob"
CAROL = "carol"
SEATS = (ALICE, BOB, CAROL)

SHARED_BRIEF = (
    "SHARED-BRIEF-imp-0290-public-question: should the council adopt a "
    "sealed-envelope first pass?"
)
CANARY_ALICE = "CANARY-ALICE-7f3a9c2e-blind-first-sealed"
CANARY_BOB = "CANARY-BOB-d41e8b11-blind-first-sealed"
CANARY_CAROL = "CANARY-CAROL-a0c4ff90-blind-first-sealed"

ALICE_TEXT = f"Alice independent position: envelopes before talk. {CANARY_ALICE}"
BOB_TEXT = f"Bob independent position: no peeking across seats. {CANARY_BOB}"
CAROL_TEXT = f"Carol independent position: timeout must not leak. {CANARY_CAROL}"

RECEIPT = "command-center/receipts/IMP-0290.json"
SENTINEL = "SUCCESS:IMP-0290"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def load_blind_first():
    """Load the live module from disk; a stale import is not evidence."""
    key = "imp0290_blind_first"
    spec = importlib.util.spec_from_file_location(key, MODULE)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {MODULE}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


def make_round(mod, *, deadline: float = 1100.0, start: float = 1000.0):
    clock = mod.LogicalClock(start)
    rnd = mod.BlindFirstRound(
        SEATS,
        shared_brief=SHARED_BRIEF,
        deadline=deadline,
        clock=clock,
    )
    return rnd, clock


def check_receipt_if_present() -> dict:
    path = REPO / RECEIPT
    if not path.is_file():
        return {"present": False, "ok": True, "reason": "receipt-not-yet-written"}
    import json

    text = path.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return {"present": True, "ok": False, "reason": "sentinel-absent"}
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return {"present": True, "ok": False, "reason": f"self-declared:{st}"}
    if doc.get("unit_id") != "IMP-0290":
        return {"present": True, "ok": False, "reason": "unit_id"}
    return {"present": True, "ok": True, "reason": "receipt-ok", "state": st}
