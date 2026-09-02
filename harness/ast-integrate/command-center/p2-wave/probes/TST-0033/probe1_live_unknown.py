#!/usr/bin/env python3
"""Probe 1: live shipped load + unknown top-level field is a named load failure.

Re-executes the client strict loader. A receipt-only reread is not this probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import client_strict_loader as L  # noqa: E402
import suite as S  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0033.json"
UNKNOWN = "notARealField"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0033-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0033":
        print("FAILED:TST-0033-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:TST-0033" not in text:
        print("FAILED:TST-0033-probe1 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0033-probe1 self-declared", st)
        return 1

    good = S.run_case(S._blob("conforming.json"), strict=True)
    bad = S.run_case(S._blob("unknown-top-level.json"), strict=True)
    named = S._errors_name_token(bad.errors, UNKNOWN) or (
        UNKNOWN in bad.named_unknown_fields
    )
    live = S.live_shipped()
    payload = {
        "probe": "probe1-live-and-unknown",
        "unit_id": "TST-0033",
        "parser": L.SCHEMA_ID,
        "hand_written_field_list": False,
        "conforming_ok": good.ok,
        "unknown_rejected": not bad.ok,
        "unknown_field_named": named,
        "unknown_field": UNKNOWN,
        "unknown_errors": bad.errors,
        "live_shipped": live,
        "pass": bool(good.ok and (not bad.ok) and named),
    }
    print(json.dumps(payload, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:TST-0033-probe1 unknown field was not a named load failure")
        return 1
    if live.get("present") and not live.get("ok"):
        print("FAILED:TST-0033-probe1 shipped plugin.json present but strict-load failed")
        return 1
    print(
        f"conforming_ok=True unknown_rejected=True named={UNKNOWN} "
        f"live_present={live.get('present')}"
    )
    print("SUCCESS:TST-0033-probe1 strict parser names unknown top-level field")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
