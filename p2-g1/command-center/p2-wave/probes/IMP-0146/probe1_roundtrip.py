#!/usr/bin/env python3
"""IMP-0146 probe1: idempotent canonical round trip over workflow-shaped
values that include every node kind the spec language supports.

export(import(export(w))) == export(w) byte-for-byte; the mutation control
(XOR one byte of the export) must NOT round trip equal (both-states)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

import agentspec.canonical as C  # noqa: E402

# Workflow-shaped values covering the node kinds: plain unit, FanOut, Barrier,
# Pipeline, Loop, Subworkflow, HumanCheckpoint, DynamicFanOut (as data).
WORKFLOWS = [
    {"kind": "WorkUnit", "id": "u1", "prompt": "do X", "timeout_s": 60,
     "receipt": {"fmt": "json", "required_fields": ["winner"]}},
    {"kind": "FanOut", "id": "f1", "unit_ids": ["u1", "u2", "u3"]},
    {"kind": "Barrier", "id": "b1", "after": "f1"},
    {"kind": "Pipeline", "id": "p1", "stages": ["u1", "u2"]},
    {"kind": "Loop", "id": "l1", "body": "u1", "max_iters": 5},
    {"kind": "Subworkflow", "id": "s1", "ref": "wf/other"},
    {"kind": "HumanCheckpoint", "id": "h1", "prompt": "approve?", "channels": ["cli"]},
    {"kind": "DynamicFanOut", "id": "d1", "source": "queue", "max_width": 8},
]


def main() -> int:
    rows = []
    all_kinds_text = None
    for w in WORKFLOWS:
        a = C.export(w)                      # bytes
        v = C.loadb(a)                       # parse back
        b = C.export(v)                      # re-export
        rows.append({
            "kind": w["kind"],
            "byte_equal": a == b,
            "bytes": len(a),
        })
    # whole-set document: every kind in one value
    whole = {"kind": "Workflow", "id": "all-kinds", "nodes": WORKFLOWS}
    text1 = C.export(whole)
    text2 = C.export(C.loadb(text1))
    all_kinds_equal = text1 == text2

    # mutation control: flip one byte -> round trip must NOT stay equal
    mutated = bytearray(text1)
    mutated[10] ^= 0x01
    try:
        m_equal = C.export(C.loadb(bytes(mutated))) == text1
    except Exception:  # noqa: BLE001
        m_equal = False

    result = {
        "unit_id": "IMP-0146",
        "probe": "probe1-roundtrip",
        "kinds": [w["kind"] for w in WORKFLOWS],
        "per_kind_byte_equal": all(r["byte_equal"] for r in rows),
        "rows": rows,
        "all_kinds_byte_equal": all_kinds_equal,
        "mutation_control_fires": not m_equal,
        "pass": all(r["byte_equal"] for r in rows) and all_kinds_equal and not m_equal,
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0146-probe1 idempotent round trip over every node kind; "
            "mutation control fires (both-states)"
            if result["pass"] else
            "FAILED:IMP-0146-probe1 canonical round-trip contract broken")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
