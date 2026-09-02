#!/usr/bin/env python3
"""Probe 2: path enumeration, overclaim, anchors, two reviewers, no DESIGN rebuild."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import anchors as A  # noqa: E402
import overclaim as O  # noqa: E402
import paths as P  # noqa: E402
import schema_gate as SG  # noqa: E402

ART = REPO / "command-center/phase3/A4/SECURITY.json"
DESIGN = REPO / "command-center/phase3/A4/DESIGN.json"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0027-probe2 {msg}")
    return 1


def main() -> int:
    if DESIGN.is_file():
        return fail("A4 DESIGN.json present; rebuild circle")
    live = P.run()
    print(
        f"paths={len(live['paths'])} complete={live['completeness']['complete']} "
        f"runtime={live['runtime']['pass']} plant={live['planted_bypass']['pass']}"
    )
    if not live["pass"]:
        return fail("live path enumeration failed")
    if not ART.is_file():
        return fail("SECURITY.json missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if not SG.garbage_rejected():
        return fail("schema is vacuous")
    if not SG.errors({}):
        return fail("schema accepted empty garbage")
    errs = SG.errors(doc)
    if errs:
        return fail("schema " + "; ".join(errs[:6]))

    ok, why = O.check_overclaim(doc, REPO)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        return fail(f"overclaim {why}")

    art_paths = {p["id"]: p for p in (doc.get("activation_paths") or []) if isinstance(p, dict)}
    live_paths = {p["id"]: p for p in live["paths"]}
    if set(art_paths) != set(live_paths):
        return fail(f"path-id mismatch art={sorted(art_paths)} live={sorted(live_paths)}")
    for pid, row in live_paths.items():
        art = art_paths[pid]
        if int(art.get("line") or 0) != int(row["line"]):
            return fail(f"{pid} line drift art={art.get('line')} live={row['line']}")
        if art.get("path") != row["path"]:
            return fail(f"{pid} path drift")
        if art.get("crosses_check") is not True:
            return fail(f"{pid} not shown to cross check")

    plant = doc.get("planted_bypass") or {}
    if plant.get("pass") is not True:
        return fail("artifact planted_bypass")
    if "activate_side_door" not in (plant.get("mutant_uncovered") or []):
        return fail("planted side door not in uncovered")

    dossier = 0
    live_tree = 0
    for i, row in enumerate(doc.get("evidence") or []):
        rel = str(row.get("path") or "")
        line = int(row.get("line") or 0)
        snippet = str(row.get("snippet") or "")
        rok, rwhy = A.resolve_anchor(REPO, rel, line, snippet)
        print(f"anchor[{i}] ok={rok} {rwhy}")
        if not rok:
            return fail(f"unresolved {rwhy}")
        kind = str(row.get("kind") or "")
        if kind == "dossier":
            dossier += 1
        elif kind == "live-tree":
            live_tree += 1
        else:
            return fail(f"bad evidence kind {kind}")
    if dossier < 1 or live_tree < 1:
        return fail(f"evidence counts dossier={dossier} live-tree={live_tree}")

    reviewers = doc.get("reviewers") or []
    if len(reviewers) < 2:
        return fail("need two reviewers")
    vendors = {str(r.get("vendor") or "").lower() for r in reviewers}
    if "openai" not in vendors and "codex" not in vendors:
        return fail("missing Codex cross-vendor reviewer")
    rev = doc.get("reviewer") or {}
    if rev.get("scope_not_agreement") is not True:
        return fail("reviewer scope_not_agreement")
    if rev.get("independent") is not True:
        return fail("reviewer not independent")

    if "SUCCESS:ARC-0027" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    print("SUCCESS:ARC-0027-probe2 path-enumeration overclaim reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
