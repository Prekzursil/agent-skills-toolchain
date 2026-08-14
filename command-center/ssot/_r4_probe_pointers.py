"""Read-only: what do the two `.git` FILES actually contain, and do their targets exist?

Both states in one run: the SEVERED cache copy (target must be absent) and a known LIVE
linked worktree (target must be present). If both read the same, a severance resolver
built on this signal would be inert.
"""

from __future__ import annotations

import pathlib

CASES = {
    "severed-cache-copy": "C:/Users/Prekzursil/.codex/plugins/cache/agent-skills-toolchain/plugin-install-64I3il/agent-skills-toolchain/0.2.0",
    "live-linked-worktree(ast-integrate)": "C:/Users/Prekzursil/source/ast-integrate",
    "live-linked-worktree(wt-salvage-probe)": "D:/wt-salvage-probe",
    "main-checkout(canonical)": "C:/Users/Prekzursil/source/agent-skills-toolchain",
    "fabricated": "C:/Users/Prekzursil/source/this-path-does-not-exist-92f1a",
}

for label, path in CASES.items():
    dg = pathlib.Path(path) / ".git"
    kind = "FILE" if dg.is_file() else "DIR" if dg.is_dir() else "MISSING"
    body = ""
    target = ""
    exists = ""
    if dg.is_file():
        body = dg.read_text(encoding="utf-8", errors="replace").strip()
        if body.lower().startswith("gitdir:"):
            target = body.split(":", 1)[1].strip()
            t = pathlib.Path(target)
            if not t.is_absolute():
                t = (pathlib.Path(path) / target).resolve()
            exists = str(t.exists())
    print(f"{label:40s} dotgit={kind:8s} target_exists={exists or '-'}")
    if body:
        print(f"{'':40s} body={body[:120]}")
