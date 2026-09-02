#!/usr/bin/env python3
"""Probe 1: codepoint-class scan + detector control (signal a).

Live HUD must be a zero-hit scan. The same scanner must fire on a planted
U+26A0. A W/F-only naive scanner must miss that seed (both-states: the
detector is not a tautology). Mechanically different from probe 2 (no tmux,
no wcwidth).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402

ART = REPO / H.OUT_REL
SENTINEL = "SUCCESS:TST-0246"


def check_artifact_if_present() -> str | None:
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
    err = check_artifact_if_present()
    if err:
        print(f"FAILED:TST-0246-probe1 {err}")
        return 1

    camp = H.campaign()
    plant = camp["plant"]
    seed = camp["seed"]
    payload = {
        "pass": camp["detector_pass"],
        "probe": "probe1-detector-control",
        "unit_id": H.UNIT,
        "live_hit_count": len(camp["live_hits"]),
        "live_naive_hit_count": len(camp["live_naive_hits"]),
        "seed_eaw": seed["east_asian_width"],
        "seed_real_class": seed["real_class"],
        "seed_naive_class": seed["naive_class"],
        "seed_real_fired": plant["seed_real_fired"],
        "seed_naive_blind": plant["seed_naive_blind"],
        "wide_real_fired": plant["wide_real_fired"],
        "wide_naive_fired": plant["wide_naive_fired"],
        "production_hud": camp["production_hud"],
        "method": "codepoint-class scan (EAW A/W/F + emoji + U+26A0 seed)",
    }
    print(json.dumps(payload, sort_keys=True))
    if camp["live_hits"]:
        print("FAILED:TST-0246-probe1 live HUD had alignment-breaker hits")
        return 1
    if camp["live_naive_hits"]:
        print("FAILED:TST-0246-probe1 live HUD had W/F hits")
        return 1
    if not plant["seed_real_fired"]:
        print("FAILED:TST-0246-probe1 planted U+26A0 did not fire the real scanner")
        return 1
    if not plant["seed_naive_blind"]:
        print("FAILED:TST-0246-probe1 W/F-only naive scanner saw U+26A0 (control dead)")
        return 1
    if not plant["wide_real_fired"] or not plant["wide_naive_fired"]:
        print("FAILED:TST-0246-probe1 planted U+4E2D (W) was not seen by both scanners")
        return 1
    if seed["east_asian_width"] == "W" or seed["naive_class"]:
        print("FAILED:TST-0246-probe1 U+26A0 is no longer a naive-blind seed")
        return 1
    print(
        "live_hits=0 planted_U+26A0=FIRE naive_U+26A0=MISS "
        f"eaw={seed['east_asian_width']} class={seed['real_class']}"
    )
    print("SUCCESS:TST-0246-probe1 detector control on planted U+26A0; live HUD zero-hit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
