#!/usr/bin/env python3
"""SessionStart hook: surface beads 'ready' work for projects that use beads.

Fail-open by contract (AGENTS.md s6): ANY error exits 0 and emits nothing, so a
broken bd/Dolt never blocks session start. Project-scoped: silent unless the cwd
has a `.beads/` dir, so non-beads repos see no noise. Additive context only.
"""

import os
import shutil
import subprocess
import sys

MAX_LINES = 25

try:
    # Only act in a beads-enabled project (bd init created `.beads/`).
    if not os.path.isdir(".beads"):
        sys.exit(0)

    bd = shutil.which("bd")
    if not bd:
        sys.exit(0)

    # `bd ready` lists unblocked, open issues. May cold-start the Dolt server.
    proc = subprocess.run(
        [bd, "ready"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=18,
    )
    text = (proc.stdout or "").strip()
    low = text.lower()
    # bd's empty states: "No open issues" / "No issues found" / "no ready work".
    if not text or "no issues" in low or "no open issue" in low or "no ready" in low:
        sys.exit(0)

    lines = text.splitlines()
    if len(lines) > MAX_LINES:
        extra = len(lines) - MAX_LINES
        lines = lines[:MAX_LINES] + [f"... (+{extra} more — run `bd ready`)"]

    print("## Beads — ready work (unblocked open issues in this repo)")
    print("\n".join(lines))
    print('\n_Manage with `bd ready` / `bd show <id>` / `bd q "..."`._')
except Exception:
    # Fail-open: never let beads break session start.
    pass

sys.exit(0)
