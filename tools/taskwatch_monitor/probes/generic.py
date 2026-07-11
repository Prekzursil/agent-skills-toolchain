"""Generic-logfile probe — a source-agnostic fallback line parser.

For any tool that logs either ``N/M`` step counters or ``NN%`` progress lines
(builds, downloads, rclone, git-clone, llm token streams …). The frontier is the
MAX counter reached (rolloff-immune) and percentages map onto a ``/100`` scale;
neither is clamped, so an overshoot survives as ``fraction() > 1`` (grill S6).
"""

from __future__ import annotations

import re

from .base import ProbeReading, extract_gpu, frontier_of, join_detail, parse_ratio

_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_TERMINAL_RE = re.compile(
    r"\b(done|complete|completed|finished|success|succeeded)\b", re.IGNORECASE
)


class GenericLogfileProbe:
    """Best-effort ``N/M`` + ``NN%`` parser for arbitrary tool logs."""

    name = "generic-logfile"

    def parse(self, lines: list[str]) -> ProbeReading:
        ratios: list[tuple[int, int]] = []
        percents: list[float] = []
        gpu = ""
        terminal = False

        for raw in lines:
            line = raw.strip()

            ratio = parse_ratio(line)
            if ratio is not None:
                ratios.append(ratio)

            percent_match = _PERCENT_RE.search(line)
            if percent_match is not None:
                percents.append(float(percent_match.group(1)))

            heartbeat = extract_gpu(line)
            if heartbeat is not None:
                gpu = heartbeat

            if _TERMINAL_RE.search(line):
                terminal = True

        frontier = frontier_of(ratios)
        if frontier is not None:
            done, total = frontier
            return ProbeReading(
                done=float(done),
                total=float(total),
                phase="",
                frontier=float(done),
                gpu=gpu,
                terminal=terminal,
                detail=join_detail(gpu),
            )
        if percents:
            top = max(percents)
            return ProbeReading(
                done=top,
                total=100.0,
                phase="",
                frontier=top,
                gpu=gpu,
                terminal=terminal,
                detail=join_detail(gpu),
            )
        return ProbeReading(
            done=None,
            total=None,
            phase="",
            frontier=None,
            gpu=gpu,
            terminal=terminal,
            detail=join_detail(gpu),
        )
