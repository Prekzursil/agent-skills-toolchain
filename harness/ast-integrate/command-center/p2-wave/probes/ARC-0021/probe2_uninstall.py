#!/usr/bin/env python3
"""Named probe 2: bash cmp/stat preservation + wipe negative control.

Mechanically different from probe 1: bash `cmp -s` and `stat -c %s` rather
than Python sha256. If the two readings disagree, BLOCKED with both numbers.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from adopt import adopt_estate  # noqa: E402
from estate import OWNER_NOTE, PRESERVE_RELS, build_estate  # noqa: E402
from uninstall import (  # noqa: E402
    legal_uninstall,
    negative_control,
    preservation_report,
    snapshot_preserve,
)

ART = REPO / "command-center/phase3/A3/MIGRATION.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:ARC-0021-probe2 migration artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "ARC-0021":
        print("FAILED:ARC-0021-probe2 unit_id", doc.get("unit_id"))
        return 1

    with tempfile.TemporaryDirectory(prefix="arc0021-p2-") as tmp:
        root = Path(tmp)
        estate = root / "estate"
        snap = root / "snap"
        build_estate(estate)
        adopt_estate(estate)
        snapshot_preserve(estate, snap)
        legal_uninstall(estate)
        report = preservation_report(estate, snap)
        if report.get("signal_disagreement"):
            print("FAILED:ARC-0021-probe2 signal disagreement (BLOCKED, not picked)")
            print(
                json.dumps(
                    {
                        "signal1_sha256_intact": report["signal1_sha256_intact"],
                        "signal2_cmp_intact": report["signal2_cmp_intact"],
                    },
                    indent=2,
                )
            )
            return 1
        if not report["pass"]:
            print("FAILED:ARC-0021-probe2 preservation")
            print(json.dumps(report, indent=2, default=str)[:2500])
            return 1

        wipe_estate = root / "wipe"
        wipe_snap = root / "wipe-snap"
        build_estate(wipe_estate)
        adopt_estate(wipe_estate)
        snapshot_preserve(wipe_estate, wipe_snap)
        neg = negative_control(wipe_estate, wipe_snap)
        if not neg.get("pass") or not neg.get("caught"):
            print("FAILED:ARC-0021-probe2 negative control did not catch wipe")
            print(json.dumps(neg, indent=2))
            return 1
        if (wipe_estate / OWNER_NOTE).is_file():
            print("FAILED:ARC-0021-probe2 wipe did not remove owner overlay")
            return 1

    tests = doc.get("tests") or {}
    rec_p = tests.get("preservation") or {}
    rec_n = tests.get("negative_control") or {}
    if rec_p.get("signal2_cmp_intact") != report["signal2_cmp_intact"]:
        print("FAILED:ARC-0021-probe2 artifact signal2 drift")
        return 1
    if rec_p.get("signal1_sha256_intact") != report["signal1_sha256_intact"]:
        print(
            "FAILED:ARC-0021-probe2 readings disagree with artifact "
            f"s1={report['signal1_sha256_intact']} "
            f"art={rec_p.get('signal1_sha256_intact')}"
        )
        return 1
    if rec_n.get("would_have_removed") != OWNER_NOTE:
        print("FAILED:ARC-0021-probe2 artifact negative path drift")
        return 1
    if not rec_n.get("caught"):
        print("FAILED:ARC-0021-probe2 artifact negative control not caught")
        return 1

    out = {
        "probe": "probe2-bash-cmp-uninstall",
        "unit_id": "ARC-0021",
        "signal2_cmp_intact": report["signal2_cmp_intact"],
        "signal1_sha256_intact": report["signal1_sha256_intact"],
        "preserve": list(PRESERVE_RELS),
        "negative_control_caught": True,
        "would_have_removed": OWNER_NOTE,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"cmp_intact={out['signal2_cmp_intact']} "
        f"sha256_intact={out['signal1_sha256_intact']} "
        f"caught_wipe={OWNER_NOTE}"
    )
    print("SUCCESS:ARC-0021-probe2 bash cmp preservation and wipe negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
