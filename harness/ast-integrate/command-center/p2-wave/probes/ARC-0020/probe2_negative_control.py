#!/usr/bin/env python3
"""Probe 2: metadata-ok / signature-bad refusal + overclaim + resolving anchors."""
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

ART = REPO / "command-center/phase3/A3/SECURITY.json"
DOSSIER_PREFIX = "command-center/phase3/A3/"


def main() -> int:
    nc = S.run_negative_control()
    print(
        "unsigned_refused="
        f"{nc['metadata_ok_signature_bad_refused']} "
        f"good_allowed={nc['metadata_ok_signature_ok_allowed']} "
        f"cached_unsigned_executed={nc['cached_unsigned_executed']} "
        f"reason={nc['unsigned_reason']}"
    )
    if nc.get("metadata_ok_signature_bad_refused") is not True:
        print("FAILED:ARC-0020-probe2 unsigned package was not refused")
        return 1
    if nc.get("metadata_ok_signature_ok_allowed") is not True:
        print("FAILED:ARC-0020-probe2 good package was not allowed")
        return 1
    if nc.get("cached_unsigned_executed") is True:
        print("FAILED:ARC-0020-probe2 cached unsigned path executed")
        return 1
    if nc.get("metadata_fields_present_on_unsigned") is not True:
        print("FAILED:ARC-0020-probe2 unsigned fixture lost metadata fields")
        return 1

    if not ART.is_file():
        print("FAILED:ARC-0020-probe2 SECURITY.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = O.check_overclaim(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:ARC-0020-probe2 overclaim check failed on artifact")
        return 1

    mutant = copy.deepcopy(doc)
    stripped = False
    for row in mutant["claims"]:
        if row.get("verdict") == "REFUTED" and "defect_locus" in row:
            del row["defect_locus"]
            stripped = True
            break
    if not stripped:
        print("FAILED:ARC-0020-probe2 no REFUTED defect_locus to strip")
        return 1
    mok, mwhy = O.check_overclaim(mutant)
    print(f"mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:ARC-0020-probe2 mutant without defect_locus was accepted")
        return 1

    art_nc = doc.get("negative_control") or {}
    if art_nc.get("metadata_ok_signature_bad_refused") is not True:
        print("FAILED:ARC-0020-probe2 artifact negative_control drift")
        return 1
    if art_nc.get("unsigned_reason") != nc.get("unsigned_reason"):
        print("FAILED:ARC-0020-probe2 artifact unsigned_reason drift")
        return 1

    evidence = doc.get("evidence") or []
    live = 0
    for i, row in enumerate(evidence):
        rel = str(row.get("path") or "")
        line = int(row.get("line") or 0)
        snippet = str(row.get("snippet") or "")
        rok, rwhy = A.resolve_anchor(REPO, rel, line, snippet)
        print(f"anchor[{i}] ok={rok} {rwhy}")
        if not rok:
            print("FAILED:ARC-0020-probe2 unresolved anchor")
            return 1
        kind = str(row.get("kind") or "")
        if kind == "dossier":
            if not rel.startswith(DOSSIER_PREFIX):
                print(f"FAILED:ARC-0020-probe2 dossier kind but path {rel}")
                return 1
        elif kind == "live-tree":
            live += 1
            if rel.startswith(DOSSIER_PREFIX):
                print(f"FAILED:ARC-0020-probe2 live-tree kind but dossier path {rel}")
                return 1
        else:
            print(f"FAILED:ARC-0020-probe2 bad evidence kind {kind}")
            return 1
    if live < 1:
        print("FAILED:ARC-0020-probe2 need live-tree evidence")
        return 1

    for i, row in enumerate(doc.get("attack_classes") or []):
        path = (row.get("design_path") or {}).get("path")
        snippet = (row.get("design_path") or {}).get("snippet")
        line = int((row.get("design_path") or {}).get("line") or 0)
        rok, rwhy = A.resolve_anchor(REPO, str(path), line, str(snippet))
        print(f"class[{i}] {row.get('id')} ok={rok} {rwhy}")
        if not rok:
            print("FAILED:ARC-0020-probe2 attack-class design path unresolved")
            return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("scope_not_agreement") is not True:
        print("FAILED:ARC-0020-probe2 reviewer is not independent scope-only")
        return 1
    xref = doc.get("cross_vendor_reviewer") or {}
    if str(xref.get("verdict") or "").upper() not in {"NOT-CHECKED", "PASS"}:
        print("FAILED:ARC-0020-probe2 cross-vendor reviewer missing or forged-absent")
        return 1
    if xref.get("verdict") == "PASS" and "codex" not in str(xref.get("reviewer_id") or "").lower():
        print("FAILED:ARC-0020-probe2 PASS cross-vendor id is not Codex")
        return 1
    if "SUCCESS:ARC-0020" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0020-probe2 sentinel absent")
        return 1
    print("SUCCESS:ARC-0020-probe2 negative-control overclaim anchors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
