#!/usr/bin/env python3
"""Probe 2: unobservable plants -> NEEDS-HUMAN-FRAMING; naive mutant always emits."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from generator import generate, generate_naive, load_unobservable_plants  # noqa: E402

UNIT = "RES-0153"
ART = REPO / (
    "command-center/research/evidence-quality/"
    "RES-0153-settling-experiment-generator.json"
)
SENTINEL = "SUCCESS:RES-0153"
OBS_CLAIM = (
    "command-center/WORK-UNIT-CATALOG.json is present on this worktree "
    "and must be readable as JSON."
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-absent")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")

    plants = load_unobservable_plants()
    if len(plants) != 5:
        return fail(f"plant-count {len(plants)}")

    human = 0
    naive_wake = 0
    for plant in plants:
        gen = generate(plant["claim"])
        naive = generate_naive(plant["claim"])
        if gen.get("status") != "NEEDS-HUMAN-FRAMING" or gen.get("command"):
            return fail(f"generator invented experiment for {plant['id']}")
        human += 1
        if naive.get("command"):
            naive_wake += 1
        else:
            return fail(f"naive silent on {plant['id']}")

    obs = generate(OBS_CLAIM)
    if obs.get("status") == "NEEDS-HUMAN-FRAMING" or not obs.get("command"):
        return fail("generator silent on observable path claim")

    recorded = doc.get("negative_control") or []
    if len(recorded) != 5:
        return fail(f"artifact plants {len(recorded)}")
    for rec, plant in zip(recorded, plants):
        if rec.get("id") != plant["id"]:
            return fail("plant id drift")
        if rec.get("final_status") != "NEEDS-HUMAN-FRAMING":
            return fail(f"artifact plant not refused {rec.get('id')}")
        if (rec.get("experiment") or {}).get("command"):
            return fail(f"artifact planted a command for {rec.get('id')}")

    controls = {c.get("id"): c for c in (doc.get("controls") or [])}
    c_un = controls.get("C-UNOBSERVABLE") or {}
    if c_un.get("watcher_wake") is not False:
        return fail("watcher must stay silent on unobservable plants")
    if c_un.get("poller_wake") is not True:
        return fail("poller (naive always-emit) must wake on unobservable plants")
    if c_un.get("verdict") != "PASS":
        return fail("unobservable control verdict")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True:
        return fail("reviewer not independent")

    payload = {
        "probe": "probe2-unobservable-control",
        "unit_id": UNIT,
        "pass": True,
        "plants_human_framing": human,
        "naive_wakes": naive_wake,
        "observable_wakes": True,
        "independent": True,
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    print(
        f"plants_human={human} naive_wakes={naive_wake} "
        f"observable_kind={obs.get('kind')}"
    )
    print(
        f"SUCCESS:{UNIT}-probe2 unobservable plants refused; "
        "naive mutant wakes; observable path still generates"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
