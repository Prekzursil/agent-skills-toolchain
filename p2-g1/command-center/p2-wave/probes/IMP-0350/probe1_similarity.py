#!/usr/bin/env python3
"""Named probe 1: first-round brief similarity to the prior conclusion.

Compares memory-off, memory-on (default, conclusion withheld), and the
explicit import_conclusion mode. Also enforces per-participant memory scope
on a mixed roster.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.participants.memory import (  # noqa: E402
    MemoryPolicyError,
    compare_on_versus_off,
    enforce_memory_scope,
    render_roster_prompts,
    resolve_policy,
)


def load_json(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0350-probe1 {msg}")
    return 1


def main() -> int:
    spec = load_json("spec-mixed.json")
    prior = load_json("prior-council.json")
    task = load_json("current-task.json")
    priors = [prior]
    conclusion = prior["conclusion"]

    template = {"id": "seat-measure", "vendor": "test", "model": "stub"}
    table = compare_on_versus_off(spec, template, priors, task)
    off_sim = float(table["memory_off"]["similarity"])
    on_sim = float(table["memory_on_default"]["similarity"])
    import_sim = float(table["memory_on_import_conclusion"]["similarity"])
    delta = float(table["delta_import_minus_off"])

    if off_sim >= 0.12:
        return fail(f"memory-off brief too similar to prior conclusion: {off_sim:.4f}")
    if on_sim >= 0.12:
        return fail(
            f"memory-on default brief too similar to prior conclusion "
            f"(conclusion should be withheld): {on_sim:.4f}"
        )
    if import_sim <= 0.35:
        return fail(
            f"import_conclusion brief not similar enough to prior conclusion: {import_sim:.4f}"
        )
    if delta <= 0.25:
        return fail(f"import_conclusion vs memory-off distributions do not separate: delta={delta:.4f}")
    if not table["independence_preserved_by_default"]:
        return fail("memory-on default failed independence_preserved_by_default")
    if not table["import_conclusion_voids_independence"]:
        return fail("import_conclusion did not void independence as required")
    if table["memory_off"]["prompt_scan"]["fired"]:
        return fail("memory-off prompt scan fired on a clean prompt")
    if table["memory_on_default"]["prompt_scan"]["fired"]:
        return fail("memory-on default prompt contains prior-conclusion text")
    if not table["memory_on_import_conclusion"]["prompt_scan"]["fired"]:
        return fail("import_conclusion prompt does not contain prior-conclusion text")
    if conclusion not in table["memory_on_import_conclusion"]["prompt"]:
        return fail("import_conclusion prompt missing the prior conclusion verbatim")
    if conclusion in table["memory_off"]["prompt"] or conclusion in table["memory_on_default"]["prompt"]:
        return fail("prior conclusion leaked into a non-import prompt")

    roster = render_roster_prompts(spec, priors, task)
    by_id = {item.participant_id: item for item in roster}
    if set(by_id) != {"seat-alice", "seat-bob", "seat-cara"}:
        return fail(f"unexpected roster: {sorted(by_id)}")
    alice = by_id["seat-alice"]
    bob = by_id["seat-bob"]
    cara = by_id["seat-cara"]
    if alice.policy.memory_enabled or alice.policy.import_conclusion:
        return fail(f"alice policy {alice.policy.as_dict()}")
    if not bob.policy.memory_enabled or bob.policy.import_conclusion:
        return fail(f"bob policy {bob.policy.as_dict()}")
    if not cara.policy.memory_enabled or not cara.policy.import_conclusion:
        return fail(f"cara policy {cara.policy.as_dict()}")
    if prior["council_id"] in alice.text:
        return fail("memory-off seat-alice received prior_council_id")
    if prior["council_id"] not in bob.text:
        return fail("memory-on seat-bob missing prior_council_id metadata")
    if conclusion in bob.text:
        return fail("memory-on seat-bob imported conclusion despite default withhold")
    if conclusion not in cara.text:
        return fail("import_conclusion seat-cara missing conclusion")

    scope = enforce_memory_scope(roster, priors)
    if not scope["ok"]:
        return fail(f"mixed-roster scope violations: {scope['violations']}")

    # Cross-seat leak must be detected: copy cara's prompt onto alice.
    leaked_alice = type(alice)(alice.participant_id, alice.policy, cara.text)
    leaked_scope = enforce_memory_scope([leaked_alice, bob, cara], priors)
    if leaked_scope["ok"]:
        return fail("cross-seat conclusion leak was not detected")

    try:
        resolve_policy(spec, {"id": "seat-bad", "memory": "sometimes"})
        return fail("unrecognized memory flag did not fail closed")
    except MemoryPolicyError:
        pass

    payload = {
        "pass": True,
        "probe": "probe1-similarity-on-versus-off",
        "unit_id": "IMP-0350",
        "memory_off_similarity": off_sim,
        "memory_on_default_similarity": on_sim,
        "memory_on_import_conclusion_similarity": import_sim,
        "delta_import_minus_off": delta,
        "independence_preserved_by_default": True,
        "import_conclusion_voids_independence": True,
        "mixed_roster_scope_ok": True,
        "cross_seat_leak_detected": True,
        "unknown_flag_fails_closed": True,
        "prior_council_id": prior["council_id"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"off={off_sim:.4f} on_default={on_sim:.4f} import={import_sim:.4f} "
        f"delta={delta:.4f} scope_ok=True"
    )
    print("SUCCESS:IMP-0350-probe1 first-round brief similarity memory on vs off")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
