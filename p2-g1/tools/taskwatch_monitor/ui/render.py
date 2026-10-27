"""Pure render-string builders for the CLI + TUI (100% covered).

Every function here is a total ``objects → str`` map with no I/O and no clock —
the rich Live loop in :mod:`ui.tui` and the ``status``/``list`` text commands
both build their frames from these, so the presentation logic is unit-tested to
100% branch coverage while only the framework render loop is coverage-omitted.

The three grill-honesty rules surface visually:

* an unknown total renders ``--%`` and no ETA (never a fake percentage, S8);
* an overshoot (``fraction > 1``) renders a full bar with a ``!`` marker rather
  than a silent clamp (S6a);
* a BLIND task renders a banner with an age stamp and keeps its last frontier,
  never relabelled DONE (S7).
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from core.models import EtaEstimate, TaskSpec, TaskStatus

from cli.status import TaskView

_SPARK_CHARS = "▁▂▃▄▅▆▇█"
_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")

_STATUS_BADGES: dict[TaskStatus, str] = {
    TaskStatus.PENDING: "· PEND",
    TaskStatus.RUNNING: "▶ RUN",
    TaskStatus.STALLED: "■ STALL",
    TaskStatus.DONE: "✓ DONE",
    TaskStatus.FAILED: "✗ FAIL",
    TaskStatus.BLIND: "? BLIND",
}


def status_badge(status: TaskStatus) -> str:
    """Short display badge for a lifecycle status (total over the enum)."""
    return _STATUS_BADGES[status]


def format_duration(seconds: float | None) -> str:
    """Human-readable ``1h02m`` / ``3m20s`` / ``45s`` duration; ``—`` for None."""
    if seconds is None:
        return "—"
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def format_eta(eta: EtaEstimate) -> str:
    """Render a p50/p90 ETA range + provenance; ``eta —`` when not estimable."""
    if not eta.estimable:
        return "eta —"
    return (
        f"eta p50 {format_duration(eta.p50)} · "
        f"p90 {format_duration(eta.p90)} [{eta.provenance.value}]"
    )


def render_bar(fraction: float | None, *, width: int = 20) -> str:
    """Progress bar; unknown total → ``--%``, overshoot → full bar + ``!``."""
    if fraction is None:
        return "[" + "·" * width + "] --%"
    overshoot = fraction > 1.0
    filled_frac = 1.0 if overshoot else fraction
    filled = int(round(filled_frac * width))
    bar = "█" * filled + " " * (width - filled)
    marker = "!" if overshoot else ""
    return f"[{bar}] {fraction * 100:.0f}%{marker}"


def render_sparkline(values: Sequence[float]) -> str:
    """Unicode block sparkline; empty → ``''``, flat series → mid-block run."""
    if not values:
        return ""
    low = min(values)
    high = max(values)
    span = high - low
    if span == 0:
        return _SPARK_CHARS[len(_SPARK_CHARS) // 2] * len(values)
    scale = len(_SPARK_CHARS) - 1
    return "".join(
        _SPARK_CHARS[int(round((value - low) / span * scale))] for value in values
    )


def parse_gpu_percent(detail: str) -> float | None:
    """Extract the first ``NN%`` reading from a GPU heartbeat detail, or None."""
    match = _PERCENT_RE.search(detail)
    if match is None:
        return None
    return float(match.group(1))


def render_gpu(gpu: str) -> str:
    """The GPU heartbeat detail, or ``—`` when the probe found none."""
    return gpu or "—"


def render_stall_flag(view: TaskView) -> str:
    """``STALL`` when the view is stalled, else the empty string."""
    return "STALL" if view.stalled else ""


def render_progress_cell(view: TaskView) -> str:
    """Leg/stage grid cell: ``<phase>  <done>/<total>`` (frontier, not %)."""
    if view.fraction is None:
        frontier = "—"
    else:
        frontier = f"{view.done:g}/{view.total:g}"
    phase = view.phase or "—"
    return f"{phase}  {frontier}"


def render_blind_banner(views: Sequence[TaskView]) -> str:
    """Banner naming BLIND tasks + their stale age; ``''`` when none are blind."""
    blind = [view for view in views if view.blind]
    if not blind:
        return ""
    parts: list[str] = []
    for view in blind:
        age = format_duration(view.blind_age) if view.blind_age is not None else "?"
        parts.append(f"{view.id} (blind {age})")
    return "BLIND — holding last verdict for " + ", ".join(parts)


def render_task_row(view: TaskView) -> str:
    """One status line: badge, id, bar, ETA, and optional gpu + stall flag."""
    parts = [
        f"{status_badge(view.status):8}",
        f"{view.id:18}",
        render_bar(view.fraction),
        format_eta(view.eta),
    ]
    if view.gpu:
        parts.append(f"gpu {view.gpu}")
    if view.stalled:
        parts.append(render_stall_flag(view))
    return "  ".join(parts)


def render_status_report(views: Sequence[TaskView]) -> str:
    """Full one-shot report: header, BLIND banner (if any), one row per task."""
    if not views:
        return "No tasks registered."
    lines = ["TASKWATCH — task status", "=" * 48]
    banner = render_blind_banner(views)
    if banner:
        lines.append(banner)
    lines.extend(render_task_row(view) for view in views)
    return "\n".join(lines)


def render_registry_table(specs: Sequence[TaskSpec]) -> str:
    """Tabular listing of registered tasks (id / adapter / parser / eta-model)."""
    if not specs:
        return "No tasks registered."
    rows = [f"{'ID':20} {'ADAPTER':18} {'PARSER':16} ETA-MODEL", "-" * 70]
    for spec in specs:
        rows.append(
            f"{spec.id:20} {spec.adapter:18} {(spec.parser or '—'):16} {spec.eta_model}"
        )
    return "\n".join(rows)
