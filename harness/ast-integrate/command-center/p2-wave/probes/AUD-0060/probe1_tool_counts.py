#!/usr/bin/env python3
"""Probe 1: tool count and serialized schema size per connected server.

Re-runs the stdio enumerator. A zero count on the known-connected fixture means
the enumerator is not reaching MCP servers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixture_server import EXPECTED_COUNT, EXPECTED_NAMES  # noqa: E402
from inventory import measure  # noqa: E402

UNIT = "AUD-0060"
ART = REPO / "command-center/audit/AUD-0060-mcp-tool-surface-inventory.json"
SENTINEL = (
    "SUCCESS:AUD-0060 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    live = measure()
    print(json.dumps({"live": live}, sort_keys=True, default=str)[:12000])
    if not live["control"]["pass"]:
        return fail("enumerator control does not discriminate mute=0 vs fixture=3")
    if live["fixture"]["summary"]["tool_count"] != EXPECTED_COUNT:
        return fail(f"fixture count {live['fixture']['summary']['tool_count']}")
    if live["fixture"]["names"] != EXPECTED_NAMES:
        return fail(f"fixture names {live['fixture']['names']}")
    if live["mute"]["tool_count"] != 0:
        return fail("mute process produced a non-zero tool count")
    if live["zero_across_connected_servers"]:
        return fail("zero tools across all connected servers; enumerator not reaching them")

    if not ART.is_file():
        return fail(f"artifact absent {ART}")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    headline = (doc.get("report") or {}).get("headline") or {}
    if headline.get("control_fixture_tool_count") != EXPECTED_COUNT:
        return fail("artifact fixture count mismatch")
    if headline.get("mute_process_tool_count") != 0:
        return fail("artifact mute count mismatch")
    named = doc.get("named_probes") or []
    if len(named) < 2:
        return fail("named probes missing from artifact")
    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe1-tool-counts",
                "unit_id": UNIT,
                "fixture_tool_count": EXPECTED_COUNT,
                "mute_tool_count": 0,
                "estate_declared_servers": live["estate"]["declared_server_rows"],
                "connected_servers": live["connected_server_count"],
                "schema_bytes": live["headline_schema_bytes_connected"],
                "schema_tokens": live["headline_schema_tokens_connected"],
                "token_method": live["fixture"]["summary"]["token_method"],
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:AUD-0060-probe1 enumerator reaches known-connected fixture; "
        f"count={EXPECTED_COUNT}; mute=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
