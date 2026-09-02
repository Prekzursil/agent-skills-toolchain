#!/usr/bin/env python3
"""Probe 2: collision detector (both states) + staging refusal (both states).

Mechanically different from probe 1: this injects a shared temp root and a
git-add attempt rather than tracing an isolated concurrent run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import isolation as I  # noqa: E402

ART = REPO / "command-center/receipts/TST-0345.json"
SENTINEL = "SUCCESS:TST-0345"


def artifact_error() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return "artifact sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact self-declared {st}"
    return None


def main() -> int:
    err = artifact_error()
    if err:
        print(f"FAILED:TST-0345-probe2 {err}")
        return 1

    good = I.run_isolated_concurrent(n_workers=2, n_writes=8)
    if not good["audit"]["isolated"]:
        print("FAILED:TST-0345-probe2 isolated control did not stay silent")
        print(json.dumps(good["audit"], sort_keys=True, default=str)[:2000])
        return 1
    if good["audit"]["collision_detected"]:
        print("FAILED:TST-0345-probe2 isolated control reported a collision")
        return 1

    collision = I.run_collision_control()
    disjoint = collision["disjoint_files_shared_root"]
    same = collision["same_file_shared_root"]
    if not disjoint["detected"]:
        print(
            "FAILED:TST-0345-probe2 shared temp root with disjoint files "
            "was not detected (detector is not load-bearing)"
        )
        return 1
    if not disjoint["write_path_intersection_empty"]:
        print(
            "FAILED:TST-0345-probe2 disjoint-file collision unexpectedly "
            "had a write-path intersection; shared_temp_roots would not be "
            "shown as the load-bearing signal"
        )
        return 1
    if not same["detected"]:
        print("FAILED:TST-0345-probe2 same-file shared-root collision not detected")
        return 1
    if not collision["detector_fired"]:
        print("FAILED:TST-0345-probe2 collision detector_fired is false")
        return 1

    staging = I.run_staging_refusal()
    if not staging["guarded_attempt"]["refused"]:
        print(
            "FAILED:TST-0345-probe2 worker git add was not refused "
            f"rc={staging['guarded_attempt']['returncode']} "
            f"err={staging['guarded_attempt']['stderr']!r}"
        )
        return 1
    if not staging["index_after_guarded"]["sibling_not_staged"]:
        print(
            "FAILED:TST-0345-probe2 sibling path present in index after guarded add "
            f"{staging['index_after_guarded']}"
        )
        return 1
    if not staging["unguarded_shared_index_control"]["swept_both_siblings"]:
        print(
            "FAILED:TST-0345-probe2 unguarded control did not sweep both siblings "
            "(detector would be inert)"
        )
        return 1
    if not staging["pass"]:
        print("FAILED:TST-0345-probe2 staging refusal bundle failed")
        return 1

    summary = {
        "pass": True,
        "probe": "probe2-collision-and-staging",
        "unit_id": "TST-0345",
        "isolated_control_silent": True,
        "shared_root_disjoint_files_detected": True,
        "shared_root_disjoint_intersection_empty": True,
        "shared_root_same_file_detected": True,
        "staging_refused": True,
        "sibling_not_staged": True,
        "unguarded_sweeps_siblings": True,
        "guarded_returncode": staging["guarded_attempt"]["returncode"],
        "unguarded_cached": staging["unguarded_shared_index_control"]["cached"],
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "collision_detected=True isolated_silent=True staging_refused=True "
        "unguarded_sweeps=True"
    )
    print("SUCCESS:TST-0345-probe2 collision detector and staging refusal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
