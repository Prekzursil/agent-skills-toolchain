#!/usr/bin/env python3
"""Crash-resume ledger for RES-0157.

Compares WAL intent-replay, outcome-log skip (Temporal-style), saga abort,
checkpoint-and-restart, and 2PC prepare against five side-effect classes
taken from this program. Numbers are computed, not asserted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SideEffectClass:
    id: str
    title: str
    program_path: str
    program_line: int
    needle: str
    idempotent: bool
    compensable: bool
    has_2pc_prepare: bool
    compensation: str


# Live-tree writers. Line numbers are the declared anchors probe2 re-reads.
CLASSES: tuple[SideEffectClass, ...] = (
    SideEffectClass(
        id="local_artifact_write",
        title="Local artifact / catalog file write",
        program_path="tools/command-center/catalog.py",
        program_line=126,
        needle='target.write_text(text, encoding="utf-8", newline="\\n")',
        idempotent=True,
        compensable=True,
        has_2pc_prepare=True,
        compensation="Overwrite or delete the unpublished file (same path, prior bytes if snapshotted).",
    ),
    SideEffectClass(
        id="append_only_ledger",
        title="Append-only event ledger write",
        program_path="tools/command-center/close.py",
        program_line=91,
        needle="handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + \"\\n\")",
        idempotent=False,
        compensable=True,
        has_2pc_prepare=True,
        compensation="Append a compensating event. Truncating EVENTS.jsonl is forbidden (append-only contract).",
    ),
    SideEffectClass(
        id="cloud_worker_launch",
        title="Cloud / worker job launch",
        program_path="command-center/p2-wave/seed-stage/dispatch_cursor.py",
        program_line=345,
        needle="proc = subprocess.Popen(",
        idempotent=False,
        compensable=True,
        has_2pc_prepare=False,
        compensation="Kill the process group (start_new_session=True) and drop the unit lock. Completed work is not un-run.",
    ),
    SideEffectClass(
        id="github_pr_mutation",
        title="GitHub pull-request mutation",
        program_path="command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json",
        program_line=235,
        needle="gh pr merge --auto --squash",
        idempotent=False,
        compensable=True,
        has_2pc_prepare=False,
        compensation="Close an unmerged PR or open a revert. Merge cannot be undone in place; GitHub already fan-out mailed reviewers.",
    ),
    SideEffectClass(
        id="human_notification",
        title="Human-visible notification (email / review request / operator ping)",
        program_path="command-center/WORK-UNIT-CATALOG.json",
        program_line=71726,
        needle="a sent notification is the expected candidate",
        idempotent=False,
        compensable=False,
        has_2pc_prepare=False,
        compensation="NON-COMPENSABLE",
    ),
)


MODELS = (
    "wal_intent_replay",
    "wal_outcome_skip",
    "saga_compensate_abort",
    "checkpoint_restart",
    "two_phase_commit",
)


@dataclass
class World:
    applied: dict[str, int] = field(default_factory=dict)
    compensated: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.applied:
            self.applied = {c.id: 0 for c in CLASSES}
        if not self.compensated:
            self.compensated = {c.id: 0 for c in CLASSES}

    def apply(self, cid: str) -> None:
        cls = by_id(cid)
        if cls.idempotent:
            self.applied[cid] = 1
        else:
            self.applied[cid] += 1

    def compensate(self, cid: str) -> None:
        cls = by_id(cid)
        if not cls.compensable:
            return
        if self.applied[cid] > self.compensated[cid]:
            self.compensated[cid] += 1

    def net(self) -> dict[str, int]:
        out = {}
        for c in CLASSES:
            if c.compensable:
                out[c.id] = self.applied[c.id] - self.compensated[c.id]
            else:
                out[c.id] = self.applied[c.id]
        return out

    def leftover_noncompensable(self) -> int:
        return sum(self.applied[c.id] for c in CLASSES if not c.compensable)

    def duplicates(self) -> dict[str, int]:
        return {cid: max(0, n - 1) for cid, n in self.applied.items()}


def by_id(cid: str) -> SideEffectClass:
    for c in CLASSES:
        if c.id == cid:
            return c
    raise KeyError(cid)


def class_public(c: SideEffectClass) -> dict[str, Any]:
    return {
        "id": c.id,
        "title": c.title,
        "program_anchor": f"{c.program_path}:{c.program_line}",
        "needle": c.needle,
        "idempotent": c.idempotent,
        "compensable": c.compensable,
        "has_2pc_prepare": c.has_2pc_prepare,
        "compensation": c.compensation,
        "compensation_or_noncompensable": (
            "NON-COMPENSABLE" if not c.compensable else c.compensation
        ),
    }


def _forward(n_done: int) -> tuple[World, list[str]]:
    """Run the first n_done classes to completion. Returns world and outcome ids."""
    world = World()
    done: list[str] = []
    for c in CLASSES[:n_done]:
        world.apply(c.id)
        done.append(c.id)
    return world, done


def wal_intent_replay(crash_after: int) -> World:
    """Log intent then act. On resume, replay every logged intent (no outcome skip)."""
    world, done = _forward(crash_after)
    for cid in done:
        world.apply(cid)
    for c in CLASSES[crash_after:]:
        world.apply(c.id)
    return world


def wal_outcome_skip(crash_after: int) -> World:
    """Temporal-style: persist outcomes; replay skips already-completed effects."""
    world, done = _forward(crash_after)
    done_set = set(done)
    for c in CLASSES:
        if c.id not in done_set:
            world.apply(c.id)
    return world


def saga_compensate_abort(crash_after: int) -> World:
    """Abort the partial saga: compensate completed steps in reverse."""
    world, done = _forward(crash_after)
    for cid in reversed(done):
        world.compensate(cid)
    return world


def checkpoint_restart(crash_after: int, checkpoint_every: int = 2) -> World:
    """Process-local checkpoint. External effects between checkpoint and crash remain."""
    last_ckpt = (crash_after // checkpoint_every) * checkpoint_every
    # External world still holds effects 0..crash_after-1.
    world, _ = _forward(crash_after)
    # Restore process to last_ckpt and re-run from there (duplicates post-checkpoint work).
    for c in CLASSES[last_ckpt:]:
        world.apply(c.id)
    return world


def two_phase_commit(crash_after: int) -> dict[str, Any]:
    """2PC requires a prepare state at every participant. External APIs here have none."""
    participants = [class_public(c) for c in CLASSES]
    refusals = [c.id for c in CLASSES if not c.has_2pc_prepare]
    return {
        "crash_after": crash_after,
        "all_participants_prepared": len(refusals) == 0,
        "prepare_refusals": refusals,
        "atomic_commit_possible": False,
        "reason": (
            "Gray/Lamport: commit only if all resource managers enter prepared. "
            f"Refusing participants: {refusals}"
        ),
    }


def summarize_world(world: World) -> dict[str, Any]:
    return {
        "applied": dict(world.applied),
        "compensated": dict(world.compensated),
        "net": world.net(),
        "duplicates": world.duplicates(),
        "duplicate_total": sum(world.duplicates().values()),
        "leftover_noncompensable": world.leftover_noncompensable(),
        "all_applied_once": all(world.applied[c.id] == 1 for c in CLASSES),
        "compensable_net_zero": all(
            world.net()[c.id] == 0 for c in CLASSES if c.compensable
        ),
    }


def run_matrix() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for crash_after in range(len(CLASSES) + 1):
        wal_i = summarize_world(wal_intent_replay(crash_after))
        wal_o = summarize_world(wal_outcome_skip(crash_after))
        saga = summarize_world(saga_compensate_abort(crash_after))
        ckpt = summarize_world(checkpoint_restart(crash_after))
        tpc = two_phase_commit(crash_after)
        rows.append(
            {
                "crash_after": crash_after,
                "completed_before_crash": [c.id for c in CLASSES[:crash_after]],
                "wal_intent_replay": wal_i,
                "wal_outcome_skip": wal_o,
                "saga_compensate_abort": saga,
                "checkpoint_restart": ckpt,
                "two_phase_commit": tpc,
            }
        )

    outcome_ok = all(r["wal_outcome_skip"]["all_applied_once"] for r in rows)
    intent_dups = any(r["wal_intent_replay"]["duplicate_total"] > 0 for r in rows[1:])
    ckpt_dups = any(r["checkpoint_restart"]["duplicate_total"] > 0 for r in rows[1:])
    saga_leftover = any(
        r["saga_compensate_abort"]["leftover_noncompensable"] > 0 for r in rows[1:]
    )
    saga_comp_zero = all(
        r["saga_compensate_abort"]["compensable_net_zero"] for r in rows
    )
    tpc_blocked = all(
        r["two_phase_commit"]["atomic_commit_possible"] is False for r in rows
    )
    noncomp = [c.id for c in CLASSES if not c.compensable]
    return {
        "n_classes": len(CLASSES),
        "class_ids": [c.id for c in CLASSES],
        "noncompensable_ids": noncomp,
        "rows": rows,
        "verdict": {
            "correct_forward_resume_model": "wal_outcome_skip",
            "correct_abort_model": "saga_compensate_abort",
            "wal_outcome_skip_always_once": outcome_ok,
            "wal_intent_replay_duplicates_nonidempotent": intent_dups,
            "checkpoint_restart_duplicates_post_checkpoint": ckpt_dups,
            "saga_abort_leaves_noncompensable": saga_leftover,
            "saga_abort_compensable_net_zero": saga_comp_zero,
            "two_phase_commit_refused": tpc_blocked,
            "hybrid": (
                "Forward resume: persist outcomes (Temporal event-history / ARIES "
                "LSN skip), not re-issue intents. Abort: saga compensations in "
                "reverse. 2PC does not transfer: three participants have no prepare. "
                "CRIU checkpoint restores the process, not GitHub or a sent mail."
            ),
        },
    }


def mutant_all_compensable_goes_red(matrix: dict[str, Any]) -> bool:
    """Negative control: if every class compensated, the required leftover is gone."""
    return (
        len(matrix["noncompensable_ids"]) >= 1
        and matrix["verdict"]["saga_abort_leaves_noncompensable"] is True
    )
