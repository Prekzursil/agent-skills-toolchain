#!/usr/bin/env python3
"""Probe 2: partial work is preserved across every injected fault.

Independent of probe 1's classification table: seed a committed artifact,
inject each fault, assert the committed digest is unchanged and staging is
never promoted. Truncation and mid-stream RST must leave staging bytes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / "command-center/receipts/TST-0098.json"


def main() -> int:
    cells = H.run_matrix(HERE / "runtime" / "probe2")
    ok, why = H.partial_ok(cells)
    mid = [
        c
        for c in cells
        if c["fault"] in {"truncated_response", "mid_stream_disconnect"}
    ]
    print(
        json.dumps(
            {
                "n_cells": len(cells),
                "partial_ok": ok,
                "why": why,
                "mid_body_staging_bytes": [
                    {
                        "boundary": c["boundary"],
                        "fault": c["fault"],
                        "staging_bytes": c["staging_bytes"],
                    }
                    for c in mid
                ],
            },
            sort_keys=True,
        )
    )
    if not ok:
        print(f"FAILED:TST-0098-probe2 partial {why}")
        for c in cells:
            if (
                not c["committed_unchanged"]
                or c["staging_promoted"]
                or (
                    c["fault"] in {"truncated_response", "mid_stream_disconnect"}
                    and c["staging_bytes"] <= 0
                )
            ):
                print(c)
        return 1
    if not ART.is_file():
        print("FAILED:TST-0098-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    pw = doc.get("partial_work") or {}
    if pw.get("all_committed_unchanged") is not True:
        print("FAILED:TST-0098-probe2 receipt partial_work flag false")
        return 1
    if pw.get("any_staging_promoted_on_fault") is True:
        print("FAILED:TST-0098-probe2 receipt claims a promotion on fault")
        return 1
    rec_cells = ((doc.get("matrix") or {}).get("cells")) or []
    live_by = {(c["boundary"], c["fault"]): c for c in cells}
    for rc in rec_cells:
        live = live_by.get((rc["boundary"], rc["fault"]))
        if live is None:
            print(f"FAILED:TST-0098-probe2 missing live cell {rc}")
            return 1
        if rc.get("committed_unchanged") is not True:
            print(f"FAILED:TST-0098-probe2 receipt committed mutated {rc}")
            return 1
        if live["committed_unchanged"] is not True:
            print(f"FAILED:TST-0098-probe2 live committed mutated {live}")
            return 1
    print("SUCCESS:TST-0098-probe2 partial work preserved on every fault")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
