#!/usr/bin/env python3
"""Probe 2: both-states control on typed-schema x active-MCP.

MCP-active without retry must HIT the interaction (not SUCCESS).
The same typed schema with --ignore-user-config must function.
A retry-enabled MCP-active dispatch must take exactly one ignore-user-config
retry and then succeed. If both arms succeed, the comparison is vacuous.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3] / "tools" / "command-center"))

import output_schema_gate as gate  # noqa: E402
from scenario import (  # noqa: E402
    argv_has_ignore,
    run_ignore_user_config,
    run_mcp_active,
)


def fail(reason: str) -> int:
    print(f"FAILED:IMP-0426-probe2 {reason}")
    return 1


def verbatim(result: dict) -> dict:
    attempts = []
    for att in result.get("attempts") or []:
        attempts.append(
            {
                "exit_code": att.get("exit_code"),
                "classification": att.get("classification"),
                "ignore_user_config": att.get("ignore_user_config"),
                "stdout": att.get("stdout"),
                "stderr": att.get("stderr"),
            }
        )
    return {
        "terminal_kind": result.get("terminal_kind"),
        "classification": (result.get("schema_gate") or {}).get("classification"),
        "retries_used": (result.get("schema_gate") or {}).get("retries_used"),
        "attempts": attempts,
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0426-p2-") as tmp:
        root = Path(tmp)
        mcp_no_retry = run_mcp_active(workdir=root / "mcp-no-retry", allow_mcp_retry=False)
        mcp_retry = run_mcp_active(workdir=root / "mcp-retry", allow_mcp_retry=True)
        ignored = run_ignore_user_config(workdir=root / "ignore")

    g_no = mcp_no_retry["schema_gate"]
    g_retry = mcp_retry["schema_gate"]
    g_ign = ignored["schema_gate"]
    vacuous = g_no["classification"] == gate.CLASS_OK and g_ign["classification"] == gate.CLASS_OK
    ok = (
        not vacuous
        and g_no["classification"] == gate.CLASS_MCP
        and mcp_no_retry["terminal_kind"] == "FAILED"
        and g_no["valid"] is False
        and g_no["retries_used"] == 0
        and g_no["consumer_invoked"] is False
        and len(mcp_no_retry["attempts"]) == 1
        and gate.MCP_MARK in str(mcp_no_retry["attempts"][0].get("stderr") or "")
        and g_ign["classification"] == gate.CLASS_OK
        and ignored["terminal_kind"] == "SUCCESS"
        and g_ign["valid"] is True
        and g_ign["retries_used"] == 0
        and g_ign["consumer_invoked"] is True
        and ignored["consumer_payloads"][0].get("answer") == "typed-output-path-ok"
        and ignored["attempts"][0].get("ignore_user_config") is True
        and g_retry["classification"] == gate.CLASS_OK
        and mcp_retry["terminal_kind"] == "SUCCESS"
        and g_retry["retries_used"] == 1
        and len(mcp_retry["attempts"]) == 2
        and mcp_retry["attempts"][0]["classification"] == gate.CLASS_MCP
        and mcp_retry["attempts"][1]["classification"] == gate.CLASS_OK
        and argv_has_ignore(mcp_retry["attempts"])
        and mcp_retry["attempts"][1].get("ignore_user_config") is True
        and g_retry["consumer_invoked"] is True
    )
    payload = {
        "probe": "probe2-mcp-both-states",
        "unit_id": "IMP-0426",
        "pass": ok,
        "vacuous": vacuous,
        "mcp_active_no_retry": verbatim(mcp_no_retry),
        "mcp_active_with_retry": verbatim(mcp_retry),
        "ignore_user_config": verbatim(ignored),
        "typed_path_functions_with_ignore_user_config": g_ign["classification"]
        == gate.CLASS_OK,
        "hits_typed_schema_mcp_interaction_when_mcp_active": g_no["classification"]
        == gate.CLASS_MCP,
    }
    print(json.dumps(payload, sort_keys=True))
    if vacuous:
        return fail("vacuous-control both arms SUCCESS; MCP interaction never fired")
    if not ok:
        return fail("mcp-active must hit interaction; --ignore-user-config must pass")
    print(
        "SUCCESS:IMP-0426-probe2 MCP-active hits typed-schema-mcp-interaction; "
        "--ignore-user-config typed path functions; one MCP retry only"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
