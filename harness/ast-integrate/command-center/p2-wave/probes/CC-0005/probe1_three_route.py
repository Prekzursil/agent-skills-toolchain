#!/usr/bin/env python3
"""Probe 1: three-route bytes + byte-delta control.

Hashes cited here come from `git cat-file -p`. git archive is the negative
control. Mechanically independent of probe 2 (gate both-states).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/CC-0005.json"
RAW = HERE / "probe1-three-route.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:CC-0005-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CC-0005":
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:CC-0005" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    live = S.measure()
    RAW.write_text(json.dumps(live, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    fails = S.failures(live)
    route_fails = [
        f
        for f in fails
        if f
        in {
            "git show != git cat-file",
            "git archive unexpectedly equals cat-file",
            "pre-fix delta != line count",
            "blob is not LF",
            "archive CRLF count != line count",
            "control sizes drifted from 3737/3837",
            "silent path did not hash via git-cat-file",
        }
    ]
    if route_fails:
        return fail("; ".join(route_fails))
    if live["blob_sha256_via"] != "git cat-file -p HEAD:" + S.REL:
        return fail("hash not cited via cat-file")
    cited = ((doc.get("three_route") or {}).get("git_cat_file") or {})
    if cited.get("sha256") != live["blob_sha256"]:
        return fail("receipt blob sha256 is stale vs live cat-file")
    print(
        "cat_file_bytes={blob_bytes} crlf={blob_crlf} sha256={blob_sha256} via={blob_sha256_via} "
        "show_equals={show_equals_cat_file} archive_bytes={archive_bytes} archive_crlf={archive_crlf} "
        "delta={pre_fix_delta_bytes} lines={line_count} delta_equals_lines={delta_equals_line_count}".format(
            **live
        )
    )
    print("SUCCESS:CC-0005-probe1 three-route cat-file vs archive byte-delta")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
