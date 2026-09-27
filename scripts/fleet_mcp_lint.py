#!/usr/bin/env python3
"""fleet_mcp_lint.py — post-wave MCP behavior audit (report-only, exit 0).

Scans Claude Code workflow transcript dirs (agent-*.jsonl) and reports ACTUAL
MCP tool CALLS per agent, discriminating catalog mentions (the tool list every
transcript embeds) from real tool_use records via the '"name":"mcp__..."'
JSON shape. Grounded in the wf_c8e4c79c-1c8 incident (2026-09-22): 2/20 agents,
12 nested claude_code calls, prompt-only guards.

Usage: python fleet_mcp_lint.py <transcript_dir> [watch_glob]
  watch_glob: optional regex applied to tool names (default: flagged set below)
Known-positive control: the incident workflow must report a2429541*=5, aca1b6af*=7.
"""
import re
import sys
from pathlib import Path

# Tools that warrant attention when called from subagent contexts.
DEFAULT_WATCH = re.compile(
    r"claude-code-mcp|nested-subagent|claude_code", re.I
)
CALL_SHAPE = re.compile(r'"name"\s*:\s*"(mcp__[A-Za-z0-9_\-]+?__[A-Za-z0-9_\-]+?)"')


def lint_agent(path: Path, watch: re.Pattern) -> dict:
    calls: dict[str, int] = {}
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                for name in CALL_SHAPE.findall(line):
                    calls[name] = calls.get(name, 0) + 1
    except OSError:
        return {"agent": path.stem, "error": "unreadable"}
    flagged = {k: v for k, v in calls.items() if watch.search(k)}
    return {"agent": path.stem, "total_mcp_calls": sum(calls.values()),
            "by_tool": calls, "flagged": flagged}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    root = Path(argv[1])
    watch = re.compile(argv[2], re.I) if len(argv) > 2 else DEFAULT_WATCH
    files = sorted(root.glob("agent-*.jsonl"))
    if not files:
        print(f"FLEET-LINT: no agent transcripts in {root} (nothing to audit)")
        return 0  # report-only; absence of agents is not a finding
    flagged_agents = 0
    for f in files:
        r = lint_agent(f, watch)
        if r.get("flagged"):
            flagged_agents += 1
            print(f"FLAG {r['agent']}: {r['flagged']} (all: {r['total_mcp_calls']} mcp calls)")
    print(f"FLEET-LINT: {len(files)} agents scanned, {flagged_agents} flagged, watch={watch.pattern!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
