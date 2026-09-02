#!/usr/bin/env python3
"""AUD-0060 probe 2: usage trace over recent sessions (invoked vs exposed)."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONTROL_JSONL = HERE / "fixtures" / "usage_control.jsonl"
FIXTURE_ALPHA = "aud0060_fixture_alpha"
FIXTURE_GAMMA = "aud0060_fixture_gamma"

TRANSCRIPT_ROOTS = (
    Path("/root/.cursor/projects/opt-p2-ast-integrate/agent-transcripts"),
    Path.home() / ".cursor" / "projects",
    Path.home() / ".claude" / "projects",
)

FIRST_PARTY = {
    "Read",
    "Grep",
    "Glob",
    "Shell",
    "Write",
    "StrReplace",
    "Delete",
    "EditNotebook",
    "WebSearch",
    "WebFetch",
    "TodoWrite",
    "Task",
    "AskQuestion",
    "ReadLints",
    "AwaitShell",
    "GetDynamicTools",
    "CallDynamicTool",
    "FetchMcpResource",
    "SwitchMode",
    "PowerShell",
    "Bash",
}


def walk_tool_uses(obj: Any, acc: list[dict]) -> None:
    if isinstance(obj, dict):
        if obj.get("type") == "tool_use" and isinstance(obj.get("name"), str):
            inp = obj.get("input") if isinstance(obj.get("input"), dict) else {}
            name = obj["name"]
            row = {
                "name": name,
                "namespace": inp.get("namespace") if name == "CallDynamicTool" else None,
                "mcp_tool": inp.get("toolName") if name == "CallDynamicTool" else None,
            }
            acc.append(row)
        for val in obj.values():
            walk_tool_uses(val, acc)
    elif isinstance(obj, list):
        for val in obj:
            walk_tool_uses(val, acc)


def scan_jsonl(path: Path, limit_bytes: int = 8_000_000) -> list[dict]:
    uses: list[dict] = []
    try:
        size = path.stat().st_size
        if size > limit_bytes:
            return uses
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return uses
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        walk_tool_uses(obj, uses)
    return uses


def classify(uses: list[dict]) -> dict:
    first_party: Counter[str] = Counter()
    mcp: Counter[str] = Counter()
    for row in uses:
        if row.get("name") == "CallDynamicTool" and row.get("mcp_tool"):
            key = f"{row.get('namespace') or '?'}/{row['mcp_tool']}"
            mcp[key] += 1
        elif row.get("name"):
            first_party[row["name"]] += 1
    return {
        "invocation_count": len(uses),
        "first_party": dict(first_party.most_common()),
        "mcp": dict(mcp.most_common()),
        "mcp_invocation_count": int(sum(mcp.values())),
        "first_party_invocation_count": int(sum(first_party.values())),
    }


def scan_roots(roots: tuple[Path, ...] | list[Path], file_cap: int = 80) -> dict:
    files_scanned = 0
    uses: list[dict] = []
    present_roots = []
    for root in roots:
        if not root.exists():
            continue
        present_roots.append(str(root))
        try:
            paths = sorted(root.rglob("*.jsonl"))
        except OSError:
            continue
        for path in paths:
            if files_scanned >= file_cap:
                break
            files_scanned += 1
            uses.extend(scan_jsonl(path))
    tallied = classify(uses)
    return {
        "roots": present_roots,
        "files_scanned": files_scanned,
        **tallied,
    }


def control_use_vs_mention() -> dict:
    uses = scan_jsonl(CONTROL_JSONL)
    tallied = classify(uses)
    alpha_used = any(
        u.get("mcp_tool") == FIXTURE_ALPHA or u.get("name") == FIXTURE_ALPHA for u in uses
    )
    gamma_as_tool_use = any(
        u.get("mcp_tool") == FIXTURE_GAMMA or u.get("name") == FIXTURE_GAMMA for u in uses
    )
    mention_in_prose = "aud0060_fixture_gamma is unused" in CONTROL_JSONL.read_text(
        encoding="utf-8"
    )
    fires = mention_in_prose and not gamma_as_tool_use
    silent = alpha_used
    return {
        "id": "AUD0060-C2",
        "kind": "use-vs-mention",
        "fired_on_bad_state": fires,
        "silent_on_good_state": silent,
        "pass": bool(fires and silent),
        "alpha_used": alpha_used,
        "gamma_counted_as_invocation": gamma_as_tool_use,
        "mention_present": mention_in_prose,
        "tallied": tallied,
        "raw_use_count": len(uses),
    }


def compare_exposed_vs_used(exposed_names: list[str], mcp_used: dict) -> dict:
    used_keys = set(mcp_used)
    used_short = {k.split("/", 1)[-1] for k in used_keys}
    unused = []
    used = []
    for name in exposed_names:
        if name in used_keys or name in used_short:
            used.append(name)
        else:
            unused.append(name)
    return {
        "exposed_count": len(exposed_names),
        "used_count": len(used),
        "unused_count": len(unused),
        "used": used,
        "unused": unused,
        "finding": (
            "large-exposed-surface-with-zero-mcp-invocations"
            if exposed_names and not used
            else (
                "mixed-used-and-unused"
                if unused and used
                else ("all-exposed-tools-invoked" if used else "no-exposed-mcp-tools")
            )
        ),
    }


def measure(exposed_tool_names: list[str] | None = None) -> dict:
    ctl = control_use_vs_mention()
    live = scan_roots(TRANSCRIPT_ROOTS)
    names = list(exposed_tool_names or [])
    comparison = compare_exposed_vs_used(names, live.get("mcp") or {})
    return {
        "control": {
            "id": ctl["id"],
            "fired_on_bad_state": ctl["fired_on_bad_state"],
            "silent_on_good_state": ctl["silent_on_good_state"],
            "pass": ctl["pass"],
            "alpha_used": ctl["alpha_used"],
            "gamma_counted_as_invocation": ctl["gamma_counted_as_invocation"],
            "mention_present": ctl["mention_present"],
            "tallied": ctl["tallied"],
        },
        "live": live,
        "exposed_vs_used": comparison,
        "program_need": {
            "declared_mcp_need_count": 0,
            "invoked_mcp_count": live.get("mcp_invocation_count", 0),
            "note": (
                "Catalog-declared tools for AUD-0060 are first-party. MCP tools this "
                "program actually needs: none declared. Invoked MCP tools are a usage "
                "trace, not a declared requirement."
            ),
        },
    }


def main() -> int:
    from fixture_server import EXPECTED_NAMES

    doc = measure(list(EXPECTED_NAMES) + ["CreateGoal", "GenerateImage", "UpdateGoal"])
    print(json.dumps(doc, sort_keys=True))
    if not doc["control"]["pass"]:
        print("FAILED:AUD-0060 usage use-vs-mention control")
        return 1
    print(
        "SUCCESS:AUD-0060-usage "
        f"files={doc['live']['files_scanned']} "
        f"mcp_invocations={doc['live']['mcp_invocation_count']} "
        f"finding={doc['exposed_vs_used']['finding']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
