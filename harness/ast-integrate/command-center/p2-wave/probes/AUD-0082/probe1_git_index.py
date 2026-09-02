#!/usr/bin/env python3
"""Probe 1: path-string classifier over the git index (no os.path.relpath).

The classifier must flag a NUL component and a 300-character path. A crash or a
zero count on that fixture is the failure class this unit exists to prevent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402

UID = "AUD-0082"
ART = REPO / "command-center/audit/AUD-0082-windows-path-hazard-census.json"
SENTINEL = (
    "SUCCESS:AUD-0082 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
RAW = HERE / "probe1-git-index.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0082-probe1 {msg}")
    return 1


def main() -> int:
    live = C.probe1_live(REPO)
    RAW.write_text(json.dumps(live, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(live, sort_keys=True))
    if not live.get("pass"):
        return fail("classifier/enumerator control did not pass")
    ctl = live.get("control") or {}
    if not ctl.get("nul_found") or not ctl.get("long_found"):
        return fail("fixture NUL or 300-char path not enumerated")
    if not ctl.get("naive_went_red"):
        return fail("naive relpath enumerator did not go red on NUL")
    census = live.get("census") or {}
    if int(census.get("classified") or 0) <= 0:
        return fail("index/path-string census classified zero paths")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("artifact not an object")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if doc.get("unit_id") != UID:
        return fail(f"unit_id {doc.get('unit_id')}")
    recorded = ((doc.get("report") or {}).get("probe1") or {}).get("census") or {}
    if int(recorded.get("classified") or -1) != int(census["classified"]):
        return fail(
            f"artifact classified {recorded.get('classified')} != live {census['classified']}"
        )
    print(
        "SUCCESS:AUD-0082-probe1 git-index classifier; "
        f"classified={census['classified']} reserved={census['reserved_count']} "
        f"long={census['long_path_count']} case={census['case_collision_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
