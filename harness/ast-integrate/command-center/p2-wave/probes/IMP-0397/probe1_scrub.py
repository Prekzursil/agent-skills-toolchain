#!/usr/bin/env python3
"""Probe 1: planted secret and absolute path must be absent from emitted telemetry.

Both-states: with scrub disabled the canaries are present (detector fires).
Fail-closed: assert_clean refuses a leaky payload.
"""
from __future__ import annotations

import json
from copy import deepcopy

from harness import RECEIPT, REPO, SENTINEL, T, canaries, load_events, live_report


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0397-probe1 {msg}")
    return 1


def main() -> int:
    secret, abs_path = canaries()
    events = load_events()
    raw_blob = json.dumps(events, sort_keys=True)
    if secret not in raw_blob:
        return fail("fixture does not plant the secret canary")
    if abs_path not in raw_blob:
        return fail("fixture does not plant the abs-path canary")

    clean = T.emit_records(
        events, REPO, month="2026-07", extra_canaries=(secret, abs_path)
    )
    blob = T.dump_for_leak_scan(clean)
    if secret in blob:
        return fail("secret canary survived scrub")
    if abs_path in blob:
        return fail("abs-path canary survived scrub")
    if "user-alice" in blob or "raw-sess-01" in blob:
        return fail("raw session or user identifier leaked into emit")
    hits = T.leak_hits(blob, REPO, (secret, abs_path))
    if hits:
        return fail(f"leak_hits on clean emit: {hits}")

    dirty_note = {
        "session_id": "raw-sess-note",
        "type": "router.offer",
        "capabilities": ["cap.lint"],
        "note": f"see {abs_path} token={secret}",
    }
    scrubbed_note = T.scrub_event(dirty_note, REPO, drop_sensitive=False)
    note_blob = T.dump_for_leak_scan(scrubbed_note)
    if secret in note_blob or abs_path in note_blob:
        return fail("note-field canaries not redacted")
    if T.REDACTED_SECRET not in note_blob and T.REDACTED_PATH not in note_blob:
        return fail("redaction markers missing from scrubbed note")

    leaked = T.emit_records(
        events, REPO, month="2026-07", test_disable_scrub=True
    )
    leak_blob = T.dump_for_leak_scan(leaked)
    if secret not in leak_blob:
        return fail("detector silent: secret missing from unscanned payload")
    if abs_path not in leak_blob:
        return fail("detector silent: abs-path missing from unscanned payload")
    leak_hits = T.leak_hits(leak_blob, REPO, (secret, abs_path))
    if "canary" not in leak_hits:
        return fail(f"detector did not flag canaries on dirty emit: {leak_hits}")

    mutant = deepcopy(clean)
    mutant[0]["offered"] = list(mutant[0]["offered"]) + [secret]
    try:
        T.assert_clean(mutant, REPO, (secret, abs_path))
    except T.ScrubFailure:
        pass
    else:
        return fail("assert_clean accepted a secret-injected record")

    if not RECEIPT.is_file():
        return fail("receipt missing")
    receipt_text = RECEIPT.read_text(encoding="utf-8")
    if secret in receipt_text or abs_path in receipt_text:
        return fail("receipt contains planted canary plaintext")
    if SENTINEL not in receipt_text:
        return fail("receipt sentinel absent")
    doc = json.loads(receipt_text)
    scrub = doc.get("scrub") or {}
    if scrub.get("secret_canary_absent") is not True:
        return fail("receipt scrub.secret_canary_absent is not true")
    if scrub.get("abs_path_canary_absent") is not True:
        return fail("receipt scrub.abs_path_canary_absent is not true")
    if scrub.get("emit_refused_on_leak") is not True:
        return fail("receipt scrub.emit_refused_on_leak is not true")

    report = live_report()
    print(
        "clean_sessions="
        + str(len(clean))
        + " dirty_canary_hits="
        + ",".join(leak_hits)
        + " fail_closed=True note_redacted=True breadth="
        + str(report["breadth"]["denominator_statement"])
    )
    print("SUCCESS:IMP-0397-probe1 scrub canaries absent both-states fail-closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
