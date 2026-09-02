#!/usr/bin/env python3
"""Probe 2: duplicate suppression + round-trip close.

Catalog tests:
  * no question already answered in OWNER-DECISIONS.md may appear
  * a recorded answer must close the corresponding claim on re-run without re-asking
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from packet import (  # noqa: E402
    ESTATE_DECISIONS_REL,
    build_packet,
    estate_decisions_intact,
    load_unresolved,
    parse_decisions,
    record_answer,
    render_decisions,
)

ART = REPO / "command-center/receipts/CNF-0161.json"
LIVE_DECISIONS = REPO / ESTATE_DECISIONS_REL
FIXTURE = HERE / "fixtures" / "unresolved.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0161-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0161" not in json.dumps(doc):
        return fail("sentinel-absent")

    loaded = load_unresolved(FIXTURE)
    claims = loaded["claims"]
    if len(claims) != 2:
        return fail(f"fixture claims={len(claims)}")

    first, skipped = build_packet(claims, decisions=[])
    if skipped or [e["claim_id"] for e in first] != ["CLAIM-TRI-001", "CLAIM-TRI-002"]:
        return fail(f"first open {[e['claim_id'] for e in first]} skipped={skipped}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    after_owner = record_answer(
        [],
        claim_id=first[0]["claim_id"],
        question=first[0]["question"],
        answer="Close as AMBIGUOUS-CLAIM. Owner recorded this in the probe.",
        source="owner",
        recorded_at=now,
    )
    second, skipped_owner = build_packet(claims, after_owner)
    ids_second = [e["claim_id"] for e in second]
    if "CLAIM-TRI-001" in ids_second:
        return fail("answered claim was re-asked")
    if ids_second != ["CLAIM-TRI-002"]:
        return fail(f"after owner answer open={ids_second}")
    if not any(s["claim_id"] == "CLAIM-TRI-001" for s in skipped_owner):
        return fail("answered claim not listed as skipped")

    third, skipped_again = build_packet(claims, after_owner)
    if [e["claim_id"] for e in third] != ["CLAIM-TRI-002"]:
        return fail("re-run re-asked a closed claim")
    if not any(s["claim_id"] == "CLAIM-TRI-001" for s in skipped_again):
        return fail("second re-run lost skip")

    after_default = record_answer(
        after_owner,
        claim_id=second[0]["claim_id"],
        question=second[0]["question"],
        answer=second[0]["default_if_unanswered"],
        source="default",
        recorded_at=now,
    )
    fourth, skipped_all = build_packet(claims, after_default)
    if fourth:
        return fail(f"default-applied claim still open {[e['claim_id'] for e in fourth]}")
    if {s["claim_id"] for s in skipped_all} != {"CLAIM-TRI-001", "CLAIM-TRI-002"}:
        return fail(f"skip set {skipped_all}")

    rendered = render_decisions(after_owner)
    parsed = parse_decisions(rendered)
    fifth, _ = build_packet(claims, parsed)
    if [e["claim_id"] for e in fifth] != ["CLAIM-TRI-002"]:
        return fail("round-trip through markdown re-asked the closed claim")

    if not LIVE_DECISIONS.is_file():
        return fail("live OWNER-DECISIONS.md missing")
    live_text = LIVE_DECISIONS.read_text(encoding="utf-8")
    if not estate_decisions_intact(live_text):
        return fail("estate OWNER-DECISIONS.md missing generated marker or overwritten")
    live_decisions = parse_decisions(live_text)
    live_src = load_unresolved(REPO / "command-center/receipts/CNF-0160.json")
    live_open, _ = build_packet(live_src["claims"], live_decisions)
    live_ids = {e["claim_id"] for e in live_open}
    answered_ids = {
        d["claim_id"] for d in live_decisions if (d.get("answer") or "").strip()
    }
    overlap = live_ids & answered_ids
    if overlap:
        return fail(f"live packet re-asks answered claims {sorted(overlap)}")

    print(
        json.dumps(
            {
                "probe": "probe2-duplicate-roundtrip",
                "unit_id": "CNF-0161",
                "first_open": [e["claim_id"] for e in first],
                "after_owner_open": ids_second,
                "after_default_open": [e["claim_id"] for e in fourth],
                "markdown_roundtrip_open": [e["claim_id"] for e in fifth],
                "answered_claim_not_reasked": True,
                "live_answered_not_reasked": True,
                "pass": True,
            }
        )
    )
    print("SUCCESS:CNF-0161-probe2 duplicate check and round-trip close")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
