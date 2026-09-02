#!/usr/bin/env python3
"""Probe 2: both-states version-insensitive claims + missing-pin detector.

Mechanically different from probe 1: this probe does not re-assert UP051
divergence. It re-runs F401/clean claims (must agree) and parses the CI
inventory for tools used without an explicit pin.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0185.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0185-probe2 {msg}")
    return 1


def main() -> int:
    live = S.run_matrix()
    inv = I.collect()
    insensitive = live["insensitive"]
    missing = inv["missing_pins"]
    tools_missing = sorted({m["tool"] for m in missing})
    ruff_exact = any(
        u.get("tool") == "ruff" and u.get("pin") == "0.15.17"
        for u in inv["usages"]
    )
    print(
        json.dumps(
            {
                "probe": "probe2-both-states-missing-pin",
                "insensitive_count": len(insensitive),
                "insensitive_ids": [c["id"] for c in insensitive],
                "missing_pin_count": len(missing),
                "missing_pin_tools": tools_missing,
                "ruff_has_exact_pin": ruff_exact,
            },
            sort_keys=True,
        )
    )
    if len(insensitive) < 2:
        return fail("need >=2 version-insensitive claims")
    for c in insensitive:
        if c["verdict_ci_pin"] != c["verdict_comparison"]:
            return fail(f"insensitive claim split: {c['id']}")
    if not ruff_exact:
        return fail("ruff==0.15.17 pin not found; detector would be vacuous")
    if not missing:
        return fail("no missing-pin findings; detector silent")
    if "osv-scanner" not in tools_missing and "gitleaks" not in tools_missing:
        return fail(f"expected osv-scanner or gitleaks unpinned, got {tools_missing}")
    if any(m.get("tool") == "ruff" for m in missing):
        return fail("ruff exact pin was reported as missing")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    art_missing = S.domain_get(doc, "missing_pins") or []
    if not isinstance(art_missing, list) or len(art_missing) < 1:
        return fail("artifact missing_pins empty")
    art_tools = {m.get("tool") for m in art_missing if isinstance(m, dict)}
    if not (art_tools & set(tools_missing)):
        return fail("artifact missing_pins do not overlap live inventory")
    cells = S.domain_get(doc, "cells") or []
    if not isinstance(cells, list):
        cells = []
    ins_cells = [
        c
        for c in cells
        if isinstance(c, dict) and c.get("classification") == "version-insensitive"
    ]
    if len(ins_cells) < 2:
        return fail("artifact lacks both-states insensitive cells")
    print(
        f"insensitive={len(insensitive)} missing_pins={len(missing)} "
        f"tools={tools_missing} ruff_pinned={ruff_exact}"
    )
    print("SUCCESS:CNF-0185-probe2 both-states and missing-pin detection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
