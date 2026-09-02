#!/usr/bin/env python3
"""Probe 2: whitespace-only template change must NOT trip the output pin.

Also: source-hash of generator.py WOULD trip (noisy-gate control), overclaim
checker requires DESIGN+SENTENCE loci, and dropping defect_locus fails.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import overclaim as O  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/phase3/A2/SECURITY.json"
DOSSIER_PREFIX = "command-center/phase3/A2/"


def main() -> int:
    run = S.run()
    white = run["whitespace"]
    print(
        f"whitespace silent={white['silent']} tripped={white['tripped']} "
        f"reason={white['reason']} source_hash_would_trip="
        f"{white['source_hash_gate_would_trip']}"
    )
    if not white.get("silent"):
        print("FAILED:ARC-0013-probe2 whitespace tripped the output pin")
        return 1
    if not white.get("source_hash_gate_would_trip"):
        print("FAILED:ARC-0013-probe2 source-hash control did not discriminate")
        return 1
    if not run["planted_edit"].get("caught"):
        print("FAILED:ARC-0013-probe2 planted edit no longer caught")
        return 1

    if not ART.is_file():
        print("FAILED:ARC-0013-probe2 SECURITY.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = O.check_overclaim(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:ARC-0013-probe2 overclaim check failed on artifact")
        return 1

    mutant = copy.deepcopy(doc)
    stripped = False
    for row in mutant["claims"]:
        if row.get("verdict") == "REFUTED" and "defect_locus" in row:
            del row["defect_locus"]
            stripped = True
            break
    if not stripped:
        print("FAILED:ARC-0013-probe2 no REFUTED defect_locus to strip")
        return 1
    mok, mwhy = O.check_overclaim(mutant)
    print(f"mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:ARC-0013-probe2 mutant without defect_locus was accepted")
        return 1

    evidence = doc.get("evidence") or []
    dossier = 0
    live = 0
    for i, row in enumerate(evidence):
        rel = str(row.get("path") or "")
        line = int(row.get("line") or 0)
        snippet = str(row.get("snippet") or "")
        rok, rwhy = A.resolve_anchor(REPO, rel, line, snippet)
        print(f"anchor[{i}] ok={rok} {rwhy}")
        if not rok:
            print("FAILED:ARC-0013-probe2 unresolved anchor")
            return 1
        kind = str(row.get("kind") or "")
        if kind == "dossier":
            if not rel.startswith(DOSSIER_PREFIX):
                print(f"FAILED:ARC-0013-probe2 dossier kind but path {rel}")
                return 1
            dossier += 1
        elif kind == "live-tree":
            live += 1
        else:
            print(f"FAILED:ARC-0013-probe2 bad evidence kind {kind}")
            return 1
    if dossier < 1 or live < 1:
        print(f"FAILED:ARC-0013-probe2 evidence counts dossier={dossier} live={live}")
        return 1

    rec_ws = (doc.get("demonstration") or {}).get("whitespace") or {}
    if rec_ws.get("silent") is not True:
        print("FAILED:ARC-0013-probe2 artifact did not record whitespace silent")
        return 1
    if rec_ws.get("source_hash_gate_would_trip") is not True:
        print("FAILED:ARC-0013-probe2 artifact omitted noisy-gate control")
        return 1
    if doc.get("github_codeowners_live") is True:
        print("FAILED:ARC-0013-probe2 overclaimed live GitHub CODEOWNERS")
        return 1
    if "SUCCESS:ARC-0013" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0013-probe2 sentinel absent")
        return 1
    print("SUCCESS:ARC-0013-probe2 whitespace-control overclaim anchors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
