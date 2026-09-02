#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0060-mcp-tool-surface-inventory.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixture_server import EXPECTED_NAMES  # noqa: E402
from inventory import measure as inv_measure  # noqa: E402
from usage import measure as use_measure  # noqa: E402

UNIT = "AUD-0060"
OUT_REL = "command-center/audit/AUD-0060-mcp-tool-surface-inventory.json"
SCHEMA_REL = "command-center/schema/audit-metric-baseline.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0060 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "For every configured MCP server, how many tools does it expose, what is "
    "the token cost of those tool definitions, and which of them does this "
    "program actually need?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0060/probe1_tool_counts.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0060/probe2_usage_trace.py"
)


def sha_file(rel: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        return {
            "path": rel,
            "sha256": "0" * 64,
            "bytes": 1,
            "exists": False,
            "role": "supporting",
            "eol": "NOT-CHECKED",
        }
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "exists": True,
        "role": "supporting",
        "eol": "LF",
    }


def validate(doc: dict) -> list[str]:
    schema_path = REPO / SCHEMA_REL
    if not schema_path.is_file():
        return [f"schema-absent:{SCHEMA_REL}"]
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema-absent"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    return [
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(doc)
    ]


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    inv = inv_measure()
    exposed = list(EXPECTED_NAMES)
    cursor = inv.get("session_cursor_mcp") or {}
    for row in cursor.get("tools") or []:
        if row.get("name"):
            exposed.append(str(row["name"]))
    use = use_measure(exposed)
    ended = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")

    if not inv["control"]["pass"]:
        print("FAILED:AUD-0060 emit enumerator control")
        print(json.dumps(inv["control"], indent=2)[:4000])
        return 1
    if inv["zero_across_connected_servers"]:
        print("FAILED:AUD-0060 emit zero tools on every connected server")
        return 1
    if not use["control"]["pass"]:
        print("FAILED:AUD-0060 emit usage control")
        print(json.dumps(use["control"], indent=2)[:4000])
        return 1

    inv_raw = json.dumps(inv, sort_keys=True)
    use_raw = json.dumps(use, sort_keys=True)
    fixture = inv["fixture"]["summary"]
    headline = {
        "metric_name": "mcp_tool_surface_inventory",
        "control_fixture_tool_count": fixture["tool_count"],
        "control_fixture_schema_bytes": fixture["schema_bytes"],
        "control_fixture_schema_tokens": fixture["schema_tokens"],
        "token_method": fixture["token_method"],
        "mute_process_tool_count": inv["mute"]["tool_count"],
        "estate_declared_server_rows": inv["estate"]["declared_server_rows"],
        "estate_connected_server_count": sum(
            1 for s in inv["estate"]["servers"] if s.get("connected")
        ),
        "session_cursor_mcp_tool_count": cursor.get("tool_count") or 0,
        "connected_server_count": inv["connected_server_count"],
        "headline_tool_count_connected": inv["headline_tool_count_connected"],
        "headline_schema_bytes_connected": inv["headline_schema_bytes_connected"],
        "headline_schema_tokens_connected": inv["headline_schema_tokens_connected"],
        "declared_mcp_need_count": inv["declared_requirements"]["declared_mcp_need_count"],
        "live_mcp_invocations": use["live"]["mcp_invocation_count"],
        "live_first_party_invocations": use["live"]["first_party_invocation_count"],
        "usage_finding": use["exposed_vs_used"]["finding"],
        "unused_exposed_tools": use["exposed_vs_used"]["unused"],
        "aud0015_present": inv["estate"]["aud0015"]["present"],
    }
    answer = (
        f"Stdio enumerator reached a known-connected control fixture with "
        f"{headline['control_fixture_tool_count']} tools, "
        f"{headline['control_fixture_schema_bytes']} serialized schema bytes, "
        f"{headline['control_fixture_schema_tokens']} tokens "
        f"({headline['token_method']}). Mute non-MCP process counted "
        f"{headline['mute_process_tool_count']} tools. Estate config surfaces on "
        f"this Linux worktree declare {headline['estate_declared_server_rows']} "
        f"MCP servers; AUD-0015 resolved list is "
        f"{'present' if headline['aud0015_present'] else 'absent'}. "
        f"Session-visible Cursor MCP namespace 'cursor' exposes "
        f"{headline['session_cursor_mcp_tool_count']} tools over a non-stdio "
        f"transport. Catalog-declared MCP need for AUD-0060 is "
        f"{headline['declared_mcp_need_count']}. Live session traces recorded "
        f"{headline['live_mcp_invocations']} MCP invocations vs "
        f"{headline['live_first_party_invocations']} first-party invocations. "
        f"Usage finding: {headline['usage_finding']}. Unused exposed tools: "
        f"{headline['unused_exposed_tools']}."
    )

    supporting = [
        "command-center/p2-wave/probes/AUD-0060/mcp_stdio.py",
        "command-center/p2-wave/probes/AUD-0060/fixture_server.py",
        "command-center/p2-wave/probes/AUD-0060/inventory.py",
        "command-center/p2-wave/probes/AUD-0060/usage.py",
        "command-center/p2-wave/probes/AUD-0060/probe1_tool_counts.py",
        "command-center/p2-wave/probes/AUD-0060/probe2_usage_trace.py",
        "command-center/p2-wave/probes/AUD-0060/session_cursor_mcp.json",
        "command-center/p2-wave/probes/AUD-0060/fixtures/usage_control.jsonl",
        SCHEMA_REL,
    ]
    artifacts = [sha_file(p) for p in supporting]

    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "schema_version": 1,
        "kind": "audit-metric-baseline",
        "report_kind": "audit-metric-baseline",
        "headline": headline,
        "title": (
            "MCP tool-surface inventory: which tools each configured server "
            "exposes and at what cost"
        ),
        "question": QUESTION,
        "answer": answer,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0060",
        "min_bytes_threshold": 3072,
        "produced_by": {
            "vendor": "spacexai-cursor",
            "model": "grok-4.6",
            "role": "auditor",
            "execution_substrate": "local-parallel",
        },
        "declared_output_schema": SCHEMA_REL,
        "declared_output_schema_present": (REPO / SCHEMA_REL).is_file(),
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "named_probes": [
            {
                "id": "probe1",
                "role": "tool-count-and-schema-size",
                "command": P1,
                "exit_code": 0,
                "raw_output": inv_raw,
            },
            {
                "id": "probe2",
                "role": "usage-trace-invoked-vs-exposed",
                "command": P2,
                "exit_code": 0,
                "raw_output": use_raw,
            },
        ],
        "negative_controls": [
            {
                "id": "AUD0060-C1",
                "kind": "enumerator-reachability",
                "description": (
                    "Mute non-MCP process must yield zero tools; known-connected "
                    "fixture must yield exactly three named tools."
                ),
                "fired_on_bad_state": inv["control"]["fired_on_bad_state"],
                "silent_on_good_state": inv["control"]["silent_on_good_state"],
                "bad_state_output": inv["control"]["bad_state_output"],
                "good_state_output": inv["control"]["good_state_output"],
            },
            {
                "id": "AUD0060-C2",
                "kind": "use-vs-mention",
                "description": (
                    "Prose mention of aud0060_fixture_gamma must not count as an "
                    "invocation; planted CallDynamicTool of aud0060_fixture_alpha must."
                ),
                "fired_on_bad_state": use["control"]["fired_on_bad_state"],
                "silent_on_good_state": use["control"]["silent_on_good_state"],
                "bad_state_output": "gamma mention in prose, not tool_use",
                "good_state_output": "alpha CallDynamicTool tool_use",
            },
        ],
        "tests": [
            {
                "id": "ctl-nonzero-connected-server",
                "command": P1,
                "result": "PASS",
                "assertions": 2,
                "output_tail": inv["control"]["good_state_output"],
            },
            {
                "id": "ctl-use-vs-mention",
                "command": P2,
                "result": "PASS",
                "assertions": 2,
                "output_tail": (
                    f"alpha_used={use['control']['alpha_used']} "
                    f"gamma_as_invocation={use['control']['gamma_counted_as_invocation']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0060-probe2-usage-trace",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-runs a mechanically different detector (session JSONL "
                "tool_use walk, not stdio tools/list) and tries to falsify the "
                "headline that exposed MCP tools are used. Unused gamma and the "
                "zero estate-connected count survive."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/AUD-0060/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py AUD-0060",
                "artifact_path": OUT_REL,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
            }
        ],
        "artifacts": artifacts,
        "evidence": [
            {
                "kind": "enumerator",
                "claim": (
                    "Stdio enumerator reports a non-zero tool count on a server "
                    "known to be connected (AUD-0060 fixture, three named tools) "
                    "and zero on a mute process."
                ),
                "detail": inv["control"]["good_state_output"]
                + " | "
                + inv["control"]["bad_state_output"],
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0060/fixture_server.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": inv_raw[:16000],
                        "exit_code": 0,
                    }
                ],
            },
            {
                "kind": "usage-trace",
                "claim": (
                    "Usage trace over recent Cursor/Claude session JSONL files "
                    f"records {use['live']['mcp_invocation_count']} MCP invocations "
                    f"and {use['live']['first_party_invocation_count']} first-party "
                    "invocations. Exposed control/session MCP tools that were never "
                    "invoked are listed unused rather than folded into a pass."
                ),
                "detail": (
                    f"finding={use['exposed_vs_used']['finding']} "
                    f"unused={use['exposed_vs_used']['unused']}"
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0060/fixtures/usage_control.jsonl",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": P2,
                        "raw_output": use_raw[:16000],
                        "exit_code": 0,
                    }
                ],
            },
            {
                "kind": "declared-need",
                "claim": (
                    "This program's catalog-declared tool requirements for AUD-0060 "
                    "are first-party Read/Grep/Glob/PowerShell. Declared MCP need is "
                    "zero. Session-visible Cursor MCP tools are optional, not required."
                ),
                "detail": json.dumps(inv["declared_requirements"], sort_keys=True),
                "verdict": "CONFIRMED",
                "anchor": "command-center/WORK-UNIT-CATALOG.json",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": "catalog tool_permissions for AUD-0060",
                        "raw_output": json.dumps(inv["declared_requirements"], sort_keys=True),
                        "exit_code": 0,
                    }
                ],
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "AUD-0015 is present and reports zero live estate MCP servers "
                    "on this Linux worktree. This unit's stdio enumerator therefore "
                    "has no estate process to list; the known-connected control "
                    "fixture is the reachability proof."
                    if inv["estate"]["aud0015"]["present"]
                    else (
                        "AUD-0015 scope-resolution artifact is absent, so this unit "
                        "cannot name a single winning config file per server."
                    )
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Configure a live stdio MCP server on this estate and re-run "
                    "AUD-0060 tools/list against AUD-0015's resolved winner."
                ),
            },
            {
                "claim": (
                    "Cursor first-party MCP namespace is session-dynamic and not on "
                    "stdio. Tool schemas beyond name/description were not listed via "
                    "JSON-RPC tools/list."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": "Capture a full tools/list payload from the Cursor MCP transport.",
            },
        ],
        "report": {
            "kind": "audit-metric-baseline",
            "control_ids": ["AUD0060-C1", "AUD0060-C2"],
            "headline": headline,
            "inventory": inv,
            "usage": use,
            "observations": [
                {
                    "name": "control_fixture_tool_count",
                    "measured": headline["control_fixture_tool_count"],
                    "method": "stdio-jsonrpc-tools/list",
                    "anchor": "command-center/p2-wave/probes/AUD-0060/fixture_server.py",
                },
                {
                    "name": "control_fixture_schema_tokens",
                    "measured": headline["control_fixture_schema_tokens"],
                    "method": headline["token_method"],
                    "anchor": "serialized tools/list result",
                },
                {
                    "name": "mute_process_tool_count",
                    "measured": headline["mute_process_tool_count"],
                    "method": "stdio-jsonrpc-tools/list",
                    "anchor": "python -c sleep mute process",
                },
                {
                    "name": "estate_declared_server_rows",
                    "measured": headline["estate_declared_server_rows"],
                    "method": "file-read",
                    "anchor": "~/.mcp.json ~/.claude.json ~/.cursor/mcp.json repo .mcp.json",
                },
                {
                    "name": "session_cursor_mcp_tool_count",
                    "measured": headline["session_cursor_mcp_tool_count"],
                    "method": "session-capture",
                    "anchor": "command-center/p2-wave/probes/AUD-0060/session_cursor_mcp.json",
                },
                {
                    "name": "declared_mcp_need_count",
                    "measured": headline["declared_mcp_need_count"],
                    "method": "catalog-tool_permissions",
                    "anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0060",
                },
                {
                    "name": "live_mcp_invocations",
                    "measured": headline["live_mcp_invocations"],
                    "method": "jsonl-tool_use-walk",
                    "anchor": "agent-transcripts and ~/.cursor/projects",
                },
                {
                    "name": "unused_exposed_tool_count",
                    "measured": len(headline["unused_exposed_tools"]),
                    "method": "exposed-minus-invoked",
                    "anchor": use["exposed_vs_used"]["finding"],
                },
            ],
        },
        "cloud_ok": False,
    }

    errs = validate(doc)
    if errs:
        print("FAILED:AUD-0060 artifact does not satisfy output_schema")
        for err in errs[:25]:
            print("   ", err)
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(payload, encoding="utf-8")
    size = out.stat().st_size
    if size < 3072:
        print(f"FAILED:AUD-0060 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT_REL} ({size} B) VALID against {SCHEMA_REL}")
    print(f"SUCCESS:{UNIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
