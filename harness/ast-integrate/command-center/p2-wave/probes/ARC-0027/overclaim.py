"""Overclaim gate for ARC-0027. Cloud ok is not delivery."""
from __future__ import annotations

from pathlib import Path
from typing import Any

VERDICTS = frozenset({"REFUTED", "CONFIRMED", "PARTIAL", "NOT-CHECKED"})
LOCI = frozenset({"DESIGN", "SENTENCE"})
EV_KINDS = frozenset({"dossier", "live-tree"})
DESIGN_REL = "command-center/phase3/A4/DESIGN.json"


def check_overclaim(doc: dict[str, Any], repo: Path) -> tuple[bool, str]:
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return False, f"self-declared:{doc.get('state')}"
    if doc.get("unit_id") != "ARC-0027":
        return False, "unit_id"
    if "SUCCESS:ARC-0027" not in str(doc.get("sentinel") or ""):
        return False, "sentinel"
    if doc.get("architecture_id") != "A4":
        return False, "architecture_id"
    if doc.get("design_present") is True:
        return False, "claimed-design-present"
    if (repo / DESIGN_REL).is_file():
        return False, "a4-design-rebuilt"
    if doc.get("cloud_ok") is True:
        return False, "cloud_ok-is-not-delivery"
    if str(doc.get("authoritative_check_epoch") or "") != "activation":
        return False, "authoritative-epoch"

    claims = doc.get("claims")
    if not isinstance(claims, list) or len(claims) < 3:
        return False, "claims-short"
    refuted = 0
    confirmed = 0
    for i, row in enumerate(claims):
        if not isinstance(row, dict):
            return False, f"claims[{i}]-type"
        verdict = str(row.get("verdict") or "")
        if verdict not in VERDICTS:
            return False, f"claims[{i}]-verdict"
        if verdict == "REFUTED":
            refuted += 1
            if str(row.get("defect_locus") or "") not in LOCI:
                return False, f"claims[{i}]-locus"
        elif verdict == "CONFIRMED":
            confirmed += 1
        if len(str(row.get("claim") or "")) < 8:
            return False, f"claims[{i}]-empty"
        if len(str(row.get("anchor") or "")) < 3:
            return False, f"claims[{i}]-anchor"
    if refuted < 1:
        return False, "no-REFUTED"
    if confirmed < 1:
        return False, "no-CONFIRMED"

    both = doc.get("both_states") or {}
    if both.get("index_slipped") is not True:
        return False, "index-did-not-slip"
    if both.get("activation_caught") is not True:
        return False, "activation-did-not-catch"

    paths = doc.get("activation_paths") or []
    if not isinstance(paths, list) or len(paths) < 2:
        return False, "paths-short"
    for i, row in enumerate(paths):
        if not isinstance(row, dict) or row.get("crosses_check") is not True:
            return False, f"path[{i}]-no-check"
        if not row.get("path") or int(row.get("line") or 0) < 1:
            return False, f"path[{i}]-file-line"

    plant = doc.get("planted_bypass") or {}
    if plant.get("pass") is not True:
        return False, "planted-bypass-not-caught"

    reviewers = doc.get("reviewers") or []
    if not isinstance(reviewers, list) or len(reviewers) < 2:
        return False, "need-two-reviewers"
    vendors = {
        str(r.get("vendor") or "").lower() for r in reviewers if isinstance(r, dict)
    }
    if "openai" not in vendors and "codex" not in vendors:
        return False, "missing-cross-vendor-codex"

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        return False, "reviewer-not-independent"
    if rev.get("scope_not_agreement") is not True:
        return False, "reviewer-scope"
    rid = str(rev.get("reviewer_id") or "")
    vendor = str(rev.get("vendor") or "").lower()
    if "codex" not in rid.lower() and vendor not in {"openai", "codex"}:
        return False, "primary-reviewer-not-codex"

    evidence = doc.get("evidence") or []
    if not isinstance(evidence, list) or len(evidence) < 4:
        return False, "evidence-short"
    kinds = {e.get("kind") for e in evidence if isinstance(e, dict)}
    if "dossier" not in kinds or "live-tree" not in kinds:
        return False, "evidence-kinds"
    return True, f"refuted={refuted} confirmed={confirmed}"
