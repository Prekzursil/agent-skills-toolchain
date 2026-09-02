#!/usr/bin/env python3
"""Fixture vendor CLI modelling typed-schema x active-MCP.

This is not a live Codex/Anthropic API. It reproduces the documented
interaction: a typed --output-schema cannot be applied while an MCP inventory
from user config is loaded. --ignore-user-config drops that inventory and the
typed-output path functions.

Schema-invalid emission is explicit (--emit-invalid) so the adapter gate can
prove it classifies schema-invalid and does not retry.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MCP_MARK = "CLASSIFICATION:typed-schema-mcp-interaction"


def load_servers(path: Path | None, ignore_user_config: bool) -> list[str]:
    if ignore_user_config or path is None:
        return []
    if not path.is_file():
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    servers = doc.get("mcpServers") if isinstance(doc, dict) else None
    if isinstance(servers, dict):
        return sorted(str(k) for k in servers)
    return []


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--prompt-file", required=True)
    p.add_argument("--output-last-message", required=True)
    p.add_argument("--output-schema", required=True)
    p.add_argument("--unit-id", required=True)
    p.add_argument("--mcp-inventory")
    p.add_argument("--ignore-user-config", action="store_true")
    p.add_argument("--emit-invalid", action="store_true")
    args = p.parse_args()

    prompt_path = Path(args.prompt_file)
    if not prompt_path.is_file() or not prompt_path.read_text(encoding="utf-8").strip():
        print("vendor_cli: prompt file missing or empty", file=sys.stderr)
        return 2
    schema_path = Path(args.output_schema)
    if not schema_path.is_file():
        print("vendor_cli: typed output schema missing", file=sys.stderr)
        return 2

    inventory = Path(args.mcp_inventory) if args.mcp_inventory else None
    servers = load_servers(inventory, args.ignore_user_config)
    if servers:
        print(
            f"{MCP_MARK} typed schema cannot be applied while MCP servers "
            f"are loaded from user config servers={servers}",
            file=sys.stderr,
        )
        print(
            "TYPED-SCHEMA-MCP: retry once with --ignore-user-config "
            "(not a schema-invalid payload)",
            file=sys.stderr,
        )
        return 3

    out = Path(args.output_last_message)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.emit_invalid:
        payload = {"unexpected": True, "note": "deliberately schema-invalid"}
    else:
        payload = {
            "answer": "typed-output-path-ok",
            "unit_id": args.unit_id,
        }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    flag = "ignore-user-config" if args.ignore_user_config else "mcp-inactive-or-empty"
    print(f"vendor_cli: typed-output-path-ok mode={flag} servers={servers}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
