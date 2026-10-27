#!/usr/bin/env python3
"""Probe 2: detector control — ALIVE for a known-running process before DEAD.

A heartbeat-only mutant must stay HUNG after kill (no second flip). Production
must flip to DEAD only after the ALIVE control passed.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import liveness as L  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0151.json"
SENTINEL = "SUCCESS:TST-0151"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0151-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    with tempfile.TemporaryDirectory(prefix="tst0151-p2-") as td:
        ctrl = L.run_known_alive_then_kill(Path(td))

    print(
        json.dumps(
            {
                "sequence": ctrl["sequence"],
                "alive_before_dead": ctrl["alive_before_dead"],
                "trusted_dead": ctrl["trusted_dead"],
                "heartbeat_only_mutant_after_kill": ctrl["heartbeat_only_mutant_after_kill"],
                "alive_window_s": ctrl["known_running"]["window_s"],
                "alive_cpu_delta": ctrl["known_running"]["cpu_delta"],
                "alive_heartbeat_age_s": ctrl["known_running"]["heartbeat_age_s"],
            },
            sort_keys=True,
        )
    )

    if ctrl["sequence"] != [L.ALIVE, L.DEAD]:
        return fail(f"sequence={ctrl['sequence']}")
    if not ctrl["alive_before_dead"]:
        return fail("DEAD/HUNG without a prior ALIVE on a known-running process")
    if not ctrl["trusted_dead"]:
        return fail("refused to trust DEAD: ALIVE control failed")
    if ctrl["heartbeat_only_mutant_after_kill"] != L.HUNG:
        return fail("heartbeat-only mutant flipped after kill (no DEAD distinctness)")
    if ctrl["known_running"]["window_s"] < L.WINDOW_S - 0.5:
        return fail(f"alive window {ctrl['known_running']['window_s']} < 20s")
    if ctrl["known_running"]["heartbeat_t1"] <= ctrl["known_running"]["heartbeat_t0"]:
        return fail("known-running heartbeat did not advance")
    if ctrl["known_running"]["work_t0"] != 0 or ctrl["known_running"]["work_t1"] != 0:
        return fail("known-running wrote work bytes")
    if ctrl["killed"]["pid_alive"] is True:
        return fail("killed pid still alive")

    published = (doc.get("detector_control") or {}).get("sequence")
    if published != ctrl["sequence"]:
        return fail(f"receipt sequence drifted live={ctrl['sequence']} art={published}")
    if doc.get("detector_control", {}).get("alive_before_dead") is not True:
        return fail("receipt alive_before_dead not true")

    print("SUCCESS:TST-0151-probe2 alive-before-dead")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
