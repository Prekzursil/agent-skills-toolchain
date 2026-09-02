#!/usr/bin/env python3
"""Probe 1: both-states — silent while idle-alive, fires when SIGSTOPped.

Live 20s heartbeat-age + CPU-time-delta samples. Work output stays empty.
A work-silence mutant must fire on the idle cell (single-signal defect).
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
    print(f"FAILED:TST-0151-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0151":
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    with tempfile.TemporaryDirectory(prefix="tst0151-p1-") as td:
        both = L.run_idle_then_sigstop_then_kill(Path(td))

    print(
        json.dumps(
            {
                "sequence": both["sequence"],
                "silent_idle": both["detector_silent_idle"],
                "fires_sigstop": both["detector_fires_sigstop"],
                "flipped_on_sigstop": both["flipped_on_sigstop"],
                "flipped_on_kill": both["flipped_on_kill"],
                "work_independent": both["work_independent_idle"],
                "work_silence_mutant_fires_on_idle": both["work_silence_mutant_fires_on_idle"],
                "idle_window_s": both["idle"]["window_s"],
                "sigstop_window_s": both["sigstop"]["window_s"],
                "idle_cpu_delta": both["idle"]["cpu_delta"],
                "sigstop_cpu_delta": both["sigstop"]["cpu_delta"],
                "idle_heartbeat_age_s": both["idle"]["heartbeat_age_s"],
                "sigstop_heartbeat_age_s": both["sigstop"]["heartbeat_age_s"],
            },
            sort_keys=True,
        )
    )

    if both["sequence"] != [L.ALIVE, L.HUNG, L.DEAD]:
        return fail(f"sequence={both['sequence']}")
    if not both["detector_silent_idle"]:
        return fail("detector fired on idle-alive")
    if not both["detector_fires_sigstop"]:
        return fail("detector silent on SIGSTOP")
    if not both["flipped_on_sigstop"]:
        return fail("did not flip ALIVE→HUNG on SIGSTOP")
    if not both["flipped_on_kill"]:
        return fail("did not flip HUNG→DEAD on kill")
    if not both["work_independent_idle"]:
        return fail("idle cell wrote work bytes")
    if not both["work_silence_mutant_fires_on_idle"]:
        return fail("work-silence mutant did not go red on idle-alive")
    if both["heartbeat_only_mutant_after_kill"] != L.HUNG:
        return fail("heartbeat-only mutant flipped to DEAD (mutant did not stay HUNG)")
    if both["mtime_idle"]["verdict"] != L.UNDECIDABLE:
        return fail("mtime observation was not UNDECIDABLE")
    if both["idle"]["window_s"] < L.WINDOW_S - 0.5:
        return fail(f"idle window {both['idle']['window_s']} < 20s")
    if both["sigstop"]["window_s"] < L.WINDOW_S - 0.5:
        return fail(f"sigstop window {both['sigstop']['window_s']} < 20s")
    if both["sigstop"]["cpu_delta"] != 0:
        return fail(f"SIGSTOP cpu_delta={both['sigstop']['cpu_delta']} not frozen")
    if both["sigstop"]["heartbeat_t1"] != both["sigstop"]["heartbeat_t0"]:
        return fail("SIGSTOP heartbeat still advancing")
    if both["idle"]["heartbeat_t1"] <= both["idle"]["heartbeat_t0"]:
        return fail("idle-alive heartbeat did not advance")

    published = (doc.get("both_states") or {}).get("sequence")
    if published != both["sequence"]:
        return fail(f"receipt sequence drifted live={both['sequence']} art={published}")

    print("SUCCESS:TST-0151-probe1 idle-alive-silent-sigstop-fires")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
