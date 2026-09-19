#!/usr/bin/env python3
"""Validate the shared MCP registry without exposing credential values."""
from __future__ import annotations

import argparse
import json
import pathlib

import mcp_control_plane as control


DEFAULT_ROOT = pathlib.Path(r"C:\Users\Prekzursil\.agents")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agents-config",
        default=str(DEFAULT_ROOT / "agents.json"),
    )
    parser.add_argument(
        "--rotation-manifest",
        default=str(DEFAULT_ROOT / "scripts" / "credential_rotation_manifest.json"),
    )
    args = parser.parse_args()

    config_path = pathlib.Path(args.agents_config)
    manifest_path = pathlib.Path(args.rotation_manifest)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    control.validate_registry(config)
    claude_count = len(
        control.expected_target_names(
            config,
            "claude",
            plugin_provided=control.CLAUDE_PLUGIN_PROVIDED_SERVERS,
        )
    )
    codex_count = len(control.expected_target_names(config, "codex"))
    server_count = len(config["mcp"]["servers"])

    # Owner 2026-08-28: never rotate. A missing manifest is the policy,
    # not a broken control plane — do not require the deleted file.
    if not manifest_path.is_file():
        print(
            "SUCCESS:mcp-control-plane-validate "
            f"servers={server_count} "
            f"claude_targets={claude_count} codex_targets={codex_count} "
            "rotation_providers=0 rotation_policy=never"
        )
        return 0

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    control.validate_rotation_manifest(manifest)
    print(
        "SUCCESS:mcp-control-plane-validate "
        f"servers={server_count} "
        f"claude_targets={claude_count} codex_targets={codex_count} "
        f"rotation_providers={len(manifest['providers'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
