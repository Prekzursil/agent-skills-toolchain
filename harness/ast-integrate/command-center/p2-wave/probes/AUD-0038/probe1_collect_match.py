#!/usr/bin/env python3
"""Probe 1: string-match TEST-REGISTRY node IDs against pytest --collect-only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = E.REPO / "command-center/audit/AUD-0038-test-registry-resolution.json"
SENTINEL = (
    "SUCCESS:AUD-0038 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0038-probe1 {msg}")
    return 1


def main() -> int:
    data = E.resolve()
    ctrl = E.control_ok(data)
    live_ids = [r["test_id"] for r in data["live_matched"]]
    payload = {
        "probe": "probe1-collect-string-match",
        "unit_id": "AUD-0038",
        "registry_entry_count": data["registry"]["entry_count"],
        "collect_returncode": data["collect"]["returncode"],
        "nodeid_count": data["collect"]["nodeid_count"],
        "nodeids": data["collect"]["nodeids"],
        "live_matched_test_ids": live_ids,
        "live_missing_test_ids": [r["test_id"] for r in data["live_missing"]],
        "ghost_collectible": data["ghost"]["collectible"],
        "ghost_test_id": E.GHOST_TEST_ID,
        "ghost_in_collect_nodeids": any(
            nid.endswith("::" + E.GHOST_TEST_ID) for nid in data["collect"]["nodeids"]
        ),
        "mention_trap_collectible": data["mention_trap"]["collectible"],
        "grep_trap_would_false_positive": data["grep_trap"][
            "ghost_test_id_in_file_text"
        ],
        "always_present_mutant_counts_ghost": data[
            "always_present_mutant_counts_ghost"
        ],
        "setup_error_collectible": data["setup_error_control"]["collectible"],
        "pass": ctrl["pass"] if ctrl["execution_discriminates"] is None else (
            ctrl["ghost_reported_missing"]
            and ctrl["live_all_collectible"]
            and ctrl["grep_of_mention_trap_would_false_positive"]
            and ctrl["always_present_mutant_rejected"]
            and ctrl["setup_error_collectible"]
        ),
    }
    print(json.dumps(payload, sort_keys=True))

    if data["registry"]["entry_count"] < 1:
        return fail("empty TEST-REGISTRY")
    if data["collect"]["nodeid_count"] < 1:
        print(data["collect"]["raw"][-2000:])
        return fail("collector produced zero nodeids")
    if payload["live_missing_test_ids"]:
        return fail(f"live missing {payload['live_missing_test_ids']}")
    if len(live_ids) != data["registry"]["entry_count"]:
        return fail("live match count != registry entry count")
    if payload["ghost_collectible"] or payload["ghost_in_collect_nodeids"]:
        return fail("ghost node counted present")
    if not payload["grep_trap_would_false_positive"]:
        return fail("mention-trap file no longer contains ghost test_id")
    if not payload["always_present_mutant_counts_ghost"]:
        return fail("always-present mutant did not fire on ghost")
    if not payload["setup_error_collectible"]:
        return fail("setup-error control not collectible")
    if not payload["mention_trap_collectible"]:
        return fail("mention-trap test not collectible")
    raw = data["collect"]["raw"]
    for row in data["live"]:
        needle = f"::{row['test_id']}"
        if needle not in raw:
            return fail(f"string-match miss in collect output: {needle}")
    if f"::{E.GHOST_TEST_ID}" in raw:
        # collect-only -q must not emit the ghost as a nodeid component
        if any(nid.endswith("::" + E.GHOST_TEST_ID) for nid in data["collect"]["nodeids"]):
            return fail("ghost nodeid in collect output")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            return fail(f"artifact unparseable:{type(exc).__name__}")
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"artifact state={doc.get('state')}")
        if SENTINEL not in text:
            return fail("completion sentinel absent")
        print(f"artifact_state={doc.get('state')} bytes={ART.stat().st_size}")

    print(
        f"matched={len(live_ids)} ghost_missing={not payload['ghost_collectible']} "
        f"setup_collectible={payload['setup_error_collectible']}"
    )
    print("SUCCESS:AUD-0038-probe1 collect string-match; ghost reported missing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
