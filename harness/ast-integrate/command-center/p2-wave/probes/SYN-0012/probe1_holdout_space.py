#!/usr/bin/env python3
"""Probe 1: hold-out space equals the declared source inventory.

Every declared source is a matrix column. Every conclusion x source cell is
computed. A 3-of-40 sweep is labelled SAMPLE, not COMPLETE.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import sensitivity as S  # noqa: E402
from universe import build_universe, label_completeness  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0012.sensitivity.json"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0012-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    payload = S.payload(doc)
    live = S.analyze(build_universe())
    declared = [s["id"] for s in live["sources"]]
    hs = payload.get("holdout_space") or {}
    cols = list((payload.get("matrix") or {}).get("columns") or [])
    hs_ids = [s.get("id") for s in (hs.get("sources") or []) if isinstance(s, dict)]

    if sorted(declared) != sorted(cols):
        return fail(
            f"holdout-space-mismatch declared={sorted(declared)} columns={sorted(cols)}"
        )
    if sorted(declared) != sorted(hs_ids):
        return fail("holdout_space.sources != declared inventory")
    if int(hs.get("declared_size") or 0) != len(declared):
        return fail("declared_size != inventory len")
    if int(hs.get("swept_size") or 0) != int(hs.get("declared_size") or -1):
        if str(hs.get("completeness") or "") != "SAMPLE":
            return fail("partial-sweep-reported-as-complete")
    if int(hs.get("swept_size") or 0) == int(hs.get("declared_size") or -1):
        if str(hs.get("completeness") or "") != "COMPLETE":
            return fail("full census not labelled COMPLETE")

    rows = list((payload.get("matrix") or {}).get("rows") or [])
    cells = [
        c
        for c in ((payload.get("matrix") or {}).get("cells") or [])
        if isinstance(c, dict)
    ]
    expected = len(declared) * len(rows)
    if len(cells) != expected:
        return fail(f"matrix-cell-not-computed have={len(cells)} want={expected}")
    seen = {(c.get("conclusion_id"), c.get("source_id")) for c in cells}
    missing = []
    for cid in rows:
        for sid in cols:
            if (cid, sid) not in seen:
                missing.append(f"{cid}x{sid}")
    if missing:
        return fail(f"matrix-cell-not-computed {missing[:8]}")
    for c in cells:
        if c.get("verdict") not in {"SURVIVES", "VANISHES", "REVERSES"}:
            return fail(f"bad cell verdict {c}")

    if label_completeness(3, 40) != "SAMPLE":
        return fail("3-of-40 must be SAMPLE")
    if label_completeness(10, 10) != "COMPLETE":
        return fail("10-of-10 must be COMPLETE")
    if live["holdout_space"]["completeness"] != hs.get("completeness"):
        return fail("live completeness != artifact")

    cons = payload.get("conclusions") or []
    if len(cons) != len(rows):
        return fail("conclusion rows != matrix.rows")
    print(
        "holdout_equals_inventory=true "
        f"declared={len(declared)} swept={hs.get('swept_size')} "
        f"completeness={hs.get('completeness')} cells={len(cells)} "
        f"partial_3_of_40={label_completeness(3, 40)}"
    )
    print("SUCCESS:SYN-0012-probe1 hold-out space equals declared inventory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
