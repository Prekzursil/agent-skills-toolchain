"""Jaguar QM probe — per-subsystem interaction-energy job state (grill S6/S7).

A Schrodinger Jaguar interaction-energy run computes the QM energy of three
subsystems — the receptor **cluster**, the **ligand**, and the **shared pocket**
(complex) — and takes ΔE_int only once all three finish. Two signals drive it:

* ``_qm_results.log`` — one ``DONE_<job>_exit_<code>`` marker per finished job
  (``exit_0`` = converged/done; any non-zero = failed; ``exit_3`` is Jaguar's
  SCF-non-convergence code).
* the live ``.log`` — streaming ``etot <iter> <E> <dE> <drms>`` SCF lines for the
  running job, giving its in-progress iteration and convergence (drms).

The probe is source-agnostic over its line stream (both marker kinds may arrive
interleaved — a combined results log, or a tee of both files). Mirroring the FEP
probe's leg-tracking, an ``etot`` line is attributed to the job most recently
named by a ``RUNNING <job>`` / ``RUNNING_<job>`` marker.

Per grill S7 the reading is BLIND-aware: with no marker/SCF signal at all the
frontier is honestly ``None`` (unknown-early → the downstream ETA says unknown,
never a fabricated countdown). Interaction-energy readiness is true ONLY when
all three subsystems have a done (exit-0) job.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast

from .base import ProbeReading, join_detail

_DONE_RE = re.compile(r"DONE_(.+?)_exit_(\d+)", re.IGNORECASE)
_RUNNING_RE = re.compile(r"\bRUNNING[_ ]+(\S+)", re.IGNORECASE)
# ``etot <iter> <energy> <dE> <drms>`` — iter is mandatory; drms is the 4th
# field, optional so a short ``etot <iter>`` line still marks the job running.
_ETOT_RE = re.compile(r"\betot\s+(\d+)(?:\s+\S+\s+\S+\s+(\S+))?", re.IGNORECASE)

# Jaguar's SCF non-convergence exit code (surfaced in per-job detail).
_SCF_FAIL_CODE = 3
# The three subsystems whose completion gates the interaction-energy step.
_ROLES: tuple[str, ...] = ("cluster", "ligand", "pocket")


@dataclass
class QmJob:
    """One Jaguar subsystem job's distilled state."""

    name: str
    state: str  # "done" | "running" | "failed" | "pending"
    exit_code: int | None
    iteration: int | None
    drms: float | None

    @property
    def scf_failed(self) -> bool:
        """True when the job failed specifically on SCF non-convergence."""
        return self.state == "failed" and self.exit_code == _SCF_FAIL_CODE

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "state": self.state,
            "exit_code": self.exit_code,
            "iteration": self.iteration,
            "drms": self.drms,
            "scf_failed": self.scf_failed,
        }


@dataclass
class QmReading:
    """The QM probe's per-job view plus interaction-energy readiness."""

    jobs: list[QmJob]
    interaction_ready: bool
    discovered: bool  # any real DONE/RUNNING/etot signal was seen

    @property
    def done_count(self) -> int:
        return sum(1 for job in self.jobs if job.state == "done")

    @property
    def running(self) -> QmJob | None:
        return next((job for job in self.jobs if job.state == "running"), None)

    def to_reading(self) -> ProbeReading:
        """Bridge to the uniform :class:`~probes.base.ProbeReading`.

        Frontier is the done-job count over the tracked total; with no signal at
        all it is honestly ``None`` (unknown-early). ``terminal`` echoes
        interaction-energy readiness.
        """
        states = " ".join(f"{job.name}:{job.state}" for job in self.jobs)
        ready = "interaction-energy ready" if self.interaction_ready else ""
        detail = join_detail(states, ready)
        if not self.discovered:
            return ProbeReading(
                done=None,
                total=None,
                phase="qm",
                frontier=None,
                gpu="",
                terminal=False,
                detail=detail,
            )
        run = self.running
        if run is not None and run.iteration is not None:
            phase = f"{run.name} scf {run.iteration}"
            gpu = f"drms {run.drms}" if run.drms is not None else ""
        elif run is not None:
            phase = f"{run.name} running"
            gpu = ""
        else:
            phase = "qm"
            gpu = ""
        done = float(self.done_count)
        return ProbeReading(
            done=done,
            total=float(len(self.jobs)),
            phase=phase,
            frontier=done,
            gpu=gpu,
            terminal=self.interaction_ready,
            detail=detail,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "jobs": [job.to_dict() for job in self.jobs],
            "interaction_ready": self.interaction_ready,
            "done_count": self.done_count,
            "total": len(self.jobs),
        }


def _parse_float(token: str | None) -> float | None:
    """Parse a drms token to float; ``None`` for a missing/garbage token."""
    if token is None:
        return None
    try:
        return float(token)
    except ValueError:
        return None


class JaguarQmProbe:
    """Parser for the Jaguar QM interaction-energy job set."""

    name = "jaguar-qm"

    def parse(self, lines: list[str]) -> ProbeReading:
        return self.parse_jobs(lines).to_reading()

    def parse_jobs(self, lines: list[str]) -> QmReading:
        done: dict[str, int] = {}
        running: dict[str, tuple[int | None, float | None]] = {}
        current: str | None = None

        for raw in lines:
            line = raw.strip()

            done_match = _DONE_RE.search(line)
            if done_match is not None:
                done[done_match.group(1)] = int(done_match.group(2))

            run_match = _RUNNING_RE.search(line)
            if run_match is not None:
                # The ``(\S+)`` job group is required, so it always participates.
                current = cast("str", run_match.group(1))
                running.setdefault(current, (None, None))

            etot_match = _ETOT_RE.search(line)
            if etot_match is not None and current is not None:
                running[current] = (
                    int(etot_match.group(1)),
                    _parse_float(etot_match.group(2)),
                )

        return self._assemble(done, running)

    def _assemble(
        self,
        done: dict[str, int],
        running: dict[str, tuple[int | None, float | None]],
    ) -> QmReading:
        jobs: list[QmJob] = []
        tracked = sorted(set(done) | set(running))
        for name in tracked:
            if name in done:
                code = done[name]
                jobs.append(
                    QmJob(
                        name=name,
                        state="done" if code == 0 else "failed",
                        exit_code=code,
                        iteration=None,
                        drms=None,
                    )
                )
            else:
                iteration, drms = running[name]
                jobs.append(
                    QmJob(
                        name=name,
                        state="running",
                        exit_code=None,
                        iteration=iteration,
                        drms=drms,
                    )
                )

        # Seed any interaction-energy role with no signal yet as pending.
        for role in _ROLES:
            if not any(role in name.lower() for name in tracked):
                jobs.append(
                    QmJob(
                        name=role,
                        state="pending",
                        exit_code=None,
                        iteration=None,
                        drms=None,
                    )
                )
        jobs.sort(key=lambda job: job.name)

        ready = all(
            any(job.state == "done" and role in job.name.lower() for job in jobs)
            for role in _ROLES
        )
        return QmReading(
            jobs=jobs, interaction_ready=ready, discovered=bool(done or running)
        )
