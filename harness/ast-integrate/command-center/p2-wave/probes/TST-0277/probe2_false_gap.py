#!/usr/bin/env python3
"""Named probe 2: false-gap control — a covered panel must not recruit.

Mechanically different from probe 1: asserts silence (no trigger, no
recruited seats, exclusive claim absent) and a hole/covered differential
on the recruitment boolean.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from checks import covered_verdict, hole_verdict  # noqa: E402
from fixtures import UNIQUE_CLAIM_ID, UNIQUE_CLAIM_TEXT  # noqa: E402
from simulate import covered_run, hole_run  # noqa: E402

ART = REPO / "command-center/receipts/TST-0277.json"
UNIT = "TST-0277"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    live_covered = covered_run()
    live_hole = hole_run(recruited_mode="substantive")
    if not live_covered.get("completed") or not live_hole.get("completed"):
        return fail("a live run did not complete")

    cov_v = covered_verdict(live_covered)
    if not cov_v["pass"]:
        return fail("covered panel triggered recruitment", cov_v)
    hole_v = hole_verdict(live_hole)
    if not hole_v["pass"]:
        return fail("hole control collapsed in probe2", hole_v)

    if live_covered["recruitment"]["triggered"] == live_hole["recruitment"]["triggered"]:
        return fail("recruitment boolean did not differ across both states")
    if UNIQUE_CLAIM_ID in live_covered["transcript"] or UNIQUE_CLAIM_TEXT in live_covered["transcript"]:
        return fail("exclusive recruited claim leaked into covered run")

    hole_sha = sha(live_hole["transcript"])
    covered_sha = sha(live_covered["transcript"])
    if hole_sha == covered_sha:
        return fail("transcripts collided")

    runs = {r.get("id"): r for r in (doc.get("runs") or []) if isinstance(r, dict)}
    art_cov = runs.get("fully-covered")
    art_hole = runs.get("competency-hole")
    if not art_cov or not art_hole:
        return fail("artifact missing a required run")
    if art_cov.get("transcript") != live_covered["transcript"]:
        return fail("artifact fully-covered != live")
    if art_hole.get("transcript") != live_hole["transcript"]:
        return fail("artifact competency-hole != live")
    if art_cov.get("recruitment_triggered") is not False:
        return fail("artifact covered run claims a trigger")
    if art_cov.get("recruited_seat_ids"):
        return fail("artifact covered run seated a recruit")

    cmp_ = doc.get("comparison") or {}
    if cmp_.get("recruitment_differs") is not True:
        return fail("artifact comparison.recruitment_differs is not true")
    if cmp_.get("hole_transcript_sha256") != hole_sha:
        return fail("artifact hole sha mismatch")
    if cmp_.get("covered_transcript_sha256") != covered_sha:
        return fail("artifact covered sha mismatch")

    out = {
        "probe": "probe2-false-gap",
        "unit_id": UNIT,
        "pass": True,
        "covered_completed": True,
        "hole_completed": True,
        "covered_triggered": False,
        "hole_triggered": True,
        "recruitment_differs": True,
        "exclusive_claim_absent_from_covered": True,
        "hole_transcript_sha256": hole_sha,
        "covered_transcript_sha256": covered_sha,
        "artifact_matches_live": True,
    }
    (HERE / "probe2-false-gap.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:TST-0277-probe2 false-gap silence and both-states differential")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
