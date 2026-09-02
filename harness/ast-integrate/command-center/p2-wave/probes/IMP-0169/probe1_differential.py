#!/usr/bin/env python3
"""Named probe 1: hostile vs benign render differential is confined to DATA."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from fixtures import benign_imports, hostile_imports  # noqa: E402
from import_quarantine import (  # noqa: E402
    CANARY,
    HOSTILE_INSTRUCTION,
    data_spans,
    differential,
    payload_bytes,
    render_prompt,
    unquoted_hits,
    utf8,
)


def main() -> int:
    benign = render_prompt(benign_imports())
    hostile = render_prompt(hostile_imports())
    b, h = benign.raw, hostile.raw
    diff = differential(b, h)

    canary = utf8(CANARY)
    needle = utf8(HOSTILE_INSTRUCTION)
    present_in_data = False
    for span in data_spans(h):
        payload = payload_bytes(h, span.source_id)
        if canary in payload and needle in payload:
            present_in_data = True
            break

    unquoted = unquoted_hits(h)
    ok = (
        diff["non_vacuous"]
        and diff["all_diffs_inside_data"]
        and diff["directives_identical"]
        and present_in_data
        and canary in h
        and not unquoted
        and canary not in b
    )
    report = {
        "probe": "probe1-differential",
        "unit_id": "IMP-0169",
        "pass": ok,
        "differential": diff,
        "canary_in_hostile_bytes": canary in h,
        "canary_in_benign_bytes": canary in b,
        "canary_in_a_data_payload": present_in_data,
        "unquoted_hits_on_quoted_hostile": len(unquoted),
        "benign_bytes": len(b),
        "hostile_bytes": len(h),
        "source_classes": [i.source_class for i in hostile_imports()],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not ok:
        print("FAILED:IMP-0169-probe1 differential not confined to DATA or vacuous")
        return 1
    print("SUCCESS:IMP-0169-probe1 hostile payload confined to quoted DATA region")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
