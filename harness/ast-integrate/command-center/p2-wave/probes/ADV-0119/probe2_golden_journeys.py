#!/usr/bin/env python3
"""Probe 2: golden journeys after rollback + leftover-N-state control.

Mechanically different from probe 1: an inventory can match while leftover
N-format state makes N-1 behaviour fail.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    run_clean_n1_control,
    run_honest_rollback,
    run_leftover_n_state_control,
    run_naive_rollback_control,
)

ART = REPO / "command-center/adversarial/ADV-0119-rollback-user-data-preservation.json"
SENTINEL_FRAG = "SUCCESS:ADV-0119 emitted ONLY when the artifact"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
UNIT = "ADV-0119"


def _check_artifact() -> tuple[int, dict | None]:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0119-probe2 artifact missing")
        return 1, None
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:ADV-0119-probe2 unparseable {exc}")
        return 1, None
    if SENTINEL_FRAG not in text:
        print("FAILED:ADV-0119-probe2 sentinel-absent")
        return 1, None
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        print(f"FAILED:ADV-0119-probe2 self-declared:{st}")
        return 1, None
    return 0, doc


def main() -> int:
    rc, doc = _check_artifact()
    if rc != 0:
        return rc
    with tempfile.TemporaryDirectory(prefix="adv0119-p2-") as tmp:
        root = Path(tmp)
        honest = run_honest_rollback(root / "honest")
        clean = run_clean_n1_control(root / "clean")
        leftover = run_leftover_n_state_control(root / "leftover")
        naive = run_naive_rollback_control(root / "naive")
    post_j = ((honest.get("journeys") or {}).get("post_rollback") or {})
    payload = {
        "ok": bool(
            honest.get("pass")
            and clean.get("pass")
            and leftover.get("pass")
            and naive.get("pass")
        ),
        "probe": "probe2-golden-journeys",
        "unit_id": UNIT,
        "post_rollback_journeys_pass": post_j.get("pass"),
        "clean_n1_journeys_pass": (clean.get("journeys") or {}).get("pass"),
        "leftover_state_fired": leftover.get("fired_on_bad_state"),
        "leftover_user_inventory_still_matches": leftover.get(
            "user_inventory_still_matches"
        ),
        "naive_fired": naive.get("fired_on_bad_state"),
        "live_canary_intact": all(
            (
                honest.get("live_canary_intact"),
                clean.get("live_canary_intact"),
                leftover.get("live_canary_intact"),
                naive.get("live_canary_intact"),
            )
        ),
    }
    print(json.dumps(payload, sort_keys=True))
    if not honest.get("pass") or not post_j.get("pass"):
        print("FAILED:ADV-0119-probe2 post-rollback golden journeys")
        return 1
    if not clean.get("pass"):
        print("FAILED:ADV-0119-probe2 clean N-1 control")
        return 1
    if not leftover.get("pass"):
        print("FAILED:ADV-0119-probe2 leftover N-format state did not break journeys")
        return 1
    if leftover.get("user_inventory_still_matches") is not True:
        print("FAILED:ADV-0119-probe2 leftover-state control mutated user files")
        return 1
    if not naive.get("pass"):
        print("FAILED:ADV-0119-probe2 naive rollback control did not fire")
        return 1
    art_j = ((doc or {}).get("golden_journeys") or {}).get("post_rollback_pass")
    if art_j is not True:
        print("FAILED:ADV-0119-probe2 artifact journey claim drifted")
        return 1
    print(
        "SUCCESS:ADV-0119-probe2 golden journeys after rollback; "
        "leftover N-format state fails journeys while user inventory still matches"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
