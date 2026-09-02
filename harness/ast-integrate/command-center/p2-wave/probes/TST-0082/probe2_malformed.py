#!/usr/bin/env python3
"""Probe 2: $schema hooks.json loads zero hooks while files still look installed.

Both-states: the same trigger against a healthy config must still fire, so a
probe silent in both states cannot pass. A tolerant parse of the malformed
file still sees the registered commands (the installed appearance); strict
load must not execute them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import dispatcher as D  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / S.OUT
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def fail(msg: str) -> int:
    print(f"FAILED:TST-0082-probe2 {msg}")
    return 1


def main() -> int:
    S.ensure_fixtures()
    broken = D.malformed_session(HERE / "captures" / "probe2-malformed-receipt.txt")
    healthy = D.healthy_session(HERE / "captures" / "probe2-healthy-receipt.txt")
    print(
        json.dumps(
            {
                "probe": "probe2-malformed-zero-load",
                "broken": {
                    "rejected_keys": broken["rejected_keys"],
                    "registered_count": broken["registered_count"],
                    "loaded_count": broken["loaded_count"],
                    "fired_count": broken["fired_count"],
                    "reason": broken["reason"],
                    "looks_installed": broken["appearance"]["looks_installed"],
                    "naive": broken["naive_file_count"],
                },
                "healthy": {
                    "loaded_count": healthy["loaded_count"],
                    "fired_count": healthy["fired_count"],
                    "child_written": healthy["child_written"],
                    "reason": healthy["reason"],
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    if "$schema" not in broken["rejected_keys"]:
        return fail(f"rejected_keys={broken['rejected_keys']} want $schema")
    if broken["registered_count"] != len(S.EVENTS):
        return fail(
            f"tolerant-registered={broken['registered_count']} "
            "malformed file must still contain the hook entries"
        )
    if broken["loaded_count"] != 0:
        return fail(f"strict-loaded={broken['loaded_count']} want 0")
    if broken["fired_count"] != 0:
        return fail(f"fired={broken['fired_count']} want 0 on unloaded config")
    if not broken["appearance"]["looks_installed"]:
        return fail("malformed config no longer looks installed")
    if broken["naive_file_count"]["sum"] != healthy["naive_file_count"]["sum"]:
        return fail("naive file counts diverged; listing must not be the discriminator")
    executed_broken = [row for row in broken["runs"] if row.get("executed")]
    if executed_broken:
        return fail("strict-unload still executed a command")
    if healthy["fired_count"] != len(S.EVENTS) or not healthy["child_written"]:
        return fail("healthy-state-silent probe cannot see the broken state")
    if healthy["loaded_count"] == broken["loaded_count"]:
        return fail("silent-in-both-states")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        raw = json.loads(text)
        doc = S.receipt_payload(raw)
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            return fail(f"self-declared {doc.get('state')}")
        if "SUCCESS:TST-0082" not in text:
            return fail("sentinel-absent")
        tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
        row = tests.get("test_malformed_config_is_detected_as_zero_hooks_loaded")
        if not row or row.get("result") != "PASS":
            return fail("receipt-test2-not-pass")
        found = [
            c
            for c in (doc.get("controls") or [])
            if isinstance(c, dict)
            and c.get("id") == "C-SCHEMA-ZERO-LOAD"
            and c.get("verdict") == "found"
        ]
        if not found:
            return fail("receipt-missing-schema-zero-load-found")

    print(
        f"broken_loaded={broken['loaded_count']} broken_fired={broken['fired_count']} "
        f"healthy_fired={healthy['fired_count']} schema_rejected=True"
    )
    print("SUCCESS:TST-0082-probe2 malformed config detected as zero hooks loaded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
