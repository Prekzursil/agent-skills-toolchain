#!/usr/bin/env python3
"""completion.py -- the ONE shared completion predicate (C1) for this harness.

WHY THIS EXISTS
---------------
Five independent implementations of "is it done?" drifted apart on this box and two of them were
SILENTLY LOSING WORK:

  * ``dbx_dispatch.py --only-missing`` globbed 4 of the 5 result trees, so 621 finished artifacts
    were invisible and it would have re-dispatched completed work to a paid cluster.
  * ``dbx_harvest.py`` skipped any local file ``> 512 B`` while the real gate was ``>= 1 KB + a
    sentinel``, so a truncated partial counted as "already have it" and permanently blocked
    re-fetching the good copy.
  * ``run-wave1.ps1`` required ``exit == 0`` even when a complete, sentinel-bearing artifact was on
    disk, so F036 was scored FAILED after successfully producing 24 KB of work.
  * Two Monitors declared a lane terminal on a single liveness probe -- once because the
    orchestrator had killed the watched runner itself.
  * ``codex-monitor`` classified threads by rollout mtime + last-event-type, so a DEAD thread
    rendered identically to a slow one and sat IDLE forever.

THE GOVERNING RULES (each one is paid for in a real incident)
------------------------------------------------------------
1. AND-gate >= 2 mechanically independent signals before a TERMINAL verdict.
2. Exit code alone is never sufficient. Exit 0 with no artifact is a severed stream (FAILED);
   a NON-ZERO exit with a valid artifact is still DONE -- the deliverable is what matters.
3. A FAILED DETECTOR IS NOT AN ABSENCE. If the probe itself errored, return UNKNOWN. Never let a
   broken matcher, a timed-out WMI call, or an empty result render as "nothing there".
4. Liveness uses a CPU **delta** over a window, never cumulative CPU. A process blocked mid-call has
   near-zero delta but may have hours of cumulative time; ranking by cumulative kills the busy one.
5. RUNNING must be bounded. Without a staleness rule a husk stays "running" forever -- 12 codex
   threads sat at 0.2-0.4 s CPU across 170-220 MINUTES and never drained.
6. Producer and consumer must share ONE sentinel contract. This module is that contract.

Stdlib-only, no I/O beyond stat/read of the artifact, safe to import from hooks.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

DONE = "DONE"
FAILED = "FAILED"
RUNNING = "RUNNING"
UNKNOWN = "UNKNOWN"

DEFAULT_MIN_BYTES = 1024
DEFAULT_SENTINEL_TAIL = 600  # bytes of the tail searched for the sentinel


@dataclass
class Verdict:
    """A typed terminal-state result (AGENTS.md 4: prefer terminal-state outputs)."""
    state: str
    reason: str
    signals: dict = field(default_factory=dict)

    @property
    def terminal(self) -> bool:
        return self.state in (DONE, FAILED)

    def __str__(self) -> str:  # SUCCESS:<id> / FAILED:<id> style rendering
        return f"{self.state}: {self.reason}"


def artifact_ok(path: Optional[str], sentinel: Optional[str] = None,
                min_bytes: int = DEFAULT_MIN_BYTES,
                sentinel_tail: int = DEFAULT_SENTINEL_TAIL) -> tuple[bool, str]:
    """The artifact half of the AND-gate: exists AND >= min_bytes AND (optionally) ends with the
    sentinel. This is the single definition every producer and consumer must share."""
    if not path:
        return False, "no artifact path given"
    try:
        if not os.path.exists(path):
            return False, "artifact missing"
        size = os.path.getsize(path)
        if size < min_bytes:
            return False, f"artifact too small ({size}B < {min_bytes}B)"
        if sentinel:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                tail = fh.read()[-sentinel_tail:]
            if sentinel not in tail:
                return False, f"sentinel {sentinel!r} absent from last {sentinel_tail}B"
        return True, f"artifact ok ({size}B)"
    except OSError as e:
        # A stat/read error is a DETECTOR failure, not evidence of absence (rule 3). The caller
        # turns this into UNKNOWN rather than FAILED.
        return False, f"DETECTOR-ERROR: {e}"


def classify(
    artifact: Optional[str] = None,
    sentinel: Optional[str] = None,
    min_bytes: int = DEFAULT_MIN_BYTES,
    exit_code: Optional[int] = None,
    pid_alive: Optional[bool] = None,
    cpu_delta_s: Optional[float] = None,
    cpu_total_s: Optional[float] = None,   # accepted but NEVER used for liveness (rule 4)
    idle_s: Optional[float] = None,
    stale_after_s: Optional[float] = None,
    detector_ok: bool = True,
) -> Verdict:
    """Classify a unit of work as DONE | FAILED | RUNNING | UNKNOWN.

    Precedence, highest first:
      0. detector_ok is False            -> UNKNOWN   (rule 3: a broken probe is not an absence)
      1. artifact passes the AND-gate    -> DONE      (regardless of exit code -- rule 2)
      2. artifact read raised OSError    -> UNKNOWN   (rule 3 again, at the artifact layer)
      3. process is alive and moving     -> RUNNING   (cpu DELTA only -- rule 4)
      4. process alive but stale         -> FAILED    (rule 5: RUNNING must be bounded)
      5. process gone / exit code known  -> FAILED
      6. otherwise                       -> UNKNOWN   (refuse to guess)
    """
    sig: dict = {}

    # ---- rule 3: the detector's own health outranks everything it reports --------------------
    if not detector_ok:
        return Verdict(UNKNOWN, "detector reported failure; absence is not evidence",
                       {"detector_ok": False})

    # ---- rule 1+2: the artifact is the strongest single signal -------------------------------
    ok, why = artifact_ok(artifact, sentinel, min_bytes)
    sig["artifact"] = why
    if ok:
        # A non-zero exit with a complete artifact is STILL done (the F036 incident).
        if exit_code not in (None, 0):
            sig["exit_code"] = exit_code
            return Verdict(DONE, f"artifact valid despite exit={exit_code}", sig)
        return Verdict(DONE, why, sig)
    if why.startswith("DETECTOR-ERROR"):
        return Verdict(UNKNOWN, why, sig)

    # ---- rule 2: exit 0 with no artifact is a severed stream, not a success -------------------
    if exit_code == 0 and artifact:
        sig["exit_code"] = 0
        return Verdict(FAILED, "severed-stream: exit 0 but artifact did not pass the gate", sig)

    # ---- rules 4+5: liveness by DELTA, bounded by staleness -----------------------------------
    if pid_alive is True:
        sig["cpu_delta_s"] = cpu_delta_s
        if cpu_total_s is not None:
            sig["cpu_total_s_ignored"] = cpu_total_s  # recorded, deliberately not used
        moving = cpu_delta_s is not None and cpu_delta_s > 0.05
        if moving:
            return Verdict(RUNNING, f"process alive, cpu delta {cpu_delta_s}s", sig)
        if stale_after_s is not None and idle_s is not None and idle_s >= stale_after_s:
            return Verdict(FAILED,
                           f"husk: alive but cpu-flat for {idle_s}s (>= {stale_after_s}s)", sig)
        if cpu_delta_s is None:
            return Verdict(UNKNOWN, "process alive but no cpu-delta measured", sig)
        return Verdict(RUNNING, "process alive, cpu-flat but inside the staleness window", sig)

    if pid_alive is False:
        sig["pid_alive"] = False
        return Verdict(FAILED, "process gone and no valid artifact", sig)

    if exit_code is not None and exit_code != 0:
        sig["exit_code"] = exit_code
        return Verdict(FAILED, f"exit={exit_code} and no valid artifact", sig)

    # ---- rule: refuse to guess ----------------------------------------------------------------
    return Verdict(UNKNOWN, "insufficient signals to reach a terminal verdict", sig)


if __name__ == "__main__":  # tiny self-check
    print(classify(artifact=__file__, sentinel=None, exit_code=0))
    print(classify(artifact="/nope", sentinel="X", exit_code=0))
    print(classify(detector_ok=False))
