#!/usr/bin/env python3
"""Probe 1: cold-resume rehearsal. Reader uses only structured package fields."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import resume as R  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0048.handoff-package.json"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0048-probe1 {msg}")
    return 1


def main() -> int:
    failures = R.run_fixture_battery()
    if failures:
        for item in failures:
            print(f"fixture {item}")
        return fail("fixture battery")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    body = R.payload(doc)
    sentinel = str(
        doc.get("completion_sentinel")
        or body.get("completion_sentinel")
        or doc.get("sentinel")
        or ""
    )
    if "SUCCESS:SYN-0048" not in sentinel or sentinel not in text:
        return fail("sentinel-absent")

    derived = R.next_action(doc)
    recorded = body.get("next_action") or doc.get("next_action") or {}
    if derived.get("kind") != recorded.get("kind"):
        return fail(f"kind mismatch derived={derived} recorded={recorded}")
    if derived.get("unit_id") != recorded.get("unit_id"):
        return fail(f"unit_id mismatch derived={derived} recorded={recorded}")
    if derived.get("kind") != "RESUME-IN-FLIGHT":
        return fail(f"live next_action {derived.get('kind')} expected RESUME-IN-FLIGHT")

    flight = body.get("in_flight") or doc.get("in_flight") or []
    if not flight:
        return fail("live in_flight empty")
    first = flight[0]["unit_id"]
    out_rel = flight[0]["output_path"]
    if (REPO / out_rel).is_file():
        return fail(f"in_flight[0] {first} output actually exists at {out_rel}")
    if derived.get("unit_id") != first:
        return fail(f"reader did not select first in_flight unit {first}")

    planted = json.loads(json.dumps(doc))
    idle = {
        "kind": "PROGRAM-IDLE",
        "instruction": "planted idle; must be ignored",
        "unit_id": None,
    }
    planted["next_action"] = idle
    planted["cold_resume"] = {
        "method": "planted method string is long enough",
        "next_action": idle,
        "transcript": ["planted transcript padding ok"],
        "rehearsal_result": "PASS",
    }
    if isinstance(planted.get("report"), dict):
        planted["report"]["next_action"] = idle
        planted["report"]["cold_resume"] = planted["cold_resume"]
    replanted = R.next_action(planted)
    if replanted.get("kind") != "RESUME-IN-FLIGHT":
        return fail("reader followed planted next_action prose")

    print(
        json.dumps(
            {
                "derived": derived,
                "first_in_flight": first,
                "fixture_battery": "PASS",
                "ignored_planted_idle": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("SUCCESS:SYN-0048-probe1 cold-resume rehearsal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
