"""Owner-approval token gate (TST-0226)."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any

OWNER_SECRET = b"owner-channel-secret-tst-0226"
UNIT = "TST-0226"


def _mac(payload: dict[str, Any], secret: bytes = OWNER_SECRET) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(secret, blob, hashlib.sha256).hexdigest()


def _token(unit_id: str, secret: bytes = OWNER_SECRET) -> dict[str, Any]:
    payload = {"unit_id": unit_id, "channel": "owner"}
    return {"payload": payload, "mac": _mac(payload, secret)}


def accept(token: dict[str, Any], unit_id: str, *, channel: str) -> dict[str, Any]:
    payload = token.get("payload") if isinstance(token, dict) else None
    if not isinstance(payload, dict):
        return {"accepted": False, "reason": "malformed"}
    if channel not in {"env", "fd", "owner"}:
        return {"accepted": False, "reason": "not-owner-channel"}
    if _mac(payload) != token.get("mac"):
        return {"accepted": False, "reason": "mac-mismatch", "payload": payload}
    if payload.get("unit_id") != unit_id:
        return {"accepted": False, "reason": "unit-mismatch", "payload": payload}
    return {"accepted": True, "reason": "owner-channel-ok", "payload": payload}


def run_required_controls() -> dict[str, Any]:
    genuine = _token(UNIT)
    genuine_env = accept(genuine, UNIT, channel="env")
    genuine_fd = accept(genuine, UNIT, channel="fd")
    forged = accept({"payload": {"unit_id": UNIT, "channel": "owner"}, "mac": "00" * 32}, UNIT, channel="env")
    self_issued = _token(UNIT, secret=b"agent-hmac-self")
    self_res = accept(self_issued, UNIT, channel="env")
    replay = _token("OTHER-0001")
    replay_res = accept(replay, UNIT, channel="env")
    return {
        "genuine_env": genuine_env,
        "genuine_fd": genuine_fd,
        "forged": {**forged, "reason": forged.get("reason") or "mac-mismatch"},
        "self_issued": self_res,
        "replay": replay_res,
    }


def control_failures(report: dict[str, Any]) -> list[str]:
    fails = []
    if not report["genuine_env"]["accepted"]:
        fails.append("genuine-env")
    if not report["genuine_fd"]["accepted"]:
        fails.append("genuine-fd")
    if report["forged"]["accepted"]:
        fails.append("forged-accepted")
    if report["self_issued"]["accepted"]:
        fails.append("self-issued-accepted")
    if report["replay"]["accepted"]:
        fails.append("replay-accepted")
    return fails
