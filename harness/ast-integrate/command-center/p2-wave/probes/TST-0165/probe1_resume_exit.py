#!/usr/bin/env python3
"""Named probe 1: resume exit status and message (catalog evidence signal a).

Does not inspect field-set diffs. Pass criteria are only exit_code and the
operator-facing message for each fixture.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/receipts/TST-0165.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0165-probe1 {msg}")
    return 1


def main() -> int:
    paths = E.materialize_fixtures()
    rows = E.evaluate_strict(paths)

    current = rows["current-v2"]["resume"]
    if current["exit_code"] != 0:
        return fail(f"current-v2 exit {current['exit_code']} {current['message']}")
    msg = current["message"]
    if "schema_version=2" not in msg and "schema_version 2" not in msg:
        return fail(f"current-v2 message does not name schema_version=2: {msg}")
    if "no migration" not in msg.lower():
        return fail(f"current-v2 message is not a no-migration resume: {msg}")
    if current.get("refused"):
        return fail("current-v2 refused")

    old = rows["old-v1"]["resume"]
    if old["exit_code"] != 0:
        return fail(f"old-v1 exit {old['exit_code']} {old['message']}")
    omsg = old["message"]
    if "migrat" not in omsg.lower():
        return fail(f"old-v1 message is not a migration: {omsg}")
    if "1" not in omsg or "2" not in omsg:
        return fail(f"old-v1 message does not name both schema versions: {omsg}")
    if old.get("refused"):
        return fail("old-v1 refused instead of migrating")

    extra = rows["old-v1-unknown-extra"]["resume"]
    if extra["exit_code"] == 0:
        return fail("old-v1-unknown-extra exited 0; extra field was not refused")
    emsg = extra["message"]
    if "secret_operator_note" not in emsg:
        return fail(f"unknown-extra refuse does not name the field: {emsg}")
    if "schema_version=1" not in emsg and "schema_version 1" not in emsg:
        return fail(f"unknown-extra refuse does not name schema_version: {emsg}")
    if "partial" not in emsg.lower() and "unknown" not in emsg.lower():
        return fail(f"unknown-extra refuse is not loud about partial/unknown: {emsg}")

    future = rows["future-v99"]["resume"]
    if future["exit_code"] == 0:
        return fail("future-v99 exited 0; unknown version was not refused")
    fmsg = future["message"]
    if "schema_version" not in fmsg:
        return fail(f"future refuse does not name schema_version: {fmsg}")
    if "99" not in fmsg:
        return fail(f"future refuse does not name 99: {fmsg}")

    unread = rows["unreadable"]["resume"]
    if unread["exit_code"] == 0:
        return fail("unreadable exited 0")
    umsg = unread["message"]
    if "JSONDecodeError" not in umsg and "unreadable" not in umsg.lower():
        return fail(f"unreadable refuse is not actionable: {umsg}")
    if "unreadable.json" not in umsg:
        return fail(f"unreadable refuse does not name the file: {umsg}")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("unit_id") != "TST-0165":
            return fail(f"artifact unit_id {doc.get('unit_id')}")
        if "SUCCESS:TST-0165" not in ART.read_text(encoding="utf-8"):
            return fail("artifact sentinel absent")
        ev = doc.get("evidence_a") or {}
        claimed = {r.get("id"): r for r in (ev.get("rows") or []) if isinstance(r, dict)}
        for fid, want_exit in (
            ("current-v2", 0),
            ("old-v1", 0),
            ("old-v1-unknown-extra", 2),
            ("future-v99", 2),
            ("unreadable", 2),
        ):
            live = rows[fid]["resume"]["exit_code"]
            if live != want_exit:
                return fail(f"live {fid} exit {live} want {want_exit}")
            if fid in claimed and claimed[fid].get("exit_code") != live:
                return fail(
                    f"artifact evidence_a {fid} exit mismatch "
                    f"{claimed[fid].get('exit_code')} vs live {live}"
                )

    payload = {
        "probe": "probe1-resume-exit",
        "unit_id": "TST-0165",
        "pass": True,
        "exits": {fid: rows[fid]["resume"]["exit_code"] for fid in rows},
        "messages": {fid: rows[fid]["resume"]["message"] for fid in rows},
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "current_v2_exit=0 old_v1_exit=0 extra_refused=True "
        "future_refused=True unreadable_refused=True"
    )
    print("SUCCESS:TST-0165-probe1 resume exit status and message")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
