#!/usr/bin/env python3
"""Named probe 2: planted canary secret is rejected or redacted at write time.

Consumer call site is eventlog.append_record. Secrets fail closed (reject);
personal home paths are redacted. Isolated tempfile; never live EVENTS.jsonl.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import eventlog as E  # noqa: E402

ART = REPO / "command-center/phase4/contracts/ARC-0086.json"
LIVE = REPO / "command-center/events/EVENTS.jsonl"
CANARY_PATH = "/home/arc0086-canary/secret.txt"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0086-probe2 {msg}")
    return 1


def base_kwargs() -> dict:
    return {
        "actor": "probe2",
        "unit_id": "ARC-0086",
        "phase": "4",
        "from_state": "OPEN",
        "to_state": "IN-PROGRESS",
        "correlation_id": "arc-0086-probe2",
        "writer_id": "probe2-w",
        "ts": "2026-08-24T20:10:00Z",
    }


def main() -> int:
    if LIVE.is_file() and LIVE.stat().st_size > 0:
        before_live = LIVE.read_bytes()
    else:
        before_live = None
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("contract artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if "SUCCESS:ARC-0086" not in blob:
        return fail("sentinel absent")
    rules = doc.get("redaction_rules") or {}
    if rules.get("secrets_at_write") != "reject":
        return fail("contract secrets_at_write is not reject")
    if rules.get("personal_paths_at_write") != "redact":
        return fail("contract personal_paths_at_write is not redact")
    if E.CANARY_SECRET not in blob:
        return fail("contract does not name the planted canary token")

    with tempfile.TemporaryDirectory(prefix="arc0086-p2-") as tmp:
        path = Path(tmp) / "EVENTS.jsonl"
        # Clean write must succeed (negative control: rejection is not a broken writer).
        clean = E.append_record(
            path,
            payload={"note": "no-secret", "n": 0},
            **base_kwargs(),
        )
        clean_bytes = path.read_bytes()
        if E.CANARY_SECRET.encode("utf-8") in clean_bytes:
            return fail("canary present before plant")
        if CANARY_PATH.encode("utf-8") in clean_bytes:
            return fail("personal path present before plant")

        rejected = False
        reject_reason = ""
        try:
            E.append_record(
                path,
                payload={
                    "note": "planted",
                    "nested": {"token": E.CANARY_SECRET},
                },
                **base_kwargs(),
            )
        except E.SecretRejected as exc:
            rejected = True
            reject_reason = str(exc)
        if not rejected:
            return fail("canary secret was accepted at write")
        after_reject = path.read_bytes()
        if after_reject != clean_bytes:
            return fail("rejected write mutated the durable log")
        if E.CANARY_SECRET.encode("utf-8") in after_reject:
            return fail("canary secret persisted after reject")

        pathed = E.append_record(
            path,
            payload={"note": "path-only", "home": CANARY_PATH},
            writer_id="probe2-path",
            actor="probe2",
            unit_id="ARC-0086",
            phase="4",
            from_state="IN-PROGRESS",
            to_state="IN-PROGRESS",
            correlation_id="arc-0086-probe2",
            ts="2026-08-24T20:10:01Z",
        )
        durable = path.read_text(encoding="utf-8")
        if CANARY_PATH in durable or "arc0086-canary" in durable:
            return fail("personal path survived write-time redaction")
        if E.REDACTED_PATH not in durable:
            return fail("redaction token missing from durable bytes")
        if not pathed.get("redactions"):
            return fail("redactions array empty after path write")
        if E.CANARY_SECRET in durable:
            return fail("canary leaked into path write")
        chain = E.verify_chain(E.load_records(path))
        if not chain["ok"]:
            return fail("chain broken after accepted writes")
        if path.resolve() == LIVE.resolve():
            return fail("wrote to live EVENTS.jsonl")

    if before_live is None:
        if LIVE.is_file() and LIVE.stat().st_size > 0:
            return fail("created live EVENTS.jsonl")
    elif LIVE.read_bytes() != before_live:
        return fail("mutated live EVENTS.jsonl")

    summary = {
        "probe": "probe2-redaction",
        "unit_id": "ARC-0086",
        "pass": True,
        "canary_secret": E.CANARY_SECRET,
        "canary_is_synthetic": True,
        "secret_rejected_at_write": True,
        "secret_in_durable_bytes": False,
        "log_unchanged_on_reject": True,
        "personal_path_redacted": True,
        "personal_path_in_durable_bytes": False,
        "clean_write_accepted": True,
        "clean_event_id": clean["event_id"],
        "reject_reason": reject_reason,
        "wrote_to_live_events": False,
        "call_site": "command-center/p2-wave/probes/ARC-0086/eventlog.py:append_record",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "secret_rejected=True path_redacted=True canary_in_log=False "
        "clean_accepted=True"
    )
    print("SUCCESS:ARC-0086-probe2 redaction control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
