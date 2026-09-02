"""Planted council specs for TST-0274.

Three states of the same factual dispute:
  unanimous_wrong — every seat votes the wrong digest; the hash check PASSes
  probe_error     — same wrong vote; the bound check crashes
  both_agree      — every seat votes the measured digest; reason must still
                    be the check, not the tally
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
PAYLOAD = FIXTURES / "payload.txt"
CHECK_HASH = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0274/fixtures/check_hash.py"
)
CHECK_ERROR = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0274/fixtures/check_error.py"
)
WRONG_DIGEST = "0" * 64
N_SEATS = 5
SEED = 274


def payload_digest() -> str:
    raw = PAYLOAD.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _ballots(position: str) -> list[dict[str, str]]:
    return [
        {"seat": f"seat-{i}", "position": position} for i in range(1, N_SEATS + 1)
    ]


def spec_unanimous_wrong() -> dict[str, Any]:
    gold = payload_digest()
    if gold == WRONG_DIGEST:
        raise RuntimeError("planted wrong digest collided with payload")
    return {
        "seed": SEED,
        "kind": "unanimous_wrong",
        "proposition": (
            f"sha256(command-center/p2-wave/probes/TST-0274/fixtures/payload.txt) "
            f"== {gold}"
        ),
        "ballots": _ballots(WRONG_DIGEST),
        "check_command": CHECK_HASH,
        "gold": gold,
        "wrong": WRONG_DIGEST,
    }


def spec_probe_error() -> dict[str, Any]:
    gold = payload_digest()
    return {
        "seed": SEED,
        "kind": "probe_error",
        "proposition": (
            f"sha256(command-center/p2-wave/probes/TST-0274/fixtures/payload.txt) "
            f"== {gold}"
        ),
        "ballots": _ballots(WRONG_DIGEST),
        "check_command": CHECK_ERROR,
        "gold": gold,
        "wrong": WRONG_DIGEST,
    }


def spec_both_agree() -> dict[str, Any]:
    gold = payload_digest()
    return {
        "seed": SEED,
        "kind": "both_agree",
        "proposition": (
            f"sha256(command-center/p2-wave/probes/TST-0274/fixtures/payload.txt) "
            f"== {gold}"
        ),
        "ballots": _ballots(gold),
        "check_command": CHECK_HASH,
        "gold": gold,
        "wrong": WRONG_DIGEST,
    }
