#!/usr/bin/env python3
"""Named probe 2: a handoff missing the re-anchored goal must fail validation.

Independent of probe 1's exception path: this probe builds a typed-looking
document whose first section is not a goal, and asserts both the API and the
schema reject it. The live artifact must show goal as section 1.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import handoff as H  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0414.json"
SENTINEL = "SENTINEL:IMP-0414:HANDOFF-TYPED-ONLY"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0414-probe2 {msg}")
    return 1


def context_only() -> list[H.TypedSection]:
    return [
        H.make_section(
            "context",
            "No goal here",
            {"note": "completeness must fail without a re-anchored goal"},
            id="context",
        )
    ]


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"artifact unparseable {exc}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")

    api_failed = False
    api_msg = ""
    try:
        H.accept_handoff(
            unit_id="IMP-0414",
            sentinel=SENTINEL,
            sections=context_only(),
        )
    except H.HandoffCompletenessError as exc:
        api_failed = True
        api_msg = str(exc)
    if not api_failed or "goal" not in api_msg.lower():
        return fail("API accepted a handoff with no goal section")

    drifted = {
        "kind": "typed-handoff",
        "schema_version": 1,
        "unit_id": "IMP-0414",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "sections": [
            {
                "id": "context",
                "kind": "context",
                "ordinal": 1,
                "title": "Goal drifted off the top",
                "body": {"note": "first section is not goal"},
                "evidence_anchors": [],
            }
        ],
    }
    schema_errors = H.validate_document(drifted)
    if not schema_errors:
        return fail("schema accepted a handoff whose section 1 is not goal")

    live = H.load_handoff(ART)
    sections = live.to_dict().get("sections") or []
    if not sections:
        return fail("live artifact has no sections")
    if sections[0].get("kind") != "goal" or sections[0].get("ordinal") != 1:
        return fail("live artifact goal is not section 1")
    if not sections[0].get("evidence_anchors"):
        return fail("live goal has no evidence anchors")
    if any(s.get("kind") == "goal" for s in sections[1:]):
        return fail("live artifact has a drifted extra goal")

    prefix = H.prefix_for_next_agent(live)
    if prefix[0]["kind"] != "goal":
        return fail("prefix_for_next_agent did not lead with goal")

    payload = {
        "pass": True,
        "probe": "probe2-missing-goal-fails",
        "unit_id": "IMP-0414",
        "api_rejected_missing_goal": True,
        "schema_rejected_nongoal_first": True,
        "live_section_1_kind": sections[0]["kind"],
        "live_section_1_ordinal": sections[0]["ordinal"],
        "schema_error_sample": schema_errors[0][:200],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "missing_goal_rejected=True nongoal_first_invalid=True "
        "live_goal_section_1=True"
    )
    print("SUCCESS:IMP-0414-probe2 missing re-anchored goal fails validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
