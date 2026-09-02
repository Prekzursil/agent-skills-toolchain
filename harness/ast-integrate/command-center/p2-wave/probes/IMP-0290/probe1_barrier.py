#!/usr/bin/env python3
"""Named probe 1: barrier under a slow seat and a timeout.

Also covers retry and streaming paths: an early submitter's text must not
reach a later participant before the legitimate barrier opens. Event-order
audit is the second signal (timestamps), distinct from the prompt scan.
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
    BOB_TEXT,
    CANARY_ALICE,
    CANARY_BOB,
    CANARY_CAROL,
    CAROL,
    CAROL_TEXT,
    SHARED_BRIEF,
    check_receipt_if_present,
    load_blind_first,
    make_round,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0290-probe1 {msg}")
    return 1


def _no_peer_canaries(prompt: str, own: str) -> list[str]:
    hits = []
    for tok in (CANARY_ALICE, CANARY_BOB, CANARY_CAROL):
        if tok in own:
            continue
        if tok in prompt:
            hits.append(tok)
    return hits


def main() -> int:
    mod = load_blind_first()
    rnd, clock = make_round(mod)

    # Shared brief is visible to everyone from t0.
    p_alice = rnd.assemble_prompt(ALICE)
    if SHARED_BRIEF not in p_alice:
        return fail("shared brief missing from alice prompt")
    clock.advance()

    # Alice submits first. Bob and Carol assemble: must not see Alice.
    rnd.submit(ALICE, ALICE_TEXT)
    clock.advance()
    p_bob = rnd.assemble_prompt(BOB)
    p_carol = rnd.assemble_prompt(CAROL)
    if _no_peer_canaries(p_bob, BOB_TEXT):
        return fail(f"bob saw alice before barrier: {_no_peer_canaries(p_bob, BOB_TEXT)}")
    if _no_peer_canaries(p_carol, CAROL_TEXT):
        return fail("carol saw a peer before barrier")
    if CANARY_ALICE in p_bob or CANARY_ALICE in p_carol:
        return fail("alice canary leaked pre-barrier")

    # Retry: Alice replaces her sealed text. Still must not leak.
    clock.advance()
    rnd.submit(ALICE, ALICE_TEXT + " RETRY-MARKER-alice")
    clock.advance()
    p_bob2 = rnd.assemble_prompt(BOB)
    if CANARY_ALICE in p_bob2 or "RETRY-MARKER-alice" in p_bob2:
        return fail("retry leaked alice text to bob")

    # Streaming: Bob streams his canary in chunks; Carol must not see it.
    clock.advance()
    rnd.submit_chunk(BOB, BOB_TEXT[:20])
    clock.advance()
    rnd.submit_chunk(BOB, BOB_TEXT[20:])
    clock.advance()
    p_carol2 = rnd.assemble_prompt(CAROL)
    if CANARY_BOB in p_carol2 or BOB_TEXT in p_carol2:
        return fail("stream buffer leaked to carol")
    rnd.finalize_stream(BOB)
    clock.advance()
    p_carol3 = rnd.assemble_prompt(CAROL)
    if CANARY_BOB in p_carol3:
        return fail("bob sealed text leaked to carol while carol still slow")

    # Slow participant (Carol) + timeout: tick to deadline without Carol.
    # Before deadline, Alice must not see Bob either (barrier still closed).
    p_alice_pre = rnd.assemble_prompt(ALICE)
    if CANARY_BOB in p_alice_pre:
        return fail("alice saw bob before timeout barrier")

    leaks_pre = rnd.scan_delivered_prompts()
    if leaks_pre:
        return fail(f"pre-timeout scan not zero: {leaks_pre[:3]}")

    clock.now = rnd.deadline
    rnd.tick()
    if rnd.legitimate_barrier_at() != rnd.deadline:
        return fail(f"timeout did not set legitimate barrier {rnd.legitimate_barrier_at()}")

    # After timeout, submitted seats may see each other.
    p_alice_post = rnd.assemble_prompt(ALICE)
    p_bob_post = rnd.assemble_prompt(BOB)
    if CANARY_BOB not in p_alice_post:
        return fail("alice did not receive bob after legitimate timeout barrier")
    if CANARY_ALICE not in p_bob_post:
        return fail("bob did not receive alice after legitimate timeout barrier")

    # Timed-out Carol must NOT receive peer positions (cannot contaminate a late write).
    p_carol_to = rnd.assemble_prompt(CAROL)
    if CANARY_ALICE in p_carol_to or CANARY_BOB in p_carol_to:
        return fail("timed-out carol received peer positions")
    if "TIMEOUT" not in p_carol_to:
        return fail("timed-out carol prompt missing TIMEOUT status")

    # Carol cannot submit after the legitimate barrier.
    try:
        rnd.submit(CAROL, CAROL_TEXT)
        return fail("post-timeout submit was accepted")
    except mod.BlindFirstError:
        pass

    # Scan still reports zero on prompts assembled *before* the legitimate barrier.
    leaks = rnd.scan_delivered_prompts()
    if leaks:
        return fail(f"scan not zero after timeout path: {leaks[:3]}")

    audit = rnd.audit_event_order()
    if not audit["ok"]:
        return fail(f"event-order audit failed: {audit['violations'][:3]}")
    if audit["deliver_events"] < 2:
        return fail("expected post-barrier DELIVER events")

    # All-submitted path on a fresh round (no timeout): barrier at max submit ts.
    rnd2, clock2 = make_round(mod, deadline=2000.0, start=1500.0)
    rnd2.submit(ALICE, ALICE_TEXT)
    clock2.advance()
    rnd2.submit(BOB, BOB_TEXT)
    clock2.advance()
    pre = rnd2.assemble_prompt(CAROL)
    if CANARY_ALICE in pre or CANARY_BOB in pre:
        return fail("all-submit path leaked before carol submitted")
    rnd2.submit(CAROL, CAROL_TEXT)
    if rnd2.legitimate_barrier_at() != clock2.now:
        return fail("all-submit barrier timestamp is not last submit")
    post = rnd2.assemble_prompt(ALICE)
    if CANARY_BOB not in post or CANARY_CAROL not in post:
        return fail("all-submit path did not deliver peers after barrier")
    leaks2 = rnd2.scan_delivered_prompts()
    if leaks2:
        return fail(f"all-submit scan not zero: {leaks2[:3]}")
    audit2 = rnd2.audit_event_order()
    if not audit2["ok"]:
        return fail(f"all-submit event-order failed: {audit2['violations'][:3]}")

    rec = check_receipt_if_present()
    if not rec["ok"]:
        return fail(f"receipt {rec['reason']}")

    out = {
        "probe": "probe1-barrier",
        "unit_id": "IMP-0290",
        "pass": True,
        "slow_and_timeout": {
            "pre_timeout_leaks": 0,
            "post_timeout_peer_delivery": True,
            "timed_out_seat_withheld": True,
            "post_barrier_submit_rejected": True,
        },
        "retry_clean": True,
        "stream_clean": True,
        "all_submitted_path": {
            "pre_barrier_leaks": 0,
            "post_barrier_delivery": True,
        },
        "event_order_ok": True,
        "receipt": rec,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "slow_timeout_ok=True retry_clean=True stream_clean=True "
        "scan_zero=True event_order_ok=True"
    )
    print("SUCCESS:IMP-0290-probe1 barrier semantics under slow participant and timeout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
