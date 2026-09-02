"""Mechanism fusion constraint engine for WFA-0062.

Each canonical mechanism asserts zero or more exclusive *slots*.
Same-stage fusion is SAT iff no two mechanisms assert different values
for the same slot. A pair that shares no slot may still be SOFT (awkward
scheduling or cache-key friction) without being contradictory.

This is the experimental substrate: combining a conflicting pair is not
argued on paper; fuse_same_stage returns UNSAT with the clashing slot.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any, Iterable, Sequence

# Exclusive configuration slots. Two values in one slot cannot coexist
# in a single fused stage.
SLOTS: tuple[str, ...] = (
    "visibility",
    "rng",
    "join",
    "stop",
    "io_bind",
    "control",
)

# Canonical mechanism vocabulary used by this unit. WFA-0058's closed
# vocabulary artifact is absent on this worktree; ids here are local and
# namespaced mech.* so they cannot collide with wf-*/BP-* catalogs.
MECHANISMS: dict[str, dict[str, Any]] = {
    "mech.blind_independent_first_pass": {
        "label": "Blind independent first pass",
        "asserts": {"visibility": "blind"},
        "definition": (
            "Each participant produces a first artifact without seeing any "
            "other participant's draft. Shared context is withheld until "
            "the submission barrier."
        ),
    },
    "mech.shared_context_deliberation": {
        "label": "Shared-context deliberation",
        "asserts": {"visibility": "shared"},
        "definition": (
            "Every participant reads the live shared transcript and may "
            "condition on others' in-flight tokens."
        ),
    },
    "mech.deterministic_replay": {
        "label": "Deterministic replay",
        "asserts": {"rng": "deterministic"},
        "definition": (
            "The same event log plus the same inputs must reproduce the "
            "same plan byte-for-byte. Sampling is forbidden."
        ),
    },
    "mech.nondeterministic_sampling": {
        "label": "Non-deterministic sampling",
        "asserts": {"rng": "stochastic"},
        "definition": (
            "Token draws use a non-zero temperature or an unseeded RNG; "
            "two replays of the same prompt are not required to match."
        ),
    },
    "mech.fire_and_forget_dispatch": {
        "label": "Fire-and-forget dispatch",
        "asserts": {"join": "fire_and_forget"},
        "definition": (
            "A child is launched without a join handle. The parent does "
            "not wait and must not read a result that was never collected."
        ),
    },
    "mech.blocking_fanin_barrier": {
        "label": "Blocking fan-in barrier",
        "asserts": {"join": "blocking_fanin"},
        "definition": (
            "The parent blocks until every dispatched child reports a "
            "terminal state. Missing a handle is a defect, not a skip."
        ),
    },
    "mech.stop_first_success": {
        "label": "First-success stop",
        "asserts": {"stop": "first_success"},
        "definition": (
            "The stage terminates when the first child reports SUCCESS; "
            "remaining children are cancelled."
        ),
    },
    "mech.stop_unanimous": {
        "label": "Unanimous stop",
        "asserts": {"stop": "unanimous"},
        "definition": (
            "The stage terminates only when every child has reported the "
            "same terminal class. A single dissent keeps the barrier closed."
        ),
    },
    "mech.exclusive_output_bind": {
        "label": "Exclusive output bind",
        "asserts": {"io_bind": "exclusive"},
        "definition": (
            "Exactly one writer owns the output path. A second writer is "
            "a collision, not a merge."
        ),
    },
    "mech.shared_output_bind": {
        "label": "Shared output bind",
        "asserts": {"io_bind": "shared"},
        "definition": (
            "Multiple writers append or overlay the same path under a "
            "shared lock or last-writer-wins rule."
        ),
    },
    "mech.exclusive_session_lock": {
        "label": "Exclusive session lock",
        "asserts": {"control": "exclusive"},
        "definition": (
            "The live harness session is a mutex. A second controller "
            "must not mutate the same control plane."
        ),
    },
    "mech.shared_control_plane": {
        "label": "Shared control plane",
        "asserts": {"control": "shared"},
        "definition": (
            "Two workflows may issue commands into one session; the "
            "control plane is a bus, not a mutex."
        ),
    },
    # Mechanisms that assert no exclusive slot. They can coexist with
    # anyone; some pairs are still SOFT (awkward, not contradictory).
    "mech.artifact_cache": {
        "label": "Artifact cache",
        "asserts": {},
        "definition": "Memoize stage outputs keyed by input digest.",
    },
    "mech.parallel_fanout": {
        "label": "Parallel fan-out",
        "asserts": {},
        "definition": "Dispatch N independent children concurrently.",
    },
    "mech.sequential_stages": {
        "label": "Sequential stages",
        "asserts": {},
        "definition": "Stages run one after another; stage k+1 sees stage k outputs.",
    },
    "mech.pause_resume": {
        "label": "Pause and resume",
        "asserts": {},
        "definition": "A serialised checkpoint can halt and later continue the same run.",
    },
    "mech.human_checkpoint": {
        "label": "Human checkpoint",
        "asserts": {},
        "definition": "A named gate waits for an owner decision before proceeding.",
    },
    "mech.auto_retry": {
        "label": "Auto retry",
        "asserts": {},
        "definition": "A failed child is re-dispatched up to a bounded retry budget.",
    },
}

# Awkward but satisfiable pairs: operational friction, not a slot clash.
SOFT_FRICTION: dict[tuple[str, str], str] = {
    (
        "mech.artifact_cache",
        "mech.nondeterministic_sampling",
    ): (
        "Cache keys that omit entropy will serve a stale sample as if it "
        "were a hit. The pair is SAT if the cache key includes the seed "
        "or a 'do-not-cache-stochastic' flag; it is awkward, not a slot clash."
    ),
    (
        "mech.sequential_stages",
        "mech.parallel_fanout",
    ): (
        "A sequential spine can contain a parallel fan-out stage. Nesting "
        "is SAT; treating them as globally exclusive is a false HARD."
    ),
    (
        "mech.pause_resume",
        "mech.fire_and_forget_dispatch",
    ): (
        "A paused parent cannot collect a fire-and-forget child that has "
        "no handle. SAT if fire-and-forget children are outside the "
        "checkpoint boundary; awkward if they are inside it."
    ),
    (
        "mech.human_checkpoint",
        "mech.auto_retry",
    ): (
        "Retries inside a human gate are SAT (retry then ask). Retries "
        "that skip the gate are a policy smell, not a slot contradiction."
    ),
    (
        "mech.human_checkpoint",
        "mech.fire_and_forget_dispatch",
    ): (
        "A human gate that never sees the child's result is operationally "
        "deaf. SAT if the fire-and-forget path is a side log; not a slot clash."
    ),
    (
        "mech.artifact_cache",
        "mech.deterministic_replay",
    ): (
        "Replay wants the cache to be a function of the log; a cache that "
        "keys only on the prompt can hide log divergence. Awkward, SAT."
    ),
    (
        "mech.pause_resume",
        "mech.blocking_fanin_barrier",
    ): (
        "A paused barrier must serialise in-flight children. SAT with a "
        "join-set in the checkpoint; awkward without one."
    ),
    (
        "mech.parallel_fanout",
        "mech.human_checkpoint",
    ): (
        "N parallel children plus one human gate is SAT (barrier then gate). "
        "Awkward only if the gate is duplicated per child without a fan-in."
    ),
}


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def mechanism_ids() -> list[str]:
    return sorted(MECHANISMS)


def fuse_same_stage(mech_ids: Sequence[str]) -> dict[str, Any]:
    """Fuse mechanisms into one stage. UNSAT iff a slot is assigned twice differently."""
    unknown = [m for m in mech_ids if m not in MECHANISMS]
    if unknown:
        raise KeyError(f"unknown mechanism ids: {unknown}")
    assignment: dict[str, tuple[str, str]] = {}
    clashes: list[dict[str, str]] = []
    for mid in mech_ids:
        asserts = MECHANISMS[mid]["asserts"]
        for slot, value in asserts.items():
            if slot in assignment and assignment[slot][0] != value:
                prev_val, prev_mech = assignment[slot]
                clashes.append(
                    {
                        "slot": slot,
                        "left_mech": prev_mech,
                        "left_val": prev_val,
                        "right_mech": mid,
                        "right_val": value,
                    }
                )
            elif slot not in assignment:
                assignment[slot] = (value, mid)
    return {
        "sat": len(clashes) == 0,
        "mech_ids": list(mech_ids),
        "assignment": {slot: pair[0] for slot, pair in assignment.items()},
        "owners": {slot: pair[1] for slot, pair in assignment.items()},
        "clashes": clashes,
        "verdict": "SAT" if not clashes else "UNSAT",
    }


def exclusive_pairs() -> list[dict[str, Any]]:
    """Every pair whose same-stage fusion is UNSAT."""
    out: list[dict[str, Any]] = []
    for a, b in combinations(mechanism_ids(), 2):
        fused = fuse_same_stage([a, b])
        if not fused["sat"]:
            clash = fused["clashes"][0]
            out.append(
                {
                    "left": a,
                    "right": b,
                    "slot": clash["slot"],
                    "left_val": clash["left_val"],
                    "right_val": clash["right_val"],
                    "fusion": fused,
                }
            )
    return out


def soft_pairs() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw_key, reason in SOFT_FRICTION.items():
        a, b = _pair_key(*raw_key)
        fused = fuse_same_stage([a, b])
        if not fused["sat"]:
            raise RuntimeError(f"SOFT pair {a},{b} is actually UNSAT")
        out.append({"left": a, "right": b, "grade": "SOFT", "reason": reason, "fusion": fused})
    return out


def is_hard_pair(a: str, b: str) -> bool:
    return not fuse_same_stage([a, b])["sat"]


def friction_reason(a: str, b: str) -> str | None:
    return SOFT_FRICTION.get(_pair_key(a, b))


def naive_union_today(mech_ids: Iterable[str]) -> dict[str, Any]:
    """What the estate does today: there is no fusion gate.

    A naive set-union of mechanism ids is shipped as if it were a workflow.
    This function is that union plus the solver observation.
    """
    ids = sorted(set(mech_ids))
    fused = fuse_same_stage(ids)
    return {
        "gate_present": False,
        "method": "naive-set-union-of-mechanism-ids",
        "fused": fused,
        "what_happens_today": (
            "No fuse() implementation exists in this worktree (search: "
            "def fuse / fuse_workflows / fusion_operator → 0 hits). A naive "
            "union of mechanism ids is therefore accepted as a fused IR. "
            "When the union is UNSAT, the contradiction is silent until a "
            "later stage tries to satisfy both slot values at once."
            if not fused["sat"]
            else "Naive union is SAT for this set; no silent contradiction."
        ),
    }
