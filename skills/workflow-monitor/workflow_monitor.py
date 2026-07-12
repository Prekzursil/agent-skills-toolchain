#!/usr/bin/env python3
"""workflow_monitor.py — live, READ-ONLY, whole-fleet Textual cockpit for Claude Code Workflow fan-outs.

Reads the native, live-flushed telemetry manifests via the M1 shared parser (``workflow_run``) across the
WHOLE FLEET (all sessions/projects) with O(changed) polling, and renders a full cockpit:

    Header
    RunRollupBar     one line: N active runs · running/done/error · total tokens · follow-state
    ┌ LeftPane ──────────────┐┌ RightPane ─────────────────────────────────────────┐
    │ filter Input           ││ AgentHeader (label·phase·model·state·tokens·tools·idle) │
    │ status chips (toggle)  ││ Collapsible "Task"   = agent_prompt()                  │
    │ run → phase → agent    ││ Collapsible "Feed"   = live RichLog transcript tail     │
    │   TREE (triage-sorted) ││ Collapsible "Result" = report_headline() + agent_output()│
    └────────────────────────┘└─────────────────────────────────────────────────────┘
    Footer

STRICTLY READ-ONLY: every path is opened for reading only; the live run is never mutated. All file I/O runs
in Textual thread-workers (fleet poll + per-agent detail load + feed tail) so the UI thread never blocks.

The Feed reuses ``agent_tail.render`` (the D:\\agent-monitor event→coloured-line mapper) and converts its
ANSI output to Rich ``Text`` via ``Text.from_ansi`` for the RichLog. A self-contained fallback renderer is
used if that module is unavailable.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time

# ── import the M1 shared parser (same directory) ────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import workflow_run as wr  # noqa: E402

# ── reuse agent_tail.render (ANSI event lines) for the Feed pane ─────────────
_AGENT_TAIL_DIR = r"D:\agent-monitor"
try:
    if _AGENT_TAIL_DIR not in sys.path:
        sys.path.insert(0, _AGENT_TAIL_DIR)
    import agent_tail  # type: ignore  # noqa: E402
except Exception:  # pragma: no cover - fallback when D:\agent-monitor is absent
    agent_tail = None

from rich.text import Text  # noqa: E402
from textual import work  # noqa: E402
from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Horizontal, Vertical, VerticalScroll  # noqa: E402
from textual.widgets import (  # noqa: E402
    Button,
    Collapsible,
    Footer,
    Header,
    Input,
    RichLog,
    Static,
    Tree,
)

# ── tunables ────────────────────────────────────────────────────────────────
MAX_RUNS = 80  # cap tree size for whole-fleet scale (569+ runs on disk)
MAX_AGENTS_PER_RUN = 50  # cap leaves built per run (bound _tree_lines rebuild cost)
BACKFILL = 14  # transcript events shown when an agent is first selected
FEED_WIDTH = 160  # width passed to the event renderer
STALL_MS = 90_000  # idle-while-active threshold → triage "STALL"
POLL_SEC = 1.0  # fleet refresh cadence
DETAIL_CHARS = 8000  # truncate Task/Result panes to keep the UI snappy
FEED_TAIL_WINDOW = 65_536  # bytes scanned from EOF to find the last complete line
STATUSES = ("running", "done", "error", "idle")

_GLYPH = {"running": "◔", "done": "✓", "error": "✗", "idle": "·"}
_STYLE = {
    "running": "bold yellow",
    "done": "green",
    "error": "bold red",
    "idle": "grey58",
}


# ── pure helpers ────────────────────────────────────────────────────────────
def _now_ms() -> float:
    return time.time() * 1000.0


def _bucket(a: "wr.WFAgent") -> str:
    if a.errored:
        return "error"
    if a.state == "done":
        return "done"
    if a.running:
        return "running"
    return "idle"


def _agent_priority(a: "wr.WFAgent", now: float) -> int:
    """Triage order for floating problem agents to the top within a phase/run."""
    if a.errored:
        return 0
    if a.running and a.idle_ms(now) > STALL_MS:  # stalled
        return 1
    if a.retrying:
        return 2
    if a.running:
        return 3
    if a.state == "done":
        return 5
    return 4  # idle / unknown


def _last_complete_offset(path: str) -> int:
    """Byte offset just past the last complete (newline-terminated) line.

    Seeds the feed cursor so a trailing partial line the writer has flushed without its
    terminator is NOT skipped — it is re-read once it is completed on a later poll.
    """
    try:
        sz = os.path.getsize(path)
    except OSError:
        return 0
    if sz == 0:
        return 0
    try:
        with open(path, "rb") as fh:
            back = min(sz, FEED_TAIL_WINDOW)
            fh.seek(sz - back)
            data = fh.read()
    except OSError:
        return 0
    nl = data.rfind(b"\n")
    if nl == -1:  # no complete line in the tail window → re-read from window start
        return sz - back
    return (sz - back) + nl + 1


def _fuzzy(query: str, text: str) -> bool:
    """Case-insensitive subsequence match (empty query matches everything)."""
    if not query:
        return True
    i = 0
    q = query.lower()
    for ch in text.lower():
        if i < len(q) and ch == q[i]:
            i += 1
    return i == len(q)


def _model_short(model: str) -> str:
    return model.split("[")[0].replace("claude-", "") if model else ""


def _fmt_elapsed(ms: float) -> str:
    """Longest-active-run elapsed as compact H/M/S."""
    s = int(max(0.0, ms) / 1000)
    if s >= 3600:
        return f"{s // 3600}h {s % 3600 // 60}m"
    if s >= 60:
        return f"{s // 60}m {s % 60}s"
    return f"{s}s"


def _run_flags(r: "wr.WFRun", now: float) -> tuple[bool, bool, bool]:
    err = any(a.errored for a in r.agents)
    retry = any(a.retrying for a in r.agents)
    stall = r.active and any(a.running and a.idle_ms(now) > STALL_MS for a in r.agents)
    return err, retry, stall


def _agent_line(a: "wr.WFAgent", now: float) -> Text:
    b = _bucket(a)
    t = Text()
    t.append(f"{_GLYPH[b]} ", _STYLE[b])
    t.append(a.label or a.agent_id[:8], _STYLE[b])
    if a.retrying:
        t.append(f" ↻{a.attempt}", "magenta")
    meta: list[str] = []
    if a.model:
        meta.append(_model_short(a.model))
    if a.tokens:
        meta.append(f"{a.tokens:,}tok")
    if a.tool_calls:
        meta.append(f"{a.tool_calls}tc")
    if a.last_tool:
        meta.append(a.last_tool)
    idle = a.idle_ms(now)
    if b == "running" and idle > STALL_MS:
        meta.append(f"STALL {int(idle / 1000)}s")
    if meta:
        t.append("  " + " · ".join(meta), "grey50")
    return t


def _run_label(r: "wr.WFRun", now: float) -> Text:
    err, retry, stall = _run_flags(r, now)
    c = r.counts
    t = Text()
    if err or stall:
        t.append("⚠ ", "bold red")
    elif retry:
        t.append("↻ ", "magenta")
    elif r.active:
        t.append("● ", "bold green")
    else:
        t.append("· ", "grey50")
    t.append(r.name or r.wf_id, "bold" if r.active else "")
    t.append(f"  {r.wf_id}", "grey50")
    t.append(f"  {c['done']}✓ {c['error']}✗ {c['running']}◔/{c['total']}", "cyan")
    t.append(f"  {r.status}", "grey58")
    if r.total_tokens:
        t.append(f"  {r.total_tokens:,}tok", "grey50")
    return t


def _phase_label(title: str, agents: list) -> Text:
    done = sum(1 for a in agents if _bucket(a) == "done")
    err = sum(1 for a in agents if _bucket(a) == "error")
    run = sum(1 for a in agents if _bucket(a) == "running")
    t = Text()
    t.append(f"▸ {title}", "bold grey70")
    t.append(f"  {done}✓ {err}✗ {run}◔/{len(agents)}", "grey50")
    return t


# ── self-contained fallback event renderer (only if agent_tail is missing) ───
def _fallback_tail_entries(path: str, n: int) -> list[dict]:
    try:
        sz = os.path.getsize(path)
        with open(path, "rb") as fh:
            fh.seek(max(0, sz - 200_000))
            data = fh.read().decode("utf-8", "ignore")
    except OSError:
        return []
    rows = []
    for line in data.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows[-n:]


def _fallback_render(entry: dict) -> list[Text]:
    msg = entry.get("message") if isinstance(entry.get("message"), dict) else {}
    content = msg.get("content")
    blocks = (
        content
        if isinstance(content, list)
        else ([{"type": "text", "text": content}] if isinstance(content, str) else [])
    )
    out: list[Text] = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t == "thinking" and b.get("thinking"):
            out.append(
                Text(
                    "💭 " + " ".join(str(b["thinking"]).split())[:FEED_WIDTH], "grey62"
                )
            )
        elif t == "text" and b.get("text"):
            out.append(
                Text("📝 " + " ".join(str(b["text"]).split())[:FEED_WIDTH], "green")
            )
        elif t == "tool_use":
            out.append(Text(f"🔧 {b.get('name', '?')}", "cyan"))
        elif t == "tool_result":
            rc = b.get("content")
            s = rc if isinstance(rc, str) else json.dumps(rc, ensure_ascii=False)
            style = "red" if b.get("is_error") else "yellow"
            glyph = "✗" if b.get("is_error") else "↳"
            out.append(Text(f"{glyph} " + " ".join(str(s).split())[:FEED_WIDTH], style))
    return out


def _render_events(entries: list[dict]) -> list[Text]:
    lines: list[Text] = []
    for e in entries:
        if agent_tail is not None:
            try:
                for ln in agent_tail.render(e, FEED_WIDTH):
                    lines.append(Text.from_ansi(ln))
                continue
            except Exception:
                pass
        lines.extend(_fallback_render(e))
    return lines


def _tail_entries(path: str, n: int) -> list[dict]:
    if agent_tail is not None:
        try:
            return agent_tail.read_tail_entries(path, n)
        except Exception:
            pass
    return _fallback_tail_entries(path, n)


# ── the cockpit ─────────────────────────────────────────────────────────────
class WorkflowMonitor(App):
    """Whole-fleet, read-only live board for Claude Code Workflow fan-outs."""

    TITLE = "Workflow Cockpit"
    CSS = """
    Screen { layout: vertical; }
    #rollup { height: 1; padding: 0 1; background: $panel; color: $text; }
    #body { height: 1fr; }
    #left { width: 42%; border-right: solid $primary-darken-2; }
    #right { width: 1fr; }
    #filter { height: 3; border: tall $primary-darken-2; }
    #chips { height: 3; }
    .chip { width: 1fr; margin: 0 1; min-width: 6; }
    .chip.on { background: $success-darken-1; }
    #tree { height: 1fr; }
    #ahdr { height: auto; padding: 0 1; background: $panel; }
    #c-task { height: auto; }
    #c-result { height: auto; }
    .detail-scroll { max-height: 12; height: auto; }
    #c-feed { height: 1fr; }
    #c-feed Contents { height: 1fr; }
    #feed { height: 1fr; background: $surface-darken-1; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+q", "quit", "Quit", show=False),
        Binding("f", "toggle_follow", "Follow"),
        Binding("r", "force_poll", "Refresh"),
        Binding("e", "export", "Export"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="rollup")
        with Horizontal(id="body"):
            with Vertical(id="left"):
                yield Input(placeholder="filter runs / agents…", id="filter")
                with Horizontal(id="chips"):
                    for s in STATUSES:
                        yield Button(
                            f"{_GLYPH[s]} {s}", id=f"chip-{s}", classes="chip on"
                        )
                yield Tree("fleet", id="tree")
            with Vertical(id="right"):
                yield Static("Select an agent in the tree ←", id="ahdr")
                with Collapsible(
                    title="Task (prompt / lens)", collapsed=True, id="c-task"
                ):
                    with VerticalScroll(classes="detail-scroll"):
                        yield Static("", id="task")
                with Collapsible(
                    title="Feed (live transcript)", collapsed=False, id="c-feed"
                ):
                    yield RichLog(
                        id="feed",
                        wrap=False,
                        markup=False,
                        highlight=False,
                        auto_scroll=True,
                    )
                with Collapsible(
                    title="Result (headline + output)", collapsed=True, id="c-result"
                ):
                    with VerticalScroll(classes="detail-scroll"):
                        yield Static("", id="result")
        yield Footer()

    # ── lifecycle ──
    def on_mount(self) -> None:
        self.poller = wr.FleetPoller()
        self._runs_all: list = []
        self._query = ""
        self._status_on: set[str] = set(STATUSES)
        self._run_nodes: dict = {}
        self._agent_nodes: dict = {}
        self._expanded: set[str] = set()
        self._last_sig = None
        self._last_shown = 0
        self._last_rollup: dict | None = None
        self._last_elapsed_ms = 0.0
        self._sel_key: str | None = None
        self._sel_jsonl: str | None = None
        self._feed_pos = 0
        self._feed_ready = False  # True only once _fill_detail has seeded _feed_pos
        self._follow = True
        self._polling = False  # re-entrancy guard: never run two polls at once
        self.query_one("#tree", Tree).show_root = True
        self._schedule_poll()
        self.set_interval(POLL_SEC, self._schedule_poll)

    def _schedule_poll(self) -> None:
        # A thread worker cannot be preempted; skip a tick while one is still in flight so
        # two poll threads never mutate FleetPoller's dicts concurrently.
        if self._polling:
            return
        self._polling = True
        self._poll_worker()

    # ── fleet polling (thread worker → never blocks the UI) ──
    @work(exclusive=True, thread=True, group="poll")
    def _poll_worker(self) -> None:
        try:
            runs = self.poller.poll()
            self._runs_all = runs
            now = _now_ms()
            picked, total = self._display_runs(now)
            sig = self._sig(picked, now)
            rollup = wr.fleet_rollup(runs)
            elapsed_ms = max(
                (now - r.started_at for r in runs if r.active and r.started_at > 0),
                default=0.0,
            )
            # Feed increment: snapshot the selection atomically-ish; _apply re-verifies it
            # is still current before touching #feed (single UI-thread owner of _feed_pos).
            feed = None
            if self._follow and self._feed_ready and self._sel_jsonl:
                key = self._sel_key
                path = self._sel_jsonl
                pos = self._feed_pos
                new_pos, lines = self._read_feed_increment(path, pos)
                feed = (key, path, new_pos, lines)
            self.call_from_thread(
                self._apply, picked, total, sig, rollup, elapsed_ms, feed
            )
        finally:
            self._polling = False

    def _read_feed_increment(self, path: str, pos: int) -> tuple[int, list[Text]]:
        """Return (new_pos, rendered_lines) for bytes appended past the last COMPLETE line.

        Advances only past newline-terminated lines: a trailing partial line the writer
        flushed without its terminator is left for the next poll, so no event is dropped.
        """
        try:
            sz = os.path.getsize(path)
        except OSError:
            return pos, []
        if sz < pos:  # truncated / rotated → restart
            pos = 0
        if sz <= pos:
            return pos, []
        try:
            with open(path, "rb") as fh:
                fh.seek(pos)
                chunk = fh.read(sz - pos)
        except OSError:
            return pos, []
        nl = chunk.rfind(b"\n")
        if (
            nl == -1
        ):  # only a partial line so far → do not advance, wait for its terminator
            return pos, []
        new_pos = pos + nl + 1
        entries: list[dict] = []
        for raw in chunk[:nl].split(b"\n"):
            raw = raw.strip()
            if not raw.startswith(b"{"):
                continue
            try:
                entries.append(json.loads(raw.decode("utf-8", "ignore")))
            except Exception:
                pass
        return new_pos, _render_events(entries)

    def _apply(
        self,
        picked: list,
        total: int,
        sig: tuple,
        rollup: dict,
        elapsed_ms: float,
        feed: tuple | None,
    ) -> None:
        self._last_shown = total
        self._last_rollup = rollup
        self._last_elapsed_ms = elapsed_ms
        if sig != self._last_sig:
            self._rebuild_tree(picked)
            self._last_sig = sig
        else:
            self._update_labels(picked)
        self._update_rollup()
        if feed is not None:
            sel_key, path, new_pos, lines = feed
            # Drop the increment unless the selection is unchanged AND it advances the
            # cursor — guards against a feed read that raced an agent switch / detail seed.
            if (
                lines
                and sel_key == self._sel_key
                and path == self._sel_jsonl
                and new_pos > self._feed_pos
            ):
                self._feed_pos = new_pos
                rl = self.query_one("#feed", RichLog)
                for ln in lines:
                    rl.write(ln)

    # ── selection / filtering ──
    def _display_runs(self, now: float | None = None) -> tuple[list, int]:
        if now is None:
            now = _now_ms()
        q = self._query
        picked: list = []
        for r in self._runs_all:
            vis = [a for a in r.agents if _bucket(a) in self._status_on]
            if r.agents and not vis:
                continue  # every agent filtered out by status chips
            if q:
                hay = f"{r.name} {r.wf_id} {r.session}"
                if not _fuzzy(q, hay) and not any(_fuzzy(q, a.label) for a in vis):
                    continue
            picked.append((r, vis))

        def keyf(item):
            r, _ = item
            err, retry, stall = _run_flags(r, now)
            pri = 0 if (err or stall) else 1 if retry else 2 if r.active else 3
            return (pri, -r.mtime)

        picked.sort(key=keyf)
        return picked[:MAX_RUNS], len(picked)

    def _sig(self, picked: list, now: float | None = None) -> tuple:
        if now is None:
            now = _now_ms()
        # Fold a coarse per-run stall flag in so an agent crossing the STALL threshold
        # forces a rebuild + triage re-sort (not just a label refresh).
        return tuple(
            (
                r.wf_id,
                r.status,
                any(a.running and a.idle_ms(now) > STALL_MS for a in vis),
                tuple((a.agent_id, _bucket(a)) for a in vis),
            )
            for r, vis in picked
        )

    def _rebuild_tree(self, picked: list) -> None:
        tree = self.query_one("#tree", Tree)
        now = _now_ms()
        prev_sel = self._sel_key
        prev_expanded = set(self._expanded)
        tree.clear()
        self._run_nodes = {}
        self._agent_nodes = {}
        for r, vis in picked:
            expand = (r.wf_id in prev_expanded) or r.active
            rn = tree.root.add(_run_label(r, now), data=("run", r.wf_id), expand=expand)
            self._run_nodes[r.wf_id] = rn
            groups: dict = {}
            order: list = []
            for a in vis:
                title = a.phase_title or (
                    r.phases[a.phase_index]
                    if 0 <= a.phase_index < len(r.phases) and r.phases[a.phase_index]
                    else f"phase {a.phase_index}"
                )
                key = (a.phase_index, title)
                if key not in groups:
                    groups[key] = []
                    order.append(key)
                groups[key].append(a)
            budget = MAX_AGENTS_PER_RUN  # bound leaves built per run
            built = 0
            for key in order:
                title = key[1] or f"phase {key[0]}"
                full = groups[key]
                pn = rn.add(  # phase counts reflect ALL agents in the phase
                    _phase_label(title, full),
                    data=("phase", r.wf_id),
                    expand=True,
                )
                # float error/stall/retry agents to the top within the phase
                for a in sorted(full, key=lambda a: (_agent_priority(a, now), a.index)):
                    if budget <= 0:
                        break
                    akey = f"{r.wf_id}/{a.agent_id}"
                    an = pn.add_leaf(
                        _agent_line(a, now), data=("agent", r.wf_id, a.agent_id)
                    )
                    self._agent_nodes[akey] = an
                    budget -= 1
                    built += 1
            hidden = len(vis) - built
            if hidden > 0:
                rn.add_leaf(
                    Text(f"  … +{hidden} more agents (triaged)", "grey50"),
                    data=("more", r.wf_id),
                )
        tree.root.expand()
        # Restore the highlighted agent AFTER the post-clear paint populates node._line —
        # a synchronous select_node here silently fails to move the cursor (textual 8.2.7).
        if prev_sel and prev_sel in self._agent_nodes:
            self.call_after_refresh(tree.select_node, self._agent_nodes[prev_sel])

    def _update_labels(self, picked: list) -> None:
        now = _now_ms()
        for r, vis in picked:
            rn = self._run_nodes.get(r.wf_id)
            if rn is not None:
                rn.set_label(_run_label(r, now))
            for a in vis:
                an = self._agent_nodes.get(f"{r.wf_id}/{a.agent_id}")
                if an is not None:
                    an.set_label(_agent_line(a, now))

    def _update_rollup(self) -> None:
        roll = self._last_rollup
        if roll is None:
            return
        shown = self._last_shown
        t = Text()
        t.append(f" {roll['active_runs']} active", "bold green")
        t.append(f" / {roll['runs']} runs   ", "grey58")
        t.append(f"{roll['running']}◔ ", "yellow")
        t.append(f"{roll['done']}✓ ", "green")
        t.append(f"{roll['error']}✗", "red")
        t.append(f"   {roll['tokens']:,} tok", "cyan")
        t.append(f"   elapsed {_fmt_elapsed(self._last_elapsed_ms)}", "grey58")
        if shown > MAX_RUNS:
            t.append(f"   (showing {MAX_RUNS}/{shown})", "grey50")
        t.append("   follow:", "grey58")
        t.append(
            "ON" if self._follow else "off",
            "bold magenta" if self._follow else "grey50",
        )
        self.query_one("#rollup", Static).update(t)

    # ── tree events ──
    def on_tree_node_highlighted(self, ev: Tree.NodeHighlighted) -> None:
        self._select_node(ev.node)

    def on_tree_node_selected(self, ev: Tree.NodeSelected) -> None:
        self._select_node(ev.node)

    def on_tree_node_expanded(self, ev: Tree.NodeExpanded) -> None:
        d = ev.node.data
        if d and d[0] == "run":
            self._expanded.add(d[1])

    def on_tree_node_collapsed(self, ev: Tree.NodeCollapsed) -> None:
        d = ev.node.data
        if d and d[0] == "run":
            self._expanded.discard(d[1])

    def _select_node(self, node) -> None:
        d = node.data
        if not d or d[0] != "agent":
            return
        _, wf_id, agent_id = d
        key = f"{wf_id}/{agent_id}"
        if key == self._sel_key:
            return
        run = next((r for r in self._runs_all if r.wf_id == wf_id), None)
        if run is None:
            return
        a = next((x for x in run.agents if x.agent_id == agent_id), None)
        if a is None:
            return
        self._feed_ready = False  # freeze feed until _fill_detail seeds the new cursor
        self._sel_key = key
        wf_dir = run.subagents_dir()
        jsonl = os.path.join(wf_dir, f"agent-{agent_id}.jsonl")
        self._sel_jsonl = jsonl
        self._update_agent_header(a, run)
        self.query_one("#task", Static).update("loading…")
        self.query_one("#result", Static).update("loading…")
        rl = self.query_one("#feed", RichLog)
        rl.clear()
        rl.write(Text("loading feed…", "grey50"))
        self._load_detail(wf_dir, jsonl, agent_id, key)

    def _update_agent_header(self, a, run) -> None:
        now = _now_ms()
        b = _bucket(a)
        idle = a.idle_ms(now)
        t = Text()
        t.append(f"{_GLYPH[b]} ", _STYLE[b])
        t.append(a.label or a.agent_id[:8], "bold " + _STYLE[b])
        t.append(f"\n{run.name or run.wf_id} ", "grey62")
        t.append(f"· {a.phase_title or ('phase %d' % a.phase_index)} ", "grey58")
        if a.model:
            t.append(f"· {a.model} ", "grey58")
        t.append(f"· {b} ", _STYLE[b])
        t.append(f"· {a.tokens:,} tok · {a.tool_calls} tools", "cyan")
        if idle:
            t.append(f" · idle {int(idle / 1000)}s", "grey50")
        if a.last_tool:
            t.append(f" · last:{a.last_tool}", "grey50")
        self.query_one("#ahdr", Static).update(t)

    # ── per-agent detail load (thread worker) ──
    @work(exclusive=True, thread=True, group="detail")
    def _load_detail(self, wf_dir: str, jsonl: str, agent_id: str, key: str) -> None:
        prompt = wr.agent_prompt(jsonl) or "(no prompt captured)"
        out = wr.agent_output(jsonl, wf_dir, agent_id) or "(no result yet)"
        head = wr.report_headline(out)
        backfill = _render_events(_tail_entries(jsonl, BACKFILL))
        # Seed the feed cursor at the last COMPLETE line so an event straddling EOF
        # (a partial line mid-write at selection time) is not lost.
        pos = _last_complete_offset(jsonl)
        self.call_from_thread(self._fill_detail, key, prompt, head, out, backfill, pos)

    def _fill_detail(self, key, prompt, head, out, backfill, pos) -> None:
        if key != self._sel_key:  # user moved on before the load finished
            return
        self.query_one("#task", Static).update(prompt[:DETAIL_CHARS])
        res = Text()
        if head:
            res.append(head + "\n\n", "bold")
        res.append(out[:DETAIL_CHARS])
        self.query_one("#result", Static).update(res)
        rl = self.query_one("#feed", RichLog)
        rl.clear()
        for ln in backfill:
            rl.write(ln)
        self._feed_pos = pos
        self._feed_ready = True  # poll may now tail this agent's transcript

    # ── input / chips / actions ──
    def on_input_changed(self, ev: Input.Changed) -> None:
        if ev.input.id != "filter":
            return
        self._query = ev.value.strip()
        self._reflow()

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        bid = ev.button.id or ""
        if not bid.startswith("chip-"):
            return
        s = bid[len("chip-") :]
        if s in self._status_on:
            self._status_on.discard(s)
            ev.button.remove_class("on")
        else:
            self._status_on.add(s)
            ev.button.add_class("on")
        self._reflow()

    def _reflow(self) -> None:
        """Force a structural rebuild after a filter/chip change."""
        now = _now_ms()
        picked, total = self._display_runs(now)
        self._rebuild_tree(picked)
        self._last_sig = self._sig(picked, now)
        self._last_shown = total
        self._update_rollup()

    def action_toggle_follow(self) -> None:
        self._follow = not self._follow
        self._update_rollup()

    def action_force_poll(self) -> None:
        self._schedule_poll()

    # ── export (read-only snapshot of the current selection) ──
    def _agent_label(self, wf_id: str, agent_id: str) -> str | None:
        """The label of ``agent_id`` inside run ``wf_id`` (``collect_run`` scopes by label)."""
        run = next((r for r in self._runs_all if r.wf_id == wf_id), None)
        if run is None:
            return None
        a = next((x for x in run.agents if x.agent_id == agent_id), None)
        if a is None:
            return None
        return a.label or None

    def action_export(self) -> None:
        """Export the selected run (or one agent) to a redacted timeline doc, off-thread.

        Reads the selection from ``tree.cursor_node.data`` (NOT ``_sel_key`` — that only ever
        holds *agent* selections, so a highlighted run/phase node would export the wrong thing):
        ``agent`` → scope=agent pre-filled with that agent's label; ``run``/``phase``/``more`` →
        scope=run for the enclosing run. Nothing selectable → a warning toast.
        """
        node = self.query_one("#tree", Tree).cursor_node
        d = node.data if node is not None else None
        scope = "run"
        agents: list[str] | None = None
        if d and d[0] == "agent":
            _, wf_id, agent_id = d
            label = self._agent_label(wf_id, agent_id)
            if not label:
                self.notify("select a run/agent first", severity="warning")
                return
            scope = "agent"
            agents = [label]
        elif d and d[0] in ("run", "phase", "more"):
            wf_id = d[1]
        else:
            self.notify("select a run/agent first", severity="warning")
            return
        out = os.path.join(tempfile.gettempdir(), "wfmon-exports")
        self._export_worker(wf_id, scope, agents, out)

    @work(thread=True, group="export", exclusive=False)
    def _export_worker(
        self, wf_id: str, scope: str, agents: list[str] | None, out: str
    ) -> None:
        """Run the export off the UI thread. Lazy-imports ``run_export`` INSIDE the worker so a
        missing OPTIONAL pdf dep (or an as-yet-unbuilt export module) can never break startup;
        mirrors the ``_poll_worker``/``_load_detail`` thread-worker pattern. Read-only + idempotent.
        """
        try:
            from wfmon_export.cli import run_export

            path = run_export(
                wf_id,
                scope=scope,
                agents=agents,
                fmt="md",
                tools="full",
                thinking=True,
                redact=True,
                out=out,
                projects=self.poller.projects,
            )
        except Exception as exc:
            self.call_from_thread(
                self.notify, f"export failed: {exc}", severity="warning"
            )
            return
        self.call_from_thread(self.notify, f"exported → {path}")


def main() -> int:
    WorkflowMonitor().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
