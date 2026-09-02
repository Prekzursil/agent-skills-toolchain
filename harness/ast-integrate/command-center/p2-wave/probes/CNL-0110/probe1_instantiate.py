#!/usr/bin/env python3
"""Named probe 1: instantiate the preset and prove the schema is not vacuous."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from instantiate import instantiate, seat_roster  # noqa: E402
from preset import REQUIRED_CLASSES, preset as load_preset  # noqa: E402
from schema_check import error_count, invalid_record  # noqa: E402

ART_REL = (
    "command-center/design/council/"
    "CNL-0110-requirements-council-elicitation-plus-conflict-reconciliat.md"
)
TASK = HERE / "fixtures" / "task_api_tokens.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0110-probe1 {msg}")
    return 1


def main() -> int:
    art_path = REPO / ART_REL
    if not art_path.is_file():
        return fail("artifact missing")
    doc = json.loads(art_path.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNL-0110":
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:CNL-0110" not in json.dumps(doc):
        return fail("sentinel absent")
    if doc.get("answers", {}).get("unreconcilable_pair_outcome") != "irreducible-disagreement":
        return fail("unreconcilable outcome is not irreducible-disagreement")

    good_n = error_count(doc)
    bad_n = error_count(invalid_record(doc))
    if good_n != 0:
        return fail(f"schema errors on artifact={good_n}")
    if bad_n < 1:
        return fail("invalid record accepted (vacuous validator)")

    task = json.loads(TASK.read_text(encoding="utf-8"))
    inst = instantiate(task, load_preset())
    if not inst.get("ok"):
        return fail(f"instantiate not ok {inst.get('reason')}")
    roster_classes = {s["class"] for s in inst["roster"]}
    if set(REQUIRED_CLASSES) != roster_classes:
        return fail(f"roster classes {sorted(roster_classes)}")
    if inst["protocol_schedule"] != ["p-elicit", "p-reconcile"]:
        return fail(f"schedule {inst['protocol_schedule']}")
    if inst["voting"]["elicit"] != "record-only":
        return fail("elicit voting is not record-only")
    if inst["voting"]["reconcile"] != "pairwise-originator-conjunction":
        return fail("reconcile voting is not pairwise-originator-conjunction")

    kinds = {tuple(o["pair_key"]): o["kind"] for o in inst["pair_outcomes"]}
    if kinds.get(("W-erase", "W-plain")) != "irreducible-disagreement":
        return fail(f"plain/erase kind {kinds}")
    if kinds.get(("W-fast", "W-tests")) != "reconciled":
        return fail(f"fast/tests kind {kinds}")

    blend = inst["negative_control"]["planted_blend"]
    known = inst["negative_control"]["known_irreducible"]
    if not blend["fires"]:
        return fail("blend negative control did not fire")
    if known["fires"]:
        return fail("irreducible pair incorrectly fired blend control")

    art_inst = doc["instantiation"]
    if art_inst["voting"] != inst["voting"]:
        return fail("artifact voting drifted from live instantiate")
    if art_inst["protocol_schedule"] != inst["protocol_schedule"]:
        return fail("artifact schedule drifted")

    unbalanced = {
        "id": "task.unbalanced",
        "candidates": [
            {"id": "ops-a", "class": "operator"},
            {"id": "ops-b", "class": "operator"},
        ],
        "wants": [],
        "proposed_rewrites": [],
    }
    seated = seat_roster(unbalanced, load_preset())
    if seated["balanced"] or not seated["blocked_elicit"]:
        return fail("unbalanced roster was not blocked")

    print(
        json.dumps(
            {
                "probe": "probe1-instantiate",
                "schema_good_errors": good_n,
                "schema_bad_errors": bad_n,
                "roster": sorted(roster_classes),
                "protocol_schedule": inst["protocol_schedule"],
                "voting": inst["voting"],
                "stopping": inst["stopping"],
                "pair_kinds": {f"{a}+{b}": k for (a, b), k in kinds.items()},
                "blend_fires": blend["fires"],
                "irreducible_silent": (not known["fires"]),
                "unbalanced_blocked": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNL-0110-probe1 instantiate schema blend-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
