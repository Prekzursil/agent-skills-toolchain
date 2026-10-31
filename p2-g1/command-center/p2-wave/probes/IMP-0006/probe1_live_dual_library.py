#!/usr/bin/env python3
"""Named probe 1 (IMP-0006): live dual-library schema validation.

The restored .claude-plugin/plugin.json must validate green under the authored
plugin.schema.json via manifest_schema.validate_file (jsonschema Draft 2020-12
PLUS the in-module independent structural checker, labeled fastjsonschema).
Also requires: distinct library identities, no control-plane siblings (no
second manifest file), and a reviewer-authored-from-schema manifest validates
with the Phase-4 optional fields present.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin"))

import manifest_schema as ms  # noqa: E402

UNIT = "IMP-0006"
RECEIPT = REPO / "command-center" / "receipts" / "IMP-0006.json"


def main() -> int:
    if not RECEIPT.is_file() or RECEIPT.stat().st_size < 200:
        print(f"FAILED:{UNIT}-probe1 receipt missing")
        return 1
    text = RECEIPT.read_text(encoding="utf-8")
    if f"SUCCESS:{UNIT}" not in text:
        print(f"FAILED:{UNIT}-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:{UNIT}-probe1 self-declared {st}")
        return 1

    result = ms.validate_file(ms.MANIFEST_PATH)
    if not result.get("ok"):
        print(f"FAILED:{UNIT}-probe1 live manifest fails validation: {result}")
        return 1
    if not result.get("libraries_agree"):
        print(f"FAILED:{UNIT}-probe1 libraries disagree: {result}")
        return 1
    if result["jsonschema"]["library"] == result["fastjsonschema"]["library"]:
        print(f"FAILED:{UNIT}-probe1 library identities not distinct")
        return 1
    siblings = ms.control_plane_siblings()
    if siblings:
        print(f"FAILED:{UNIT}-probe1 duplicate control-plane manifest: {siblings}")
        return 1
    schema = ms.load_schema()
    reviewer = ms.reviewer_authored_manifest()
    rr = ms.validate_instance(reviewer, schema)
    if not rr.get("ok"):
        print(f"FAILED:{UNIT}-probe1 reviewer-authored manifest invalid: {rr['jsonschema']['codes']}")
        return 1
    lm = doc.get("live_manifest") or {}
    row = {
        "unit_id": UNIT,
        "probe": "probe1-live-dual-library",
        "live_manifest_path": ms.MANIFEST_PATH.relative_to(REPO).as_posix(),
        "schema_path": ms.SCHEMA_PATH.relative_to(REPO).as_posix(),
        "jsonschema_ok": result["jsonschema"]["ok"],
        "independent_checker_ok": result["fastjsonschema"]["ok"],
        "libraries_agree": result["libraries_agree"],
        "control_plane_siblings": siblings,
        "reviewer_authored_validates": rr["ok"],
        "recorded_live_manifest_keys": lm.get("keys"),
        "live_keys_now": sorted(ms.live_manifest_object().keys()),
    }
    print(json.dumps(row, indent=1))
    print(f"SUCCESS:{UNIT}-probe1 live dual-library validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
