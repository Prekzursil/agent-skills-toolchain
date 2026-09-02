"""WFA-0102 union fusion operator.

Unions two workflow IRs (stages, roles, gates). Name collisions are resolved by
qualification (`{source_id}::{id}`), never by overwrite. A HARD mechanism-pair
conflict refuses the union; a SOFT (awkward) pair does not.

A union that always succeeds is the named failure class: it is the direct path
to the more-stages-is-better fallacy. Size of the fused graph is not a value
claim; a task-coverage benchmark decides.
"""
from __future__ import annotations

import copy
from typing import Any, Iterable, Mapping, Sequence

HARD = "HARD"
SOFT = "SOFT"

# Canonical mechanism-level conflicts named by WFA-0062's question. Awkward
# pairs stay SOFT so they are not smuggled into the conflict list.
DEFAULT_CONFLICT_EDGES: tuple[tuple[str, str, str], ...] = (
    ("independent-first-pass", "shared-context-deliberation", HARD),
    ("deterministic-replay", "non-deterministic-sampling", HARD),
    ("fire-and-forget-dispatch", "blocking-fan-in", HARD),
    ("sequential-schedule", "parallel-schedule", SOFT),
)


class FusionRefused(Exception):
    """Union refused because sources carry a HARD mechanism conflict."""

    def __init__(self, conflicts: Sequence[Mapping[str, Any]], left_id: str, right_id: str):
        self.conflicts = [dict(c) for c in conflicts]
        self.left_id = left_id
        self.right_id = right_id
        self.reason = "MECHANISM_CONFLICT"
        pairs = ", ".join(
            f"{c['left_mechanism']} ⊥ {c['right_mechanism']}" for c in self.conflicts
        )
        super().__init__(
            f"union refused: {self.reason} {left_id}+{right_id} [{pairs}]"
        )


def mechanisms_of(workflow: Mapping[str, Any]) -> set[str]:
    found: set[str] = set()
    for key in ("mechanisms",):
        for item in workflow.get(key) or []:
            if isinstance(item, str) and item:
                found.add(item)
    for bucket in ("stages", "roles", "gates"):
        for node in workflow.get(bucket) or []:
            if not isinstance(node, Mapping):
                continue
            for item in node.get("mechanisms") or []:
                if isinstance(item, str) and item:
                    found.add(item)
    return found


def _norm_pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def conflict_index(
    edges: Sequence[tuple[str, str, str]] | None = None,
) -> dict[tuple[str, str], str]:
    table: dict[tuple[str, str], str] = {}
    for a, b, grade in DEFAULT_CONFLICT_EDGES if edges is None else edges:
        table[_norm_pair(a, b)] = grade
    return table


def find_conflicts(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    edges: Sequence[tuple[str, str, str]] | None = None,
) -> list[dict[str, Any]]:
    table = conflict_index(edges)
    ml = mechanisms_of(left)
    mr = mechanisms_of(right)
    hits: list[dict[str, Any]] = []
    for mech_l in sorted(ml):
        for mech_r in sorted(mr):
            grade = table.get(_norm_pair(mech_l, mech_r))
            if grade is None:
                continue
            hits.append(
                {
                    "left_mechanism": mech_l,
                    "right_mechanism": mech_r,
                    "grade": grade,
                    "refuses": grade == HARD,
                }
            )
    return hits


def _qualify(name: str, source_id: str, used: set[str]) -> tuple[str, bool]:
    if name not in used:
        used.add(name)
        return name, False
    qualified = f"{source_id}::{name}"
    n = 2
    while qualified in used:
        qualified = f"{source_id}::{name}::{n}"
        n += 1
    used.add(qualified)
    return qualified, True


def _remap_node(
    node: Mapping[str, Any],
    id_map: Mapping[str, str],
    role_map: Mapping[str, str],
    gate_map: Mapping[str, str],
) -> dict[str, Any]:
    out = copy.deepcopy(dict(node))
    old = str(out.get("id") or "")
    out["id"] = id_map.get(old, old)
    if "role_id" in out:
        rid = str(out.get("role_id") or "")
        out["role_id"] = role_map.get(rid, rid)
    if "gate_ids" in out:
        out["gate_ids"] = [gate_map.get(str(g), str(g)) for g in (out.get("gate_ids") or [])]
    if "depends_on" in out:
        out["depends_on"] = [id_map.get(str(d), str(d)) for d in (out.get("depends_on") or [])]
    return out


def _union_bucket(
    left_nodes: Sequence[Mapping[str, Any]],
    right_nodes: Sequence[Mapping[str, Any]],
    left_id: str,
    right_id: str,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str], list[dict[str, Any]]]:
    used: set[str] = set()
    left_map: dict[str, str] = {}
    right_map: dict[str, str] = {}
    qualifications: list[dict[str, Any]] = []
    merged: list[dict[str, Any]] = []

    for node in left_nodes:
        old = str(node.get("id") or "")
        new, collided = _qualify(old, left_id, used)
        left_map[old] = new
        kept = copy.deepcopy(dict(node))
        kept["id"] = new
        kept["source_workflow"] = left_id
        merged.append(kept)
        if collided:
            qualifications.append(
                {
                    "source_workflow": left_id,
                    "original_id": old,
                    "qualified_id": new,
                    "rule": "qualification-not-overwrite",
                }
            )

    for node in right_nodes:
        old = str(node.get("id") or "")
        new, collided = _qualify(old, right_id, used)
        right_map[old] = new
        kept = copy.deepcopy(dict(node))
        kept["id"] = new
        kept["source_workflow"] = right_id
        merged.append(kept)
        if collided:
            qualifications.append(
                {
                    "source_workflow": right_id,
                    "original_id": old,
                    "qualified_id": new,
                    "rule": "qualification-not-overwrite",
                }
            )

    return merged, left_map, right_map, qualifications


def union_fuse(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    edges: Sequence[tuple[str, str, str]] | None = None,
) -> dict[str, Any]:
    """Union two workflows. Raises FusionRefused on a HARD mechanism conflict."""
    left_id = str(left.get("id") or "left")
    right_id = str(right.get("id") or "right")
    hits = find_conflicts(left, right, edges=edges)
    hard = [h for h in hits if h["refuses"]]
    if hard:
        raise FusionRefused(hard, left_id, right_id)

    roles, l_roles, r_roles, q_roles = _union_bucket(
        list(left.get("roles") or []),
        list(right.get("roles") or []),
        left_id,
        right_id,
    )
    gates, l_gates, r_gates, q_gates = _union_bucket(
        list(left.get("gates") or []),
        list(right.get("gates") or []),
        left_id,
        right_id,
    )
    stages_raw, l_stages, r_stages, q_stages = _union_bucket(
        list(left.get("stages") or []),
        list(right.get("stages") or []),
        left_id,
        right_id,
    )

    remapped_stages: list[dict[str, Any]] = []
    for node in stages_raw:
        src = str(node.get("source_workflow") or "")
        if src == left_id:
            id_map, role_map, gate_map = l_stages, l_roles, l_gates
        else:
            id_map, role_map, gate_map = r_stages, r_roles, r_gates
        remapped_stages.append(_remap_node(node, id_map, role_map, gate_map))

    fused = {
        "id": f"union({left_id},{right_id})",
        "fusion": {
            "operator": "union",
            "sources": [left_id, right_id],
            "collision_rule": "qualify-never-overwrite",
            "conflict_policy": "refuse-HARD-mechanism-pairs",
        },
        "stages": remapped_stages,
        "roles": roles,
        "gates": gates,
        "mechanisms": sorted(mechanisms_of(left) | mechanisms_of(right)),
        "qualifications": {
            "stages": q_stages,
            "roles": q_roles,
            "gates": q_gates,
        },
        "soft_conflicts_observed": [h for h in hits if h["grade"] == SOFT],
    }
    return fused


def union_overwrite(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    """Broken sibling: same-id nodes from the right overwrite the left.

    This is the silent capability-loss mutant. It ignores mechanism conflicts.
    """
    left_id = str(left.get("id") or "left")
    right_id = str(right.get("id") or "right")

    def overlay(a: Sequence[Mapping[str, Any]], b: Sequence[Mapping[str, Any]]) -> list[dict]:
        by_id: dict[str, dict] = {}
        for node in a:
            kept = copy.deepcopy(dict(node))
            kept["source_workflow"] = left_id
            by_id[str(kept.get("id") or "")] = kept
        for node in b:
            kept = copy.deepcopy(dict(node))
            kept["source_workflow"] = right_id
            by_id[str(kept.get("id") or "")] = kept
        return list(by_id.values())

    fused = {
        "id": f"overwrite({left_id},{right_id})",
        "fusion": {
            "operator": "union-overwrite-mutant",
            "sources": [left_id, right_id],
            "collision_rule": "overwrite",
        },
        "stages": overlay(list(left.get("stages") or []), list(right.get("stages") or [])),
        "roles": overlay(list(left.get("roles") or []), list(right.get("roles") or [])),
        "gates": overlay(list(left.get("gates") or []), list(right.get("gates") or [])),
    }
    fused["mechanisms"] = sorted(mechanisms_of(fused))
    return fused


def union_always_succeed(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    edges: Sequence[tuple[str, str, str]] | None = None,
) -> dict[str, Any]:
    """Broken sibling: skip HARD conflict refusal. Always returns a body."""
    del edges
    empty: tuple[tuple[str, str, str], ...] = ()
    return union_fuse(left, right, edges=empty)


def incidence_matrix(
    labeled: Mapping[str, Mapping[str, Any]],
    vocabulary: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Mechanism-by-artifact 0/1 incidence. Capability set = column support."""
    columns = list(labeled.keys())
    present: dict[str, set[str]] = {
        name: mechanisms_of(wf) for name, wf in labeled.items()
    }
    vocab = list(vocabulary) if vocabulary is not None else sorted({m for s in present.values() for m in s})
    matrix: dict[str, dict[str, int]] = {}
    for mech in vocab:
        matrix[mech] = {col: int(mech in present[col]) for col in columns}
    capability_sets = {col: sorted(present[col]) for col in columns}
    return {
        "vocabulary": vocab,
        "columns": columns,
        "matrix": matrix,
        "capability_sets": capability_sets,
    }


def capability_set(workflow: Mapping[str, Any]) -> frozenset[str]:
    return frozenset(mechanisms_of(workflow))


def capability_union_holds(left: Mapping[str, Any], right: Mapping[str, Any], fused: Mapping[str, Any]) -> bool:
    return capability_set(fused) == (capability_set(left) | capability_set(right))


def pad_stages(workflow: Mapping[str, Any], n: int) -> dict[str, Any]:
    """Add empty stages. Size rises; capability set does not. Size is not value."""
    out = copy.deepcopy(dict(workflow))
    stages = list(out.get("stages") or [])
    for i in range(int(n)):
        stages.append(
            {
                "id": f"pad-{i}",
                "role_id": "",
                "gate_ids": [],
                "depends_on": [],
                "mechanisms": [],
            }
        )
    out["stages"] = stages
    return out


def task_benchmark(workflow: Mapping[str, Any], task_mechanisms: Sequence[str]) -> dict[str, Any]:
    """Value is task coverage, not stage count.

    A larger union is not a win unless coverage of the named task rises.
    """
    have = capability_set(workflow)
    task = [m for m in task_mechanisms if m]
    covered = [m for m in task if m in have]
    n_stages = len(list(workflow.get("stages") or []))
    n_roles = len(list(workflow.get("roles") or []))
    n_gates = len(list(workflow.get("gates") or []))
    coverage = (len(covered) / len(task)) if task else 0.0
    return {
        "task_mechanisms": list(task),
        "covered": covered,
        "coverage": coverage,
        "n_stages": n_stages,
        "n_roles": n_roles,
        "n_gates": n_gates,
        "n_nodes": n_stages + n_roles + n_gates,
        "value_metric": "task_coverage",
        "stage_count_is_not_value": True,
    }


# Probe-facing names (kept stable for named_probes).
FusionRefused = FusionRefused
pad_stages = pad_stages
task_benchmark = task_benchmark
union_always_succeed = union_always_succeed
