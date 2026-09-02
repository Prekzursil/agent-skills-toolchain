#!/usr/bin/env python3
"""Probe 2: filesystem walk that survives NUL and records index-absent paths.

Independent of probe 1. Must return a non-zero count on a fixture containing a
NUL-named file and a 300-character path. A crash or a zero count is the known
failure this unit exists to prevent.
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
RAW = HERE / "probe2-fs-walk.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0082-probe2 {msg}")
    return 1


def main() -> int:
    live = C.probe2_live(REPO)
    RAW.write_text(json.dumps(live, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(live, sort_keys=True))
    if not live.get("pass"):
        return fail("filesystem enumerator control did not pass")
    ctl = live.get("control") or {}
    if int(ctl.get("production_count") or 0) <= 0:
        return fail("fixture enumerator returned zero")
    if not ctl.get("nul_found"):
        return fail("NUL-named file missing from walk")
    if not ctl.get("long_found") or int(ctl.get("long_rel_len") or 0) < 300:
        return fail("300-character path not enumerated")
    if not ctl.get("naive_went_red"):
        return fail("naive walker did not go red on NUL")
    walk = live.get("walk") or {}
    if walk.get("aborted"):
        return fail(f"repo walk aborted errors={walk.get('errors_sample')}")
    if int(walk.get("file_count") or 0) <= 0:
        return fail("repo walk file_count=0")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact unparseable {exc}")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    recorded = ((doc.get("report") or {}).get("probe2") or {}).get("walk") or {}
    if int(recorded.get("file_count") or -1) != int(walk["file_count"]):
        return fail(
            f"artifact walk file_count {recorded.get('file_count')} != live {walk['file_count']}"
        )
    print(
        "SUCCESS:AUD-0082-probe2 fs-walk; "
        f"files={walk['file_count']} reserved={live['census']['reserved_count']} "
        f"long={live['census']['long_path_count']} "
        f"case={live['census']['case_collision_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
