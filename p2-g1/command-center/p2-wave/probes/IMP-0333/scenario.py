"""Shared motions, speakers, and assignment maps for IMP-0333 probes."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council.protocol.oxford import (  # noqa: E402
    DebateConfig,
    EvidenceBoundSpeaker,
    SideBoundSpeaker,
    balanced_taste_motion,
    decisive_arithmetic_motion,
)

ART = "command-center/receipts/IMP-0333.json"
MODULE = "tools/council/protocol/oxford.py"
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/council/tests/test_oxford.py"
)
ASSIGNMENTS = {"alice": "proposition", "bob": "opposition"}
CONFIG = DebateConfig(turn_budget_ms=1000, max_rebuttal_depth=2)


def evidence_speakers() -> dict:
    return {
        "alice": EvidenceBoundSpeaker("alice"),
        "bob": EvidenceBoundSpeaker("bob"),
    }


def side_speakers() -> dict:
    return {
        "alice": SideBoundSpeaker("alice"),
        "bob": SideBoundSpeaker("bob"),
    }


def mixed_speakers() -> dict:
    return {
        "alice": EvidenceBoundSpeaker("alice"),
        "bob": SideBoundSpeaker("bob"),
    }


def decisive():
    return decisive_arithmetic_motion()


def balanced():
    return balanced_taste_motion()
