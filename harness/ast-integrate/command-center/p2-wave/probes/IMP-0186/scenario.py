"""IMP-0186 fixtures: a live conditional-hybrid spec and planted unreachable twins.

The good spec routes search+cheap → scout, extract → extract, else → general.
Every branch is reachable over the finite enum type; default is last and explicit.

Planted fixtures are detector controls: the same operator must REFUSE them.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[3] / "tools"


def _wf(wid: str, kind: str, extra_stage: str) -> dict[str, Any]:
    return {
        "id": wid,
        "stages": [
            {
                "id": "ingest",
                "kind": "read-input",
                "inputs": ["runtime"],
                "outputs": ["case.json"],
            },
            {
                "id": extra_stage,
                "kind": kind,
                "inputs": ["case.json"],
                "outputs": ["result.json"],
            },
        ],
        "stopping": {"max_stages": 2, "on_error": "halt"},
    }


def input_type() -> dict[str, Any]:
    return {
        "fields": {
            "task_class": {
                "kind": "enum",
                "values": ["search", "extract", "summarize"],
            },
            "budget": {"kind": "enum", "values": ["cheap", "expensive"]},
            "locale": {"kind": "enum", "values": ["en", "ja", "other"]},
        }
    }


def good_spec() -> dict[str, Any]:
    return {
        "id": "fusion.conditional-hybrid.imp-0186",
        "strategy": "conditional-hybrid",
        "input_type": input_type(),
        "sources": {
            "wf.scout": _wf("wf.scout", "index-search", "fanout"),
            "wf.extract": _wf("wf.extract", "span-extract", "slice"),
            "wf.general": _wf("wf.general", "summarize", "reduce"),
        },
        "branches": [
            {
                "id": "br.search-cheap",
                "source_id": "wf.scout",
                "is_default": False,
                "predicate": {
                    "op": "and",
                    "args": [
                        {"op": "eq", "field": "task_class", "value": "search"},
                        {"op": "eq", "field": "budget", "value": "cheap"},
                    ],
                },
            },
            {
                "id": "br.extract",
                "source_id": "wf.extract",
                "is_default": False,
                "predicate": {"op": "eq", "field": "task_class", "value": "extract"},
            },
            {
                "id": "br.default",
                "source_id": "wf.general",
                "is_default": True,
                "predicate": {"op": "true"},
            },
        ],
    }


def plant_never() -> dict[str, Any]:
    """Unsatisfiable `false` arm inserted before default — dead capability."""
    spec = copy.deepcopy(good_spec())
    spec["id"] = "fusion.conditional-hybrid.plant-never"
    spec["branches"].insert(
        2,
        {
            "id": "br.dead-never",
            "source_id": "wf.scout",
            "is_default": False,
            "predicate": {"op": "false"},
        },
    )
    return spec


def plant_out_of_enum() -> dict[str, Any]:
    """eq to a value the type does not admit — unsatisfiable, not a parse error."""
    spec = copy.deepcopy(good_spec())
    spec["id"] = "fusion.conditional-hybrid.plant-out-of-enum"
    spec["branches"].insert(
        2,
        {
            "id": "br.dead-ghost-class",
            "source_id": "wf.extract",
            "is_default": False,
            "predicate": {"op": "eq", "field": "task_class", "value": "translate"},
        },
    )
    return spec


def plant_subsumed() -> dict[str, Any]:
    """Duplicate of br.search-cheap after it — every hitting input already taken."""
    spec = copy.deepcopy(good_spec())
    spec["id"] = "fusion.conditional-hybrid.plant-subsumed"
    spec["branches"].insert(
        1,
        {
            "id": "br.dead-subsumed",
            "source_id": "wf.scout",
            "is_default": False,
            "predicate": {
                "op": "and",
                "args": [
                    {"op": "eq", "field": "task_class", "value": "search"},
                    {"op": "eq", "field": "budget", "value": "cheap"},
                ],
            },
        },
    )
    return spec


def plant_contradiction() -> dict[str, Any]:
    spec = copy.deepcopy(good_spec())
    spec["id"] = "fusion.conditional-hybrid.plant-contradiction"
    spec["branches"].insert(
        2,
        {
            "id": "br.dead-contradiction",
            "source_id": "wf.general",
            "is_default": False,
            "predicate": {
                "op": "and",
                "args": [
                    {"op": "eq", "field": "task_class", "value": "search"},
                    {"op": "eq", "field": "task_class", "value": "extract"},
                ],
            },
        },
    )
    return spec


PLANTS = {
    "never": (plant_never, "br.dead-never"),
    "out-of-enum": (plant_out_of_enum, "br.dead-ghost-class"),
    "subsumed": (plant_subsumed, "br.dead-subsumed"),
    "contradiction": (plant_contradiction, "br.dead-contradiction"),
}


def write_fixture_json() -> Path:
    dest = HERE / "fixtures"
    dest.mkdir(parents=True, exist_ok=True)
    payload = {
        "good": good_spec(),
        "plants": {name: factory() for name, (factory, _) in PLANTS.items()},
        "plant_dead_ids": {name: dead for name, (_, dead) in PLANTS.items()},
    }
    path = dest / "conditional-hybrid.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
