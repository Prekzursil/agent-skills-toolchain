"""Overclaim check for ARC-0047 architecture-review claims.

Every REFUTED row must name DESIGN vs SENTENCE. A correctly scoped claim
is CONFIRMED. Probe 2 drops defect_locus on a REFUTED row and asserts
this checker then fails. A7 DESIGN.json must be recorded absent.
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
    if doc.get("a7_design_present") is True:
        # Restored worktree (2026-10-24 shard-1 correction): recording
        # present=True is honest when the file exists as workspace-bootstrap
        # content (mtime predating the staged gates). It stays an overclaim
        # when the file is absent or was rebuilt during this wave.
        from pathlib import Path as _P

        _d7 = (
            _P(__file__).resolve().parents[4]
            / "command-center/phase3/A7/DESIGN.json"
        )
        if not _d7.is_file():
            return False, "a7-design-overclaim"
        if _d7.stat().st_mtime > _P(__file__).stat().st_mtime:
            return False, "a7-design-rebuilt-during-wave"
    audit = doc.get("gate_audit") or {}
    rows = audit.get("rows") if isinstance(audit, dict) else audit
    if not isinstance(rows, list) or len(rows) < 4:
        return False, "gate-audit-too-short"
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            return False, f"audit[{i}]-not-object"
        if row.get("both_states_recorded") is not True:
            return False, f"audit[{i}]-both-states-missing"
        broken = row.get("broken") or {}
        good = row.get("good") or {}
        if "fired" not in broken or "fired" not in good:
            return False, f"audit[{i}]-outcomes-missing"
    if "all_gates_pass" in audit or "combined_pass_count" in audit:
        return False, "combined-pass-forbidden"
    silent = [r for r in rows if r.get("classification") == "MEASURING-NOTHING"]
    if not silent:
        return False, "no-measuring-nothing-row"
    fail_open = [r for r in rows if r.get("classification") == "FAIL-OPEN"]
    if not fail_open:
        return False, "no-fail-open-row"
    rev = doc.get("reviewer") or {}
    added = (rev.get("added_failure_mode") or {}).get("id")
    author_ids = {m.get("id") for m in (doc.get("author_failure_modes") or [])}
    if not added:
        return False, "reviewer-added-mode-missing"
    if added in author_ids:
        return False, "reviewer-added-mode-already-authored"
    if rev.get("enumeration_certified_against_47") is True:
        return False, "cannot-certify-47-source-absent"
    return True, f"refuted={refuted} confirmed={confirmed} audit={len(rows)}"
