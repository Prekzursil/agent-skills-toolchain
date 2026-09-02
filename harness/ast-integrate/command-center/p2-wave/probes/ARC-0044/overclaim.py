"""Overclaim check for ARC-0044.

Every REFUTED row names DESIGN vs SENTENCE. Probe 2 drops defect_locus and
asserts this checker then fails. Scope must pick contract / tier / docs.
The two vendor artifacts must be produced and quoted, not narrated.
"""
from __future__ import annotations

from typing import Any

LOCUS = frozenset({"DESIGN", "SENTENCE"})
VERDICTS = frozenset({"REFUTED", "CONFIRMED", "PARTIAL", "NOT-CHECKED"})
SCOPE = frozenset(
    {"contract_wrong", "tier_assignment_wrong", "documentation_only_overclaim"}
)


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

    vs = doc.get("verdict_scope") or {}
    if not isinstance(vs, dict):
        return False, "verdict-scope-missing"
    chosen = str(vs.get("chosen") or "")
    if chosen not in SCOPE:
        return False, f"verdict-scope-bad-chosen:{chosen}"
    if vs.get("documentation_only_overclaim") is True and chosen != "documentation_only_overclaim":
        return False, "verdict-scope-docs-flag-inconsistent"
    if chosen == "documentation_only_overclaim" and vs.get("tier_assignment_wrong") is True:
        return False, "cannot-be-docs-only-if-tier-wrong"

    pair = doc.get("produced_pair") or {}
    if not isinstance(pair, dict) or pair.get("both_predicate_pass") is not True:
        return False, "produced-pair-missing"
    paths = pair.get("paths") or {}
    if not isinstance(paths, dict) or not paths.get("claude-confirm") or not paths.get("codex-auto"):
        return False, "produced-pair-paths-missing"

    qd = doc.get("quoted_divergence") or {}
    if not isinstance(qd, dict):
        return False, "quoted-divergence-missing"
    left = qd.get("claude-confirm") or {}
    right = qd.get("codex-auto") or {}
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False, "quoted-divergence-not-objects"
    if left.get("writes_applied") == right.get("writes_applied") and left.get("body") == right.get("body"):
        return False, "quoted-divergence-not-divergent"
    if not str(qd.get("observable") or "").strip():
        return False, "observable-unnamed"
    return True, f"refuted={refuted} confirmed={confirmed} scope={chosen}"
