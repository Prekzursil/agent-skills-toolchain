#!/usr/bin/env python3
"""Probe 2: create_connection + strace, plus payload-not-stored scan of the artifact.

Mechanically different from probe 1 (high-level create_connection / syscall
trace rather than a socket.socket subclass). Does not rewrite the artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402


def main() -> int:
    live = M.run("create_connection")
    M.require_live(live, "probe2")
    strace = M.strace_declared_control()
    if not M.ART.is_file():
        print("FAILED:CNF-0115 capture-incomplete artifact-absent")
        return 1
    raw = M.ART.read_bytes()
    if M.USER_MARKER.encode("ascii") in raw:
        print("FAILED:CNF-0115 contract-violation captured-marker-stored-in-artifact")
        return 1
    doc = json.loads(raw.decode("utf-8"))
    honest = M.assert_artifact_honest(doc)
    if honest:
        print("FAILED:CNF-0115 contract-violation " + " ".join(honest))
        return 1
    schema_errs = M.validate_schema(doc)
    if schema_errs:
        print("FAILED:CNF-0115 schema-invalid " + " | ".join(schema_errs[:8]))
        return 1
    if doc.get("payload_bytes_stored") is not False:
        print("FAILED:CNF-0115 contract-violation payload_bytes_stored")
        return 1
    insp = doc.get("payload_inspection") or {}
    if insp.get("undeclared_plant_contained_user_content") is not True:
        print("FAILED:CNF-0115 detector-failure artifact-plant-marker-not-recorded")
        return 1
    if insp.get("declared_event_contained_user_content") is not False:
        print("FAILED:CNF-0115 contract-violation declared-event-user-content")
        return 1
    if strace.get("available") and not strace.get("ptrace_denied"):
        if not strace.get("declared_event_observed"):
            print("FAILED:CNF-0115 capture-incomplete strace-missed-declared-event")
            return 1
    print(
        json.dumps(
            {
                "instrument": "create_connection",
                "declared_event_observed": live["declared_event_observed"],
                "undeclared_plant_observed": live["undeclared_plant_observed"],
                "strace": {
                    "available": strace.get("available"),
                    "declared_event_observed": strace.get("declared_event_observed"),
                    "ptrace_denied": strace.get("ptrace_denied"),
                },
                "payload_bytes_stored": False,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0115-probe2 independent-capture payload-not-stored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
