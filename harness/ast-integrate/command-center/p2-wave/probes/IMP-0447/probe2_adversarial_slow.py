#!/usr/bin/env python3
"""Probe 2: adversarial attempts to stall a live slow unit must fail.

Mechanically different from probe 1: this entry point only scores attacks
against a live unit (frozen heartbeat + growing bytes, plus mtime bait and
heartbeat-only classification). A true hung fixture remains STALLED so the
detector is not inert.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from runtime import HD, kill, spawn  # noqa: E402

STALL = 0.28
POLL = 0.05
HARD = 4.0
ALIVE_FOR = 0.70


def _watch(mode: str, tmp: Path, tag: str, **kwargs):
    hb = tmp / f"{tag}.hb.json"
    out = tmp / f"{tag}.out"
    proc = spawn(mode, hb, out, interval=0.05)
    try:
        kwargs.setdefault("timeout_s", HARD)
        kwargs.setdefault("stall_window_s", STALL)
        kwargs.setdefault("poll_s", POLL)
        kwargs.setdefault("unit_id", tag)
        verdict, samples = HD.watch(hb, out, **kwargs)
        return verdict, samples
    finally:
        kill(proc)


def main() -> int:
    attacks: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="imp0447-p2-") as td:
        tmp = Path(td)

        live_v, live_s = _watch("bytes", tmp, "adv-bytes", confirm_alive_s=ALIVE_FOR)
        attacks.append({"id": "frozen-hb-growing-bytes", **live_v.to_dict()})
        if live_v.state == HD.STALLED:
            print("FAILED:IMP-0447-probe2 live slow unit classified STALLED")
            print(json.dumps(live_v.to_dict(), sort_keys=True))
            return 1
        if live_v.state != HD.ALIVE or live_v.byte_growth is not True:
            print(f"FAILED:IMP-0447-probe2 expected ALIVE with byte growth, got {live_v.state}")
            return 1

        hb_v, _ = _watch("heartbeat", tmp, "adv-hb", confirm_alive_s=ALIVE_FOR)
        attacks.append({"id": "growing-hb-frozen-bytes", **hb_v.to_dict()})
        if hb_v.state == HD.STALLED:
            print("FAILED:IMP-0447-probe2 heartbeat-only-live unit classified STALLED")
            return 1

        both_v, _ = _watch("both", tmp, "adv-both", confirm_alive_s=ALIVE_FOR)
        attacks.append({"id": "both-signals-slow", **both_v.to_dict()})
        if both_v.state == HD.STALLED:
            print("FAILED:IMP-0447-probe2 dual-live unit classified STALLED")
            return 1

        try:
            HD.classify(
                live_s,
                timeout_s=HARD,
                stall_window_s=STALL,
                extra={"mtime_only": True, "mtime_ns": 1},
            )
            print("FAILED:IMP-0447-probe2 mtime-only bait was accepted")
            return 1
        except HD.MtimeRejected as exc:
            attacks.append({"id": "mtime-bait", "state": "REJECTED", "reason": str(exc)})

        one = HD.classify(
            live_s,
            timeout_s=HARD,
            stall_window_s=STALL,
            signals=(HD.HEARTBEAT,),
        )
        attacks.append({"id": "heartbeat-only-api", **one.to_dict()})
        if one.state == HD.STALLED:
            print("FAILED:IMP-0447-probe2 heartbeat-only API emitted STALLED on a live unit")
            return 1

        hung_v, _ = _watch("hung", tmp, "adv-hung")
        attacks.append({"id": "negative-control-hung", **hung_v.to_dict()})
        if hung_v.state != HD.STALLED:
            print(f"FAILED:IMP-0447-probe2 hung negative control classified {hung_v.state}")
            return 1
        if hung_v.heartbeat_advanced is not False or hung_v.byte_growth is not False:
            print("FAILED:IMP-0447-probe2 hung control missing two dead signals")
            return 1

    stalled_attacks = [a for a in attacks if a.get("state") == HD.STALLED and a["id"] != "negative-control-hung"]
    if stalled_attacks:
        print("FAILED:IMP-0447-probe2 adversarial stall succeeded")
        print(json.dumps(stalled_attacks, sort_keys=True))
        return 1

    summary = {
        "attacks": attacks,
        "adversarial_stalls": 0,
        "hung_still_detected": True,
        "pass": True,
        "probe": "probe2-adversarial-slow",
        "unit_id": "IMP-0447",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"attacks={len(attacks)} adversarial_stalls=0 "
        f"hung={hung_v.state} live_bytes={live_v.state}"
    )
    print("SUCCESS:IMP-0447-probe2 live slow unit not stalled; hung still STALLED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
