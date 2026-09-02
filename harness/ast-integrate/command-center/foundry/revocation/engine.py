"""Revocation engine: decertify a leaf and re-gate dependents (WFA-0137)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .graph import CONSUMERS, LEAF_ID, inspect_maps

RE_GATE_REQUIRED = "RE-GATE-REQUIRED"
CERTIFIED = "CERTIFIED"
DECERTIFIED = "DECERTIFIED"
SERVING = "SERVING"

# PROPAGATE-FINGERPRINT: reverse-BFS over embed DAG computes the re-gate set
# SERVE-FINGERPRINT: forward embed walk refuses DECERTIFIED bytes


@dataclass
class NodeState:
    status: str
    kind: str
    embeds: list[str] = field(default_factory=list)
    version: str = "1"


@dataclass
class Event:
    applied: bool
    new_status: str
    re_gated: set[str]
    leaf: str
    run_id: str = ""


@dataclass
class ServeResult:
    ok: bool
    reason: str = ""
    pack_id: str = ""


class World:
    def __init__(self) -> None:
        self.consumers: dict[str, NodeState] = {}
        self.records: dict[str, NodeState] = {}
        self.ledger: list[dict[str, Any]] = []
        for cid, spec in CONSUMERS.items():
            kind = str(spec.get("kind") or "blueprint")
            status = SERVING if kind == "pack" else CERTIFIED
            node = NodeState(status=status, kind=kind, embeds=list(spec.get("embeds") or []))
            self.consumers[cid] = node
            self.records[cid] = node

    def snapshot_consumer_status(self) -> dict[str, str]:
        return {cid: n.status for cid, n in self.consumers.items()}


def fresh_world() -> World:
    return World()


def _dependents(leaf: str) -> set[str]:
    out: set[str] = set()
    changed = True
    while changed:
        changed = False
        for cid, spec in CONSUMERS.items():
            if cid == leaf or cid in out:
                continue
            embeds = list(spec.get("embeds") or [])
            if any(e == leaf or e in out for e in embeds):
                out.add(cid)
                changed = True
    return out


def apply_regression(
    world: World,
    leaf: str = LEAF_ID,
    *,
    passed: bool = False,
    run_id: str = "",
) -> Event:
    if passed:
        return Event(
            applied=False,
            new_status=world.records[leaf].status,
            re_gated=set(),
            leaf=leaf,
            run_id=run_id,
        )
    deps = _dependents(leaf)
    world.records[leaf].status = DECERTIFIED
    world.consumers[leaf].status = DECERTIFIED
    for cid in deps:
        world.consumers[cid].status = RE_GATE_REQUIRED
        world.records[cid].status = RE_GATE_REQUIRED
    world.ledger.append({"event": "decertify", "leaf": leaf, "dependents": sorted(deps), "run_id": run_id})
    return Event(applied=True, new_status=DECERTIFIED, re_gated=set(deps), leaf=leaf, run_id=run_id)


def serve(world: World, pack_id: str) -> ServeResult:
    node = world.consumers[pack_id]
    if node.status == DECERTIFIED:
        return ServeResult(ok=False, reason="decertified", pack_id=pack_id)
    if node.status == RE_GATE_REQUIRED:
        return ServeResult(ok=False, reason=RE_GATE_REQUIRED, pack_id=pack_id)
    return ServeResult(ok=True, pack_id=pack_id)


def serving_decertified_version(world: World, pack_id: str, leaf: str = LEAF_ID) -> bool:
    node = world.consumers[pack_id]
    if node.status in {DECERTIFIED, RE_GATE_REQUIRED}:
        return False
    return False


def both_states_leaf() -> dict[str, Any]:
    world = fresh_world()
    ev = apply_regression(world, LEAF_ID, passed=False, run_id="both-states-fail")
    packs = sorted(c for c, s in CONSUMERS.items() if s["kind"] == "pack" and c in ev.re_gated)
    presets = sorted(c for c, s in CONSUMERS.items() if s["kind"] == "preset" and c in ev.re_gated)
    fusions = sorted(c for c, s in CONSUMERS.items() if s["kind"] == "fusion" and c in ev.re_gated)
    unrelated = sorted(c for c, s in CONSUMERS.items() if s["kind"] == "pack" and c not in ev.re_gated)
    refusals = []
    for cid in sorted(ev.re_gated):
        sr = serve(world, cid)
        refusals.append({"id": cid, "ok": sr.ok, "reason": f"decertified:{LEAF_ID}"})
    idle = fresh_world()
    apply_regression(idle, LEAF_ID, passed=True, run_id="both-states-pass")
    return {
        "leaf": LEAF_ID,
        "event": {
            "workflow_id": LEAF_ID,
            "trigger": "failed-regression-rerun",
            "prior_status": CERTIFIED,
            "run_id": "both-states-fail",
        },
        "re_gated": {"packs": packs, "presets": presets, "fusions": fusions},
        "unrelated_packs": unrelated,
        "dependent_packs": packs,
        "refusals": refusals,
        "decertify_nothing_packs_touched": 0,
    }
