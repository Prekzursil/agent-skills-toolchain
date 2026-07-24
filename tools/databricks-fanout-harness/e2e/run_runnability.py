#!/usr/bin/env python3
"""Program E — Step 2 driver: runnability + push preflight for one repo.

Submits the runnability unit on the node (clone -> install -> run suite -> coverage -> push-probe),
gates it, and on DONE persists the uncovered-file gaps to e2e/_E_<repo>_gaps.json for run_fanout.py.

Requires the WRITE github_token in scope codex-harness-prekzursil (for the push half). Run from the
repo root so `from harness...` imports resolve (conftest.py adds the root to sys.path).

Usage:
    python e2e/run_runnability.py env-inspector https://github.com/Prekzursil/env-inspector
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from harness.lanes import run_E


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        print("usage: run_runnability.py <repo> <clone_url>", file=sys.stderr)
        return 2
    repo, clone_url = argv[0], argv[1]
    ok, gaps, text = run_E.runnability(repo, clone_url)
    out = Path(__file__).resolve().parent / f"_E_{repo}_gaps.json"
    out.write_text(json.dumps({"repo": repo, "ok": ok, "gaps": gaps}, indent=2), encoding="utf-8")
    if not ok:
        print(f"FAILED: runnability preflight for {repo} did not reach DONE")
        return 1
    print(f"SUCCESS: runnability for {repo} -> {len(gaps)} uncovered-file gap(s) -> {out}")
    for g in gaps:
        print(f"  gap: {g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
