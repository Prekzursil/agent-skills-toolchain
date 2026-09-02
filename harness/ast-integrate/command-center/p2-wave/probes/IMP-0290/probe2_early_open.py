#!/usr/bin/env python3
"""Named probe 2 (adversarial, starts from the tests): early-open negative control.

The catalog control: open the barrier early and assert the delivered-prompt
scan FIRES. Both-states: the same sequence without force-open must stay silent.
A scanner that trusted the protocol's own opened-at timestamp would be silent
on the bad state; this probe fails that mutant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    ALICE,
    ALICE_TEXT,
    BOB,
    CANARY_ALICE,
    check_receipt_if_present,
    load_blind_first,
    make_round,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0290-probe2 {msg}")
    return 1


def _mutant_scan_uses_actual_open(rnd) -> list:
    """What a dishonest scanner would do: trust actual opened_at.

    Prompts after force-open would be treated as post-barrier and skipped.
    """
    cutoff = rnd._actual_opened_at
    hits = []
    for rec in rnd.prompt_log():
        if cutoff is not None and rec.ts >= cutoff:
            continue
        if CANARY_ALICE in rec.text and rec.seat != ALICE:
            hits.append(rec.seat)
    return hits


def main() -> int:
    mod = load_blind_first()

    # --- bad state: force-open before Carol/Bob submit ---
    bad, clock = make_round(mod)
    bad.submit(ALICE, ALICE_TEXT)
    clock.advance()
    p_bob_pre = bad.assemble_prompt(BOB)
    if CANARY_ALICE in p_bob_pre:
        return fail("production assemble leaked before any open (not the control)")
    opened = bad.open_barrier(force=True)
    if not opened:
        return fail("force-open did not open")
    if bad.legitimate_barrier_at() is not None:
        return fail("force-open must not write the legitimate barrier timestamp")
    clock.advance()
    p_bob_bad = bad.assemble_prompt(BOB)
    if CANARY_ALICE not in p_bob_bad:
        return fail("force-open did not deliver alice text; control cannot fire")
    leaks_bad = bad.scan_delivered_prompts()
    if not leaks_bad:
        return fail("prompt scan SILENT on early-open (detector failure)")
    if not any(h.peer_seat == ALICE and h.prompt_seat == BOB for h in leaks_bad):
        return fail(f"scan fired but not on bob<-alice: {leaks_bad[:3]}")
    audit_bad = bad.audit_event_order()
    if audit_bad["ok"]:
        return fail("event-order audit silent on early DELIVER (second signal dead)")
    mutant_hits = _mutant_scan_uses_actual_open(bad)
    if mutant_hits:
        return fail("mutant scanner unexpectedly fired; control is mis-built")

    # --- good state: same submits, no force-open ---
    good, clock_g = make_round(mod)
    good.submit(ALICE, ALICE_TEXT)
    clock_g.advance()
    p_bob_good = good.assemble_prompt(BOB)
    if CANARY_ALICE in p_bob_good:
        return fail("good-state bob saw alice")
    leaks_good = good.scan_delivered_prompts()
    if leaks_good:
        return fail(f"scan fired on good state: {leaks_good[:3]}")
    audit_good = good.audit_event_order()
    if not audit_good["ok"]:
        return fail(f"event-order failed on good state: {audit_good['violations'][:3]}")
    good.open_barrier(force=False)
    if good.barrier_actually_open():
        return fail("non-force open succeeded with missing seats")

    rec = check_receipt_if_present()
    if not rec["ok"]:
        return fail(f"receipt {rec['reason']}")

    out = {
        "probe": "probe2-early-open",
        "unit_id": "IMP-0290",
        "pass": True,
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
        "legitimate_untouched_by_force": True,
        "mutant_actual_opened_at_scanner_silent_on_bad": True,
        "event_order_fires_on_bad": True,
        "leak_count_bad": len(leaks_bad),
        "receipt": rec,
        "reviewer_starts_from": "negative control (early barrier open), not author summary",
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"early_open_scan_fires={len(leaks_bad)} good_silent=True "
        "mutant_actual_open_silent=True"
    )
    print("SUCCESS:IMP-0290-probe2 early-open negative control fires")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
