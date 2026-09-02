#!/usr/bin/env python3
"""Probe 2: independent bitmask recount + overclaim/anchor review.

Re-derives incompatible/compatible counts from fixtures/templates.json using
bitmask_recount.py. A disagreement in the number blocks the unit. Does not
import solver.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import bitmask_recount as B  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0029-incompatible-role-and-conflict-of-interest-checker-as-a-co.md"
)
TEMPLATES = HERE / "fixtures" / "templates.json"
OVERCLAIM_MARKERS = ("58/58", "all 58 protocol", "every protocol record")


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNL-0029-probe2 design note missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0029-probe2 self-declared {doc.get('state')}")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0029" not in text:
        print("FAILED:CNL-0029-probe2 sentinel absent")
        return 1
    for marker in OVERCLAIM_MARKERS:
        if marker in (doc.get("answer") or ""):
            print(f"FAILED:CNL-0029-probe2 overclaim marker in answer: {marker}")
            return 1

    library = json.loads(TEMPLATES.read_text(encoding="utf-8"))
    live = B.recount(library)
    matrix = doc.get("matrix") or {}
    if int(matrix.get("incompatible_ordered") or -1) != live["incompatible_ordered"]:
        print(
            "FAILED:CNL-0029-probe2 incompatible_ordered "
            f"artifact={matrix.get('incompatible_ordered')} live={live['incompatible_ordered']}"
        )
        return 1
    if int(matrix.get("compatible_ordered") or -1) != live["compatible_ordered"]:
        print("FAILED:CNL-0029-probe2 compatible_ordered disagreement")
        return 1
    if list(matrix.get("incompatible_unordered") or []) != live["incompatible_unordered"]:
        print("FAILED:CNL-0029-probe2 unordered set disagreement")
        return 1
    art_cells = {(c["a"], c["b"]): bool(c["incompatible"]) for c in (matrix.get("cells") or [])}
    live_cells = {(r["a"], r["b"]): bool(r["incompatible"]) for r in live["rows"]}
    if art_cells != live_cells:
        print("FAILED:CNL-0029-probe2 cell-by-cell disagreement")
        return 1

    if int((doc.get("family") or {}).get("counted_n") or -1) != live["template_count"]:
        print("FAILED:CNL-0029-probe2 family.counted_n disagreement")
        return 1
    residuals = " ".join(doc.get("residual_unknowns") or [])
    if "12-COUNCIL-PROTOCOLS-AND-PRESETS.json" not in residuals:
        print("FAILED:CNL-0029-probe2 residual does not name missing protocol file")
        return 1

    claims = doc.get("claims") or []
    refuted = 0
    confirmed = 0
    loci = set()
    for i, row in enumerate(claims):
        verdict = str(row.get("verdict") or "")
        if verdict == "REFUTED":
            refuted += 1
            locus = str(row.get("defect_locus") or "")
            if locus not in {"DESIGN", "SENTENCE"}:
                print(f"FAILED:CNL-0029-probe2 claims[{i}] REFUTED missing defect_locus")
                return 1
            if not str(row.get("scoped_restatement") or "").strip():
                print(f"FAILED:CNL-0029-probe2 claims[{i}] REFUTED missing scoped_restatement")
                return 1
            loci.add(locus)
        elif verdict == "CONFIRMED":
            confirmed += 1
    if refuted < 1 or confirmed < 1:
        print(f"FAILED:CNL-0029-probe2 claims refuted={refuted} confirmed={confirmed}")
        return 1
    if "DESIGN" not in loci or "SENTENCE" not in loci:
        print(f"FAILED:CNL-0029-probe2 REFUTED loci incomplete {sorted(loci)}")
        return 1

    evidence = doc.get("evidence") or []
    mechs = set()
    for i, row in enumerate(evidence):
        rel = str(row.get("path") or "")
        line = int(row.get("line") or 0)
        snippet = str(row.get("snippet") or "")
        rok, rwhy = A.resolve_anchor(REPO, rel, line, snippet)
        print(f"anchor[{i}] ok={rok} {rwhy}")
        if not rok:
            print("FAILED:CNL-0029-probe2 unresolved anchor")
            return 1
        mechs.add(str(row.get("mechanism") or ""))
    if "python-set-overlap" not in mechs or "bitmask-OR-then-AND" not in mechs:
        print(f"FAILED:CNL-0029-probe2 evidence mechanisms {sorted(mechs)}")
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("scope_not_agreement") is not True:
        print("FAILED:CNL-0029-probe2 reviewer is not independent scope-only")
        return 1
    if rev.get("reviewer_id") != "CNL-0029-probe2-bitmask-recount":
        print("FAILED:CNL-0029-probe2 reviewer_id mismatch")
        return 1

    print(
        f"recount mechanism={live['mechanism']} incompatible_ordered={live['incompatible_ordered']} "
        f"compatible_ordered={live['compatible_ordered']} unordered={live['incompatible_unordered_count']}"
    )
    print("SUCCESS:CNL-0029-probe2 independent recount overclaim anchors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
