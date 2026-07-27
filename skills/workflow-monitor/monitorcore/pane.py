"""``pane`` — the switchable-pane seam the unified cockpit board dispatches on (WU9-WU13).

Phase 1 shipped ONE hard-coded Codex view. Phase 2 turns it into ONE board with SWITCHABLE
PANES (codex · agents · workflows · databricks · mcp). This module owns the *seam*, never
the content: a :class:`Pane` is a THIN adapter that folds one already-polled
:class:`~monitorcore.contract.Snapshot` into a :class:`PaneBody` — the ANSI-free logical
rows the board frames, plus how many of them the cursor may land on. A pane opens no file,
no socket and no clock; the existing :class:`~monitorcore.contract.MonitorSource` adapters
(``codex_source`` / ``agents_source`` / ``databricks_source`` / ``mcp_source``) do every
read, exactly once per tick, and the board hands the result to whichever pane is active.

Three invariants every pane inherits:

* **Untrusted text is stripped at INGEST and again at the LAST MILE.** :func:`safe` runs
  :func:`monitorcore.textsafe.strip_controls` the moment a foreign string enters a row, and
  :func:`cursor_rows` re-clips every row through :func:`monitorcore.codex_tail.clip` (which
  strips again) before it can reach a painted frame. Either barrier alone defangs a CSI/OSC
  injection; both are kept so a future pane that forgets one still cannot emit an escape
  byte — the PR #206 defect class, closed structurally rather than per-field.
* **``None`` means NOT MEASURED — never zero, never dead.** A source with no config, no
  credentials or no reachable stream renders :func:`not_measured`, never a fabricated ``0``.
  (:mod:`monitorcore.databricks_source` already treats an unmeasured signal this way; the
  panes extend the same rule to every new column.)
* **A pane never raises.** A payload that does not carry the attribute a pane expects
  degrades to an empty row set via :func:`payload_rows`, so one mis-wired source degrades a
  single pane instead of tearing the board down — the ``poll`` cardinal rule, one layer up.

Pure over its inputs (no I/O, no clock, no global state), so it reaches 100% line+branch
under injected values and vendors cleanly into a skill's plain Python.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from .codex_tail import clip
from .contract import Snapshot
from .textsafe import strip_controls

__all__ = [
    "CURSOR",
    "GUTTER",
    "NOT_MEASURED",
    "Pane",
    "PaneBody",
    "PaneCtx",
    "PaneId",
    "clamp",
    "cursor_rows",
    "not_measured",
    "pane_bar",
    "payload_rows",
    "safe",
    "state_badge",
]

# The selection marker is width 2 and aligns with the plain gutter, exactly as ``view`` does,
# so switching panes never shifts the columns under the operator's eye.
CURSOR = "> "
GUTTER = "  "
NOT_MEASURED = "not measured"

_GUTTER_LEN = len(GUTTER)


class PaneId(StrEnum):
    """The stable pane identifiers (a ``str`` at runtime, so it doubles as the CLI value)."""

    CODEX = "codex"
    AGENTS = "agents"
    WORKFLOWS = "workflows"
    DATABRICKS = "databricks"
    MCP = "mcp"


@dataclass(frozen=True)
class PaneCtx:
    """Everything a pane may know: the width, the poll epoch, the cursor position/visibility.

    ``cursor=False`` is the read-only ``--once`` frame (no selection marker), mirroring
    :func:`monitorcore.view.render_view`'s own ``cursor`` seam.
    """

    cols: int
    now: float
    selected: int = 0
    cursor: bool = True


@dataclass(frozen=True)
class PaneBody:
    """A pane's rendered rows plus the number of SELECTABLE rows the cursor may occupy.

    ``count`` is what the board clamps the next keystroke against; it is ``0`` for a pane
    with nothing to select (an unmeasured or empty source), which pins the cursor at row 0.
    """

    lines: tuple[str, ...] = ()
    count: int = 0


@runtime_checkable
class Pane(Protocol):
    """The behavioural contract a pane implements to appear in the board's tab strip.

    ``id`` is the switch key / CLI value; ``title`` is the tab label; ``source_id`` names the
    :class:`~monitorcore.contract.MonitorSource` whose snapshot this pane reads (two panes
    MAY share one source — ``workflows`` is a second projection of the ``agents`` scan).
    ``body`` MUST tolerate ``snap=None`` (source not registered) and MUST NOT raise.
    """

    id: str
    title: str
    source_id: str

    def body(self, snap: Snapshot[Any] | None, ctx: PaneCtx) -> PaneBody: ...


def safe(value: object) -> str:
    """Barrier 1 — coerce ``value`` to text and strip every terminal control byte.

    Applied at INGEST, i.e. the moment an untrusted string (an agent name, an MCP server
    name, a workflow label, an exception text) enters a row. ``None`` becomes ``""`` rather
    than the literal ``"None"``, so an unmeasured field never renders as a fake value.
    """
    if value is None:
        return ""
    return strip_controls(str(value))


def clamp(idx: int, count: int) -> int:
    """Clamp ``idx`` into ``[0, count)`` (``0`` when there is nothing selectable)."""
    if count <= 0:
        return 0
    if idx < 0:
        return 0
    if idx >= count:
        return count - 1
    return idx


def cursor_rows(lines: Sequence[str], ctx: PaneCtx) -> tuple[str, ...]:
    """Barrier 2 — prefix each row with the cursor/gutter and clip it to the pane width.

    ``clip`` strips control bytes BEFORE its width slice, so the slice can never cut through
    a partial escape and no ESC/BEL/OSC byte survives into the frame even if a pane forgot
    :func:`safe` at ingest.
    """
    inner = max(0, ctx.cols - _GUTTER_LEN)
    sel = clamp(ctx.selected, len(lines))
    out: list[str] = []
    for idx, line in enumerate(lines):
        marker = CURSOR if (ctx.cursor and idx == sel) else GUTTER
        out.append(marker + clip(line, inner))
    return tuple(out)


def not_measured(label: str, detail: str = "") -> str:
    """The explicit unmeasured row: ``"<label>: not measured (<detail>)"``.

    Used wherever a fabricated ``0`` would be a lie — an absent MCP config, an unreachable
    Databricks stream, a pane whose source was never registered.
    """
    text = f"{safe(label)}: {NOT_MEASURED}"
    if detail:
        return f"{text} ({safe(detail)})"
    return text


def payload_rows(snap: Snapshot[Any] | None, attr: str) -> tuple[Any, ...]:
    """The payload's ``attr`` sequence, or ``()`` — a mismatched payload never raises.

    ``poll_all`` can hand a pane a synthesised snapshot whose payload is ``None`` (a rogue
    adapter that raised), and a mis-registered source could hand it the wrong payload type.
    Both degrade to "no rows" instead of an ``AttributeError`` inside the paint path.
    """
    if snap is None:
        return ()
    rows = getattr(snap.payload, attr, ())
    if isinstance(rows, tuple | list):
        return tuple(rows)
    return ()


def state_badge(snap: Snapshot[Any] | None, *, source_id: str) -> str:
    """The one-line source status under the tab strip (already control-stripped).

    Reports reachability/staleness as FLAGS and the freshness as ``age=`` — ``age=-`` when
    the adapter does not compute freshness, which is "not measured", not "0 seconds old".
    """
    if snap is None:
        return not_measured(source_id, "no source registered")
    age = "-" if snap.age_s is None else f"{snap.age_s:.0f}s"
    flags: list[str] = []
    if not snap.reachable:
        flags.append("unreachable")
    if snap.stale:
        flags.append("stale")
    suffix = f" [{' '.join(flags)}]" if flags else ""
    error = f"  err={safe(snap.error)}" if snap.error else ""
    return (
        f"{safe(snap.source_id)} [{safe(snap.state)}] "
        f"age={age}{suffix}  {safe(snap.headline)}{error}"
    )


def pane_bar(panes: Sequence[Pane], active: str, cols: int) -> str:
    """The tab strip: ``[1:codex] 2:agents …`` with the ACTIVE pane bracketed.

    The digit is the switch key (``1``-``9``); ``tab`` cycles and ``q`` quits, both spelled
    out so the binding is discoverable without a help pane.
    """
    cells: list[str] = []
    for idx, pane in enumerate(panes, start=1):
        label = f"{idx}:{safe(pane.title)}"
        cells.append(f"[{label}]" if pane.id == active else f" {label} ")
    return clip("panes " + "".join(cells) + "  tab=next  q=quit", cols)
