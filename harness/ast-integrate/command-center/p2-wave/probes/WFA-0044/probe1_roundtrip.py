#!/usr/bin/env python3
"""Probe 1: all 10 corpus files parse, re-render, and match field-by-field.

A self-scored round-trip is evidence A, not evidence B (see probe 2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import ir as IR  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0044-probe1 {msg}")
    return 1


def main() -> int:
    info_rows = C.load_texts()
    disc = C.discover()
    if len(info_rows) != 10:
        return fail(f"corpus n={len(info_rows)} expected 10 names={disc.get('names')}")
    results = []
    for row in info_rows:
        sem = IR.parse_source(row["text"], row["path"])
        ir_doc = IR.to_ir(sem)
        errs = IR.validate_anchors(ir_doc)
        if errs:
            return fail(f"{row['name']} anchors {errs[:5]}")
        rendered = IR.render_source(sem)
        sem2 = IR.parse_source(rendered, row["path"])
        mismatches = IR.field_by_field(sem, sem2)
        if mismatches:
            return fail(f"{row['name']} round-trip {mismatches[:4]}")
        back = IR.from_ir(ir_doc)
        ir_mismatch = IR.field_by_field(sem, back)
        if ir_mismatch:
            return fail(f"{row['name']} ir-round-trip {ir_mismatch[:4]}")
        results.append(
            {
                "name": row["name"],
                "n_constructs": len(sem["constructs"]),
                "n_nodes": len(ir_doc["nodes"]),
                "lossy": IR.lossy_codes(sem),
                "kinds": [c["kind"] for c in sem["constructs"]],
            }
        )
    kinds_seen = {k for r in results for k in r["kinds"]}
    required = {"stage", "fanout", "barrier", "loop", "stop", "agent", "lossy"}
    missing = sorted(required - kinds_seen)
    if missing:
        return fail(f"corpus does not exercise kinds {missing}")
    print(
        json.dumps(
            {
                "n": len(results),
                "source": disc["source"],
                "names": [r["name"] for r in results],
                "lossy_files": [r["name"] for r in results if r["lossy"]],
            },
            sort_keys=True,
        )
    )
    print("round_trip 10/10 field-by-field")
    print("SUCCESS:WFA-0044-probe1 all 10 parse and re-render equivalently")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
