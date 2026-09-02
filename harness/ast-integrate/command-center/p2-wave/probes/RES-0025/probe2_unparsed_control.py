#!/usr/bin/env python3
"""Probe 2: unparsed files are counted, not dropped (both-states control)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import sampler as S  # noqa: E402

ART = REPO / "command-center/research/RES-0025.json"
BAD = HERE / "fixtures" / "unparseable.mdc"


def main() -> int:
    if not BAD.is_file() or BAD.stat().st_size <= 0:
        print("FAILED:RES-0025-probe2 unparseable fixture missing")
        return 1

    green = S.sample_public_rules()
    red = S.sample_public_rules(extra_files=[(BAD, "fixtures/unparseable.mdc")])

    print(
        "green unparsed_count="
        f"{green['unparsed_count']} attempted={green['attempted']} "
        f"files={len(green['files'])}"
    )
    print(
        "red unparsed_count="
        f"{red['unparsed_count']} attempted={red['attempted']} "
        f"files={len(red['files'])}"
    )

    if green["dropped_files"] != 0 or red["dropped_files"] != 0:
        print("FAILED:RES-0025-probe2 sampler dropped files")
        return 1
    if len(green["files"]) != green["attempted"]:
        print("FAILED:RES-0025-probe2 green files[] dropped entries")
        return 1
    if len(red["files"]) != red["attempted"]:
        print("FAILED:RES-0025-probe2 red files[] dropped entries")
        return 1
    if green["parsed_count"] + green["unparsed_count"] != green["attempted"]:
        print("FAILED:RES-0025-probe2 green parsed+unparsed != attempted")
        return 1
    if red["parsed_count"] + red["unparsed_count"] != red["attempted"]:
        print("FAILED:RES-0025-probe2 red parsed+unparsed != attempted")
        return 1
    if red["attempted"] != green["attempted"] + 1:
        print("FAILED:RES-0025-probe2 extra file did not increment attempted")
        return 1
    if red["unparsed_count"] != green["unparsed_count"] + 1:
        print("FAILED:RES-0025-probe2 malformed file not counted as unparsed")
        return 1
    if "fixtures/unparseable.mdc" not in red["unparsed_paths"]:
        print("FAILED:RES-0025-probe2 malformed path absent from unparsed_paths")
        return 1
    bad_row = next(f for f in red["files"] if f["path"] == "fixtures/unparseable.mdc")
    if bad_row["parsed"] is not False or not bad_row["unparse_reason"]:
        print("FAILED:RES-0025-probe2 malformed file marked parsed or reason empty")
        return 1

    # Artifact must report the public-sample unparsed count (green), not hide it.
    if not ART.is_file():
        print("FAILED:RES-0025-probe2 research artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:RES-0025-probe2 self-declared {doc.get('state')}")
        return 1
    if int(doc["unparsed_file_count"]) != green["unparsed_count"]:
        print("FAILED:RES-0025-probe2 artifact unparsed_file_count != green sampler")
        return 1
    portable = next(
        (c for c in doc["claims"] if c["id"] == "C-PORTABLE-SUBSET"),
        None,
    )
    if portable is None or portable.get("verdict") != "CONFIRMED":
        print("FAILED:RES-0025-probe2 portable-subset claim missing")
        return 1
    if len(portable.get("rails") or []) < 2:
        print("FAILED:RES-0025-probe2 portable-subset claim single-rail")
        return 1
    print("unparsed_counted_not_dropped=True both_states=True")
    print("SUCCESS:RES-0025-probe2 unparsed-file control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
