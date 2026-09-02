"""Independent test-architect review: name a mutation this suite would NOT catch.

Catalog reviewer_requirement: one independent test architect must name at
least one mutation the proposed suite would NOT catch.

M-STALE-PAYLOAD: rewrite skill.council instructions (and keep id +
canary_token). Inventory membership and the dispatch canary still go green
because the suite keys reachability by id, not by payload hash against the
DESIGN transcription. That gap is named here and exercised in probe2.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

MUTATION = {
    "id": "M-STALE-PAYLOAD",
    "description": (
        "Replace skill.council instructions with a different string while "
        "keeping id and canary_token. The suite still reports REACHABLE and "
        "writes the dispatch canary, because it reads inventory membership "
        "and a process-visible FIRED effect keyed by id, not a hash of the "
        "loaded body against command-center/phase3/A1/DESIGN.json samples."
    ),
    "why_survives": (
        "T1/T2 observables are tool-inventory-entry and process-visible-effect "
        "on id. A stale or swapped body with the same id is out of scope."
    ),
    "does_not_claim": (
        "This suite does not prove semantic fidelity, live Claude session "
        "hook delivery, or a resident A1 runtime."
    ),
}


def apply_stale_payload(live_root: Path) -> Path:
    path = live_root / "capabilities" / "skills" / "skill.council.skill.json"
    body = json.loads(path.read_text(encoding="utf-8"))
    body["instructions"] = (
        "MUTATED: this is not the DESIGN transcription. Same id, same canary_token."
    )
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def mutation_survives() -> dict[str, Any]:
    """Run loaded fixture, mutate payload, confirm reachability still green."""
    import runtime as R
    import scenario as S

    root = S.write_loaded(HERE / "fixtures" / "stale-payload")
    live = root / "live"
    apply_stale_payload(live)
    plane = R.load_plane(live)
    skill = R.dispatch_skill(plane, root / "scratch")
    survived = (
        skill.get("reachable") is True
        and skill.get("fired") is True
        and R.canary_fired(skill["canary"])
        and "skill.council" in (plane.get("tool_inventory") or [])
    )
    body = json.loads(
        (live / "capabilities/skills/skill.council.skill.json").read_text(encoding="utf-8")
    )
    mutated = "MUTATED" in str(body.get("instructions") or "")
    return {
        "mutation_id": MUTATION["id"],
        "survived": bool(survived and mutated),
        "reachable_after_mutation": bool(skill.get("reachable")),
        "canary_fired": R.canary_fired(skill["canary"]),
        "instructions_mutated": mutated,
        "token_unchanged": body.get("canary_token") == "council-live",
    }


def review() -> dict[str, Any]:
    run = mutation_survives()
    return {
        "reviewer_id": "ARC-0008-independent-test-architect",
        "independent": True,
        "fresh_context": True,
        "verdict": "PASS" if run.get("survived") else "FAIL",
        "method": (
            "Named M-STALE-PAYLOAD and executed it on the loaded fixture. "
            "Agreement with the suite's reachability definition is not required; "
            "the obligation is to name a mutation the suite would not catch."
        ),
        "mutation_suite_would_not_catch": {
            "id": MUTATION["id"],
            "description": MUTATION["description"],
            "why_survives": MUTATION["why_survives"],
            "does_not_claim": MUTATION["does_not_claim"],
            "executed": True,
            "survived": run.get("survived"),
        },
        "execution": run,
    }
