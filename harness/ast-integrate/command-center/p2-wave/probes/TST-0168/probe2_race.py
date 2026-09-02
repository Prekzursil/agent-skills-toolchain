#!/usr/bin/env python3
"""Probe 2: race amplification — 20 seeded suspend points inside the fan-out.

Independent of probe1's tempdir. Re-derives child ids after each resume and
checks receipt counts stay at one per child. Also binds the artifact's tick
list to this seeded sample.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenarios as S  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0168.json"
SENTINEL = "SUCCESS:TST-0168"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def _check_artifact(live_ticks: list[int]) -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0168-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:TST-0168-probe2 unparseable {exc}")
        return 1
    if SENTINEL not in text:
        print("FAILED:TST-0168-probe2 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        print(f"FAILED:TST-0168-probe2 self-declared:{st}")
        return 1
    race = doc.get("race") or {}
    if race.get("ok") is not True:
        print("FAILED:TST-0168-probe2 receipt race.ok is not true")
        return 1
    if race.get("n") != 20:
        print("FAILED:TST-0168-probe2 receipt race.n is not 20")
        return 1
    art_ticks = race.get("ticks")
    if art_ticks != live_ticks:
        print("FAILED:TST-0168-probe2 artifact ticks != live seeded sample")
        print(" artifact", art_ticks)
        print(" live    ", live_ticks)
        return 1
    return 0


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0168-p2-") as tmp:
        race = S.run_race(Path(tmp))

    ticks = list(race.get("ticks") or [])
    if _check_artifact(ticks) != 0:
        return 1

    payload = {
        "probe": "probe2-race",
        "unit_id": "TST-0168",
        "n": race.get("n"),
        "seed": race.get("seed"),
        "ticks": ticks,
        "ok": race.get("ok"),
        "failing_ticks": [
            r.get("tick") for r in (race.get("rows") or []) if not r.get("ok")
        ],
        "pass": bool(race.get("ok") and race.get("n") == 20),
    }
    print(json.dumps(payload, sort_keys=True))
    if not race.get("ok"):
        print("FAILED:TST-0168-probe2 race amplification")
        return 1
    if race.get("n") != 20:
        print("FAILED:TST-0168-probe2 expected 20 suspend points")
        return 1
    print(
        "n=%s seed=%s first_spawn=%s last_receipt=%s"
        % (
            race.get("n"),
            race.get("seed"),
            race.get("first_spawn_tick"),
            race.get("last_receipt_tick"),
        )
    )
    print("SUCCESS:TST-0168-probe2 20 in-flight suspends re-derived children once")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
