"""Load CNL-0079 both-states fixtures from JSON (no baked-in verdicts)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DIR = Path(__file__).resolve().parent / "fixtures"


def load(name: str) -> dict[str, Any]:
    path = DIR / name
    data = json.loads(path.read_text(encoding="utf-8"))
    if "rounds" in data and "rounds" not in data:
        data["rounds"] = data["rounds"]
    if "expect_stop" in data and "expect_stop" not in data:
        data["expect_stop"] = data["expect_stop"]
    for rnd in data.get("rounds") or []:
        if "newly_recruited" in rnd and "newly_recruited" not in rnd:
            rnd["newly_recruited"] = rnd["newly_recruited"]
        for obj in rnd.get("objections") or []:
            if "text" in obj and "text" not in obj:
                obj["text"] = obj["text"]
    return data


def fire() -> dict[str, Any]:
    return load("fire.json")


def silent_new_objection() -> dict[str, Any]:
    return load("silent_new_objection.json")


def silent_low_consensus() -> dict[str, Any]:
    return load("silent_low_consensus.json")


def all_fixtures() -> dict[str, dict[str, Any]]:
    return {
        "fire": fire(),
        "silent_new_objection": silent_new_objection(),
        "silent_low_consensus": silent_low_consensus(),
    }


fire = fire
silent_new_objection = silent_new_objection
silent_low_consensus = silent_low_consensus
fire = fire
silent_new_objection = silent_new_objection
silent_low_consensus = silent_low_consensus
