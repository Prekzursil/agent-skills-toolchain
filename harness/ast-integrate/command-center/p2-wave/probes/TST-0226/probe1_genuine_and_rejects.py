#!/usr/bin/env python3
"""Probe 1: genuine owner approval passes; forge, self-issue, replay fail.

Both-states control: the same gate instance accepts a token presented from
an owner channel (env / inherited fd) and rejects a forged token, an
agent-HMAC self-issued token, and a previously valid token bound to a
different unit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.lib import owner_approval as G  # noqa: E402

ART = REPO / "command-center/receipts/TST-0226.json"
SENTINEL = "SUCCESS:TST-0226"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0226-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0226":
        return fail(f"unit_id={doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")

    report = G.run_required_controls()
    fails = G.control_failures(report)
    if fails:
        return fail("; ".join(fails))

    genuine = report["genuine_env"]
    genuine_fd = report["genuine_fd"]
    forged = report["forged"]
    self_issued = report["self_issued"]
    replay = report["replay"]

    if not genuine["accepted"] or genuine["reason"] != "owner-channel-ok":
        return fail(f"genuine env {genuine}")
    if not genuine_fd["accepted"]:
        return fail(f"genuine fd {genuine_fd}")
    if forged["accepted"]:
        return fail("forged accepted")
    if self_issued["accepted"] or self_issued["reason"] != "mac-mismatch":
        return fail(f"self-issued {self_issued}")
    if replay["accepted"] or replay["reason"] != "unit-mismatch":
        return fail(f"replay {replay}")
    if str((replay.get("payload") or {}).get("unit_id")) == "TST-0226":
        return fail("replay payload still bound to TST-0226")

    live = doc.get("live_controls") or {}
    if live.get("genuine_env", {}).get("reason") != "owner-channel-ok":
        return fail("receipt genuine_env reason drift")
    if live.get("replay", {}).get("reason") != "unit-mismatch":
        return fail("receipt replay reason drift")

    payload = {
        "probe": "probe1-genuine-and-rejects",
        "unit_id": "TST-0226",
        "pass": True,
        "genuine_env_accepted": genuine["accepted"],
        "genuine_fd_accepted": genuine_fd["accepted"],
        "forged_reason": forged["reason"],
        "self_issued_reason": self_issued["reason"],
        "replay_reason": replay["reason"],
        "replay_bound_unit": (replay.get("payload") or {}).get("unit_id"),
        "secret_channel": (report.get("secret_provenance") or {}).get("channel"),
        "receipt_matches_live": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "genuine_env=ok genuine_fd=ok "
        f"forged={forged['reason']} self_issued={self_issued['reason']} "
        f"replay={replay['reason']}"
    )
    print("SUCCESS:TST-0226-probe1 genuine owner token passes; forge/self-issue/replay fail")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
