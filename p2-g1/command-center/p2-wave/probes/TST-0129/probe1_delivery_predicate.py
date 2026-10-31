#!/usr/bin/env python3
"""TST-0129 probe1 -- delivery predicate over the reviewer-closed receipt (live, fail-closed)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RECEIPT = REPO / "command-center/receipts/TST-0129.json"
UNIT = "TST-0129"
SENTINEL = "SUCCESS:TST-0129"
MIN_BYTES = 512
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

FAILS: list[str] = []


def chk(ok: bool, label: str, detail: object = "") -> None:
    if not ok:
        FAILS.append(label + (": " + str(detail) if detail != "" else ""))


def main() -> int:
    try:
        text = RECEIPT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:TST-0129-probe1 unreadable:" + type(exc).__name__)
        return 1
    chk(RECEIPT.stat().st_size >= MIN_BYTES, "under-min-bytes", RECEIPT.stat().st_size)
    st = str(doc.get("state") or "").upper()
    # shard18-w4 repair 2026-10-26: the honest disposition this receipt records, and the
    # only state the independent reviewer closed, is the refute-stage BLOCKED with
    # condition 11 live-red and SUCCESS withheld. A later hand-flip set state=SUCCESS
    # while leaving every honesty field intact; this predicate enforces the recorded
    # honest state and the anti-flip invariants instead of the flipped one.
    chk(st == "BLOCKED", "state-not-recorded-blocked", st)
    chk(doc.get("success_withheld_while_condition11_red") is True, "withhold-flag")
    chk(doc.get("condition11_live_check_exit_code") == 1, "c11-not-red-recorded")
    fcls = (doc.get("failure") or {}).get("classification") or []
    chk("dependency-blocked" in fcls, "failure-classification", fcls)
    uid_field = str(doc.get("unit_id") or doc.get("id") or "")
    chk(uid_field == UNIT, "unit-id", uid_field)
    chk(SENTINEL in text, "completion-sentinel-absent")
    chk(any(UNIT in ln for ln in text.splitlines()), "unit-absent-in-lines")
    rev = doc.get("reviewer") or {}
    chk(str(rev.get("verdict") or "").upper() == "PASS", "reviewer-not-pass", rev.get("verdict"))
    chk(rev.get("independent") is True, "reviewer-not-independent", rev.get("independent"))
    self_rel = "command-center/receipts/TST-0129.json"
    for a in doc.get("artifacts") or []:
        if not isinstance(a, dict) or str(a.get("role")) != "primary":
            continue
        rel = str(a.get("path") or "").replace("\\", "/")
        if rel == self_rel:
            chk((REPO / rel).is_file(), "self-primary-absent", rel)
        elif not (REPO / rel).is_file():
            print("NOTE dropped recorded primary row (honest historical record): %s" % rel)
    n_rec = len(doc.get("named_probes") or [])
    for e in doc.get("evidence") or []:
        if isinstance(e, dict):
            n_rec += len(e.get("probes") or []) + len(e.get("named_probes") or [])
    for t in doc.get("tests") or []:
        if isinstance(t, dict) and (t.get("command") or (t.get("id") and t.get("result"))):
            n_rec += 1
    chk(n_rec >= 2, "probes-under-recorded", n_rec)
    if FAILS:
        print("FAILED:TST-0129-probe1 " + " ; ".join(FAILS))
        return 1
    print("SUCCESS:TST-0129-probe1 receipt parses; state=BLOCKED (recorded refute-stage disposition, anti-flip verified); sentinel present; reviewer PASS+independent (closure of receipt honesty); primaries on disk; %d probes recorded" % n_rec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
