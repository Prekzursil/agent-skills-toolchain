#!/usr/bin/env python3
"""Join every measured signal into ONE ranked KEEP / DISABLE / INVESTIGATE table.

Four signals, joined and NEVER collapsed into a single boolean.  Collapsing them is the
measured error the grounding lane quantified: reading ``claude mcp list`` as a mount
signal over-counts the live fleet 2.3x (53 "Connected" vs 23 actually mounted).

  config_state     S1  mcpctl over the 5 on-disk JSON scopes  -- "what the config says"
  host_reachable   S2  ``claude mcp list``                    -- "can a fresh process connect"
  session_mounted  S3  the mcp__* namespaces in this session  -- "can the model see it"
  call_verified    S4  a real initialize+tools/list handshake -- "does it actually work"

DISPOSITION IS AN ALGORITHM, NOT AN OPINION.  ``decide()`` is a pure function of the
joined row plus the exact set arithmetic in overlap-report.json.  ``REMOVE`` is not a
representable outcome -- ``assert_reversible()`` fails the run closed if one appears --
because every recommendation here must be undoable by re-enabling one JSON key.

Run::

    python rank_disposition.py -o disposition.json --md ../..//docs/mcp-audit/table.md
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from probe_capability import MOUNTED, load_specs  # noqa: E402

KEEP, DISABLE, INVESTIGATE = "KEEP", "DISABLE", "INVESTIGATE"

# Servers deliberately NOT given an S4 real call, with the reason.  Recording the reason
# is the difference between a measured gap and a silent one.
S4_DECLINED = {
    "brightdata": "metered third-party API -- a real call bills the owner's account",
    "claude-code-mcp": "a real tool call spawns a whole nested Claude session",
    "paper-search": "every tool is a live network search; handshake covers capability",
    "scholarly-access": "same -- live network search per call",
    "deepwiki": "live network call against a third-party AI service",
    "context7": "live network docs fetch, rate-limited",
    "repomix": "cheapest tool still walks a tree",
}

# Real in-session tool calls executed by the auditing session (S4), with the tool used.
# These are the HTTP-transport servers a stdio handshake CANNOT reach at all.
S4_EXECUTED = {
    "agent-mail": ("health_check", "status=ok"),
    "basic-memory": ("list_memory_projects", "2 projects, default=main"),
    "figma": ("whoami", "handle + Full seat returned"),
    "huggingface": ("hf_whoami", "status=anonymous (server answered)"),
    "github": ("get_me", "authenticated login returned"),
    "codex": ("codex (grounding lane)", "returned PONG with a threadId"),
    "qlty": ("qlty (grounding lane)", "PASS"),
}


def parse_host_list(path: pathlib.Path) -> dict[str, str]:
    """``claude mcp list`` -> name -> Connected / FAILED."""
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8", errors="replace")
    pat = re.compile(r"^([A-Za-z0-9_.\- ]+?):\s+(.*?)\s+-\s+(.*)$")
    out: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith(("Checking", "⚠")):
            continue
        m = pat.match(line)
        if m:
            out[m.group(1)] = "Connected" if "Connected" in m.group(3) else "FAILED"
    return out


def best_capability(paths: list[pathlib.Path]) -> dict[str, dict[str, Any]]:
    """Merge capability runs, preferring a verified row and then the larger surface.

    Two runs of the same server can disagree: ``angr`` reported PASS at 23 s, then
    TIMEOUT under a 45 s budget, then PASS again at 48 s.  A fixed timeout is itself a
    detector with a false-negative rate, so a later FAIL must not overwrite an earlier
    PASS -- the PASS is positive evidence the capability exists.
    """
    best: dict[str, dict[str, Any]] = {}
    for path in paths:
        if not path.exists():
            continue
        blob = json.loads(path.read_text(encoding="utf-8"))
        for row in blob.get("rows", []):
            name = row.get("name")
            prev = best.get(name)
            if prev is None:
                best[name] = row
                continue
            rank = (bool(row.get("call_verified")), row.get("tool_count") or 0)
            prev_rank = (bool(prev.get("call_verified")), prev.get("tool_count") or 0)
            if rank > prev_rank:
                best[name] = row
    return best


def decide(row: dict[str, Any], eligible: dict[str, str]) -> tuple[str, str]:
    """Pure disposition function -> (disposition, evidence sentence)."""
    name = row["name"]
    if name in eligible:
        container = eligible[name]
        return (
            DISABLE,
            f"exact set arithmetic: all {row['tool_count']} tool names are a strict "
            f"subset of {container}'s surface, 0 unique -- nothing becomes unreachable",
        )
    if row["call_verified"]:
        return (
            KEEP,
            f"real initialize+tools/list returned {row['tool_count']} tools in "
            f"{row['elapsed_ms']}ms",
        )
    if row["s4_executed"]:
        tool, result = row["s4_executed"]
        return KEEP, f"real in-session call {tool!r} -> {result}"
    if row["probe_method"] == "not-spawnable" and not row["s4_executed"]:
        return (
            INVESTIGATE,
            "HTTP transport: no stdio command to spawn, and no real call was made "
            f"({S4_DECLINED.get(name, 'not attempted this round')})",
        )
    return (
        INVESTIGATE,
        f"handshake did not complete: {row.get('last_error') or 'unknown'}",
    )


def assert_reversible(rows: list[dict[str, Any]]) -> None:
    bad = [
        r["name"] for r in rows if r["disposition"] not in {KEEP, DISABLE, INVESTIGATE}
    ]
    if bad:
        raise SystemExit(f"FAILED:rank-disposition non-reversible disposition on {bad}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=str(HERE))
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--md", default="")
    args = ap.parse_args(argv)
    base = pathlib.Path(args.base)

    mcpctl_path = base / "mcpctl-matrix.json"
    if not mcpctl_path.exists():
        print("FAILED:rank-disposition mcpctl-matrix.json missing")
        return 1
    mcpctl = json.loads(mcpctl_path.read_text(encoding="utf-8-sig"))
    cfg = {r["name"]: r for r in mcpctl["rows"]}

    host = parse_host_list(base / "claude-mcp-list.txt")
    caps = best_capability(
        [base / "capability-matrix.json", base / "capability-slowrows.json"]
    )
    overlap_path = base / "overlap-report.json"
    eligible: dict[str, str] = {}
    if overlap_path.exists():
        for pair in json.loads(overlap_path.read_text(encoding="utf-8"))["pairs"]:
            target = pair.get("retirement_eligible")
            if target:
                eligible[target] = pair["b"] if target == pair["a"] else pair["a"]

    specs = load_specs()
    if not caps:
        print("FAILED:rank-disposition zero capability rows (fail closed)")
        return 1

    rows: list[dict[str, Any]] = []
    for name in MOUNTED:
        cap = caps.get(name, {})
        conf = cfg.get(name, {})
        spec = specs.get(name, {})
        env_fields = conf.get("env_fields") or []
        row: dict[str, Any] = {
            "name": name,
            # --- the four never-collapsed signals
            "config_state": conf.get("state", "-absent-"),
            "host_reachable": host.get(name, "-absent-"),
            "session_mounted": name in MOUNTED,
            "call_verified": bool(cap.get("call_verified")),
            # --- inventory (DoD: scope + source file)
            "definition_scope": spec.get("definition_scope"),
            "source_file": spec.get("source_file"),
            "config_basis": conf.get("basis"),
            "transport": cap.get("transport") or conf.get("transport"),
            # --- capability + cost
            "probe_method": cap.get("probe_method"),
            "tool_count": cap.get("tool_count"),
            "name_bytes": cap.get("name_bytes"),
            "schema_bytes": cap.get("schema_bytes"),
            "elapsed_ms": cap.get("elapsed_ms"),
            "commit_bytes": cap.get("commit_bytes"),
            "last_error": cap.get("last_error"),
            # --- security (names only, never values)
            "env_var_names": [f.get("name") for f in env_fields],
            "env_kinds": sorted({f.get("kind") for f in env_fields if f.get("kind")}),
            "credential_bearing": bool(env_fields),
            "s4_executed": S4_EXECUTED.get(name),
        }
        row["disposition"], row["evidence"] = decide(row, eligible)
        rows.append(row)

    assert_reversible(rows)
    order = {DISABLE: 0, INVESTIGATE: 1, KEEP: 2}
    rows.sort(
        key=lambda r: (order[r["disposition"]], -(r["tool_count"] or 0), r["name"])
    )

    counts = {d: sum(1 for r in rows if r["disposition"] == d) for d in order}
    print("== disposition ==")
    for r in rows:
        print(
            f"  {r['disposition']:12} {r['name']:22} tools={str(r['tool_count']):>4} "
            f"cfg={r['config_state']:16} host={r['host_reachable']:10} "
            f"call={'Y' if r['call_verified'] or r['s4_executed'] else 'n'}"
        )
    print(f"\n{counts}")

    payload = {
        "report": "mcp-disposition",
        "generated_utc_date": "2026-08-12",
        "reversibility_invariant": (
            "REMOVE is not a representable outcome; every DISABLE is undone by "
            "re-enabling one JSON key. Route disables through mcpapply's "
            "DISABLE_PREFERENCE (project-scoped): a disable written to root "
            "disabledMcpServers hides the tools but does NOT prevent the spawn, so it "
            "saves zero RAM (mcpapply/plan.py SPAWN_PREVENTING)."
        ),
        "signals": {
            "config_state": "mcpctl over 5 JSON scopes",
            "host_reachable": "claude mcp list (NOT a mount signal)",
            "session_mounted": "mcp__* namespaces in the auditing session",
            "call_verified": "real initialize+tools/list, or a real in-session tool call",
        },
        "counts": counts,
        "s4_declined": S4_DECLINED,
        "rows": rows,
    }
    if args.out:
        pathlib.Path(args.out).write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"wrote {args.out}")
    if args.md:
        pathlib.Path(args.md).write_text(
            render_md(rows, counts), encoding="utf-8", newline="\n"
        )
        print(f"wrote {args.md}")
    print(f"SUCCESS:rank-disposition rows={len(rows)} {counts}")
    return 0


def render_md(rows: list[dict[str, Any]], counts: dict[str, int]) -> str:
    head = (
        "| disposition | server | S1 config | S2 host | S3 mounted | S4 real call | "
        "tools | name B | schema B | evidence |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
    )
    body = []
    for r in rows:
        s4 = "PASS" if r["call_verified"] else ("PASS*" if r["s4_executed"] else "--")
        body.append(
            f"| **{r['disposition']}** | `{r['name']}` | {r['config_state']} | "
            f"{r['host_reachable']} | {'yes' if r['session_mounted'] else 'no'} | {s4} | "
            f"{r['tool_count'] if r['tool_count'] is not None else '--'} | "
            f"{r['name_bytes'] if r['name_bytes'] is not None else '--'} | "
            f"{r['schema_bytes'] if r['schema_bytes'] is not None else '--'} | "
            f"{r['evidence']} |"
        )
    tail = (
        f"\n\n`S4 PASS*` = verified by a real in-session tool call rather than a stdio "
        f"handshake (HTTP transport cannot be spawned).  Counts: {counts}.\n"
    )
    return head + "\n".join(body) + tail


if __name__ == "__main__":
    raise SystemExit(main())
