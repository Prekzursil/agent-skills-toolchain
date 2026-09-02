#!/usr/bin/env python3
"""Probe 1: hung unit stalls; slow-but-alive must not; byte-growth mutation turns red."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from runtime import HD, REPO, kill, spawn  # noqa: E402

STALL = 0.28
POLL = 0.05
HARD = 4.0
ALIVE_FOR = 0.70


def _watch(mode: str, tmp: Path, **kwargs):
    hb = tmp / f"{mode}.hb.json"
    out = tmp / f"{mode}.out"
    proc = spawn(mode, hb, out, interval=0.05)
    slot = HD.SlotTracker(capacity=1)
    try:
        kwargs.setdefault("timeout_s", HARD)
        kwargs.setdefault("stall_window_s", STALL)
        kwargs.setdefault("poll_s", POLL)
        kwargs.setdefault("unit_id", mode)
        kwargs.setdefault("slot", slot)
        verdict, samples = HD.watch(hb, out, **kwargs)
        return verdict, samples, slot
    finally:
        kill(proc)


def main() -> int:
    catalog = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
    catalog_timeout = HD.catalog_timeout_seconds(catalog, "IMP-0447")
    if catalog_timeout != 2700:
        print(f"FAILED:IMP-0447-probe1 catalog timeout_seconds={catalog_timeout} expected 2700")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0447-p1-") as td:
        tmp = Path(td)

        hung_v, hung_s, hung_slot = _watch("hung", tmp)
        if hung_v.state != HD.STALLED:
            print(f"FAILED:IMP-0447-probe1 hung classified {hung_v.state} not STALLED")
            print(json.dumps(hung_v.to_dict(), sort_keys=True))
            return 1
        if hung_v.heartbeat_advanced is not False or hung_v.byte_growth is not False:
            print("FAILED:IMP-0447-probe1 hung STALLED without both signals dead")
            print(json.dumps(hung_v.to_dict(), sort_keys=True))
            return 1
        if not hung_v.slot_released or hung_slot.occupied_count() != 0:
            print("FAILED:IMP-0447-probe1 hung did not release slot")
            return 1
        ttc = hung_v.time_to_classification_s
        if ttc is None or ttc < STALL or ttc >= HARD:
            print(f"FAILED:IMP-0447-probe1 hung time-to-class {ttc} not in [{STALL}, {HARD})")
            return 1
        hung_slot.acquire("next-unit")
        if hung_slot.occupied_count() != 1:
            print("FAILED:IMP-0447-probe1 slot not reusable after STALLED")
            return 1

        bytes_v, bytes_s, _ = _watch("bytes", tmp, confirm_alive_s=ALIVE_FOR)
        if bytes_v.state != HD.ALIVE:
            print(f"FAILED:IMP-0447-probe1 slow-bytes classified {bytes_v.state} not ALIVE")
            print(json.dumps(bytes_v.to_dict(), sort_keys=True))
            return 1
        if bytes_v.byte_growth is not True:
            print("FAILED:IMP-0447-probe1 slow-bytes showed no byte growth")
            print(json.dumps(bytes_v.to_dict(), sort_keys=True))
            return 1
        if bytes_v.heartbeat_advanced is not False:
            print("FAILED:IMP-0447-probe1 slow-bytes heartbeat unexpectedly advanced")
            return 1

        mutant = HD.classify_heartbeat_only_defective(
            bytes_s,
            timeout_s=HARD,
            stall_window_s=STALL,
        )
        if mutant.state != HD.STALLED:
            print("FAILED:IMP-0447-probe1 mutation removing byte-growth did not turn slow-alive red")
            print(json.dumps(mutant.to_dict(), sort_keys=True))
            return 1

        hb_v, _, _ = _watch("heartbeat", tmp, confirm_alive_s=ALIVE_FOR)
        if hb_v.state != HD.ALIVE or hb_v.heartbeat_advanced is not True:
            print(f"FAILED:IMP-0447-probe1 slow-heartbeat classified {hb_v.state}")
            print(json.dumps(hb_v.to_dict(), sort_keys=True))
            return 1

        one_signal = HD.classify(
            hung_s,
            timeout_s=HARD,
            stall_window_s=STALL,
            signals=(HD.HEARTBEAT,),
        )
        if one_signal.state == HD.STALLED:
            print("FAILED:IMP-0447-probe1 production classify emitted single-signal STALLED")
            return 1
        if one_signal.state != HD.UNDECIDABLE:
            print(f"FAILED:IMP-0447-probe1 expected UNDECIDABLE for one signal, got {one_signal.state}")
            return 1

        try:
            HD.classify(hung_s, timeout_s=HARD, stall_window_s=STALL, extra={"mtime": 1})
            print("FAILED:IMP-0447-probe1 mtime extra was accepted")
            return 1
        except HD.MtimeRejected:
            pass

        timeout_v, _, timeout_slot = _watch(
            "both",
            tmp,
            timeout_s=0.40,
            stall_window_s=STALL,
            unit_id="timeout-alive",
        )
        if timeout_v.state != HD.TIMEOUT:
            print(f"FAILED:IMP-0447-probe1 live unit did not TIMEOUT, got {timeout_v.state}")
            print(json.dumps(timeout_v.to_dict(), sort_keys=True))
            return 1
        if not timeout_v.slot_released or timeout_slot.occupied_count() != 0:
            print("FAILED:IMP-0447-probe1 TIMEOUT did not release slot")
            return 1

    summary = {
        "catalog_timeout_seconds": catalog_timeout,
        "hung": hung_v.to_dict(),
        "slow_bytes": bytes_v.to_dict(),
        "mutant_red": mutant.to_dict(),
        "slow_heartbeat": hb_v.to_dict(),
        "one_signal": one_signal.to_dict(),
        "hard_timeout_alive": timeout_v.to_dict(),
        "pass": True,
        "probe": "probe1-hung-and-slow",
        "unit_id": "IMP-0447",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"hung_ttc_s={hung_v.time_to_classification_s} "
        f"hung={hung_v.state} slow_bytes={bytes_v.state} mutant={mutant.state} "
        f"timeout={timeout_v.state} catalog_timeout_s={catalog_timeout}"
    )
    print("SUCCESS:IMP-0447-probe1 hung STALLED two-signal; slow-alive not stalled; mutation red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
