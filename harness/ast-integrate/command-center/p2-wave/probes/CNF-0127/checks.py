#!/usr/bin/env python3
"""Artifact checker for CNF-0127. Shared by emit and probe2.

A KEEP is allowed only on a measured gain above the noise floor AND a guard
case that fails on baseline and passes on the improved variant. Neutral,
harmful, noise-dominated, and unguarded changes cannot be retained merely
because an agent produced them.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
SENTINEL = (
    "SUCCESS:CNF-0127 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every retained "
    "improvement has an independent re-measurement or an explicit revert "
    "recommendation. Any other terminal state is FAILED:CNF-0127 "
    "<classification> with the diagnostic tail attached."
)
ART_REL = "command-center/confirmation/CNF-0127-retention-remeasure.json"


def domain(doc: dict) -> dict:
    """Cases live under report when receipt_core forbids extra top-level keys."""
    for key in ("report", "extensions"):
        blob = doc.get(key)
        if isinstance(blob, dict) and isinstance(blob.get("cases"), list):
            return blob
    return doc


def _num(x: Any) -> float:
    return float(x)


def check_artifact(doc: dict) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "not-an-object"
    if str(doc.get("unit_id") or "") != "CNF-0127":
        return False, "unit_id"
    state = str(doc.get("state") or "").upper()
    if state in NOT_DELIVERING:
        return False, f"self-declared:{state}"
    if SENTINEL not in str(doc.get("sentinel") or ""):
        return False, "sentinel-absent"
    payload = domain(doc)
    if payload.get("every_retained_has_remeasure_or_revert") is not True:
        return False, "every-retained-flag"

    cases = payload.get("cases") or []
    if not isinstance(cases, list) or len(cases) < 4:
        return False, "cases-short"

    reverts: list[str] = []
    filed: list[str] = []
    keeps: list[str] = []
    independent = 0
    for row in cases:
        if not isinstance(row, dict):
            return False, "case-not-object"
        cid = str(row.get("id") or "")
        verdict = str(row.get("verdict") or "")
        rem = row.get("remeasurements") or {}
        raw = rem.get("raw") if isinstance(rem, dict) else None
        if not isinstance(raw, list) or len(raw) < 2:
            if verdict not in {"REVERT", "FILE", "UNMEASURABLE"}:
                return False, f"unmeasured-retention:{cid}"
            return False, f"raw-missing:{cid}"
        reported = str(rem.get("reported_as") or "")
        if reported == "7/7" and list(rem.get("outcomes") or []).count("red") > 0:
            return False, f"last-green-overwrite:{cid}"
        indep = row.get("independence") or {}
        if not indep.get("independent"):
            return False, f"author-not-independent:{cid}"
        independent += 1
        if verdict == "KEEP":
            keeps.append(cid)
            if not row.get("guard_case"):
                return False, f"keep-without-guard:{cid}"
            if not row.get("guard_catches_original_failure"):
                return False, f"keep-unguarded-failure:{cid}"
            gain = _num(row.get("measured_gain") or 0)
            floor = _num(row.get("noise_floor_value") or 0)
            if gain <= floor:
                return False, f"keep-inside-noise:{cid}"
        elif verdict == "REVERT":
            reverts.append(cid)
        elif verdict == "FILE":
            filed.append(cid)
            if row.get("added_benchmark_case") is True:
                return False, f"file-but-guard-present:{cid}"
        elif verdict in {"UNMEASURABLE", "NOT-CHECKED"}:
            reverts.append(cid)
        else:
            return False, f"bad-verdict:{cid}:{verdict}"

    if not reverts:
        return False, "neutral-or-harmful-not-listed-for-revert"
    if not filed:
        return False, "missing-guard-case-not-filed"
    if not keeps:
        return False, "no-measurable-keep-control"

    classes = {str(row.get("classification") or "") for row in cases}
    if "neutral-or-harmful" not in classes:
        return False, "neutral-or-harmful-class-absent"
    if "missing-guard-case" not in classes:
        return False, "missing-guard-class-absent"

    controls = payload.get("independence_controls") or {}
    rb = (controls.get("rule_b_reviewed_impl") or {}) if isinstance(controls, dict) else {}
    if rb.get("rejected") is not True:
        return False, "cnf-0002-rule-b-inert"
    if rb.get("authorship_only_would_accept") is not True:
        return False, "cnf-0002-rule-b-not-distinguished"
    rc = (controls.get("rule_c_ancestor_author") or {}) if isinstance(controls, dict) else {}
    if rc.get("rejected") is not True:
        return False, "cnf-0002-rule-c-missed"

    flake = payload.get("flake_measurement_demo") or {}
    if str(flake.get("reported_as") or "") != "1/7":
        return False, "flake-not-1/7"
    if str(flake.get("forbidden_overwrite") or "") != "7/7":
        return False, "flake-overwrite-unmarked"

    reviewers = payload.get("reviewers") or []
    ids = [str(r.get("reviewer_id") or "") for r in reviewers if isinstance(r, dict)]
    if len(set(ids)) < 2:
        return False, "reviewers-not-independent"
    if any(r.get("filed_before_seeing_peer") is not True for r in reviewers if isinstance(r, dict)):
        return False, "reviewers-anchored"

    return True, (
        f"ok keeps={len(keeps)} reverts={len(reverts)} filed={len(filed)} "
        f"independent={independent}"
    )


def main() -> int:
    art = Path(__file__).resolve().parents[3] / ART_REL
    if not art.is_file() or art.stat().st_size <= 0:
        print("FAILED:CNF-0127-checks artifact missing")
        return 1
    ok, why = check_artifact(json.loads(art.read_text(encoding="utf-8")))
    print(why)
    if not ok:
        print("FAILED:CNF-0127-checks")
        return 1
    print("SUCCESS:CNF-0127-checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
