"""FEP-Databricks probe — parses the ``fep_plus`` / multisim driver log.

The Schrodinger FEP+ driver runs a LOMAP-connected map; each edge exchanges
replicas across lambda windows in a **complex leg** and a **solvent leg**, and
the multisim harness reports its progress as ordered ``Stage`` lines, per-leg
``lambda window i/n`` lines, a ``[prog]`` GPU heartbeat, and finally an
``_out.fmp`` / Bennett-``ddG`` completion.

This probe distils those into a :class:`~probes.base.ProbeReading` while killing
the two FEP-dashboard bugs (grill S6):

* **Per-leg FRONTIER, not distinct-count.** The window frontier is the MAX index
  reached in each leg — a rolled log tail can never undercount it.
* **No phantom cap.** A window frontier past its ``n`` is preserved as an
  overshoot (fraction > 1), never clamped to the denominator.

It also recognises the a2d per-edge-map form (``edges banked N/Total``) as a
fallback frontier when window lines are absent.
"""

from __future__ import annotations

import re

from .base import ProbeReading, extract_gpu, frontier_of, join_detail

_STAGE_RE = re.compile(r"[Ss]tage\s+(\d+)(?:\s+of\s+(\d+))?")
_LEG_RE = re.compile(r"\b(complex|solvent)\s+leg\b", re.IGNORECASE)
_WINDOW_RE = re.compile(r"(?:lambda\s+)?window\s+(\d+)\s*/\s*(\d+)", re.IGNORECASE)
_EDGE_RE = re.compile(r"\bedges?\b[^\d]*(\d+)\s*/\s*(\d+)", re.IGNORECASE)
_TERMINAL_RE = re.compile(
    r"_out\.fmp|Bennett\s+ddG|\bddG\b|cycle[- ]closure", re.IGNORECASE
)


class FepDatabricksProbe:
    """Parser for the FEP+ multisim driver log."""

    name = "fep-databricks"

    def parse(self, lines: list[str]) -> ProbeReading:  # noqa: C901 - linear scan
        stage = ""
        current_leg = ""
        complex_windows: list[tuple[int, int]] = []
        solvent_windows: list[tuple[int, int]] = []
        edges: list[tuple[int, int]] = []
        gpu = ""
        terminal = False

        for raw in lines:
            line = raw.strip()

            leg_match = _LEG_RE.search(line)
            if leg_match is not None:
                current_leg = leg_match.group(1).lower()

            stage_match = _STAGE_RE.search(line)
            if stage_match is not None:
                total = stage_match.group(2)
                stage = (
                    f"stage {stage_match.group(1)}/{total}"
                    if total is not None
                    else f"stage {stage_match.group(1)}"
                )

            window_match = _WINDOW_RE.search(line)
            if window_match is not None:
                pair = (int(window_match.group(1)), int(window_match.group(2)))
                if current_leg == "solvent":
                    solvent_windows.append(pair)
                else:
                    complex_windows.append(pair)

            edge_match = _EDGE_RE.search(line)
            if edge_match is not None:
                edges.append((int(edge_match.group(1)), int(edge_match.group(2))))

            heartbeat = extract_gpu(line)
            if heartbeat is not None:
                gpu = heartbeat

            if _TERMINAL_RE.search(line):
                terminal = True

        return self._assemble(
            stage, current_leg, complex_windows, solvent_windows, edges, gpu, terminal
        )

    def _assemble(
        self,
        stage: str,
        current_leg: str,
        complex_windows: list[tuple[int, int]],
        solvent_windows: list[tuple[int, int]],
        edges: list[tuple[int, int]],
        gpu: str,
        terminal: bool,
    ) -> ProbeReading:
        legs = [
            f
            for f in (frontier_of(complex_windows), frontier_of(solvent_windows))
            if f is not None
        ]
        if legs:
            done = float(sum(leg_done for leg_done, _ in legs))
            total = float(sum(leg_total for _, leg_total in legs))
            leg = f"{current_leg} leg" if current_leg else "fep"
            phase = stage or leg
            return ProbeReading(
                done=done,
                total=total,
                phase=phase,
                frontier=done,
                gpu=gpu,
                terminal=terminal,
                detail=join_detail(phase, gpu),
            )

        edge_frontier = frontier_of(edges)
        if edge_frontier is not None:
            edge_done, edge_total = edge_frontier
            phase = stage or "edges"
            return ProbeReading(
                done=float(edge_done),
                total=float(edge_total),
                phase=phase,
                frontier=float(edge_done),
                gpu=gpu,
                terminal=terminal,
                detail=join_detail(phase, gpu),
            )

        return ProbeReading(
            done=None,
            total=None,
            phase=stage,
            frontier=None,
            gpu=gpu,
            terminal=terminal,
            detail=join_detail(stage, gpu),
        )
