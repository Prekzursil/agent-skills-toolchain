#!/usr/bin/env python3
"""Probe 2: seeded-identifier detector control + bypass review.

Both-states: plant a synthetic identifier in a scratch file, confirm the
scan finds it, remove it, confirm silence. Independently, attempt a bypass
of every mitigation before any mitigation is recorded as effective.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from control import run_seeded_control  # noqa: E402
from scan import artifact_payload  # noqa: E402
from scrub import (  # noqa: E402
    m4_location_only_ok,
    minimum_safe_set,
    mitigations_from_bypasses,
    run_bypasses,
)

ART = REPO / "command-center/research/RES-0124.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0124-probe2 {msg}")
    return 1


def main() -> int:
    control = run_seeded_control()
    print("seeded_found=" + str(control["seeded_found"]))
    print("seeded_absent_after_removal=" + str(control["seeded_absent_after_removal"]))
    print("seed_value_reproduced=" + str(control["seed_value_reproduced"]))
    print(
        "negative_users_word_only_silent="
        + str(control["negative_users_word_only_silent"])
    )
    print("tree_seeded_identifier_count=" + str(control["tree_seeded_identifier_count"]))
    print("pass=" + str(control["pass"]))
    if not control["pass"]:
        return fail("detector control did not pass")
    if control["seed_value_reproduced"] is not False:
        return fail("control reproduced a seed value")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("research artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    payload = artifact_payload(doc)
    stored = payload.get("detector_control") or {}
    if stored.get("pass") is not True:
        return fail("artifact detector_control.pass is not true")
    if stored.get("seed_value_reproduced") is not False:
        return fail("artifact reproduced a seed value")
    if not m4_location_only_ok(doc):
        return fail("artifact failed location-only / no-value check")

    live_bypasses = run_bypasses()
    live_mits = mitigations_from_bypasses(live_bypasses, m4_ok=True)
    stored_mits = (payload.get("scrubbing_contract") or {}).get("mitigations") or []
    live_map = {m["id"]: m for m in live_mits}
    stored_map = {m["id"]: m for m in stored_mits}
    if set(live_map) != set(stored_map):
        return fail("mitigation id set mismatch")
    for mid, live_m in live_map.items():
        stored_m = stored_map[mid]
        if bool(live_m["recorded_effective"]) != bool(stored_m["recorded_effective"]):
            return fail(f"{mid} recorded_effective mismatch")
        if live_m["recorded_effective"] and any(
            a["survived"] for a in live_m["bypass_attempts"]
        ):
            return fail(f"{mid} marked effective but a bypass survived")
        print(
            f"mitigation {mid} effective={live_m['recorded_effective']} "
            f"bypasses={len(live_m['bypass_attempts'])}"
        )
        for a in live_m["bypass_attempts"]:
            print(f"  bypass {a['id']} survived={a['survived']}")

    live_safe = minimum_safe_set(live_mits)
    stored_safe = (payload.get("scrubbing_contract") or {}).get("minimum_safe_set") or []
    if list(live_safe) != list(stored_safe):
        return fail("minimum_safe_set mismatch")
    if "M1_line_regex" in live_safe:
        return fail("naive line regex recorded in the minimum safe set")
    print("minimum_safe_set=" + ",".join(live_safe))
    print(
        "SUCCESS:RES-0124-probe2 seeded-identifier detector control"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
