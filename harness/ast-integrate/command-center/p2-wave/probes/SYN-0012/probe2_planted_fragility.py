#!/usr/bin/env python3
"""Probe 2: planted fragility + robust hold-outs + matrix recompute.

A conclusion supported by exactly one fabricated source must be FATAL on
that hold-out. Robust conclusions must SURVIVE every hold-out. Robustness
scores must recompute from the published matrix. Catalog schema rejects
garbage; the unit domain checker rejects a robustness_score-stripped mutant.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import schema_lib as SL  # noqa: E402
import sensitivity as S  # noqa: E402
from universe import (  # noqa: E402
    C_PLANTED_FRAGILE,
    C_ROBUST_TRIPLE,
    SRC_FABRICATED,
)

ART = REPO / "command-center/synthesis/SYN-0012.sensitivity.json"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0012-probe2 {msg}")
    return 1


def cell_map(payload: dict) -> dict[tuple[str, str], str]:
    out = {}
    for c in ((payload.get("matrix") or {}).get("cells") or []):
        if isinstance(c, dict):
            out[(str(c.get("conclusion_id")), str(c.get("source_id")))] = str(
                c.get("verdict")
            )
    return out


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:SYN-0012" not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    errs = SL.schema_errors(doc)
    if errs:
        return fail(f"schema {errs[0]}")
    if not SL.schema_errors({"totally": "unrelated"}):
        return fail("schema accepts garbage")

    domain = S.domain_errors(doc)
    if domain:
        return fail(f"domain {domain[0]}")

    mutant = copy.deepcopy(doc)
    payload = S.payload(mutant)
    if not payload.get("conclusions"):
        return fail("no conclusions")
    payload["conclusions"][0].pop("robustness_score", None)
    if not S.domain_errors(mutant):
        return fail("schema accepted robustness_score-stripped mutant")

    payload = S.payload(doc)
    cells = cell_map(payload)
    planted = cells.get((C_PLANTED_FRAGILE, SRC_FABRICATED))
    print(f"planted_fragile_cell={planted}")
    if planted != "VANISHES":
        return fail(
            f"planted fragility expected VANISHES on {SRC_FABRICATED}, got {planted}"
        )
    fatal = [
        (p.get("conclusion_id"), p.get("source_id"), p.get("verdict"))
        for p in (payload.get("fatal_pairs") or [])
        if isinstance(p, dict)
    ]
    if (C_PLANTED_FRAGILE, SRC_FABRICATED, "VANISHES") not in fatal:
        return fail("fatal_pairs missing planted singleton pair")

    robust_cells = [v for (cid, _sid), v in cells.items() if cid == C_ROBUST_TRIPLE]
    if not robust_cells:
        return fail("C-ROBUST-TRIPLE missing from matrix")
    if any(v != "SURVIVES" for v in robust_cells):
        return fail(f"robust conclusion changed across holdouts {set(robust_cells)}")
    print(f"robust_unchanged=true holdouts={len(robust_cells)}")

    by_id = {
        c["id"]: c for c in (payload.get("conclusions") or []) if isinstance(c, dict)
    }
    for cid, con in by_id.items():
        if "robustness_score" not in con:
            return fail(f"missing robustness_score {cid}")
        survives, holdouts = S.robustness_from_matrix(payload["matrix"], cid)
        if holdouts <= 0:
            return fail(f"matrix empty for {cid}")
        recomputed = survives / holdouts
        stored = float(con["robustness_score"])
        if abs(recomputed - stored) > 1e-12:
            return fail(f"score mismatch {cid} stored={stored} recomputed={recomputed}")
        frac = con.get("robustness_fraction") or {}
        if int(frac.get("survives") or -1) != survives or int(frac.get("holdouts") or -1) != holdouts:
            return fail(f"fraction mismatch {cid}")
    print(f"recompute_ok=true conclusions={len(by_id)} fatal_pairs={len(fatal)}")

    live = S.analyze()
    live_cells = {
        (c["conclusion_id"], c["source_id"]): c["verdict"]
        for c in live["matrix"]["cells"]
    }
    if live_cells != cells:
        return fail("live engine matrix != artifact matrix")
    if live["fatal_pairs"] != payload.get("fatal_pairs"):
        return fail("live fatal_pairs != artifact")

    if not isinstance(payload.get("fatal_pairs"), list):
        return fail("fatal_pairs not enumerated")
    print("SUCCESS:SYN-0012-probe2 planted FATAL, robust unchanged, scores recompute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
