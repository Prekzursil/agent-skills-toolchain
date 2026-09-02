#!/usr/bin/env python3
"""Probe 1: planted superior arm converges; swapped labels follow the arm.

Live re-run of sequential SPRT on the fixture field. Independent of probe 2
(identical-UNDECIDED and Condorcet cycles). Also requires the unpinned
registry to be refused (both-states on the pin).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find_repo(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "tools" / "foundry" / "tournament.py").is_file():
            return p
    raise SystemExit("FAILED:WFA-0132-probe1 repo root not found")


REPO = find_repo(HERE)
sys.path.insert(0, str(REPO))

from tools.foundry.tournament import (  # noqa: E402
    planted_superior_ok,
    run_tournament,
    swapped_superior_ok,
    unpinned_registry_refused,
)

ART = REPO / (
    "command-center/foundry/"
    "WFA-0132-pairwise-workflow-tournament-runner-with-a-statistic.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0132-probe1 {msg}")
    return 1


def main() -> int:
    tour = run_tournament()
    superior = planted_superior_ok(tour)
    swapped = swapped_superior_ok()
    pin = unpinned_registry_refused()
    if not superior["ok"]:
        return fail(f"planted superior did not converge {superior}")
    if not swapped["ok"]:
        return fail(f"swapped labels did not follow the arm {swapped}")
    if not pin["ok"]:
        return fail(f"unpinned registry was not refused {pin}")

    stops = [r["stopped_at"] for r in superior["pairs"]]
    if not stops or max(stops) > tour["n_cases"]:
        return fail(f"stop budget violated {stops}")
    if min(stops) < 8:
        return fail(f"stopped before n_min_decisive {stops}")

    if ART.is_file() and ART.stat().st_size > 200:
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:WFA-0132" not in text:
            return fail("sentinel absent from artifact")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"self-declared {doc.get('state')}")
        rec = (doc.get("plants") or {}).get("known_superior_converges") or {}
        if rec.get("ok") is not True:
            return fail("artifact did not record planted-superior PASS")
        rec_swap = (doc.get("plants") or {}).get("swapped_labels_follow_arm") or {}
        if rec_swap.get("ok") is not True:
            return fail("artifact did not record swapped-label PASS")

    payload = {
        "probe": "probe1-planted-superior",
        "unit_id": "WFA-0132",
        "superior_ok": True,
        "swapped_ok": True,
        "pin_refused": True,
        "stopped_at": stops,
        "winners": [r["winner"] for r in superior["pairs"]],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:WFA-0132-probe1 planted superior converges; swapped labels follow the arm"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
