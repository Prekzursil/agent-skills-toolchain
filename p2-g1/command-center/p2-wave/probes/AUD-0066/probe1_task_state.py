#!/usr/bin/env python3
"""AUD-0066 probe 1 (source, process-table): the scheduled-task and service
state as reported by the OS, filtered to program-relevant tasks."""
from __future__ import annotations

import csv
import io
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = HERE / "probe1_task_state_out.json"

RELEVANT_TOKENS = ["agent", "claude", "codex", "mcp", "mail", "monitor", "supervisor",
                   "grok", "memory", "estate", "memguard", "reaper", "biomni",
                   "hexstrike", "cyberstrike", "opencode", "gemini", "reframe"]


def main() -> int:
    p = subprocess.run(["schtasks", "/query", "/fo", "csv", "/nh"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    tasks = []
    if p.returncode == 0:
        reader = csv.reader(io.StringIO(p.stdout or ""))
        for row in reader:
            if len(row) >= 3:
                tasks.append({"name": row[0].strip(), "status": row[2].strip()})
    else:
        tasks = [{"name": "<schtasks-failed>", "status": "rc=%s %s" % (p.returncode, (p.stderr or "")[:100])}]
    total = len(tasks)
    relevant = [t for t in tasks if any(tok in t["name"].lower() for tok in RELEVANT_TOKENS)]
    result = {
        "probe": "probe1-task-state",
        "schtasks_rc": p.returncode,
        "total_tasks": total,
        "relevant_tasks": relevant,
        "relevant_count": len(relevant),
        "running_relevant": [t for t in relevant if "ready" in t["status"].lower() or "running" in t["status"].lower()],
        "pass": bool(p.returncode == 0 and total > 50),
    }
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("rc=%d total=%d relevant=%d" % (p.returncode, total, len(relevant)))
    for t in relevant:
        print("  task: %s -> %s" % (t["name"][:70], t["status"]))
    print("SUCCESS:AUD-0066-probe1 scheduled task state" if result["pass"]
          else "FAILED:AUD-0066-probe1 schtasks")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
