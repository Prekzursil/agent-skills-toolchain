"""Pass 4 - inbound references: what POINTS AT each checkout?

use-vs-mention discipline: a markdown doc naming a path is a MENTION, not a dependency.
Only a field a program READS is an inbound reference. Classified by file type + field.

SECURITY: never prints a matched LINE (settings.json holds live credentials). Prints only
path:line and which checkout token matched.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

SSOT = Path("C:/Users/Prekzursil/source/ast-integrate/command-center/ssot")

# distinctive leaf tokens - matching the full path is too brittle (\\ vs /, case, ~)
TARGETS = {
    "codexsrc-work": "C:/Users/Prekzursil/.claude/codexsrc-work",
    "toolchain-audit": "C:/Users/Prekzursil/.claude/toolchain-audit",
    "tw-merge-work": "C:/Users/Prekzursil/.claude/tw-merge-work",
    "Documents/Playground": "C:/Users/Prekzursil/Documents/Playground",
    "source/agent-skills-toolchain": "C:/Users/Prekzursil/source/agent-skills-toolchain",
    "ast-patch167": "C:/Users/Prekzursil/source/ast-patch167",
    "ast-integrate": "C:/Users/Prekzursil/source/ast-integrate",
    "agent-skills-toolchain-re": "C:/Users/Prekzursil/work/agent-skills-toolchain-re",
    "sast-depth": "D:/sast-depth/agent-skills-toolchain",
    "ast-harness-reconcile": "C:/Users/Prekzursil/source/ast-harness-reconcile",
    "inc1-wt": "D:/inc1-wt/ast-increment1",
    "wt-salvage-probe": "D:/wt-salvage-probe",
}

# regex per target, tolerant of / \ \\ and Playground/Documents variants
PATTERNS = {
    k: re.compile(
        re.escape(k).replace("/", r"[\\/]+").replace(r"\-", "-"), re.IGNORECASE
    )
    for k in TARGETS
}

EXEC_EXT = {
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".ps1",
    ".py",
    ".sh",
    ".mjs",
    ".js",
    ".cmd",
    ".bat",
    ".ini",
    ".cfg",
    ".xml",
    ".env",
}
MENTION_EXT = {".md", ".txt", ".jsonl", ".log", ".rst", ".html", ".csv"}

SCAN_ROOTS = [
    "C:/Users/Prekzursil/.claude/hooks",
    "C:/Users/Prekzursil/.claude/skills",
    "C:/Users/Prekzursil/.claude/commands",
    "C:/Users/Prekzursil/.claude/workflows",
    "C:/Users/Prekzursil/.claude/agents",
    "C:/Users/Prekzursil/.claude/rules",
    "C:/Users/Prekzursil/.claude/plugins",
    "C:/Users/Prekzursil/.agents",
    "C:/Users/Prekzursil/.codex",
    "C:/Users/Prekzursil/.local/opt",
]
SCAN_FILES = [
    "C:/Users/Prekzursil/.claude/settings.json",
    "C:/Users/Prekzursil/.claude/settings.local.json",
    "C:/Users/Prekzursil/.claude.json",
    "C:/Users/Prekzursil/.mcp.json",
    "C:/Users/Prekzursil/CLAUDE.md",
    "C:/Users/Prekzursil/AGENTS.md",
    "C:/Users/Prekzursil/.gitconfig",
]
SKIP_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    ".ruff_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".mypy_cache",
}
MAX_BYTES = 3_000_000

hits: dict[str, list[dict]] = {k: [] for k in TARGETS}


def scan_file(fp: Path) -> None:
    ext = fp.suffix.lower()
    if ext not in EXEC_EXT and ext not in MENTION_EXT and ext != "":
        return
    try:
        if fp.stat().st_size > MAX_BYTES:
            return
        # newline="" so we never re-insert CRLF and never mis-count lines
        with open(fp, "r", encoding="utf-8", errors="ignore", newline="") as fh:
            text = fh.read()
    except OSError:
        return
    if not text:
        return
    lines = text.splitlines()
    for key, pat in PATTERNS.items():
        if not pat.search(text):
            continue
        for i, ln in enumerate(lines, 1):
            if pat.search(ln):
                kind = "EXECUTABLE-CANDIDATE" if ext in EXEC_EXT else "MENTION"
                hits[key].append(
                    {"file": str(fp).replace("\\", "/"), "line": i, "kind": kind}
                )
                if (
                    len(
                        [
                            h
                            for h in hits[key]
                            if h["file"] == str(fp).replace("\\", "/")
                        ]
                    )
                    >= 4
                ):
                    break


for root in SCAN_ROOTS:
    if not Path(root).exists():
        continue
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            scan_file(Path(dirpath) / fn)

for f in SCAN_FILES:
    if Path(f).exists():
        scan_file(Path(f))

# ---- scheduled tasks ----
sched_raw = subprocess.run(
    [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-ScheduledTask | ForEach-Object { $t=$_; $_.Actions | ForEach-Object { "
        "[pscustomobject]@{Task=$t.TaskPath+$t.TaskName; State=$t.State; "
        "Execute=$_.Execute; Arguments=$_.Arguments; WorkDir=$_.WorkingDirectory} } } "
        "| ConvertTo-Json -Depth 4 -Compress",
    ],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
sched_hits = []
try:
    tasks = json.loads(sched_raw.stdout or "[]")
    if isinstance(tasks, dict):
        tasks = [tasks]
except json.JSONDecodeError:
    tasks = []
for t in tasks:
    blob = " ".join(str(t.get(f) or "") for f in ("Execute", "Arguments", "WorkDir"))
    for key, pat in PATTERNS.items():
        if pat.search(blob):
            sched_hits.append(
                {
                    "target": key,
                    "task": t.get("Task"),
                    "state": t.get("State"),
                    "execute": t.get("Execute"),
                    "workdir": t.get("WorkDir"),
                    "args_excerpt": (t.get("Arguments") or "")[:300],
                }
            )

# ---- PATH + env ----
env_hits = []
for name, val in os.environ.items():
    for key, pat in PATTERNS.items():
        if val and pat.search(val):
            env_hits.append(
                {
                    "target": key,
                    "var": name,
                    "value_excerpt": val[:250] if name.upper() != "PATH" else "<PATH>",
                }
            )
path_hits = []
for scope in ("User", "Machine"):
    p = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"[Environment]::GetEnvironmentVariable('PATH','{scope}')",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    for entry in (p or "").split(";"):
        for key, pat in PATTERNS.items():
            if entry.strip() and pat.search(entry):
                path_hits.append(
                    {"target": key, "scope": scope, "entry": entry.strip()}
                )

# ---- claude session dirs (activity evidence, NOT a hard reference) ----
proj = Path("C:/Users/Prekzursil/.claude/projects")
session_dirs = []
if proj.is_dir():
    for d in proj.iterdir():
        if not d.is_dir():
            continue
        for key, pat in PATTERNS.items():
            if (
                pat.search(d.name.replace("-", "/"))
                or key.split("/")[-1].lower() in d.name.lower()
            ):
                n = len(list(d.glob("*.jsonl")))
                newest = max((f.stat().st_mtime for f in d.glob("*.jsonl")), default=0)
                session_dirs.append(
                    {"target": key, "dir": d.name, "jsonl": n, "newest_mtime": newest}
                )
                break

out = {
    "file_hits": hits,
    "scheduled_tasks": sched_hits,
    "env": env_hits,
    "path_entries": path_hits,
    "claude_session_dirs": session_dirs,
}
with open(SSOT / "inbound-refs.json", "w", encoding="utf-8", newline="\n") as fh:
    json.dump(out, fh, indent=2)

print("=== SCHEDULED TASKS referencing a checkout ===")
for h in sched_hits:
    print(f"  [{h['target']}] {h['task']}  state={h['state']}  wd={h['workdir']}")
    print(f"      exec={h['execute']}")
    print(f"      args={h['args_excerpt'][:200]}")
print(f"  ({len(sched_hits)} hits; {len(tasks)} task-actions scanned)")

print("\n=== PATH entries ===")
for h in path_hits:
    print(f"  [{h['target']}] {h['scope']}: {h['entry']}")
print(f"  ({len(path_hits)} hits)")

print("\n=== ENV vars ===")
for h in env_hits:
    print(f"  [{h['target']}] {h['var']} = {h['value_excerpt']}")
print(f"  ({len(env_hits)} hits)")

print("\n=== FILE hits by target (EXECUTABLE-CANDIDATE first) ===")
for key in TARGETS:
    ex = [h for h in hits[key] if h["kind"] == "EXECUTABLE-CANDIDATE"]
    mn = [h for h in hits[key] if h["kind"] == "MENTION"]
    print(f"\n  {key}:  exec-candidates={len(ex)}  mentions={len(mn)}")
    seen = set()
    for h in ex:
        if h["file"] in seen:
            continue
        seen.add(h["file"])
        print(f"      EXEC  {h['file']}:{h['line']}")
    if len(seen) == 0:
        print("      (no executable-candidate hits)")

print("\n=== CLAUDE SESSION DIRS (activity, not a hard reference) ===")
for s in sorted(session_dirs, key=lambda x: -x["newest_mtime"]):
    import datetime

    ts = (
        datetime.datetime.fromtimestamp(s["newest_mtime"]).isoformat(timespec="minutes")
        if s["newest_mtime"]
        else "-"
    )
    print(f"  [{s['target']:28}] {s['dir'][:56]:56} jsonl={s['jsonl']:4} newest={ts}")
