#!/usr/bin/env python3
"""Probe 1: known-broken controls.

- Synthetic background receipt must be rejected.
- Digest naming a nonexistent path must be rejected BEFORE the digest reader runs.
- Historical fire-and-forget ledger row must fire the gate (a gate never
  exercised on a real bad input is unproven).
- Empty and unparsable files must fail check (c).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from _boot import REPO, import_pkg

di = import_pkg()


def _fail(msg: str) -> int:
    print(f"FAILED:CNF-0159-probe1 {msg}")
    return 1


def _check_names(log: dict) -> list[str]:
    return [c["name"] for c in log["checks"]]


def main() -> int:
    di.reset_parse_events()

    # --- synthetic background receipt ---
    bg = {
        "result_id": "synthetic-background",
        "result_text": (
            "Codex started in the background. Job id: probe-synthetic.\n"
            "Check /codex:status for progress."
        ),
        "contracted_output_path": "command-center/receipts/CNF-0154.json",
        "unit_id": "CNF-0154",
    }
    out = di.fan_in(REPO, bg)
    if out["accepted"]:
        return _fail("synthetic background receipt was accepted")
    if out["digest"] is not None:
        return _fail("digest reader returned a body for a background receipt")
    if di.parse_events():
        return _fail(f"digest parsed on background reject: {di.parse_events()}")
    log = out["gate"]
    if _check_names(log) != ["background_receipt", "test_path", "parseable"]:
        return _fail(f"three checks not logged: {log['checks']}")
    if log["checks"][0]["passed"]:
        return _fail("background check did not fail")
    if log["rejected_by"] != "background_receipt":
        return _fail(f"rejected_by={log['rejected_by']}")
    if log["file_opened"]:
        return _fail("file opened for background receipt")
    print("synthetic_background rejected=True reader_idle=True checks=3")

    # --- nonexistent path, plausible inline digest; reject BEFORE parse ---
    di.reset_parse_events()
    phantom_path = "command-center/receipts/CNF-0159-DOES-NOT-EXIST.json"
    phantom_digest = {
        "unit_id": "CNF-0159",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0159",
        "verdict": "CONFIRMED",
        "note": "plausible digest with no file behind it",
    }
    missing = {
        "result_id": "synthetic-missing-path",
        "result_text": json.dumps(phantom_digest),
        "contracted_output_path": phantom_path,
        "digest": phantom_digest,
        "unit_id": "CNF-0159",
    }
    out = di.fan_in(REPO, missing)
    if out["accepted"]:
        return _fail("missing-path digest was accepted")
    if out["digest"] is not None:
        return _fail("digest body returned for missing path")
    if di.parse_events():
        return _fail(
            f"digest reader ran before Test-Path reject: {di.parse_events()}"
        )
    log = out["gate"]
    if log["rejected_by"] != "test_path":
        return _fail(f"missing path rejected_by={log['rejected_by']}")
    if not log["checks"][1]["passed"] is False:
        return _fail("test_path did not fail")
    if not log["checks"][2]["skipped"]:
        return _fail("parseable was not skipped (file would have been opened)")
    if log["file_opened"]:
        return _fail("file_opened True on missing path")
    print("missing_path rejected=True before_parse=True reader_idle=True")

    # --- historical ledger (real bad input) ---
    rows = di.load_historical_ledger(REPO)
    if len(rows) < 4:
        return _fail(f"ledger too small: {len(rows)}")
    fnf = next(r for r in rows if r["kind"] == "fire-and-forget-background-receipt")
    di.reset_parse_events()
    out = di.fan_in(REPO, di.ledger_row_to_result(fnf))
    if out["accepted"]:
        return _fail("historical fire-and-forget ledger row was accepted")
    if di.parse_events():
        return _fail("digest reader ran on historical fire-and-forget row")
    if out["gate"]["rejected_by"] != "background_receipt":
        return _fail(f"historical fnf rejected_by={out['gate']['rejected_by']}")
    print(
        f"historical_ledger id={fnf['ledger_id']} rejected=True "
        f"rejected_by={out['gate']['rejected_by']}"
    )

    phantoms = [r for r in rows if r["kind"] == "plausible-digest-missing-file"]
    if len(phantoms) != 3:
        return _fail(f"expected 3 phantom-digest ledger rows, got {len(phantoms)}")
    for row in phantoms:
        di.reset_parse_events()
        out = di.fan_in(REPO, di.ledger_row_to_result(row))
        if out["accepted"] or di.parse_events():
            return _fail(f"phantom {row['ledger_id']} leaked to digest reader")
        if out["gate"]["rejected_by"] != "test_path":
            return _fail(
                f"phantom {row['ledger_id']} rejected_by={out['gate']['rejected_by']}"
            )
    print("historical_phantoms 3/3 rejected before parse")

    # --- empty + unparsable (check c) ---
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        empty = root / "empty.json"
        empty.write_bytes(b"")
        di.reset_parse_events()
        out = di.fan_in(
            root,
            {
                "result_id": "empty",
                "result_text": "ok",
                "contracted_output_path": "empty.json",
            },
        )
        if out["accepted"]:
            return _fail("empty file accepted")
        if out["gate"]["rejected_by"] != "parseable":
            return _fail(f"empty rejected_by={out['gate']['rejected_by']}")
        # Gate itself opens the file for check (c); the digest *reader* must not.
        if di.parse_events():
            return _fail("digest reader ran on empty file")

        bad = root / "bad.json"
        bad.write_bytes(b"{not json")
        di.reset_parse_events()
        out = di.fan_in(
            root,
            {
                "result_id": "unparsable",
                "result_text": "ok",
                "contracted_output_path": "bad.json",
            },
        )
        if out["accepted"] or out["gate"]["rejected_by"] != "parseable":
            return _fail(f"unparsable not rejected: {out['gate']}")
        if di.parse_events():
            return _fail("digest reader ran on unparsable file")
    print("empty_and_unparsable rejected=True reader_idle=True")

    print("SUCCESS:CNF-0159-probe1 known-broken background/missing/ledger/empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
