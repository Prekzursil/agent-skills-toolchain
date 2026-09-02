"""WFA-0104 fixtures: exclusive conditional-hybrid spec and detector plants.

Good spec partitions a finite task-class enum across specialized sources and
an explicit default. Each source carries a task-fit quote (the WFA-0035
deciding sentence) so a branch cannot be justified by preference.

Plants:
  overlap          — two specialized predicates match the same class
  hole             — no default and one class uncovered (unrouted)
  unfit            — search inputs routed to an extract-only source
  default-starved  — specialized arms cover the whole type; default never taken
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

TASK_FIT = {
    "wf.scout": {
        "class_id": "search",
        "served_classes": ["search"],
        "quote": (
            "Scout indexes the corpus and fans out retrieval; it is the "
            "search-class candidate, not a general synthesizer."
        ),
        "anchor": "command-center/p2-wave/probes/WFA-0104/fixtures/task-fit.json:wf.scout",
    },
    "wf.extract": {
        "class_id": "extract",
        "served_classes": ["extract"],
        "quote": (
            "Extract slices grounded spans from the source document; it does "
            "not retrieve and it does not summarize."
        ),
        "anchor": "command-center/p2-wave/probes/WFA-0104/fixtures/task-fit.json:wf.extract",
    },
    "wf.transform": {
        "class_id": "transform",
        "served_classes": ["transform"],
        "quote": (
            "Transform rewrites a payload into a typed target schema; it is "
            "the transform-class candidate."
        ),
        "anchor": "command-center/p2-wave/probes/WFA-0104/fixtures/task-fit.json:wf.transform",
    },
    "wf.general": {
        "class_id": "summarize",
        "served_classes": ["summarize"],
        "quote": (
            "General summarizes when no specialized operator matches the "
            "input class; summarize is its home class."
        ),
        "anchor": "command-center/p2-wave/probes/WFA-0104/fixtures/task-fit.json:wf.general",
    },
}


def input_type() -> dict[str, Any]:
    # Field insertion order is search-relevant: fuzz uses this order;
    # typed_universe sorts names. Do not alphabetize this object.
    return {
        "fields": {
            "task_class": {
                "kind": "enum",
                "values": ["search", "extract", "transform", "summarize"],
            },
            "budget": {"kind": "enum", "values": ["cheap", "expensive"]},
            "locale": {"kind": "enum", "values": ["en", "ja"]},
        }
    }


def _stage(sid: str, kind: str, extra: str, anchor: str) -> dict[str, Any]:
    return {
        "id": sid,
        "kind": kind,
        "inputs": ["runtime"] if sid == "ingest" else ["case.json"],
        "outputs": ["case.json"] if sid == "ingest" else ["result.json"],
        "source_anchor": anchor,
    }


def _wf(wid: str, kind: str, extra: str) -> dict[str, Any]:
    fit = TASK_FIT[wid]
    return {
        "id": wid,
        "served_classes": list(fit["served_classes"]),
        "task_fit": {
            "class_id": fit["class_id"],
            "quote": fit["quote"],
            "anchor": fit["anchor"],
        },
        "stages": [
            _stage("ingest", "read-input", extra, f"{fit['anchor']}.stages.ingest"),
            _stage(extra, kind, extra, f"{fit['anchor']}.stages.{extra}"),
        ],
        "stopping": {"max_stages": 2, "on_error": "halt"},
        "source_anchor": fit["anchor"],
    }


def good_spec() -> dict[str, Any]:
    return {
        "id": "wfa.fusion.conditional-hybrid.WFA-0104",
        "strategy": "conditional-hybrid",
        "input_type": input_type(),
        "sources": {
            "wf.scout": _wf("wf.scout", "index-search", "fanout"),
            "wf.extract": _wf("wf.extract", "span-extract", "slice"),
            "wf.transform": _wf("wf.transform", "schema-rewrite", "rewrite"),
            "wf.general": _wf("wf.general", "summarize", "reduce"),
        },
        "branches": [
            {
                "id": "br.search",
                "source_id": "wf.scout",
                "is_default": False,
                "predicate": {"op": "eq", "field": "task_class", "value": "search"},
            },
            {
                "id": "br.extract",
                "source_id": "wf.extract",
                "is_default": False,
                "predicate": {"op": "eq", "field": "task_class", "value": "extract"},
            },
            {
                "id": "br.transform",
                "source_id": "wf.transform",
                "is_default": False,
                "predicate": {"op": "eq", "field": "task_class", "value": "transform"},
            },
            {
                "id": "br.default",
                "source_id": "wf.general",
                "is_default": True,
                "predicate": {"op": "true"},
            },
        ],
    }


def plant_overlap() -> dict[str, Any]:
    """Two specialized arms both match search — multiply-routed."""
    spec = copy.deepcopy(good_spec())
    spec["id"] = "wfa.fusion.conditional-hybrid.plant-overlap"
    spec["branches"].insert(
        1,
        {
            "id": "br.search-dup",
            "source_id": "wf.scout",
            "is_default": False,
            "predicate": {"op": "eq", "field": "task_class", "value": "search"},
        },
    )
    return spec


def plant_hole() -> dict[str, Any]:
    """Drop default and the transform arm — transform inputs fall through."""
    spec = copy.deepcopy(good_spec())
    spec["id"] = "wfa.fusion.conditional-hybrid.plant-hole"
    spec["branches"] = [
        br for br in spec["branches"] if br["id"] not in {"br.transform", "br.default"}
    ]
    return spec


def plant_unfit() -> dict[str, Any]:
    """Route search to an extract-only source."""
    spec = copy.deepcopy(good_spec())
    spec["id"] = "wfa.fusion.conditional-hybrid.plant-unfit"
    for br in spec["branches"]:
        if br["id"] == "br.search":
            br["source_id"] = "wf.extract"
    return spec


def plant_default_starved() -> dict[str, Any]:
    """Cover summarize with a specialized arm so default is never taken."""
    spec = copy.deepcopy(good_spec())
    spec["id"] = "wfa.fusion.conditional-hybrid.plant-default-starved"
    spec["branches"].insert(
        -1,
        {
            "id": "br.summarize",
            "source_id": "wf.general",
            "is_default": False,
            "predicate": {"op": "eq", "field": "task_class", "value": "summarize"},
        },
    )
    return spec


PLANTS = {
    "overlap": (plant_overlap, "multiply-routed"),
    "hole": (plant_hole, "unrouted"),
    "unfit": (plant_unfit, "source-unfit"),
    "default-starved": (plant_default_starved, "default-unexercised"),
}


def write_fixtures() -> Path:
    dest = HERE / "fixtures"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "task-fit.json").write_text(
        json.dumps(TASK_FIT, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    payload = {
        "good": good_spec(),
        "plants": {name: factory() for name, (factory, _) in PLANTS.items()},
        "plant_expect": {name: expect for name, (_, expect) in PLANTS.items()},
    }
    path = dest / "conditional-hybrid.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
