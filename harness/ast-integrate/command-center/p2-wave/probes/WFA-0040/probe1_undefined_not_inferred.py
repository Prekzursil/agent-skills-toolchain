#!/usr/bin/env python3
"""Probe 1: absence is UNDEFINED, never inferred as a safe-default.

Both-states: plant-none and plant-inferred-graceful stay UNDEFINED on all four
modes; plant-four-modes is EVIDENCED on all four. A mutant that maps silence
to GRACEFUL is detected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import FOUR_MODES, planted_candidates  # noqa: E402
from extractor import FORBIDDEN_STATUSES, extract_one  # noqa: E402

OUT = REPO / "command-center" / "wfa" / "WFA-0040-extract-failure-behaviour.json"
SENTINEL = "SUCCESS:WFA-0040"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0040-probe1 {msg}")
    return 1


def mutant_infer_graceful(candidate: dict) -> dict:
    """Broken extractor: unnamed modes become GRACEFUL. Must be caught."""
    row = extract_one(candidate)
    for mode in FOUR_MODES:
        rec = row["modes"][mode]
        if rec["status"] == "UNDEFINED":
            rec["status"] = "GRACEFUL"
            rec["inferred_safe_default"] = True
    return row


def assert_all(row: dict, status: str, cid: str) -> str | None:
    for mode in FOUR_MODES:
        rec = row["modes"][mode]
        if rec["status"] != status:
            return f"{cid}.{mode} status={rec['status']} want={status}"
        if rec.get("inferred_safe_default") is True:
            return f"{cid}.{mode} inferred_safe_default=true"
        if str(rec["status"]).upper() in FORBIDDEN_STATUSES:
            return f"{cid}.{mode} forbidden status {rec['status']}"
    return None


def main() -> int:
    plants = {c["id"]: c for c in planted_candidates()}
    none = extract_one(plants["plant-none"])
    inferred = extract_one(plants["plant-inferred-graceful"])
    four = extract_one(plants["plant-four-modes"])
    err = assert_all(none, "UNDEFINED", "plant-none")
    if err:
        return fail(err)
    err = assert_all(inferred, "UNDEFINED", "plant-inferred-graceful")
    if err:
        return fail(err)
    err = assert_all(four, "EVIDENCED", "plant-four-modes")
    if err:
        return fail(err)
    if not none["no_failure_behaviour"]:
        return fail("plant-none no_failure_behaviour is false")
    if four["no_failure_behaviour"]:
        return fail("plant-four-modes wrongly marked no_failure_behaviour")

    broken = mutant_infer_graceful(plants["plant-none"])
    fired = any(
        broken["modes"][m]["status"] == "GRACEFUL" for m in FOUR_MODES
    )
    if not fired:
        return fail("graceful-inference mutant did not fire")
    live_none_ok = all(none["modes"][m]["status"] == "UNDEFINED" for m in FOUR_MODES)
    if not live_none_ok:
        return fail("live extractor not silent on the good (undefined) state")

    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact missing")
    text = OUT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact self-declared {doc.get('state')}")
    rows = {r["candidate_id"]: r for r in (doc.get("rows") or [])}
    if "plant-none" not in rows:
        return fail("artifact missing plant-none")
    err = assert_all(rows["plant-none"], "UNDEFINED", "artifact.plant-none")
    if err:
        return fail(err)
    for row in rows.values():
        for mode in FOUR_MODES:
            st = str((row.get("modes") or {}).get(mode, {}).get("status") or "")
            if st.upper() in FORBIDDEN_STATUSES:
                return fail(f"artifact {row.get('candidate_id')}.{mode} status={st}")

    payload = {
        "pass": True,
        "probe": "probe1-undefined-not-inferred",
        "unit_id": "WFA-0040",
        "plant_none_all_undefined": True,
        "plant_inferred_not_promoted": True,
        "plant_four_all_evidenced": True,
        "mutant_graceful_fired": True,
        "silent_on_good_state": True,
        "both_states": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "none=UNDEFINED inferred=UNDEFINED four=EVIDENCED "
        "mutant_graceful_fired=True"
    )
    print("SUCCESS:WFA-0040-probe1 absence recorded UNDEFINED, never inferred")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
