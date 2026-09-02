#!/usr/bin/env python3
"""Probe 1: re-fire the logging hook for every CLI event; match stored sha256.

Two signals per event: stdin sha256 of the live capture file, and parsed
hook_event_name. CLI vs SDK event sets are re-parsed from frozen docs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import lib as L  # noqa: E402
from constants import OUTPUT_REL, SENTINEL, UNIT_ID  # noqa: E402

ART = L.REPO / OUTPUT_REL
LOG = HERE / "hooks" / "log_stdin.py"
CAP = HERE / "captures"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT_ID}-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel-absent")
    errs = C.validate_artifact(doc)
    if errs:
        return fail("; ".join(errs[:12]))

    cli_text, sdk_text = L.load_docs()
    cli_live = L.parse_cli_events(cli_text)
    sdk_live = L.parse_sdk_events(sdk_text)
    if cli_live != list(doc.get("cli_events") or []):
        return fail("cli-events-drift")
    if sdk_live != list(doc.get("sdk_events") or []):
        return fail("sdk-events-drift")

    stored = {str(row["event"]): row for row in doc.get("captured_raw_payloads") or []}
    mismatches = []
    CAP.mkdir(parents=True, exist_ok=True)
    for event in cli_live:
        payload = L.make_payload(event)
        dest = CAP / f"{event}.json"
        result = L.run_hook(LOG, payload, timeout_s=8, capture=dest)
        if result["returncode"] != 0 or result["timed_out"]:
            return fail(f"logger-failed:{event} rc={result['returncode']}")
        live_raw = dest.read_bytes()
        live_sha = L.sha256_bytes(live_raw)
        row = stored.get(event) or {}
        parsed = json.loads(live_raw.decode("utf-8"))
        if live_sha != row.get("sha256") or parsed.get("hook_event_name") != event:
            mismatches.append(
                {
                    "event": event,
                    "sha_ok": live_sha == row.get("sha256"),
                    "name_ok": parsed.get("hook_event_name") == event,
                    "live_sha": live_sha,
                    "stored_sha": row.get("sha256"),
                }
            )
    if mismatches:
        print(json.dumps(mismatches[:8], indent=2))
        return fail("payload-sha-or-name-mismatch")

    drop_errs = C.validate_artifact(C.mutant_drop_payload(doc))
    if not drop_errs:
        return fail("drop-payload-mutant-silent")

    print(
        json.dumps(
            {
                "probe": "probe1-raw-payloads",
                "unit_id": UNIT_ID,
                "cli_events": len(cli_live),
                "sdk_events": len(sdk_live),
                "payloads": len(stored),
                "cli_only": sorted(set(cli_live) - set(sdk_live)),
                "sdk_only": sorted(set(sdk_live) - set(cli_live)),
                "drop_payload_errors": drop_errs[:8],
                "pass": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("SUCCESS:RES-0009-probe1 raw payloads re-fired and hashed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
