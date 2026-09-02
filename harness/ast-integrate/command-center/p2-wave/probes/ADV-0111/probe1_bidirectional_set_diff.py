#!/usr/bin/env python3
"""Probe 1: bidirectional set difference plus size/hash on the intersection.

Control: a listed-and-present file must verify; a deliberately unlisted file
must appear in disk_only. A one-way manifest-to-disk check is silent on the
unlisted file and is therefore not this probe. Live ARTIFACT-MANIFEST.json
is censused honestly (absence is REFUTED, not BLOCKED).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import UNIT, probe1_payload  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    payload = probe1_payload()
    print(json.dumps(payload, sort_keys=True))
    if not payload["listed_verified"]:
        return fail("listed-and-present control did not verify")
    if not payload["unlisted_in_disk_only"]:
        return fail("deliberately unlisted file not in disk_only")
    if payload["good_verified_paths"] != ["listed.txt"]:
        return fail(f"verified={payload['good_verified_paths']}")
    if payload["good_disk_only"] != ["unlisted.txt"]:
        return fail(f"disk_only={payload['good_disk_only']}")
    if payload["good_manifest_only"]:
        return fail(f"good manifest_only={payload['good_manifest_only']}")
    if not payload["one_way_silent_on_unlisted"]:
        return fail("one-way check did not stay silent on the unlisted file")
    if not payload["bidirectional_catches_unlisted"]:
        return fail("bidirectional check did not catch the unlisted file")
    if not payload["missing_listed_in_manifest_only"]:
        return fail("missing listed file did not appear in manifest_only")
    live = payload["live"]
    if live["manifest_exists"] is False and live["verdict"] != "REFUTED":
        return fail("absent live manifest must be REFUTED, not BLOCKED")
    if live["disk_count"] < 1:
        return fail("live artifact roots produced an empty disk set")
    if not payload["pass"]:
        return fail("control conjunction failed")
    print(
        f"listed_verified=True unlisted_in_disk_only=True "
        f"one_way_silent={payload['one_way_silent_on_unlisted']} "
        f"live_exists={live['manifest_exists']} live_verdict={live['verdict']} "
        f"disk_only_count={live['disk_only_count']}"
    )
    print("SUCCESS:ADV-0111-probe1 bidirectional-set-diff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
