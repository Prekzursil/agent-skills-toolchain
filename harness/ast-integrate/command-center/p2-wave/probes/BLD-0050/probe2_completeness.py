#!/usr/bin/env python3
"""Probe 2: completeness, CONSUMED-not-reaudited, direction, independent re-walk.

Catalog controls:
  * every network call and subprocess spawn site maps to exactly one boundary
  * ADV-0021 install path is CONSUMED, not re-audited (no STRIDE rebuild)
  * a bidirectional crossing is recorded twice with distinct checks
  * reviewer independently walks two flows and reports missed crossings
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from census import (  # noqa: E402
    consumed_not_reaudited,
    direction_pairs,
    build_census,
)
from walk import REPO, find_sites, site_map  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "BLD-0050.json"

REVIEW_FLOWS = (
    {
        "id": "flow-cursor-agent-spawn",
        "path": "command-center/p2-wave/seed-stage/dispatch_cursor.py",
        "needle": "proc = subprocess.Popen(",
        "must_map_to": "TB-SPAWN-CURSOR-AGENT",
        "kind": "spawn",
    },
    {
        "id": "flow-a2-banned-keys",
        "path": "command-center/p2-wave/probes/ARC-0010/generator.py",
        "needle": "if k in BANNED_KEYS:",
        "must_boundary": "TB-A2-TYPED-OUT",
        "must_status": "CHECKED",
    },
)


def _fail(msg: str) -> int:
    print(f"FAILED:BLD-0050-probe2 {msg}")
    return 1


def reviewer_walk(census: dict) -> dict:
    """Re-derive two flows from source files, not from the census narrative."""
    missed: list[str] = []
    found: list[dict] = []
    smap = census["site_map"]
    by_id = {b["id"]: b for b in census["boundaries"]}
    for flow in REVIEW_FLOWS:
        path = REPO / flow["path"]
        if not path.is_file():
            missed.append(f"{flow['id']}:source-absent")
            continue
        text = path.read_text(encoding="utf-8")
        if flow["needle"] not in text:
            missed.append(f"{flow['id']}:needle-absent")
            continue
        line = text[: text.find(flow["needle"])].count("\n") + 1
        rec = {"id": flow["id"], "path": flow["path"], "line": line}
        if "must_map_to" in flow:
            sid = f"{flow['path']}:{line}:{flow['kind']}"
            mapped = smap.get(sid)
            rec["site_id"] = sid
            rec["mapped"] = mapped
            if mapped != flow["must_map_to"]:
                missed.append(f"{flow['id']}:map-want={flow['must_map_to']} got={mapped}")
        if "must_boundary" in flow:
            row = by_id.get(flow["must_boundary"])
            rec["boundary"] = flow["must_boundary"]
            rec["status"] = None if row is None else row["check_status"]
            if row is None:
                missed.append(f"{flow['id']}:boundary-absent")
            elif row["check_status"] != flow["must_status"]:
                missed.append(
                    f"{flow['id']}:status-want={flow['must_status']} got={row['check_status']}"
                )
        found.append(rec)
    return {
        "reviewer_id": "BLD-0050-probe2-independent-rewalk",
        "independent": True,
        "vendor_role": "anthropic-reviewer-stand-in (mechanical re-walk of two flows)",
        "flows": found,
        "missed_crossings": missed,
        "verdict": "PASS" if not missed else "FAIL",
    }


def main() -> int:
    live_sites = find_sites(REPO)
    live_map = site_map(live_sites)
    census = build_census()
    known = {b["id"] for b in census["boundaries"]}
    if census["counts"]["unmapped_sites"] != 0:
        return _fail(f"unmapped={census['unmapped']}")
    for sid, bid in live_map.items():
        if bid not in known:
            return _fail(f"site {sid} maps to unknown boundary {bid}")

    cons = consumed_not_reaudited(census["boundaries"])
    if cons["re_audited"] or cons["stride_cells_present"]:
        return _fail(f"adv0021-reaudited {cons}")
    if cons["consumed_ids"] != ["TB-INSTALL-ADV0021"]:
        return _fail(f"consumed-set {cons['consumed_ids']}")
    if cons["consumed_from"] != ["ADV-0021"]:
        return _fail(f"consumed-from {cons['consumed_from']}")

    pairs = direction_pairs(census["boundaries"])
    bad_pairs = [
        p
        for p in pairs
        if p["bidirectional"] and not p["distinct_checks"]
    ]
    if bad_pairs:
        return _fail(f"bidirectional-same-check {bad_pairs}")
    if not any(p["bidirectional"] for p in pairs):
        return _fail("no-bidirectional-pairs")

    review = reviewer_walk(census)
    if review["verdict"] != "PASS":
        return _fail(f"reviewer-missed {review['missed_crossings']}")

    if RECEIPT.is_file():
        try:
            art = json.loads(RECEIPT.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return _fail(f"receipt-unparseable:{exc}")
        if art.get("kind") != "trust-boundary-census":
            return _fail("receipt-kind")
        if str(art.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return _fail(f"receipt-state:{art.get('state')}")
        rmap = art.get("site_map") or {}
        rknown = {b["id"] for b in (art.get("boundaries") or []) if isinstance(b, dict)}
        for sid, bid in live_map.items():
            if sid in rmap and rmap[sid] != bid:
                return _fail(f"receipt-map-mismatch {sid} live={bid} receipt={rmap[sid]}")
            if bid not in rknown:
                return _fail(
                    f"live-site {sid} maps to {bid} which the receipt does not enumerate"
                )
        rcons = consumed_not_reaudited(art.get("boundaries") or [])
        if rcons["re_audited"] or rcons["consumed_ids"] != ["TB-INSTALL-ADV0021"]:
            return _fail(f"receipt-consumed {rcons}")
        rpairs = direction_pairs(art.get("boundaries") or [])
        if any(p["bidirectional"] and not p["distinct_checks"] for p in rpairs):
            return _fail("receipt-bidirectional-same-check")

    payload = {
        "spawn_sites": census["counts"]["spawn_sites"],
        "network_sites": census["counts"]["network_sites"],
        "unmapped_sites": 0,
        "consumed": cons,
        "bidirectional_pairs": [p["pair_id"] for p in pairs if p["bidirectional"]],
        "distinct_check_pairs": len(pairs) - len(bad_pairs),
        "reviewer": review,
        "deliverable_absent_from_threat_models": census["counts"][
            "boundaries_in_no_existing_threat_model"
        ],
        "checked": census["counts"]["checked"],
        "unchecked": census["counts"]["unchecked"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"sites={len(live_sites)} unmapped=0 consumed={cons['consumed_ids']} "
        f"reviewer={review['verdict']} absent_from_models="
        f"{payload['deliverable_absent_from_threat_models']}"
    )
    print("SUCCESS:BLD-0050-probe2 completeness CONSUMED direction reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
