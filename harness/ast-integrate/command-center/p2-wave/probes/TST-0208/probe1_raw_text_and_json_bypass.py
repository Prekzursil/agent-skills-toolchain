#!/usr/bin/env python3
"""Probe 1: both-states — raw-text secrets redact; JSON password bypasses regex-only.

Independent of the receipt narrative: this process mints a fresh canary,
runs the regex-only redactor and the dual-path redactor, and requires
the JSON `"password"` field to survive regex-only while disappearing
under structured walk. Raw `password=` must redact on both paths.
"""
from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.lib import security as G  # noqa: E402

ART = REPO / "command-center/receipts/TST-0208.json"
SENTINEL = "SUCCESS:TST-0208"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0208-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0208":
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")

    canary = f"tst0208-p1-{secrets.token_hex(8)}-not-a-secret"
    raw = f"password={canary}"
    raw_regex = G.redact_raw_text(raw)
    raw_dual = G.redact_payload(raw)
    if canary in raw_regex or canary in str(raw_dual):
        return fail("raw-text password=VALUE retained")
    if f"password={G.REDACTED}" not in raw_regex:
        return fail("raw-text regex did not emit marker")

    payload = {"username": "alice", "password": canary, "id": 7}
    dumped = json.dumps(payload)
    regex_only = G.redact_raw_text(dumped)
    dual = G.redact_payload(dumped)
    if canary not in regex_only:
        return fail("regex-only caught JSON password; bypass seed silent")
    if canary in str(dual):
        return fail("dual path left JSON password intact")
    parsed = json.loads(dual) if isinstance(dual, str) else dual
    if parsed.get("password") != G.REDACTED:
        return fail(f"structured password {parsed.get('password')!r}")
    if parsed.get("username") != "alice" or parsed.get("id") != 7:
        return fail("non-sensitive fields dropped")
    if canary in text:
        return fail("receipt contains probe canary")

    live = G.run_required_controls()
    fails = G.control_failures(live)
    if fails:
        return fail("; ".join(fails))
    both = live.get("both_states") or {}
    if not both.get("raw_text_redacted_on_regex_and_dual"):
        return fail("live both-states raw-text failed")
    if not both.get("json_password_bypasses_regex_only"):
        return fail("live JSON bypass seed failed")
    if not both.get("json_password_caught_by_structured"):
        return fail("live structured catch failed")

    receipt_both = (doc.get("live_controls") or {}).get("both_states") or {}
    for key in (
        "raw_text_redacted_on_regex_and_dual",
        "json_password_bypasses_regex_only",
        "json_password_caught_by_structured",
    ):
        if receipt_both.get(key) is not True:
            return fail(f"receipt both_states.{key} drift")

    out = {
        "probe": "probe1-raw-text-and-json-bypass",
        "unit_id": "TST-0208",
        "pass": True,
        "raw_text_redacted": True,
        "regex_only_retains_json_password": True,
        "structured_redacts_json_password": True,
        "username_preserved": True,
        "receipt_matches_live": True,
        "catalog_js_present": live.get("catalog_js_present"),
        "gate_path": live.get("gate_path"),
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "raw_text=redacted json_regex_bypass=yes structured_catch=yes "
        f"gate={live.get('gate_path')}"
    )
    print(
        "SUCCESS:TST-0208-probe1 raw-text redacts; JSON password bypasses "
        "regex-only and is caught by structured walk"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
