#!/usr/bin/env python3
"""Probe 1: live .claude-plugin/plugin.json validates under two libraries.

Catalog signal (1): the live plugin.json is green under the new schema.
Catalog signal (2): a second JSON-Schema library reaches the same verdict.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import manifest_schema as ms  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0006.json"
SENTINEL = "SUCCESS:IMP-0006"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0006-probe1 {msg}")
    return 1


def check_receipt() -> str | None:
    if not ART.is_file() or ART.stat().st_size < 200:
        return "receipt missing"
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return "sentinel absent"
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable:{exc}"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{st}"
    return None


def main() -> int:
    err = check_receipt()
    if err:
        return fail(err)

    if not ms.MANIFEST_PATH.is_file():
        return fail("live plugin.json missing")
    if not ms.SCHEMA_PATH.is_file():
        return fail("plugin.schema.json missing")

    live = ms.live_manifest_object()
    result = ms.validate_file(ms.MANIFEST_PATH)
    payload = {
        "probe": "probe1-live-dual-library",
        "unit_id": "IMP-0006",
        "path": ".claude-plugin/plugin.json",
        "schema": ".claude-plugin/plugin.schema.json",
        "keys": sorted(live.keys()),
        "key_count": len(live.keys()),
        "version": live.get("version"),
        "libraries": {
            "jsonschema": result["jsonschema"],
            "fastjsonschema": result["fastjsonschema"],
        },
        "ok": result["ok"],
        "libraries_agree": result["libraries_agree"],
        "duplicate_key": result["duplicate_key"],
        "second_manifest_files": ms.control_plane_siblings(),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    if not result["ok"]:
        return fail("live manifest not valid")
    if not result["libraries_agree"]:
        return fail("libraries disagree on live file")
    if result["jsonschema"]["library"] == result["fastjsonschema"]["library"]:
        return fail("libraries are not independent")
    if payload["second_manifest_files"]:
        return fail(f"second manifest file: {payload['second_manifest_files']}")
    print("SUCCESS:IMP-0006-probe1 live plugin.json green under jsonschema and fastjsonschema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
