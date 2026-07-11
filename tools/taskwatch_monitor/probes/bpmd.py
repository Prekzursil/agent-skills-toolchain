"""BPMD-Modal probe — parses the Binding-Pose MetaDynamics driver log.

BPMD runs ``ntrial`` metadynamics trials SERIALLY on one GPU (the trials do not
parallelise across GPUs); parallelism is at the ligand level. The driver reports
each trial as ``Trial i of n`` (or ``trial i/n``), moves through setup →
equilibration → metadynamics → analysis phases, emits a GPU heartbeat, and
finishes with a ``PoseScore`` / ``CompScore`` composite.

Like the FEP probe, the trial frontier is the MAX index reached (rolloff-immune)
and is NEVER capped to ``ntrial`` — an overshoot widens the ETA band (grill S6).
"""

from __future__ import annotations

import re

from .base import ProbeReading, extract_gpu, frontier_of, join_detail

_TRIAL_RE = re.compile(r"trial\s+(\d+)\s*(?:of|/)\s*(\d+)", re.IGNORECASE)
_PHASE_RE = re.compile(
    r"\b(setup|equilibrat\w*|metadynamics|metad|production|analysis|posescore)\b",
    re.IGNORECASE,
)
_TERMINAL_RE = re.compile(
    r"PoseScore|CompScore|composite\s+score|persistence\s+score", re.IGNORECASE
)


class BpmdModalProbe:
    """Parser for the BPMD (metadynamics) driver log."""

    name = "bpmd-modal"

    def parse(self, lines: list[str]) -> ProbeReading:
        trials: list[tuple[int, int]] = []
        phase = ""
        gpu = ""
        terminal = False

        for raw in lines:
            line = raw.strip()

            trial_match = _TRIAL_RE.search(line)
            if trial_match is not None:
                trials.append((int(trial_match.group(1)), int(trial_match.group(2))))

            phase_match = _PHASE_RE.search(line)
            if phase_match is not None:
                phase = phase_match.group(1).lower()

            heartbeat = extract_gpu(line)
            if heartbeat is not None:
                gpu = heartbeat

            if _TERMINAL_RE.search(line):
                terminal = True

        frontier = frontier_of(trials)
        if frontier is not None:
            done, total = frontier
            return ProbeReading(
                done=float(done),
                total=float(total),
                phase=phase or "bpmd",
                frontier=float(done),
                gpu=gpu,
                terminal=terminal,
                detail=join_detail(phase, gpu),
            )
        return ProbeReading(
            done=None,
            total=None,
            phase=phase,
            frontier=None,
            gpu=gpu,
            terminal=terminal,
            detail=join_detail(phase, gpu),
        )
