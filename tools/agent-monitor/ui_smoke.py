#!/usr/bin/env python3
"""Headless smoke test for agent_monitor_ui: import, data layer, and a brief
GUI construction (window auto-closes after ~0.8s). Prints OK lines or raises."""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_monitor_ui as u  # noqa: E402

dirs = u.find_subagent_dirs()
print(f"sessions: {len(dirs)}")
assert dirs, "no subagent sessions found"
d = max(dirs, key=u.newest_mtime)
rows = u.scan_session(d)
print(f"agents in active session: {len(rows)}")
for r in rows[:10]:
    print("  %-11s %-26s %-14s %s" % (r["status"], r["name"][:26], (r["wf"][:12] or r["type"][:12]), u.human_age(r["age"])))

fs = sorted(glob.glob(os.path.join(d, "**", "agent-*.jsonl"), recursive=True), key=os.path.getmtime)
entries = [json.loads(ln) for ln in open(fs[-1], encoding="utf-8", errors="ignore") if ln.strip().startswith("{")]
segs, log = u.render(entries[-1])
print(f"render last event: {len(segs)} ui-segments, {len(log)} log chars")

# brief GUI construction (opens + auto-destroys) — proves widgets build + threads start
import tkinter as tk  # noqa: E402
root = tk.Tk()
u.MonitorUI(root)
root.after(800, root.destroy)
root.mainloop()
print("GUI smoke OK")
