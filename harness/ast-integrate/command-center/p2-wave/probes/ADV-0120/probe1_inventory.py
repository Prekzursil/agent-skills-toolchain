#!/usr/bin/env python3
"""Probe 1: inventory unrelated components before vs after uninstall.

File hashes of third-party hooks / MCP / skills must be unchanged. Shared
JSON may change (victim keys removed). A listing of the victim tree is not
this probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import drill as D  # noqa: E402

ART = REPO / "command-center/adversarial/ADV-0120-uninstall-collateral-damage.json"
SENTINEL = "SUCCESS:ADV-0120"


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0120-probe1 {msg}")
    return 1


def main() -> int:
    report = D.measure()
    payload = {
        "production_inventory_intact": report["production_inventory_intact"],
        "naive_inventory_intact": report["naive_inventory_intact"],
        "production_removed": report["production"]["inventory"]["removed"],
        "production_modified": report["production"]["inventory"]["modified"],
        "production_victim_removed": report["production_victim_removed"],
        "production_shared_docs_remain": report["production_shared_docs_remain"],
        "path_escape_refused": report["refusals"]["path_escape_refused"],
        "unmarked_profile_refused": report["refusals"]["unmarked_profile_refused"],
        "live_profile_touched": report["live_profile_touched"],
        "pass": (
            report["production_inventory_intact"]
            and report["naive_inventory_intact"]
            and report["production_victim_removed"]
            and report["production_shared_docs_remain"]
            and report["refusals"]["path_escape_refused"]
            and report["refusals"]["unmarked_profile_refused"]
            and not report["live_profile_touched"]
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    if not payload["pass"]:
        return fail("unrelated-file inventory damaged or safety refuse failed")
    if report["production"]["inventory"]["removed"]:
        return fail("production uninstall removed unrelated files")
    if report["production"]["inventory"]["modified"]:
        return fail("production uninstall modified unrelated files")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    measured = doc.get("measured") or {}
    if measured.get("production_inventory_intact") is not True:
        return fail("artifact inventory flag drifted")
    if measured.get("production_victim_removed") is not True:
        return fail("artifact victim_removed drifted")

    print(
        "intact=True victim_gone="
        f"{payload['production_victim_removed']} "
        f"shared_remain={payload['production_shared_docs_remain']}"
    )
    print("SUCCESS:ADV-0120-probe1 unrelated-file inventory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
