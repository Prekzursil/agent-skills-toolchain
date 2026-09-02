#!/usr/bin/env python3
"""Fusion duplicate-control-plane detector (WFA-0109).

Two mechanically independent signals:

  A — static census of the fused IR: distinct execution-order owners,
      schedulers, and state stores. Each axis must be exactly one.
  B — runtime observation of a fused execution: distinct scheduler
      processes (ops that own the run loop or dispatch steps) and
      distinct state-write targets. A fusion may declare one plane
      and spawn two; only B sees that.

A capability-superset check cannot see this defect: both planes can
be individually present and working. Consistency of two stores is
not singularity.

Helper processes (compute/map/reduce without schedule or persist)
are not control planes.
"""
from __future__ import annotations

from typing import Any

CONTROL_ROLES = frozenset(
    {"scheduler", "state_store", "execution_order_owner"}
)
SCHEDULER_OPS = frozenset(
    {"run_loop", "schedule_step", "dispatch_order", "own_run_loop"}
)
STATE_WRITE_OPS = frozenset({"commit_state", "persist_workflow_state"})
HELPER_OPS = frozenset({"compute", "map_item", "reduce_item", "fanout_work"})
HELPER_ROLES = frozenset(
    {"parallel_helper", "compute_worker", "fanout_worker", "helper"}
)


def _ids(items: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    if not isinstance(items, list):
        return out
    for item in items:
        ident = ""
        if isinstance(item, str):
            ident = item
        elif isinstance(item, dict):
            ident = str(item.get("id") or item.get("name") or "")
        if ident and ident not in seen:
            seen.add(ident)
            out.append(ident)
    return out


def _component_ids_with_role(ir: dict, role: str) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for comp in ir.get("components") or []:
        if not isinstance(comp, dict):
            continue
        cid = str(comp.get("id") or "")
        if not cid or cid in seen:
            continue
        roles = {str(comp.get("role") or "")}
        extra = comp.get("roles")
        if isinstance(extra, list):
            roles.update(str(x) for x in extra)
        owns = bool(comp.get("owns_execution_order"))
        if role == "execution_order_owner" and owns:
            seen.add(cid)
            ids.append(cid)
            continue
        if role in roles:
            seen.add(cid)
            ids.append(cid)
    return ids


def static_census(ir: dict) -> dict:
    """Signal A: count declared/component control-plane identities.

    Does not read runtime_script. Helpers are excluded even when they
    appear as parallel components.
    """
    declared = ir.get("declared") if isinstance(ir.get("declared"), dict) else {}
    schedulers = _ids(declared.get("schedulers"))
    stores = _ids(declared.get("state_stores"))
    owners = _ids(declared.get("execution_order_owners"))

    for cid in _component_ids_with_role(ir, "scheduler"):
        if cid not in schedulers:
            schedulers.append(cid)
    for cid in _component_ids_with_role(ir, "state_store"):
        if cid not in stores:
            stores.append(cid)
    for cid in _component_ids_with_role(ir, "execution_order_owner"):
        if cid not in owners:
            owners.append(cid)

    # Drop anything that is only a helper and was not declared as a plane.
    helper_ids = set()
    for comp in ir.get("components") or []:
        if not isinstance(comp, dict):
            continue
        roles = {str(comp.get("role") or "")}
        extra = comp.get("roles")
        if isinstance(extra, list):
            roles.update(str(x) for x in extra)
        if roles & HELPER_ROLES and not (roles & CONTROL_ROLES):
            if not comp.get("owns_execution_order"):
                helper_ids.add(str(comp.get("id") or ""))

    schedulers = [s for s in schedulers if s not in helper_ids]
    stores = [s for s in stores if s not in helper_ids]
    owners = [s for s in owners if s not in helper_ids]

    n_sched = len(schedulers)
    n_store = len(stores)
    n_owner = len(owners)
    fires = n_sched != 1 or n_store != 1 or n_owner != 1
    named: list[str] = []
    if n_sched != 1:
        named.append(f"schedulers={schedulers or ['<none>']}")
    if n_store != 1:
        named.append(f"state_stores={stores or ['<none>']}")
    if n_owner != 1:
        named.append(f"execution_order_owners={owners or ['<none>']}")
    snapshots = []
    for item in declared.get("state_stores") or []:
        if isinstance(item, dict):
            snapshots.append(
                {"id": item.get("id"), "snapshot": item.get("snapshot")}
            )
    consistent = (
        len(snapshots) >= 2
        and len({str(s.get("snapshot")) for s in snapshots}) == 1
    )
    return {
        "signal": "A-static-ir",
        "schedulers": schedulers,
        "state_stores": stores,
        "execution_order_owners": owners,
        "n_schedulers": n_sched,
        "n_state_stores": n_store,
        "n_execution_order_owners": n_owner,
        "stores_consistent": consistent,
        "fires": fires,
        "silent": not fires,
        "named_planes": named,
        "reason": (
            "duplicate-control-plane:" + ",".join(named)
            if fires
            else "singular-control-plane"
        ),
    }


def runtime_observe(ir: dict) -> dict:
    """Signal B: replay runtime_script. Independent of declared counts.

    A process is a scheduler iff it emits a scheduler op. A state-write
    target is the target (or process) of a persist op. Helper ops never
    promote a process to a control plane.
    """
    script = ir.get("runtime_script") or []
    scheduler_procs: list[str] = []
    seen_sched: set[str] = set()
    write_targets: list[str] = []
    seen_write: set[str] = set()
    helper_procs: list[str] = []
    seen_help: set[str] = set()

    for ev in script:
        if not isinstance(ev, dict):
            continue
        proc = str(ev.get("process") or "")
        op = str(ev.get("op") or "")
        if not proc:
            continue
        if op in SCHEDULER_OPS and proc not in seen_sched:
            seen_sched.add(proc)
            scheduler_procs.append(proc)
        if op in STATE_WRITE_OPS:
            target = str(ev.get("target") or proc)
            if target not in seen_write:
                seen_write.add(target)
                write_targets.append(target)
        if op in HELPER_OPS and proc not in seen_help:
            seen_help.add(proc)
            helper_procs.append(proc)

    # Helpers that also scheduled still count as schedulers; helpers that
    # only computed do not.
    helper_only = [p for p in helper_procs if p not in seen_sched]
    n_sched = len(scheduler_procs)
    n_store = len(write_targets)
    fires = n_sched != 1 or n_store != 1
    named: list[str] = []
    if n_sched != 1:
        named.append(f"scheduler_processes={scheduler_procs or ['<none>']}")
    if n_store != 1:
        named.append(f"state_write_targets={write_targets or ['<none>']}")
    return {
        "signal": "B-runtime-observation",
        "scheduler_processes": scheduler_procs,
        "state_write_targets": write_targets,
        "helper_only_processes": helper_only,
        "n_scheduler_processes": n_sched,
        "n_state_write_targets": n_store,
        "fires": fires,
        "silent": not fires,
        "named_planes": named,
        "reason": (
            "duplicate-control-plane:" + ",".join(named)
            if fires
            else "singular-control-plane"
        ),
    }


def capability_superset_ok(ir: dict) -> dict:
    """Capability check: fusion capabilities vs union of sources.

    Both duplicate planes can be working, so this check can PASS while
    the control-plane detector FIRES. That is the named blindness.
    """
    sources = ir.get("sources") or []
    union: set[str] = set()
    for src in sources:
        if isinstance(src, dict):
            for cap in src.get("capabilities") or []:
                union.add(str(cap))
        elif isinstance(src, str):
            union.add(src)
    have = {str(c) for c in (ir.get("capabilities") or [])}
    missing = sorted(union - have)
    return {
        "signal": "capability-superset",
        "required": sorted(union),
        "have": sorted(have),
        "missing": missing,
        "ok": not missing,
        "cannot_see_duplicate_planes": True,
    }


def detect(ir: dict) -> dict:
    a = static_census(ir)
    b = runtime_observe(ir)
    cap = capability_superset_ok(ir)
    diverge = bool(a["fires"]) != bool(b["fires"])
    fires = bool(a["fires"] or b["fires"])
    return {
        "fusion_id": ir.get("fusion_id"),
        "fires": fires,
        "silent": not fires,
        "signals_disagree": diverge,
        "p1_blocks_certification": fires,
        "signal_a": a,
        "signal_b": b,
        "capability_check": cap,
        "named_planes": list(a.get("named_planes") or [])
        + list(b.get("named_planes") or []),
        "reason": (
            "divergence:" + a["reason"] + "|" + b["reason"]
            if diverge
            else (a["reason"] if a["fires"] else b["reason"])
        ),
    }


def load_fixture(path) -> dict:
    import json
    from pathlib import Path

    return json.loads(Path(path).read_text(encoding="utf-8"))
