#!/usr/bin/env python3
"""Named probe 2: empty store must not silently produce a confident ranking.

Negative control (must FIRE): missing file, empty participants, and
zero-history-with-stored-zeros. All three must degrade loudly to
explicit-order, emit a named degradation event, leave ranking empty, and
not assign score 0.0 as a calibration rank.

Both-states control (must be SILENT on the good state): the same warm store
used by probe 1 must NOT emit degradation and MUST produce a confident ranking.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0268-probe2 {msg}")
    return 1


def assert_degraded(label: str, result: dict) -> str | None:
    if result.get("confident_ranking") is True:
        return f"{label} confident_ranking=true"
    if not str(result.get("strategy_used") or "").startswith("degraded:"):
        return f"{label} strategy={result.get('strategy_used')}"
    deg = result.get("degradation") or {}
    if not isinstance(deg, dict):
        return f"{label} degradation missing"
    if deg.get("loud") is not True:
        return f"{label} degradation not loud"
    if not deg.get("event"):
        return f"{label} degradation event unnamed"
    if deg.get("fallback") != "explicit-order":
        return f"{label} fallback={deg.get('fallback')}"
    if result.get("ranking"):
        return f"{label} ranking not empty: {result.get('ranking')}"
    if result.get("score_table"):
        return f"{label} score_table present on empty store"
    scores = [s.get("score") for s in (result.get("seated") or [])]
    if any(sc == 0 or sc == 0.0 for sc in scores):
        return f"{label} seated with score 0 (ranking-on-zeros)"
    if any(s.get("source") == "calibration" for s in (result.get("seated") or [])):
        return f"{label} seated source=calibration"
    seated_ids = [s.get("participant_id") for s in (result.get("seated") or [])]
    if seated_ids != S.CANDIDATES:
        return f"{label} explicit-order seated {seated_ids}"
    return None


def main() -> int:
    S.require_receipt()
    sel = S.load_selector()
    missing = HERE / "fixtures" / "no-such-store.json"
    if missing.exists():
        return fail("missing-store fixture path unexpectedly exists")

    cold_missing = sel.select_calibrated(S.CANDIDATES, missing)
    cold_empty = sel.select_calibrated(S.CANDIDATES, S.EMPTY)
    cold_zeros = sel.select_calibrated(S.CANDIDATES, S.ZERO)
    warm = sel.select_calibrated(S.CANDIDATES, S.WARM)

    for label, result in (
        ("missing-file", cold_missing),
        ("empty-participants", cold_empty),
        ("zero-history-stored-zeros", cold_zeros),
    ):
        err = assert_degraded(label, result)
        if err:
            return fail(err)

    if cold_missing.get("degradation", {}).get("event") != "CALIBRATION_STORE_EMPTY":
        return fail(f"missing-file event {cold_missing.get('degradation')}")
    if cold_empty.get("degradation", {}).get("event") != "CALIBRATION_STORE_EMPTY":
        return fail(f"empty-participants event {cold_empty.get('degradation')}")
    if cold_zeros.get("degradation", {}).get("event") != "CALIBRATION_STORE_INSUFFICIENT":
        return fail(f"zero-history event {cold_zeros.get('degradation')}")

    if warm.get("degradation") is not None:
        return fail("warm store emitted degradation (both-states silent-on-good failed)")
    if warm.get("confident_ranking") is not True:
        return fail("warm store not confident")
    if warm.get("strategy_used") != "calibration":
        return fail(f"warm strategy {warm.get('strategy_used')}")
    if not warm.get("ranking"):
        return fail("warm ranking empty")

    print(
        json.dumps(
            {
                "probe": "probe2-empty-store",
                "unit_id": "IMP-0268",
                "fired_on_missing": True,
                "fired_on_empty": True,
                "fired_on_zero_history": True,
                "silent_on_warm": True,
                "missing_event": cold_missing["degradation"]["event"],
                "empty_event": cold_empty["degradation"]["event"],
                "zero_history_event": cold_zeros["degradation"]["event"],
                "warm_ranking": warm.get("ranking"),
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0268-probe2 empty store degrades loudly; warm is silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
