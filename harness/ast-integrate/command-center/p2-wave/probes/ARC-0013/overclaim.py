"""Overclaim check for ARC-0013.

REFUTED rows must name DESIGN vs SENTENCE. Both loci must appear. The
gate must be executed (caught planted, silent on whitespace, fail-closed
on missing pin), not merely described.
"""
from __future__ import annotations

from typing import Any

LOCUS = frozenset({"DESIGN", "SENTENCE"})
VERDICTS = frozenset({"REFUTED", "CONFIRMED", "PARTIAL", "NOT-CHECKED"})


def check_overclaim(doc: dict[str, Any]) -> tuple[bool, str]:
    claims = doc.get("claims")
    if not isinstance(claims, list) or len(claims) < 3:
        return False, "claims-missing-or-short"
    refuted = 0
    confirmed = 0
    loci: set[str] = set()
    for i, row in enumerate(claims):
        if not isinstance(row, dict):
            return False, f"claims[{i}]-not-object"
        verdict = str(row.get("verdict") or "")
        if verdict not in VERDICTS:
            return False, f"claims[{i}]-bad-verdict:{verdict}"
        if verdict == "REFUTED":
            refuted += 1
            locus = str(row.get("defect_locus") or "")
            if locus not in LOCUS:
                return False, f"claims[{i}]-REFUTED-missing-defect_locus"
            if not str(row.get("claim") or "").strip():
                return False, f"claims[{i}]-empty-claim"
            if not str(row.get("scoped_restatement") or "").strip():
                return False, f"claims[{i}]-REFUTED-missing-scoped_restatement"
            loci.add(locus)
        elif verdict == "CONFIRMED":
            confirmed += 1
    if refuted < 1:
        return False, "no-REFUTED-claim"
    if confirmed < 1:
        return False, "no-CONFIRMED-claim"
    if "DESIGN" not in loci or "SENTENCE" not in loci:
        return False, f"REFUTED-loci-incomplete:{sorted(loci)}"

    demo = doc.get("demonstration") or {}
    if not isinstance(demo, dict) or demo.get("executed") is not True:
        return False, "demonstration-not-executed"
    planted = demo.get("planted_edit") or {}
    white = demo.get("whitespace") or {}
    absent = demo.get("pin_absent") or {}
    if planted.get("caught") is not True:
        return False, "planted-edit-not-caught"
    if white.get("silent") is not True:
        return False, "whitespace-not-silent"
    if white.get("source_hash_gate_would_trip") is not True:
        return False, "source-hash-control-missing"
    if absent.get("fail_closed") is not True:
        return False, "missing-pin-not-fail-closed"

    named = doc.get("named_template_files") or []
    if not isinstance(named, list) or len(named) < 1:
        return False, "named-template-files-missing"
    for row in named:
        if not isinstance(row, dict) or not str(row.get("path") or "").strip():
            return False, "named-template-row-invalid"

    if doc.get("github_codeowners_live") is True:
        return False, "overclaim-live-github-codeowners"
    if (doc.get("signing") or {}).get("org_gpg_on_this_worktree") is True:
        return False, "overclaim-org-gpg"
    return True, f"refuted={refuted} confirmed={confirmed} loci={sorted(loci)}"
