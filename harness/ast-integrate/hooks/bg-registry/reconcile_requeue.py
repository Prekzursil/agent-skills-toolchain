#!/usr/bin/env python3
r"""bg-registry/reconcile_requeue.py — H-20: SessionStart crash-reconcile REQUEUE core.

reconcile.py (the sibling) *reports* orphans; it never *resumes* them, so post-crash
recovery is manual and often skipped. H-20 supplies the missing decision: for each
orphaned ``running`` record left by a crashed/killed prior session, decide its fate.

This module is the PURE decision core (an ADAPT of reconcile.py's orphan predicate, not a
rewrite of it). It takes injected callables for artifact-completeness (H-01) and pid
liveness (H-10) so it stays stdlib-only, side-effect-free, and trivially testable. The
LIVE wiring — calling this from the SessionStart hook, performing the actual re-enqueue,
and gating a requeue storm through admission control (H-05/H-06) — is a SEPARATE,
owner-gated step. Nothing here restarts work or mutates the registry.

The four-way rule (07-OPTIONS-H.md H-20), for a ``running`` record from a DIFFERENT,
old-enough session:
  1. artifact satisfies H-01              -> DONE         (done_marker's rule, post-crash)
  2. pid dead + artifact SEVERED/partial  -> SALVAGE      (H-12 tail-continue, then requeue)
  3. pid dead + NO artifact               -> REQUEUE      (attempt += 1, H-11 pivot)
  4. pid alive (TWO signals, never pid-alone) -> LEAVE_ALIVE

Guards that precede the four-way: a record for the CURRENT session, a non-``running``
record, or one inside the grace window is IGNORE (not an orphan). And — the load-bearing
safety rule — an UNDECIDABLE liveness (the detector returned None) is UNKNOWN, NEVER read
as dead: a broken probe must not re-run a worker that is actually alive (duplicate work).

Requeue is PROMPTED by default (``auto_requeue=False``); an unconditional auto-requeue
after a freeze can immediately re-freeze the box, so automatic mode is opt-in and belongs
behind H-05/H-06 admission control.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

DONE = "DONE"
REQUEUE = "REQUEUE"
SALVAGE = "SALVAGE"
LEAVE_ALIVE = "LEAVE_ALIVE"
UNKNOWN = "UNKNOWN"
IGNORE = "IGNORE"

DEFAULT_GRACE_S = 120

# is_pid_alive(pid, pid_start) -> True | False | None(undecidable). The caller compares BOTH
# pid AND process start-time (Windows reuses pids), so this module never sees pid alone.
LivenessFn = Callable[[Any, Any], Optional[bool]]
# is_artifact_complete(expected_artifact) -> bool  (the H-01 shared DONE predicate)
CompleteFn = Callable[[Optional[str]], bool]


@dataclass(frozen=True)
class Decision:
    """The fate of one orphaned record. ``attempt`` is the record's NEW attempt count
    (incremented for REQUEUE/SALVAGE, unchanged otherwise). ``prompted`` is True when the
    requeue must be surfaced for owner approval rather than performed automatically."""

    record_id: str
    action: str
    attempt: int
    reason: str
    prompted: bool


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def classify_orphan(
    rec: Mapping[str, Any],
    *,
    current_sid: str,
    now: float,
    is_artifact_complete: CompleteFn,
    is_pid_alive: LivenessFn,
    grace_s: int = DEFAULT_GRACE_S,
    auto_requeue: bool = False,
) -> Decision:
    """Classify one registry record into a Decision. Pure: no I/O, no mutation."""
    rid = str(rec.get("id", "?"))
    attempt = int(_as_float(rec.get("attempt")))
    prompted = not auto_requeue

    # ---- orphan guards (mirror reconcile.find_orphans) ----------------------------------
    if rec.get("status") != "running":
        return Decision(rid, IGNORE, attempt, "not a running record", prompted)
    if rec.get("session") == current_sid:
        return Decision(
            rid, IGNORE, attempt, "current session's own in-flight work", prompted
        )
    started = _as_float(rec.get("started_ts"))
    if started and (now - started) < grace_s:
        return Decision(
            rid, IGNORE, attempt, f"too fresh (< {grace_s}s grace)", prompted
        )

    # ---- rule 1: a complete artifact is DONE regardless of how the process died ---------
    artifact = rec.get("expected_artifact")
    if is_artifact_complete(artifact):
        return Decision(
            rid, DONE, attempt, "artifact satisfies the DONE predicate", prompted
        )

    # ---- liveness: TWO signals, and an undecidable probe is NOT death (rule 3) ----------
    pid = rec.get("pid")
    if pid:
        alive = is_pid_alive(pid, rec.get("pid_start"))
        if alive is True:
            return Decision(
                rid, LEAVE_ALIVE, attempt, "pid alive (pid+start-time)", prompted
            )
        if alive is None:
            return Decision(
                rid,
                UNKNOWN,
                attempt,
                "liveness undecidable; not re-running a maybe-live worker",
                prompted,
            )
        # alive is False -> the process really is gone; fall through to the dead branches.

    # ---- rules 2 & 3: pid dead (or never recorded). Salvage a partial, requeue a blank. --
    if artifact:
        # An expected artifact that is not complete = a severed/partial output -> salvage first.
        return Decision(
            rid,
            SALVAGE,
            attempt + 1,
            "pid dead, artifact severed -> salvage then requeue",
            prompted,
        )
    return Decision(
        rid, REQUEUE, attempt + 1, "pid dead, no artifact -> re-enqueue", prompted
    )


def plan_requeue(
    records,
    *,
    current_sid: str,
    now: float,
    is_artifact_complete: CompleteFn,
    is_pid_alive: LivenessFn,
    grace_s: int = DEFAULT_GRACE_S,
    auto_requeue: bool = False,
) -> list[Decision]:
    """Classify a whole crashed cohort, returning only the ACTIONABLE decisions (IGNORE is
    dropped). The caller then surfaces a single terminal-state summary and, for the
    prompted requeues, asks the owner before doing anything."""
    out: list[Decision] = []
    for rec in records:
        d = classify_orphan(
            rec,
            current_sid=current_sid,
            now=now,
            is_artifact_complete=is_artifact_complete,
            is_pid_alive=is_pid_alive,
            grace_s=grace_s,
            auto_requeue=auto_requeue,
        )
        if d.action != IGNORE:
            out.append(d)
    return out
