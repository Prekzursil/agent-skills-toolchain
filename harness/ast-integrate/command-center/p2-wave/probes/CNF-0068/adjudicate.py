#!/usr/bin/env python3
"""Executable contradiction tests. Verdicts come from file/JSON facts, never agent counts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE = HERE / "fixtures" / "claims.json"
TEST_SOURCE = "command-center/p2-wave/probes/CNF-0068/adjudicate.py"


def load_fixture_edges() -> list[dict]:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    edges = list(doc.get("contradiction_edges") or [])
    registry = REPO / "command-center" / "CLAIM-REGISTRY.json"
    if registry.is_file():
        try:
            reg = json.loads(registry.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            reg = None
        extra = []
        if isinstance(reg, dict):
            extra = list(reg.get("contradiction_edges") or [])
        elif isinstance(reg, list):
            extra = [c for c in reg if isinstance(c, dict) and c.get("contradiction_edges")]
        for item in extra:
            if isinstance(item, dict) and item.get("id"):
                edges.append(item)
    return edges


def live_world() -> dict:
    return {"kind": "live", "overlay": {}}


def overlay_world(overlay: dict) -> dict:
    return {"kind": "overlay", "overlay": dict(overlay or {})}


def path_exists(world: dict, rel: str) -> bool:
    overlay = world.get("overlay") or {}
    if rel in overlay:
        return overlay[rel] is not None
    return (REPO / rel).is_file()


def read_text(world: dict, rel: str) -> str:
    overlay = world.get("overlay") or {}
    if rel in overlay:
        val = overlay[rel]
        if val is None:
            raise FileNotFoundError(rel)
        return str(val)
    path = REPO / rel
    if not path.is_file():
        raise FileNotFoundError(rel)
    return path.read_text(encoding="utf-8")


def read_json(world: dict, rel: str) -> Any:
    return json.loads(read_text(world, rel))


def dig(doc: Any, pointer: str) -> Any:
    if not pointer or pointer == "/":
        return doc
    cur = doc
    for part in pointer.strip("/").split("/"):
        if isinstance(cur, dict):
            cur = cur[part]
        elif isinstance(cur, list):
            cur = cur[int(part)]
        else:
            raise KeyError(pointer)
    return cur


def run_test(edge: dict, world: dict) -> tuple[str, str]:
    """Return (verdict, output). Never inspects agent_assertions."""
    kind = edge.get("kind")
    eid = edge.get("id")
    if kind == "irreducible":
        return "IRREDUCIBLE", f"{eid}: no executable world; irreducible"
    rel = str(edge.get("subject_path") or "")
    try:
        if kind == "existence":
            present = path_exists(world, rel)
            verdict = "SIDE_A" if present else "SIDE_B"
            return verdict, f"{eid}: exists({rel})={present} -> {verdict}"
        if kind == "json_top_type":
            doc = read_json(world, rel)
            is_array = isinstance(doc, list)
            is_object = isinstance(doc, dict)
            want_a = edge.get("side_a_type")
            if want_a == "array":
                verdict = "SIDE_A" if is_array else "SIDE_B"
            elif want_a == "object":
                verdict = "SIDE_A" if is_object else "SIDE_B"
            else:
                return "IRREDUCIBLE", f"{eid}: unknown side_a_type={want_a}"
            return (
                verdict,
                f"{eid}: type array={is_array} object={is_object} -> {verdict}",
            )
        if kind == "json_field_eq":
            doc = read_json(world, rel)
            val = dig(doc, str(edge.get("json_pointer") or "/"))
            if val == edge.get("side_a_value"):
                verdict = "SIDE_A"
            elif val == edge.get("side_b_value"):
                verdict = "SIDE_B"
            else:
                return "IRREDUCIBLE", f"{eid}: unexpected field value {val!r}"
            return verdict, f"{eid}: {rel}{edge.get('json_pointer')}={val!r} -> {verdict}"
        if kind == "json_len":
            doc = read_json(world, rel)
            val = dig(doc, str(edge.get("json_pointer") or "/"))
            n = len(val)
            if n == edge.get("side_a_len"):
                verdict = "SIDE_A"
            elif n == edge.get("side_b_len"):
                verdict = "SIDE_B"
            else:
                return "IRREDUCIBLE", f"{eid}: unexpected len {n}"
            return (
                verdict,
                f"{eid}: len({rel}{edge.get('json_pointer')})={n} -> {verdict}",
            )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, FileNotFoundError) as exc:
        return "IRREDUCIBLE", f"{eid}: test error {type(exc).__name__}:{exc}"
    return "IRREDUCIBLE", f"{eid}: unknown kind {kind}"


def both_outcomes_proof(edge: dict) -> dict | None:
    if edge.get("kind") == "irreducible":
        return None
    va, oa = run_test(edge, overlay_world(edge.get("world_a") or {}))
    vb, ob = run_test(edge, overlay_world(edge.get("world_b") or {}))
    return {
        "side_a_world_verdict": va,
        "side_b_world_verdict": vb,
        "capable": va == "SIDE_A" and vb == "SIDE_B",
        "side_a_output": oa,
        "side_b_output": ob,
    }


def majority_side(edge: dict) -> str | None:
    counts: dict[str, int] = {}
    for row in edge.get("agent_assertions") or []:
        if isinstance(row, dict):
            side = str(row.get("side") or "")
            if side:
                counts[side] = counts.get(side, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


def one_sided_always_a(edge: dict, world: dict) -> tuple[str, str]:
    """Negative control: a test that can only confirm SIDE_A is not an adjudicator."""
    del world
    return "SIDE_A", f"{edge.get('id')}: one-sided always SIDE_A"


def catalog_unit(uid: str = "CNF-0068") -> dict:
    data = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == uid:
            return unit
    raise KeyError(uid)


# Call-site aliases used by emit/probes.
TEST_SOURCE = TEST_SOURCE
both_outcomes_proof = both_outcomes_proof
majority_side = majority_side
one_sided_always_a = one_sided_always_a
overlay_world = overlay_world
