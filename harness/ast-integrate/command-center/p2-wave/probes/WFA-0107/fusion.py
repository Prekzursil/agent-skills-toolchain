#!/usr/bin/env python3
"""Independent fusion attempt.

Does not import checker.py. Does not read compat_relation.json,
mechanism_conflicts.json, or licence_matrix.json.

Construction inspects blueprint fields (wire_bus, types, stages, licences,
mechanisms) and applies a hard-coded mechanism mutex plus a hard-coded
licence lattice. An ILLEGAL checker verdict is only honest if this attempt
refuses or yields an invalid IR.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BLUEPRINTS_PATH = HERE / "fixtures" / "blueprints.json"

# Independent of world.CONFLICT_PAIRS (must stay in lock-step with fixtures,
# which probe2 asserts by comparing this set to the JSON graph).
MUTEX = frozenset(
    {
        frozenset(
            {
                "mech.blind-independent-first-pass",
                "mech.shared-context-deliberation",
            }
        ),
        frozenset(
            {
                "mech.deterministic-replay",
                "mech.nondeterministic-sampling",
            }
        ),
        frozenset(
            {
                "mech.fire-and-forget-dispatch",
                "mech.blocking-fan-in-barrier",
            }
        ),
    }
)

UNKNOWN = "UNKNOWN"
PROPRIETARY = "Proprietary"
COPYLEFT = frozenset({"GPL-3.0", "AGPL-3.0", "CC-BY-SA-4.0"})


def load_blueprints() -> dict[str, dict[str, Any]]:
    doc = json.loads(BLUEPRINTS_PATH.read_text(encoding="utf-8"))
    return {b["id"]: b for b in doc["blueprints"]}


def licence_ok(la: str, lb: str) -> tuple[bool, str | None]:
    """Lattice, not a matrix lookup."""
    if la == UNKNOWN or lb == UNKNOWN:
        a, b = sorted((la, lb))
        return False, f"licence-lattice:{a}|{b}"
    if (la == PROPRIETARY) ^ (lb == PROPRIETARY):
        a, b = sorted((la, lb))
        return False, f"licence-lattice:{a}|{b}"
    return True, None


def mutex_hit(mechs: list[str]) -> str | None:
    present = set(mechs)
    for pair in MUTEX:
        if pair <= present:
            a, b = sorted(pair)
            return f"mutex:{a}|{b}"
    return None


def _splice_ok(host: dict, donor: dict) -> bool:
    return donor["input_type"] in set(host["insertions"])


def attempt(
    left_id: str,
    right_id: str,
    operator: str,
    blueprints: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    bps = blueprints or load_blueprints()
    if left_id not in bps or right_id not in bps:
        return {
            "ok": False,
            "left": left_id,
            "right": right_id,
            "operator": operator,
            "defects": ["missing-blueprint"],
            "ir": None,
        }
    a = bps[left_id]
    b = bps[right_id]
    defects: list[str] = []
    ir: dict[str, Any] = {
        "operator": operator,
        "sources": sorted((left_id, right_id)),
        "mechanisms": sorted(set(a["mechanisms"]) | set(b["mechanisms"])),
        "licences": sorted((a["licence"], b["licence"])),
        "wire_buses": sorted({a["wire_bus"], b["wire_bus"]}),
        "stages": None,
        "orientation": None,
    }

    if a["wire_bus"] != b["wire_bus"]:
        defects.append(f"unwirable-bus {a['wire_bus']}|{b['wire_bus']}")

    ok_lic, lic_edge = licence_ok(a["licence"], b["licence"])
    if not ok_lic:
        defects.append(f"invalid-licence {lic_edge}")

    hit = mutex_hit(ir["mechanisms"])
    if hit:
        defects.append(f"invalid-mechanism-co-location {hit}")

    if operator == "union":
        ir["stages"] = [f"{a['id']}.{s}" for s in a["stages"]] + [
            f"{b['id']}.{s}" for s in b["stages"]
        ]
    elif operator == "stage-splice":
        if _splice_ok(a, b):
            ir["orientation"] = f"host={a['id']} donor={b['id']}"
            ir["stages"] = list(a["stages"]) + [f"spliced:{b['stages'][0]}"]
        elif _splice_ok(b, a):
            ir["orientation"] = f"host={b['id']} donor={a['id']}"
            ir["stages"] = list(b["stages"]) + [f"spliced:{a['stages'][0]}"]
        else:
            defects.append(
                f"splice-type-unsatisfied "
                f"{a['input_type']}@{a['id']}|{b['input_type']}@{b['id']}"
            )
    elif operator == "common-core":
        if a["family"] != b["family"]:
            defects.append(f"family-mismatch {a['family']}|{b['family']}")
        inter = sorted(set(a["stages"]) & set(b["stages"]))
        if not inter:
            defects.append(f"empty-core {a['id']}|{b['id']}")
        ir["stages"] = inter or None
    elif operator == "best-of-breed":
        overlap = sorted(set(a["benchmarks"]) & set(b["benchmarks"]))
        if not overlap:
            defects.append(f"no-scored-slot {a['id']}|{b['id']}")
        else:
            ir["stages"] = []
            for slot in overlap:
                pick = a["id"] if a["benchmarks"][slot] >= b["benchmarks"][slot] else b["id"]
                ir["stages"].append(f"{slot}@{pick}")
    elif operator == "ensemble":
        if a["output_type"] != b["output_type"]:
            defects.append(f"output-mismatch {a['output_type']}|{b['output_type']}")
        ir["stages"] = ["parallel:" + a["id"], "parallel:" + b["id"], "reconcile"]
    elif operator == "conditional-hybrid":
        if not (
            a["predicates"]
            or b["predicates"]
            or a["default_branch"]
            or b["default_branch"]
        ):
            defects.append(f"no-predicate {a['id']}|{b['id']}")
        ir["stages"] = ["route", a["id"], b["id"]]
    elif operator == "progressive":
        if a["cost"] == b["cost"]:
            defects.append(f"cost-tie {a['cost']}@{a['id']}|{b['id']}")
        cheap, dear = (a, b) if a["cost"] < b["cost"] else (b, a)
        ir["stages"] = [f"rung0:{cheap['id']}", f"rung1:{dear['id']}"]
    else:
        defects.append(f"unknown-operator {operator}")

    ok = len(defects) == 0 and ir["stages"] is not None
    return {
        "ok": ok,
        "left": left_id,
        "right": right_id,
        "operator": operator,
        "defects": defects,
        "ir": ir,
    }
