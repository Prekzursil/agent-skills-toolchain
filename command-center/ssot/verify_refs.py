"""Pass 5 - control the detectors that reported SILENCE, and resolve the
executable-candidate hits down to the FIELD (use-vs-mention).

Detector controls (both-states test):
  * scheduled-task scan reported 0 hits for every checkout. Prove it CAN see a known task
    string first, else the silence measures nothing.
  * settings.json / .claude.json must be proven READ, not silently skipped by the size cap.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

SSOT = Path("C:/Users/Prekzursil/source/ast-integrate/command-center/ssot")
res: dict = {}

print("=" * 78)
print("CONTROL 1 - scheduled-task scanner, both states")
raw = subprocess.run(
    [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-ScheduledTask | ForEach-Object { $t=$_; $_.Actions | ForEach-Object { "
        "[pscustomobject]@{Task=$t.TaskPath+$t.TaskName; State=$t.State; Execute=$_.Execute; "
        "Arguments=$_.Arguments; WorkDir=$_.WorkingDirectory} } } | ConvertTo-Json -Depth 4 -Compress",
    ],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
).stdout
tasks = json.loads(raw or "[]")
tasks = [tasks] if isinstance(tasks, dict) else tasks
blob = json.dumps(tasks)
# KNOWN-PRESENT probe: the supervisor task documented in CLAUDE.md
known = ["mcp_agent_mail", "MCPAgentMail", "Prekzursil"]
for k in known:
    print(f"  known-present probe {k!r:24} -> found={k.lower() in blob.lower()}")
# KNOWN-ABSENT probe
print(
    f"  known-absent probe   {'zzz-not-a-real-task':24} -> found={'zzz-not-a-real-task' in blob}"
)
print(f"  task-actions scanned: {len(tasks)}")
# any task whose command line mentions any repo checkout at all
repo_tasks = [
    t
    for t in tasks
    if re.search(
        r"agent-skills-toolchain|ast-integrate|ast-patch167|"
        r"toolchain-audit|tw-merge-work|codexsrc-work|"
        r"sast-depth|Playground|inc1-wt|salvage-probe",
        json.dumps(t),
        re.I,
    )
]
print(f"  tasks referencing ANY toolchain checkout: {len(repo_tasks)}")
for t in repo_tasks:
    print(f"    {t['Task']} state={t['State']} exec={t['Execute']}")
res["scheduled_tasks_scanned"] = len(tasks)
res["scheduled_tasks_referencing_checkouts"] = repo_tasks
res["control_task_scanner_sees_known_string"] = any(
    k.lower() in blob.lower() for k in known
)

print()
print("=" * 78)
print("CONTROL 2 - were the big config files actually READ?")
for f in [
    "C:/Users/Prekzursil/.claude/settings.json",
    "C:/Users/Prekzursil/.claude/settings.local.json",
    "C:/Users/Prekzursil/.claude.json",
    "C:/Users/Prekzursil/.mcp.json",
    "C:/Users/Prekzursil/.codex/config.toml",
]:
    p = Path(f)
    if not p.exists():
        print(f"  {f:52} MISSING")
        continue
    sz = p.stat().st_size
    print(f"  {f:52} {sz:>12,} bytes  under-3MB-cap={sz <= 3_000_000}")

print()
print("=" * 78)
print("FIELD-LEVEL resolution of config hits (keys only, never values)")


def walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, obj


PAT = re.compile(
    r"(ast-integrate|ast-patch167|ast-harness-reconcile|toolchain-audit|"
    r"tw-merge-work|codexsrc-work|sast-depth|inc1-wt|wt-salvage-probe|"
    r"agent-skills-toolchain-re|Documents[\\/]+Playground|"
    r"source[\\/]+agent-skills-toolchain)",
    re.I,
)

field_hits = []
for f in [
    "C:/Users/Prekzursil/.claude/settings.json",
    "C:/Users/Prekzursil/.claude/settings.local.json",
    "C:/Users/Prekzursil/.claude.json",
    "C:/Users/Prekzursil/.mcp.json",
]:
    p = Path(f)
    if not p.exists():
        continue
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError as e:
        print(f"  {f}: NOT VALID JSON ({e})")
        continue
    for keypath, val in walk(data):
        if isinstance(val, str) and PAT.search(val):
            m = PAT.search(val)
            # print the KEY PATH and the matched token only - never the raw value
            kp = keypath[:130]
            field_hits.append({"file": f, "key": kp, "token": m.group(0)})
            print(f"  {Path(f).name:22} key={kp:78} token={m.group(0)}")
res["config_field_hits"] = field_hits
print(f"  ({len(field_hits)} field-level hits)")

print()
print("=" * 78)
print("Non-JSON executable hits - show the matched line, redacted to the path token")
CODE = [
    ("C:/Users/Prekzursil/.codex/config.toml", None),
    ("C:/Users/Prekzursil/.agents/harness/modules.py", None),
    ("C:/Users/Prekzursil/.agents/skills/crcp-health/crcp_health_monitor.cmd", None),
    ("C:/Users/Prekzursil/.local/opt/mcp-http-host/run_host.ps1", None),
    ("C:/Users/Prekzursil/.claude/skills/claude-science-local/cs_monitor.py", None),
    ("C:/Users/Prekzursil/.agents/skills/claude-science-local/cs_monitor.py", None),
    ("C:/Users/Prekzursil/.claude/workflows/agentic-repair-reliability.js", None),
    (
        "C:/Users/Prekzursil/.claude/workflows/harness-self-improve-sweep-imporant.js",
        None,
    ),
    (
        "C:/Users/Prekzursil/.claude/workflows/reconcile-all-branches-prs-imporant.js",
        None,
    ),
]
code_hits = []
for f, _ in CODE:
    p = Path(f)
    if not p.exists():
        print(f"  {f} MISSING")
        continue
    with open(p, "r", encoding="utf-8", errors="ignore", newline="") as fh:
        for i, ln in enumerate(fh.read().splitlines(), 1):
            if PAT.search(ln):
                code_hits.append({"file": f, "line": i, "text": ln.strip()[:190]})
                print(f"  {Path(f).name:34}:{i:<6} {ln.strip()[:150]}")
res["code_hits"] = code_hits

print()
print("=" * 78)
print("CLAUDE SESSION DIRS - which checkouts have been used as a cwd, and how recently")
import datetime

proj = Path("C:/Users/Prekzursil/.claude/projects")
rows = []
if proj.is_dir():
    for d in proj.iterdir():
        if not d.is_dir():
            continue
        if not re.search(
            r"toolchain|ast-|Playground|sast-depth|inc1|salvage", d.name, re.I
        ):
            continue
        js = list(d.glob("*.jsonl"))
        newest = max((f.stat().st_mtime for f in js), default=0)
        rows.append((newest, d.name, len(js)))
for newest, name, n in sorted(rows, reverse=True):
    ts = (
        datetime.datetime.fromtimestamp(newest).isoformat(timespec="minutes")
        if newest
        else "-"
    )
    print(f"  {ts:20} sessions={n:<5} {name}")
res["session_dirs"] = [
    {"newest": r[0], "dir": r[1], "sessions": r[2]} for r in sorted(rows, reverse=True)
]

print()
print("=" * 78)
print("DISK footprint + last-write per checkout")
CHECKOUTS = json.loads((SSOT / "clone-measurements.json").read_text(encoding="utf-8"))[
    "checkouts"
]
sizes = []
for path in CHECKOUTS:
    p = Path(path)
    if not p.exists():
        continue
    total = 0
    newest = 0.0
    nfiles = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for fn in filenames:
            try:
                st = os.stat(os.path.join(dirpath, fn))
                total += st.st_size
                nfiles += 1
                newest = max(newest, st.st_mtime)
            except OSError:
                pass
    ts = (
        datetime.datetime.fromtimestamp(newest).isoformat(timespec="minutes")
        if newest
        else "-"
    )
    sizes.append(
        {"path": path, "bytes": total, "files": nfiles, "newest_mtime_iso": ts}
    )
    print(f"  {path:52} {total / 1e9:7.2f} GB  files={nfiles:>7}  newest={ts}")
res["disk"] = sizes
print(
    f"  TOTAL {sum(s['bytes'] for s in sizes) / 1e9:.2f} GB across {len(sizes)} checkouts"
)

with open(SSOT / "refs-verified.json", "w", encoding="utf-8", newline="\n") as fh:
    json.dump(res, fh, indent=2)
