#!/usr/bin/env python3
"""Named probe 2: delivered-prompt scan for prior-conclusion text.

Memory-off must scan to zero. The negative control plants the prior
conclusion into a memory-off prompt and asserts the scan FIRES.
This probe starts from the scan tests, not from the author's summary.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.participants.memory import (  # noqa: E402
    plant_conclusion_leak,
    render_delivered_prompt,
    render_roster_prompts,
    scan_prompt_for_conclusions,
)


def load_json(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0350-probe2 {msg}")
    return 1


def main() -> int:
    spec = load_json("spec-mixed.json")
    prior = load_json("prior-council.json")
    task = load_json("current-task.json")
    priors = [prior]
    conclusion = prior["conclusion"]

    off_seat = {"id": "seat-off", "memory": "off"}
    on_seat = {"id": "seat-on", "memory": "on"}
    off_prompt = render_delivered_prompt(
        participant=off_seat, spec=spec, prior_councils=priors, current_task=task
    )
    on_prompt = render_delivered_prompt(
        participant=on_seat, spec=spec, prior_councils=priors, current_task=task
    )

    clean_off = scan_prompt_for_conclusions(off_prompt.text, priors)
    clean_on = scan_prompt_for_conclusions(on_prompt.text, priors)
    if clean_off.fired or clean_off.hit_count != 0:
        return fail(f"memory-off scan not zero: {clean_off.as_dict()}")
    if clean_on.fired:
        return fail(f"memory-on default scan fired: {clean_on.as_dict()}")
    if conclusion in off_prompt.text:
        return fail("memory-off prompt contains prior conclusion verbatim")
    if prior["council_id"] in off_prompt.text:
        return fail("memory-off prompt contains prior council id")

    leaked = plant_conclusion_leak(off_prompt.text, conclusion)
    leak_scan = scan_prompt_for_conclusions(leaked, priors)
    if not leak_scan.fired or leak_scan.hit_count < 1:
        return fail(f"negative control did not FIRE on planted leak: {leak_scan.as_dict()}")
    if conclusion.lower() not in leaked.lower():
        return fail("planted leak missing conclusion text")

    # Both-states: clean silent, planted fires. A scan that is red on both
    # states, or green on both, measures nothing.
    if clean_off.fired or not leak_scan.fired:
        return fail("scan does not discriminate clean vs planted leak")

    roster = render_roster_prompts(spec, priors, task)
    alice = next(item for item in roster if item.participant_id == "seat-alice")
    cara = next(item for item in roster if item.participant_id == "seat-cara")
    alice_scan = scan_prompt_for_conclusions(alice.text, priors)
    cara_scan = scan_prompt_for_conclusions(cara.text, priors)
    if alice_scan.fired:
        return fail("mixed-roster memory-off seat scan fired")
    if not cara_scan.fired:
        return fail("mixed-roster import_conclusion seat scan silent")

    empty_scan = scan_prompt_for_conclusions(off_prompt.text, [])
    if empty_scan.fired:
        return fail("scan fired with empty prior-conclusion set")

    payload = {
        "pass": True,
        "probe": "probe2-prompt-scan-memory-off-zero",
        "unit_id": "IMP-0350",
        "memory_off_hit_count": clean_off.hit_count,
        "memory_on_default_fired": clean_on.fired,
        "leak_fired": leak_scan.fired,
        "leak_hit_count": leak_scan.hit_count,
        "both_states_discriminates": True,
        "mixed_roster_off_silent": not alice_scan.fired,
        "mixed_roster_import_fires": cara_scan.fired,
        "required_zero_memory_off": clean_off.hit_count == 0,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"off_hits={clean_off.hit_count} leak_fired={leak_scan.fired} "
        f"leak_hits={leak_scan.hit_count} both_states=True"
    )
    print("SUCCESS:IMP-0350-probe2 memory-off prompt scan zero; leak control FIRES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
