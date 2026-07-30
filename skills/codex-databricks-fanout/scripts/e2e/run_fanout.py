#!/usr/bin/env python3
"""Program E — Steps 3-4 driver: coverage fan-out for one repo.

Loads the gaps produced by run_runnability.py, fans out one unit per gap on the node
(up to 48 concurrent), applies the 5-clause AND-gate to each, and prints per-unit
verdicts plus the local branch (`agent/E-<repo>-<file>`) each green unit left behind.
Units clone READ-ONLY, commit their agent/ branch LOCALLY and report
`branch_ready:<sha>` — they do NOT push, and `run_coverage_fanout` neither accepts nor
injects a token (R1). Provision NO write token to run this; the curated out-of-band
push is a deferred engine step (engine.tokens).

Drives a LIVE Databricks workspace: every invocation is real, billable spend.

[OPERATOR — do BEFORE running] GitHub MCP:
mcp__github__list_pull_requests(state=open) — abort if a coverage PR is already live
for this repo (collision re-check, run_E.py docstring Step 3).
[OPERATOR — do AFTER a green run] GitHub MCP: mcp__github__create_pull_request from
the green agent/ branches (local `gh` push 401s on the read-only PAT).

Usage:
    python e2e/run_fanout.py env-inspector                    # auto-locates the gaps
    python e2e/run_fanout.py env-inspector path/to/gaps.json  # explicit gaps file
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # root (has harness/)
from harness.lanes import run_E

# `branch_ready` is the current coverage-lane artifact field. `branch_pushed` is the
# pre-rename name (CHANGELOG: "Artifact schema renamed"); artifacts harvested before
# that rename still carry it, so report either and say which one was found.
BRANCH_FIELDS = ("branch_ready", "branch_pushed")


def gaps_candidates(repo: str) -> list[str]:
    """Gaps-file basenames run_runnability.py has written, newest naming first."""
    return [f"_E_{repo}_gaps.json", f"_{repo}_gaps.json", "_runnability_gaps.json"]


def load_gaps(payload) -> list:
    """Accept both on-disk shapes: {"repo",…,"gaps":[…]} or a bare list of gaps."""
    if isinstance(payload, dict):
        return list(payload.get("gaps", []))
    return list(payload)


def resolve_gaps_path(repo: str, here: Path) -> Path:
    """First existing candidate next to this script; else the preferred name."""
    names = gaps_candidates(repo)
    for name in names:
        if (here / name).exists():
            return here / name
    return here / names[0]


def branch_of(path) -> str:
    """The local branch a green unit left behind, read from its artifact."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    for field in BRANCH_FIELDS:
        m = re.search(rf"^\s*{field}:\s*(.+)$", text, re.M)
        if m is None:
            continue
        branch = m.group(1).strip()
        if field != BRANCH_FIELDS[0]:
            branch = f"{branch}  ({field} — pre-rename artifact schema)"
        return branch
    return "?"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: run_fanout.py <repo> [gaps.json]", file=sys.stderr)
        return 2
    repo = argv[0]
    here = Path(__file__).resolve().parent
    gaps_path = Path(argv[1]) if len(argv) > 1 else resolve_gaps_path(repo, here)
    if not gaps_path.exists():
        print(
            f"FAILED: gaps file not found: {gaps_path} (run run_runnability.py first)",
            file=sys.stderr,
        )
        return 2
    gaps = load_gaps(json.loads(gaps_path.read_text(encoding="utf-8")))
    if not gaps:
        print(f"SUCCESS: no gaps for {repo} -> nothing to fan out")
        return 0
    print(f"FANOUT {repo}: {len(gaps)} gap(s) from {gaps_path.name}")

    verdicts = run_E.run_coverage_fanout(repo, gaps)
    done = sum(1 for v, _ in verdicts.values() if v == "DONE")
    for uid, (verdict, path) in sorted(verdicts.items()):
        print(f"  {verdict:8s} {uid}  {path if verdict == 'DONE' else ''}")
        if verdict == "DONE" and path and Path(path).exists():
            print(f"    branch[{uid}]: {branch_of(path)}")
    print(
        f"{'SUCCESS' if done == len(verdicts) else 'PARTIAL'}: "
        f"{done}/{len(verdicts)} units DONE for {repo}"
    )
    return 0 if done == len(verdicts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
