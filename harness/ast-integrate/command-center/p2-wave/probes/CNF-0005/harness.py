#!/usr/bin/env python3
"""Run the CNF-0005 100-brief clean scan and the one-brief leak control."""
from __future__ import annotations

from typing import Any

from builder import ALLOWED_FIELDS, DENIED_FIELDS, build_brief
from corpus import INJECT_INDEX, N_BRIEFS, load_corpus
from detector import inject_conclusion, scan_brief


def run_clean_scan(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    flagged = []
    vacuous = []
    for rec in receipts:
        brief = build_brief(rec)
        finding = scan_brief(brief, rec)
        rows.append(finding)
        if finding["vacuous"]:
            vacuous.append(finding["claim_id"])
        if finding["leak"]:
            flagged.append(finding["claim_id"])
    return {
        "briefs": len(rows),
        "leaks_found": len(flagged),
        "flagged_ids": flagged,
        "vacuous_receipts": len(vacuous),
        "vacuous_ids": vacuous,
        "rows": rows,
    }


def run_leak_control(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    if not (0 <= INJECT_INDEX < len(receipts)):
        raise IndexError("inject index out of range")
    flagged = []
    injected_id = receipts[INJECT_INDEX]["claim_id"]
    injected_finding = None
    for i, rec in enumerate(receipts):
        brief = build_brief(rec)
        if i == INJECT_INDEX:
            brief = inject_conclusion(brief, rec)
        finding = scan_brief(brief, rec)
        if finding["leak"]:
            flagged.append(finding["claim_id"])
        if i == INJECT_INDEX:
            injected_finding = finding
    others = [cid for cid in flagged if cid != injected_id]
    fired = injected_id in flagged
    silent_on_others = len(others) == 0
    clean = run_clean_scan(receipts)
    silent_in_both = (clean["leaks_found"] == 0) and (not fired)
    return {
        "injected_brief_id": injected_id,
        "injected_index": INJECT_INDEX,
        "flagged_ids": flagged,
        "fired_on_injected": fired,
        "silent_on_others": silent_on_others,
        "silent_in_both_states": silent_in_both,
        "injected_needle_count": (injected_finding or {}).get("needle_count", 0),
        "injected_fragments": (injected_finding or {}).get("fragments") or [],
        "allow_list": list(ALLOWED_FIELDS),
        "deny_list": list(DENIED_FIELDS),
        "n_briefs": N_BRIEFS,
    }


def from_artifact(doc: dict[str, Any], key: str) -> dict[str, Any]:
    """Read a domain field from a harness-report receipt.

    receipt_core forbids extra top-level keys, so emit stores scan results
    under report.<key> (and may also copy them into extensions).
    """
    if not isinstance(doc, dict):
        return {}
    val = doc.get(key)
    if isinstance(val, dict):
        return val
    for bag_name in ("report", "extensions"):
        bag = doc.get(bag_name)
        if isinstance(bag, dict) and isinstance(bag.get(key), dict):
            return bag[key]
    return {}


def run_harness() -> dict[str, Any]:
    receipts, meta = load_corpus()
    if len(receipts) < 100:
        raise RuntimeError(f"corpus too small: {len(receipts)}")
    clean = run_clean_scan(receipts)
    control = run_leak_control(receipts)
    return {
        "receipts": receipts,
        "corpus": meta,
        "clean_scan": clean,
        "deliberate_leak_control": control,
    }
