#!/usr/bin/env python3
"""Probe 2: seed a known-vulnerable dependency and confirm detection.

Both-states: requests==2.31.0 fires on snapshot B; requests==2.32.2 is silent.
The same seed is silent on snapshot A (advisory not yet published). A
prompt-only scratch never produces a package hit — that is the bypass of
'the scanner works' as a mitigation for this program's payload type.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scan as S  # noqa: E402

UNIT = "RES-0051"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    ctl = S.seeded_control()
    print(
        json.dumps(
            {
                "probe": "probe2-seeded-vulnerable",
                "unit_id": UNIT,
                "positive_detection": ctl["positive_detection"],
                "detected_ids": ctl["detected_ids"],
                "patched_silent": ctl["patched_silent"],
                "seeded_silent_on_earlier_snapshot": ctl["seeded_silent_on_earlier_snapshot"],
                "skill_never_detected": ctl["skill_never_detected"],
                "pass": ctl["pass"],
            },
            sort_keys=True,
        )
    )
    if not ctl["pass"]:
        return fail("seeded control failed both-states or snapshot-date filter")
    if not ctl["positive_detection"]:
        return fail("seeded requests==2.31.0 was not detected on snapshot B")
    if S.HIT_ID not in ctl["detected_ids"]:
        return fail(f"detection missed {S.HIT_ID}")
    if not ctl["patched_silent"]:
        return fail("patched requests==2.32.2 was not silent")
    if not ctl["seeded_silent_on_earlier_snapshot"]:
        return fail("seed fired on snapshot A; date cut is not enforced")
    if not ctl["skill_never_detected"]:
        return fail("prompt payload produced a package hit")

    art_path = S.artifact_path()
    if not art_path.is_file() or art_path.stat().st_size <= 0:
        return fail("research artifact missing")
    text = art_path.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    sentinel = S.catalog_sentinel()
    if sentinel not in text:
        return fail("catalog completion_sentinel absent from artifact")
    recorded = doc.get("seeded_vulnerable_fixture") or {}
    if recorded.get("positive_detection") is not True:
        return fail("artifact did not record positive detection")
    if S.HIT_ID not in (recorded.get("detected_ids") or []):
        return fail("artifact detection ids drifted")
    bypasses = doc.get("reviewer_bypass_attempts") or []
    if len(bypasses) < 3:
        return fail("reviewer did not attempt bypasses of listed mitigations")
    fired = [b for b in bypasses if b.get("bypass_constructed") is True]
    if not fired:
        return fail("every mitigation was recorded effective without a constructed bypass")
    print(
        f"detected={ctl['detected_ids']} patched_silent={ctl['patched_silent']} "
        f"skill_unscannable={ctl['skill_never_detected']} bypasses={len(fired)}"
    )
    print("SUCCESS:RES-0051-probe2 positive detection on seeded vulnerable fixture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
