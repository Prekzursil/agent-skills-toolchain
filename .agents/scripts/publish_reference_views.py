#!/usr/bin/env python3
"""Publish secret-free provider views from the canonical MCP registry."""
from __future__ import annotations

import argparse
import json
import pathlib

import mcp_control_plane as control
import merge_generated_claude_mcp as claude
import merge_generated_codex_mcp as codex


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_AGENTS_CONFIG = ROOT / "agents.json"
DEFAULT_OUTPUT_DIR = ROOT / "generated"


def render_views(config: dict) -> tuple[str, str]:
    control.validate_registry(config)
    claude_payload = {
        "mcpServers": claude.build_managed_servers_from_agents(config),
    }
    claude_text = json.dumps(claude_payload, indent=2, ensure_ascii=False) + "\n"
    codex_text = "\n".join(
        block.text.rstrip("\n")
        for block in codex.build_managed_blocks_from_agents(config)
    ) + "\n"
    return claude_text, codex_text


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish reference-only Claude and Codex MCP views"
    )
    parser.add_argument("--agents-config", default=str(DEFAULT_AGENTS_CONFIG))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    config_path = pathlib.Path(args.agents_config)
    output_dir = pathlib.Path(args.output_dir)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    claude_text, codex_text = render_views(config)

    control.atomic_write_text(output_dir / "claude.mcp.json", claude_text)
    control.atomic_write_text(output_dir / "codex.config.toml", codex_text)
    print("SUCCESS:mcp-reference-views providers=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
