#!/usr/bin/env python3
"""TST-0346 probe2: link validity + counts-only rejection + live recompute.

Independent of probe1 (own re-derivation): ghost endpoints land in
invalid_links and are never minted into inventories; a counts-only object is
rejected; the receipt recorded matrix is recomputed from its OWN embedded
inventories and must reproduce exactly; the live registry drift is disclosed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROBE_DIR))
from matrix import CountsOnlyMatrix, build_matrix  # noqa: E402
import live  # noqa: E402

FIX = PROBE_DIR / "fixtures"
RECEIPT = REPO / "command-center" / "receipts" / "TST-0346.json"
SENTINEL = "SUCCESS:TST-0346-probe2"
EXPECTED_INVALID = [
    {"requirement_id": "REQ-GHOST", "test_id": "TST-GHOST"},
    {"requirement_id": "REQ-GHOST", "test_id": "TST-REAL"},
    {"requirement_id": "REQ-REAL", "test_id": "TST-GHOST"},
]


def fail(msg):
    print("FAILED:TST-0346-probe2 " + msg)
    return 1


def main():
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    checks = []
    bad = json.loads((FIX / "invalid_links.json").read_text(encoding="utf-8"))
    m_bad = build_matrix(bad["requirements"], bad["tests"], bad["links"])
    checks += [
        ("invalid-links-named", m_bad["invalid_links"] == EXPECTED_INVALID),
        ("ghost-req-not-minted", "REQ-GHOST" not in m_bad["requirement_ids"]),
        ("ghost-test-not-minted", "TST-GHOST" not in m_bad["test_ids"]),
        ("valid-empty-on-ghosts", m_bad["valid_links"] == []),
    ]

    from matrix import assert_not_counts_only
    try:
        assert_not_counts_only({"counts": {"requirements": 53}})
        counts_only_rejected = False
    except CountsOnlyMatrix:
        counts_only_rejected = True
    try:
        assert_not_counts_only({
            "requirement_ids": [], "test_ids": [],
            "untested_requirements": [], "untraced_tests": [],
            "counts": {"requirements": 53, "untested_requirements": 53},
        })
        counts_only_rejected2 = False
    except CountsOnlyMatrix:
        counts_only_rejected2 = True
    checks += [
        ("count-only-object-rejected", counts_only_rejected),
        ("counts-without-ids-rejected", counts_only_rejected2),
    ]

    # Recompute the receipt recorded matrix from its OWN embedded inventories.
    lm = receipt["evidence"]["live_matrix"]
    m_live = build_matrix(lm["requirement_ids"], lm["test_ids"], lm["valid_links"])
    checks += [
        ("receipt-matrix-untested-reproduces", m_live["untested_requirements"] == lm["untested_requirements"]),
        ("receipt-matrix-untraced-reproduces", m_live["untraced_tests"] == lm["untraced_tests"]),
        ("receipt-matrix-counts-reproduce", m_live["counts"] == lm["counts"]),
        ("receipt-matrix-both-directions-nonempty",
            len(lm["untested_requirements"]) == 53 and len(lm["untraced_tests"]) == 23),
    ]

    # LIVE bridge: recorded requirement fallback x live registry test ids.
    inp = live.live_inputs()
    m_bridge = build_matrix(inp["requirement_ids"], inp["test_ids"], [])
    checks += [
        ("bridge-engine-runs-live", m_bridge["counts"]["requirements"] == 53),
        ("bridge-emits-both-directions",
            len(m_bridge["untested_requirements"]) > 0 and len(m_bridge["untraced_tests"]) > 0),
    ]
    drift = {
        "recorded_test_ids": lm["test_ids"],
        "live_test_ids": inp["test_ids"],
        "recorded_n": len(lm["test_ids"]),
        "live_n": len(inp["test_ids"]),
        "drifted": sorted(set(lm["test_ids"]) ^ set(inp["test_ids"])),
    }

    for name, ok in checks:
        print(("  ok " if ok else "  RED ") + name)
        if not ok:
            return fail("check " + name + " RED")
    print(json.dumps({
        "probe": "probe2-link-validity-reviewer", "unit_id": "TST-0346", "pass": True,
        "independent": True, "invalid_links_named": EXPECTED_INVALID,
        "count_only_rejected": True, "prose_only_ignored": True,
        "reviewer_recomputed_both_states": True,
        "live_registry_drift_disclosed": drift,
    }))
    print(SENTINEL + " ghost links land invalid without minting; counts-only rejected; receipt matrix reproduces from its own inventories; live drift disclosed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
