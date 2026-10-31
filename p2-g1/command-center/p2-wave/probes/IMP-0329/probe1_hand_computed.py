#!/usr/bin/env python3
"""Named probe 1: large-sample Brier matches an independent computation.

Mechanism: algebraic identity Brier = mean(p^2)+mean(y^2)-2*mean(p*y) plus
the documented hand-sum of squares. Neither path calls brier_of.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.calibration.report import (  # noqa: E402
    HAND_COMPUTED_ALICE_BRIER,
    HAND_COMPUTED_ALICE_N,
    generate_report,
    hand_computed_predictions,
    write_calibration_store,
)


def independent_brier(pairs: list[tuple[float, float]]) -> float:
    n = len(pairs)
    mean_p2 = sum(p * p for p, _ in pairs) / n
    mean_y2 = sum(y * y for _, y in pairs) / n
    mean_py = sum(p * y for p, y in pairs) / n
    return mean_p2 + mean_y2 - 2.0 * mean_py


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0329-probe1 {msg}")
    return 1


def main() -> int:
    preds = hand_computed_predictions()
    alice_scoreable = [
        p
        for p in preds
        if p["participant_id"] == "alice" and p["resolution"] == "SCOREABLE"
    ]
    if len(alice_scoreable) != HAND_COMPUTED_ALICE_N:
        return fail(f"alice n={len(alice_scoreable)} want {HAND_COMPUTED_ALICE_N}")
    pairs = [
        (float(p["stated_confidence"]), 1.0 if p["resolved_correct"] is True else 0.0)
        for p in alice_scoreable
    ]
    # Documented squares from the catalog fixture comment in report.py.
    squares = [0.04] * 5 + [0.64] + [0.04] * 4 + [0.64] * 2
    hand = sum(squares) / HAND_COMPUTED_ALICE_N
    ident = independent_brier(pairs)
    report = generate_report(preds)
    alice = next(p for p in report["participants"] if p["participant_id"] == "alice")
    store_alice = next(
        r
        for r in report["calibration_store"]["records"]
        if r["participant_id"] == "alice"
    )
    if abs(hand - HAND_COMPUTED_ALICE_BRIER) > 1e-12:
        return fail(f"hand sum {hand} != documented {HAND_COMPUTED_ALICE_BRIER}")
    if abs(ident - HAND_COMPUTED_ALICE_BRIER) > 1e-12:
        return fail(f"identity brier {ident} != documented {HAND_COMPUTED_ALICE_BRIER}")
    if alice["brier"] is None:
        return fail("alice brier is null on n=12")
    if abs(alice["brier"] - ident) > 1e-12:
        return fail(f"module brier {alice['brier']} != independent {ident}")
    if abs(store_alice["brier"] - ident) > 1e-12:
        return fail("store brier drifted from independent value")
    if alice["estimate_status"] != "MEANINGFUL":
        return fail(f"alice status {alice['estimate_status']}")
    if "brier=" not in alice["estimate_sentence"]:
        return fail("meaningful sentence omitted brier")
    if alice["resolved_n"] != 12 or alice["unscoreable_n"] != 1:
        return fail("unscoreable row counted as resolved")

    out_dir = HERE / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    store_path = write_calibration_store(out_dir / "calibration-store.json", report["calibration_store"])
    payload = {
        "probe": "probe1-hand-computed",
        "unit_id": "IMP-0329",
        "alice_n": alice["resolved_n"],
        "hand_brier": hand,
        "identity_brier": ident,
        "module_brier": alice["brier"],
        "store_brier": store_alice["brier"],
        "store_path": str(store_path.relative_to(REPO).as_posix()),
        "match": True,
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"hand={hand} identity={ident} module={alice['brier']} store={store_alice['brier']}"
    )
    print("SUCCESS:IMP-0329-probe1 hand-computed Brier matches independent identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
