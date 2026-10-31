"""Rich Live watch loop — the ONLY coverage-omitted module (see pyproject).

This is presentation / event-loop code: it drives a :class:`rich.live.Live`
surface, polling the snapshot engine on an interval and repainting a panel built
entirely from :mod:`ui.render` (which is 100% covered). Unit-testing this would
test rich's render loop, not this project — so ``ui/tui.py`` is the single
reasoned ``[tool.coverage.run] omit`` (mirrors mcp-manager's ``ui/app.py``). Every
testable decision (status derivation, ETA selection, string building, GPU-percent
parsing, sparkline scaling) lives in the covered ``core`` / ``cli`` / ``ui.render``
modules and is exercised there.

The loop is still fully typed and import-clean so basedpyright checks it.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable, Sequence

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from core.models import TaskSpec

from cli import engine
from cli.status import TaskView
from ui import render

Poller = Callable[..., list[TaskView]]
Sleeper = Callable[[float], None]

_GPU_WINDOW = 40


def _record_gpu(views: Sequence[TaskView], history: dict[str, deque[float]]) -> None:
    """Append each task's current GPU utilisation to its rolling window."""
    for view in views:
        percent = render.parse_gpu_percent(view.gpu)
        if percent is not None:
            history.setdefault(view.id, deque(maxlen=_GPU_WINDOW)).append(percent)


def _frame(views: Sequence[TaskView], history: dict[str, deque[float]]) -> Panel:
    """Build one Live frame: the status report plus per-task GPU sparklines."""
    body = [render.render_status_report(views)]
    for view in views:
        window = history.get(view.id)
        if window:
            spark = render.render_sparkline(list(window))
            body.append(f"gpu {view.id}: {spark}")
    return Panel(Text("\n".join(body)), title="taskwatch --watch", border_style="cyan")


def run_watch(
    specs: Sequence[TaskSpec],
    *,
    interval: float = 2.0,
    stall_after_s: float = engine.DEFAULT_STALL_AFTER_S,
    poller: Poller = engine.snapshot,
    sleep: Sleeper = time.sleep,
    console: Console | None = None,
    iterations: int | None = None,
) -> None:
    """Poll + repaint on ``interval`` until interrupted (or ``iterations`` ticks).

    ``poller``/``sleep``/``console``/``iterations`` are injectable so the loop is
    driveable in a harness, but the module itself stays coverage-omitted.
    """
    con = console or Console()
    history: dict[str, deque[float]] = {}
    tick = 0
    with Live(console=con, refresh_per_second=4, transient=False) as live:
        while iterations is None or tick < iterations:
            views = poller(specs, stall_after_s=stall_after_s)
            _record_gpu(views, history)
            live.update(_frame(views, history))
            tick += 1
            if iterations is not None and tick >= iterations:
                break
            sleep(interval)
