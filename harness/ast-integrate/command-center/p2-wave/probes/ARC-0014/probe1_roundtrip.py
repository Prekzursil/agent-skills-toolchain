#!/usr/bin/env python3
"""Named probe 1: extract then regenerate; byte-compare five real files.

Signal 1 is sha256(source) vs sha256(regenerated). Signal 2 is the LF-normalised
line-set remainder. Disagreement between those two readings is BLOCKED, not a
picked winner. Live-unique remainder must be queued; TAKE-REGENERATED is refused.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from extract import (  # noqa: E402
    ADJUDICATE,
    LIVE_LARGER_REL,
    LIVE_UNIQUE_LINE,
    artifact_sample,
    refuse_drop_remainder,
    round_trip_tree,
)
from scenario import build_live_tree  # noqa: E402

ART = REPO / "command-center/phase3/A2/MIGRATION.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0014-probe1 migration artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "ARC-0014":
        print("FAILED:ARC-0014-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:ARC-0014" not in json.dumps(doc):
        print("FAILED:ARC-0014-probe1 sentinel absent")
        return 1

    with tempfile.TemporaryDirectory(prefix="arc0014-p1-") as tmp:
        root = Path(tmp)
        build_live_tree(root)
        rows = round_trip_tree(root / "live")

    identical = [r for r in rows if r["byte_identical"]]
    adjudicated = [r for r in rows if r["decision"] == ADJUDICATE]
    live_larger = [r for r in rows if r["live_larger"]]
    disagree = [r for r in rows if r.get("signal_disagreement")]
    failed = [r["path"] for r in rows if not r["unique_lines_preserved"]]

    if len(rows) != 5:
        print(f"FAILED:ARC-0014-probe1 sample_size={len(rows)} want=5")
        return 1
    if disagree:
        print("FAILED:ARC-0014-probe1 signal disagreement (BLOCKED, not picked)")
        print(json.dumps(disagree, indent=2, default=str)[:2000])
        return 1
    if failed:
        print(f"FAILED:ARC-0014-probe1 unique lines not held {failed}")
        return 1
    if len(identical) < 4:
        print(f"FAILED:ARC-0014-probe1 byte_identical={len(identical)} want>=4")
        return 1
    if not any(r["path"] == LIVE_LARGER_REL for r in live_larger):
        print(f"FAILED:ARC-0014-probe1 live-larger missing { [r['path'] for r in live_larger] }")
        return 1
    if not any(r["path"] == LIVE_LARGER_REL and r["decision"] == ADJUDICATE for r in rows):
        print("FAILED:ARC-0014-probe1 live-larger was not adjudicated")
        return 1

    larger = next(r for r in rows if r["path"] == LIVE_LARGER_REL)
    if LIVE_UNIQUE_LINE not in (larger.get("live_unique_lines") or []):
        print("FAILED:ARC-0014-probe1 live unique line not in remainder")
        return 1
    neg = refuse_drop_remainder(larger)
    if not neg["pass"] or not neg["refused"]:
        print("FAILED:ARC-0014-probe1 negative control did not refuse drop-remainder")
        print(json.dumps(neg, indent=2))
        return 1

    recorded = {r["path"]: r for r in artifact_sample(doc)}
    for rec in rows:
        got = recorded.get(rec["path"])
        if not got:
            print(f"FAILED:ARC-0014-probe1 artifact missing sample row {rec['path']}")
            return 1
        if got.get("source_sha256") != rec["source_sha256"]:
            print(f"FAILED:ARC-0014-probe1 sha mismatch vs artifact {rec['path']}")
            return 1
        if bool(got.get("byte_identical")) != rec["byte_identical"]:
            print(f"FAILED:ARC-0014-probe1 byte_identical drift {rec['path']}")
            return 1

    out = {
        "probe": "probe1-roundtrip",
        "unit_id": "ARC-0014",
        "files_checked": len(rows),
        "byte_identical": len(identical),
        "adjudicated": len(adjudicated),
        "live_larger_in_sample": len(live_larger),
        "live_larger_paths": [r["path"] for r in live_larger],
        "negative_control_refused": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    for rec in rows:
        print(
            f"file {rec['path']} identical={rec['byte_identical']} "
            f"decision={rec['decision']} live_larger={rec['live_larger']} "
            f"live_unique={len(rec['live_unique_lines'])}"
        )
    print("SUCCESS:ARC-0014-probe1 round-trip fidelity and refuse-drop-remainder")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
