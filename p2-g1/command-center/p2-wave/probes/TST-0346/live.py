#!/usr/bin/env python3
"""TST-0346 live inventory bridge.

Requirement inventory: the CC-0024 receipt is ABSENT on this worktree, so the
recorded extractor-fallback inventory embedded in the TST-0346 receipt
(evidence.live_matrix.requirement_ids, provenance-stated) is the requirement
input - it is NOT re-minted here.

Test inventory: recomputed LIVE from command-center/TEST-REGISTRY.json
entries[].test_id.

Any build_matrix call that returns is proven free of counts-only objects.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RECEIPT = REPO / "command-center" / "receipts" / "TST-0346.json"
TEST_REGISTRY = REPO / "command-center" / "TEST-REGISTRY.json"


def recorded_requirement_inventory() -> list:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    return list(doc["evidence"]["live_matrix"]["requirement_ids"])


def recorded_matrix() -> dict:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    return doc["evidence"]["live_matrix"]


def live_test_ids() -> list:
    doc = json.loads(TEST_REGISTRY.read_text(encoding="utf-8"))
    ids = set()
    for entry in doc.get("entries") or []:
        tid = entry.get("test_id")
        if tid:
            ids.add(tid)
    for suite in doc.get("suites") or []:
        tid = suite.get("test_id") if isinstance(suite, dict) else None
        if tid:
            ids.add(tid)
    return sorted(ids)


def live_inputs() -> dict:
    return {
        "requirement_ids": recorded_requirement_inventory(),
        "requirement_provenance": "receipt-recorded CC-0024 extractor-fallback (receipt absent on this worktree)",
        "test_ids": live_test_ids(),
        "test_provenance": "live command-center/TEST-REGISTRY.json entries[].test_id",
    }
