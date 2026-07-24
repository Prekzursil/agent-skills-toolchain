#!/usr/bin/env python3
"""Program E — Steps 3-4 driver: coverage fan-out for one repo.

Loads the gaps produced by run_runnability.py, fans out one unit per gap on the node (up to 48
concurrent), applies the 5-clause AND-gate to each, and prints per-unit verdicts. Units push their
own agent/ branch (needs the WRITE github_token).

[OPERATOR — do BEFORE running] GitHub MCP: mcp__github__list_pull_requests(state=open) — abort if a
coverage PR is already live for this repo (collision re-check, run_E.py docstring Step 3).
[OPERATOR — do AFTER a green run] GitHub MCP: mcp__github__create_pull_request from the green agent/
branches (local `gh` push 401s on the read-only PAT).

Usage:
    python e2e/run_fanout.py env-inspector                    # reads e2e/_E_env-inspector_gaps.json
    python e2e/run_fanout.py env-inspector path/to/gaps.json  # explicit gaps file
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from harness.lanes import run_E


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: run_fanout.py <repo> [gaps.json]", file=sys.stderr)
        return 2
    repo = argv[0]
    gaps_path = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent / f"_E_{repo}_gaps.json"
    if not gaps_path.exists():
        print(f"FAILED: gaps file not found: {gaps_path} (run run_runnability.py first)", file=sys.stderr)
        return 2
    gaps = json.loads(gaps_path.read_text(encoding="utf-8")).get("gaps", [])
    if not gaps:
        print(f"SUCCESS: no gaps for {repo} -> nothing to fan out")
        return 0
    verdicts = run_E.run_coverage_fanout(repo, gaps)
    done = sum(1 for v, _ in verdicts.values() if v == "DONE")
    for uid, (verdict, path) in sorted(verdicts.items()):
        print(f"  {verdict:8s} {uid}  {path if verdict == 'DONE' else ''}")
    print(f"{'SUCCESS' if done == len(verdicts) else 'PARTIAL'}: {done}/{len(verdicts)} units DONE for {repo}")
    return 0 if done == len(verdicts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
