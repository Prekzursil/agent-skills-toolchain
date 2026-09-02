#!/usr/bin/env python3
"""Named probe 1: CRLF falsification + live engine vs receipt.

Mechanically different from probe 2: uses the in-tree python -m style runner
and the LF-normalise experiment. Does not invoke the CI console script.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from revalidate import revalidate  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0024.json"
SENTINEL = "SUCCESS:BLD-0024"


def main() -> int:
    live = revalidate()
    if live["eight_count"] != 8:
        print(f"FAILED:BLD-0024-probe1 eight_count={live['eight_count']}")
        return 1
    if not live["crlf_lf_green"]:
        print("FAILED:BLD-0024-probe1 CRLF dismissals not LF-green")
        return 1
    crlf = [d for d in live["dismissals"] if d["class"] == "windows-crlf"]
    if len(crlf) != 3:
        print(f"FAILED:BLD-0024-probe1 crlf_n={len(crlf)}")
        return 1
    for row in crlf:
        if row["as_is"]["outcome"] != "FAIL":
            print(f"FAILED:BLD-0024-probe1 {row['id']} as_is not FAIL")
            return 1
        if row["lf_norm"]["outcome"] != "PASS":
            print(f"FAILED:BLD-0024-probe1 {row['id']} lf_norm not PASS")
            return 1
        if row["verdict"] != "HOLDS":
            print(f"FAILED:BLD-0024-probe1 {row['id']} verdict {row['verdict']}")
            return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:BLD-0024-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:BLD-0024-probe1 sentinel-absent")
        return 1
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:BLD-0024-probe1 self-declared {doc.get('state')}")
        return 1
    art_crlf = [d for d in doc.get("dismissals") or [] if d.get("class") == "windows-crlf"]
    if len(art_crlf) != 3:
        print("FAILED:BLD-0024-probe1 artifact CRLF count")
        return 1
    live_verdicts = {d["id"]: d["verdict"] for d in live["dismissals"]}
    for row in doc.get("dismissals") or []:
        if live_verdicts.get(row["id"]) != row.get("verdict"):
            print(f"FAILED:BLD-0024-probe1 verdict drift {row['id']}")
            return 1

    printable = {
        "probe": "probe1-lf-falsify",
        "unit_id": "BLD-0024",
        "crlf_holds": [d["id"] for d in crlf],
        "lf_green": True,
        "eight_count": live["eight_count"],
        "counts": live["counts"],
        "pass": True,
    }
    print(json.dumps(printable, sort_keys=True))
    print("SUCCESS:BLD-0024-probe1 CRLF LF-normalise falsification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
