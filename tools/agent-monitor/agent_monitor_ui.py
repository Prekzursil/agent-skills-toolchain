#!/usr/bin/env python3
"""Tkinter desktop UI for the Claude Code agent monitor.

A single friendly window: a selectable list of every subagent (Task + workflow,
tagged by workflow id) on the left, and a full, verbose, timestamped, *retained*
log of the selected agent on the right. Zero third-party deps — Tkinter ships
with CPython on Windows.

Design notes:
  * Discovery/metadata reuse the proven stdlib core in agent_monitor.py.
  * Status is derived from the TRANSCRIPT (running / working / done / stalled),
    not a single mtime cutoff (which mislabels long-thinking or just-finished
    agents).
  * The log pane renders the ENTIRE transcript from line 0 and never clears on
    completion; a formatted copy is also persisted under ./logs/<session>/.
  * Retries (multiple agent-*.jsonl for one logical slot) are grouped: the
    newest attempt is shown live, older attempts are marked "superseded".

Run with no args (the launchers do this).  Power users still have
agent_monitor.py --watch/--spawn.
"""

from __future__ import annotations

import datetime as dt
import glob
import json
import os
import queue
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Reuse the proven discovery core; fall back to local copies if import shape drifts.
try:
    from agent_monitor import find_subagent_dirs, newest_mtime, PROJECTS
except Exception:  # pragma: no cover - defensive
    PROJECTS = os.path.expanduser(r"~/.claude/projects")

    def find_subagent_dirs():
        pat = os.path.join(PROJECTS, "*", "*", "subagents")
        return [
            d
            for d in glob.glob(pat)
            if glob.glob(os.path.join(d, "**", "agent-*.jsonl"), recursive=True)
        ]

    def newest_mtime(d):
        return max(
            (
                os.path.getmtime(p)
                for p in glob.glob(
                    os.path.join(d, "**", "agent-*.jsonl"), recursive=True
                )
            ),
            default=0.0,
        )


try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except Exception as e:  # pragma: no cover
    sys.stderr.write(f"Tkinter is required but unavailable: {e}\n")
    sys.exit(2)

LOGDIR = os.path.join(HERE, "logs")
FRESH = 45.0  # mtime age (s) under which an agent is definitely RUNNING
STALL = 600.0  # silence (s) after which a non-finished agent is STALLED
LIST_POLL_MS = 2000
TAIL_POLL_MS = 600
RESULT_CAP = 8000  # max chars of a single tool_result shown inline (full copy in .log)

# ── palette (dark log pane) ──────────────────────────────────────────────────
BG = "#1e1e1e"
FG = "#d4d4d4"
COL = {
    "ts": "#7d8590",
    "text": "#e6e6e6",
    "think": "#6a9955",
    "tool": "#569cd6",
    "toolarg": "#808080",
    "result": "#4ec9b0",
    "err": "#f44747",
    "dim": "#7d8590",
    "hdr": "#c586c0",
}
STATUS_GLYPH = {
    "running": ("●", "#3fb950"),
    "working": ("◐", "#d29922"),
    "done": ("✓", "#7d8590"),
    "stalled": ("✗", "#f85149"),
    "superseded": ("⊘", "#5a5a5a"),
}


def fmt_ts(iso):
    if not iso:
        return "--:--:--"
    try:
        return (
            dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
            .astimezone()
            .strftime("%H:%M:%S")
        )
    except Exception:
        return iso[-9:-1] if len(iso) > 9 else iso


def human_age(secs):
    s = int(secs)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"


def _read_lines(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read().splitlines()
    except OSError:
        return []


def _last_entry_shape(path):
    """(last_block_type, role) of the last content-bearing event — cheap tail read."""
    try:
        sz = os.path.getsize(path)
        with open(path, "rb") as fh:
            fh.seek(max(0, sz - 40_000))
            data = fh.read().decode("utf-8", "ignore")
    except OSError:
        return (None, None)
    for line in reversed(data.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        msg = o.get("message") if isinstance(o.get("message"), dict) else {}
        c = msg.get("content")
        blocks = (
            c
            if isinstance(c, list)
            else ([{"type": "text"}] if isinstance(c, str) else [])
        )
        for b in reversed(blocks):
            if isinstance(b, dict) and b.get("type"):
                return (b.get("type"), msg.get("role"))
    return (None, None)


def agent_status(path):
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return ("stalled", 1e9)
    age = time.time() - mtime
    if age < FRESH:
        return ("running", age)
    ce = _STATUS_CACHE.get(path)
    if ce and ce[0] == mtime:
        return (
            ce[1],
            age,
        )  # finished agent: mtime frozen -> reuse cached status, skip tail read
    last_type, role = _last_entry_shape(path)
    if last_type == "text" and role == "assistant":
        st = "done"
    elif age > STALL:
        st = "stalled"
    else:
        st = "working"  # recently active or awaiting a long tool call
    if st in ("done", "stalled"):
        _STATUS_CACHE[path] = (mtime, st)  # cache terminal states (mtime won't change)
    return (st, age)


_META_CACHE = {}  # path -> meta (written once at agent creation; static)
_STATUS_CACHE = {}  # path -> (mtime, terminal_status) — avoids re-reading finished agents


def load_meta(path):
    cached = _META_CACHE.get(path)
    if cached is not None:
        return cached
    mp = os.path.splitext(path)[0] + ".meta.json"
    try:
        with open(mp, encoding="utf-8", errors="ignore") as fh:
            meta = json.load(fh)
    except Exception:
        meta = {}
    if meta:
        _META_CACHE[path] = meta  # only cache once we actually have it
    return meta


def scan_session(subdir):
    """All agent transcripts in a session dir with status + retry-grouping."""
    rows = []
    for jsonl in glob.glob(os.path.join(subdir, "**", "agent-*.jsonl"), recursive=True):
        meta = load_meta(jsonl)
        parts = os.path.relpath(jsonl, subdir).replace("\\", "/").split("/")
        wf = parts[parts.index("workflows") + 1] if "workflows" in parts[:-1] else ""
        status, age = agent_status(jsonl)
        rows.append(
            {
                "jsonl": jsonl,
                "name": meta.get("name") or os.path.basename(jsonl)[6:14],
                "type": meta.get("agentType", "?"),
                "desc": meta.get("description", ""),
                "wf": wf,
                "mtime": os.path.getmtime(jsonl) if os.path.exists(jsonl) else 0,
                "age": age,
                "status": status,
            }
        )
    # group retries by (wf, name): newest is live, older are superseded
    groups = {}
    for r in rows:
        groups.setdefault((r["wf"], r["name"]), []).append(r)
    for g in groups.values():
        g.sort(key=lambda r: r["mtime"], reverse=True)
        for r in g[1:]:
            r["status"] = "superseded"
    rows.sort(key=lambda r: (r["status"] == "superseded", -r["mtime"]))
    return rows


def render(entry):
    """One transcript entry -> (ui_segments [(tag, text)], plaintext_for_log)."""
    msg = entry.get("message") if isinstance(entry.get("message"), dict) else {}
    iso = entry.get("timestamp")
    ts = fmt_ts(iso)
    content = msg.get("content")
    blocks = (
        content
        if isinstance(content, list)
        else ([{"type": "text", "text": content}] if isinstance(content, str) else [])
    )
    segs, logs = [], []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t == "thinking":
            txt = (b.get("thinking") or "").strip()
            if txt:
                segs += [("ts", f"{ts} "), ("think", f"\U0001f4ad {txt}\n")]
                logs.append(f"{iso}\t[think] {txt}")
        elif t == "text":
            txt = (b.get("text") or "").strip()
            if txt:
                segs += [("ts", f"{ts} "), ("text", f"● {txt}\n")]
                logs.append(f"{iso}\t[text] {txt}")
        elif t == "tool_use":
            name = b.get("name", "?")
            inp = b.get("input", {})
            try:
                args = json.dumps(inp, ensure_ascii=False, indent=2) if inp else ""
            except Exception:
                args = str(inp)
            segs += [("ts", f"{ts} "), ("tool", f"\U0001f527 {name}\n")]
            logs.append(f"{iso}\t[tool] {name}")
            if args:
                indented = "\n".join("        " + ln for ln in args.splitlines())
                segs.append(("toolarg", indented + "\n"))
                logs.append(indented)
        elif t == "tool_result":
            rc = b.get("content")
            s = (
                rc
                if isinstance(rc, str)
                else json.dumps(rc, ensure_ascii=False, indent=2)
            )
            full = s
            if len(s) > RESULT_CAP:
                s = (
                    s[:RESULT_CAP]
                    + f"\n        … [+{len(full) - RESULT_CAP} chars; full text in the .log]"
                )
            tag = "err" if b.get("is_error") else "result"
            glyph = "✗" if b.get("is_error") else "↳"
            segs += [("ts", f"{ts} "), (tag, f"{glyph} {s}\n")]
            logs.append(f"{iso}\t[result] {full}")
    return segs, "\n".join(logs)


# ── the app ──────────────────────────────────────────────────────────────────
class MonitorUI:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.sessions = []  # list of subagent dirs
        self.cur_session = None
        self.rows = []  # current scan rows
        self.sel_path = None  # selected agent jsonl
        self.tail_pos = 0
        self.tail_file = None
        self.log_fh = None
        self.autoscroll = tk.BooleanVar(value=True)
        self.show_all = tk.BooleanVar(value=False)  # default: active + last-30min only
        self._tail_gen = 0
        self._build()
        self._refresh_sessions(initial=True)
        self.root.after(200, self._drain)
        threading.Thread(target=self._list_poller, daemon=True).start()
        threading.Thread(target=self._tail_poller, daemon=True).start()

    # ---- UI construction ----
    def _build(self):
        self.root.title("Claude Code — Agent Monitor")
        self.root.geometry("1180x720")
        self.root.minsize(820, 460)
        top = ttk.Frame(self.root, padding=(8, 6))
        top.pack(fill="x")
        ttk.Label(top, text="Session:").pack(side="left")
        self.sess_cb = ttk.Combobox(top, state="readonly", width=46)
        self.sess_cb.pack(side="left", padx=(4, 12))
        self.sess_cb.bind("<<ComboboxSelected>>", self._on_session)
        self.hdr = ttk.Label(top, text="", foreground="#444")
        self.hdr.pack(side="left")
        ttk.Checkbutton(top, text="Auto-scroll", variable=self.autoscroll).pack(
            side="right"
        )
        ttk.Checkbutton(
            top, text="All history", variable=self.show_all, command=self._scan_now
        ).pack(side="right", padx=6)
        ttk.Button(top, text="Open .log", command=self._open_log).pack(
            side="right", padx=6
        )

        pane = ttk.PanedWindow(self.root, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        left = ttk.Frame(pane)
        cols = ("status", "name", "info", "age")
        self.tree = ttk.Treeview(
            left, columns=cols, show="headings", selectmode="browse"
        )
        for c, w, txt in (
            ("status", 70, "state"),
            ("name", 190, "agent"),
            ("info", 150, "type / [wf]"),
            ("age", 70, "age"),
        ):
            self.tree.heading(c, text=txt)
            self.tree.column(c, width=w, anchor="w", stretch=(c == "name"))
        ysb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        for st, (_, color) in STATUS_GLYPH.items():
            self.tree.tag_configure(st, foreground=color)
        pane.add(left, weight=1)

        right = ttk.Frame(pane)
        self.title_lbl = ttk.Label(
            right, text="Select an agent", font=("Segoe UI", 10, "bold")
        )
        self.title_lbl.pack(fill="x", anchor="w")
        self.desc_lbl = ttk.Label(
            right, text="", foreground="#666", wraplength=820, justify="left"
        )
        self.desc_lbl.pack(fill="x", anchor="w", pady=(0, 4))
        txtfrm = ttk.Frame(right)
        txtfrm.pack(fill="both", expand=True)
        self.txt = tk.Text(
            txtfrm,
            wrap="word",
            bg=BG,
            fg=FG,
            insertbackground=FG,
            font=("Cascadia Mono", 10),
            padx=8,
            pady=6,
            state="disabled",
            borderwidth=0,
        )
        tsb = ttk.Scrollbar(txtfrm, orient="vertical", command=self.txt.yview)
        self.txt.configure(yscrollcommand=tsb.set)
        self.txt.pack(side="left", fill="both", expand=True)
        tsb.pack(side="right", fill="y")
        for tag, color in COL.items():
            self.txt.tag_configure(tag, foreground=color)
        self.txt.tag_configure("tool", font=("Cascadia Mono", 10, "bold"))
        pane.add(right, weight=3)

        self.status_bar = ttk.Label(
            self.root, text="", anchor="w", relief="sunken", padding=(6, 2)
        )
        self.status_bar.pack(fill="x", side="bottom")

    # ---- session handling ----
    def _refresh_sessions(self, initial=False):
        dirs = sorted(find_subagent_dirs(), key=newest_mtime, reverse=True)
        self.sessions = dirs
        labels = []
        for d in dirs:
            sess = os.path.basename(os.path.dirname(d))
            proj = os.path.basename(os.path.dirname(os.path.dirname(d)))
            labels.append(f"{sess[:8]}  ·  {proj[-34:]}")
        self.sess_cb["values"] = labels
        if dirs and (initial or self.cur_session not in dirs):
            self.cur_session = dirs[0]
            self.sess_cb.current(0)

    def _on_session(self, _evt=None):
        i = self.sess_cb.current()
        if 0 <= i < len(self.sessions):
            self.cur_session = self.sessions[i]
            self._select_agent(None)
            self._scan_now()

    # ---- background pollers (push to queue; UI thread applies) ----
    def _list_poller(self):
        while True:
            try:
                if self.cur_session:
                    rows = scan_session(self.cur_session)
                    self.q.put(("list", rows))
            except Exception:
                pass
            time.sleep(LIST_POLL_MS / 1000.0)

    def _scan_now(self):
        try:
            if self.cur_session:
                self.q.put(("list", scan_session(self.cur_session)))
        except Exception:
            pass

    def _tail_poller(self):
        while True:
            try:
                path, gen = self.sel_path, self._tail_gen
                if path and os.path.exists(path):
                    sz = os.path.getsize(path)
                    if self.tail_file != path:
                        # newly selected: full backfill from line 0
                        self.tail_file = path
                        self.tail_pos = 0
                    if sz < self.tail_pos:  # rotated/truncated
                        self.tail_pos = 0
                        self.q.put(("clear", gen))
                    if sz > self.tail_pos:
                        with open(path, "rb") as fh:
                            fh.seek(self.tail_pos)
                            data = fh.read().decode("utf-8", "ignore")
                        self.tail_pos = sz
                        entries = []
                        for ln in data.splitlines():
                            ln = ln.strip()
                            if ln.startswith("{"):
                                try:
                                    entries.append(json.loads(ln))
                                except Exception:
                                    pass
                        if entries:
                            self.q.put(("log", gen, entries))
            except Exception:
                pass
            time.sleep(TAIL_POLL_MS / 1000.0)

    # ---- selection ----
    def _on_select(self, _evt=None):
        sel = self.tree.selection()
        if not sel:
            return
        self._select_agent(
            sel[0]
        )  # the Treeview iid IS the jsonl path (set in _apply_list)

    def _select_agent(self, jsonl):
        self._tail_gen += 1
        self.sel_path = jsonl
        self.tail_file = None
        self.tail_pos = 0
        if self.log_fh:
            try:
                self.log_fh.close()
            except Exception:
                pass
            self.log_fh = None
        # clear pane
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.configure(state="disabled")
        if not jsonl:
            self.title_lbl.config(text="Select an agent")
            self.desc_lbl.config(text="")
            return
        meta = load_meta(jsonl)
        name = meta.get("name") or os.path.basename(jsonl)
        self.title_lbl.config(text=name)
        self.desc_lbl.config(
            text=meta.get("description", "")
            or f"{meta.get('agentType', 'agent')} · {os.path.basename(jsonl)}"
        )
        # open persistent .log (fresh, full from creation)
        try:
            sess = (
                os.path.basename(os.path.dirname(self.cur_session))
                if self.cur_session
                else "session"
            )
            d = os.path.join(LOGDIR, sess[:8])
            os.makedirs(d, exist_ok=True)
            safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)[
                :60
            ]
            self.log_fh = open(os.path.join(d, f"{safe}.log"), "w", encoding="utf-8")
            self.log_fh.write(
                f"# {name}\n# {jsonl}\n# opened {dt.datetime.now().isoformat(timespec='seconds')}\n\n"
            )
        except Exception:
            self.log_fh = None

    # ---- queue drain (UI thread) ----
    def _drain(self):
        try:
            while True:
                item = self.q.get_nowait()
                kind = item[0]
                if kind == "list":
                    self._apply_list(item[1])
                elif kind == "clear" and item[1] == self._tail_gen:
                    self.txt.configure(state="normal")
                    self.txt.delete("1.0", "end")
                    self.txt.configure(state="disabled")
                elif kind == "log" and item[1] == self._tail_gen:
                    self._append_entries(item[2])
        except queue.Empty:
            pass
        self.root.after(150, self._drain)

    def _apply_list(self, rows):
        if (
            not self.show_all.get()
        ):  # focused view: running/working + anything active in last 30 min
            rows = [
                r
                for r in rows
                if r["status"] in ("running", "working") or r["age"] < 1800
            ]
        self.rows = rows
        sel = self.tree.selection()
        sel_iid = sel[0] if sel else None
        existing = set(self.tree.get_children())
        seen = set()
        for r in rows:
            iid = r["jsonl"]
            seen.add(iid)
            glyph, _ = STATUS_GLYPH.get(r["status"], ("?", "#888"))
            info = f"[{r['wf'][:12]}]" if r["wf"] else r["type"][:18]
            vals = (f"{glyph} {r['status']}", r["name"][:28], info, human_age(r["age"]))
            if iid in existing:
                self.tree.item(iid, values=vals, tags=(r["status"],))
            else:
                self.tree.insert("", "end", iid=iid, values=vals, tags=(r["status"],))
        for iid in existing - seen:
            self.tree.delete(iid)
        run = sum(1 for r in rows if r["status"] in ("running", "working"))
        done = sum(1 for r in rows if r["status"] == "done")
        wf = sum(1 for r in rows if r["wf"])
        self.status_bar.config(
            text=f"{len(rows)} agents · {run} active · {done} done · {wf} in workflows · "
            f"updated {dt.datetime.now().strftime('%H:%M:%S')}"
        )
        if sel_iid and sel_iid in seen:
            pass  # keep selection

    def _append_entries(self, entries):
        self.txt.configure(state="normal")
        at_bottom = self.autoscroll.get()
        for e in entries:
            segs, logtext = render(e)
            for tag, text in segs:
                self.txt.insert("end", text, (tag,))
            if self.log_fh and logtext:
                try:
                    self.log_fh.write(logtext + "\n")
                except Exception:
                    pass
        if self.log_fh:
            try:
                self.log_fh.flush()
            except Exception:
                pass
        self.txt.configure(state="disabled")
        if at_bottom:
            self.txt.see("end")

    def _open_log(self):
        if not self.sel_path or not self.log_fh:
            return
        try:
            os.startfile(
                self.log_fh.name
            )  # Windows-only; fine here (this tool targets Windows)
        except Exception as e:
            messagebox.showinfo(
                "Open .log", f"Log file:\n{getattr(self.log_fh, 'name', '?')}\n\n{e}"
            )


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except Exception:
        pass
    MonitorUI(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
