#!/usr/bin/env python3
"""Validate the shared MCP registry without exposing credential values.

``--check-paths`` adds the L0 static rung (T0-2): every ENABLED stdio server's
``--directory`` value and script argument that lives under the toolchain checkout
must exist on disk. It is report-only unless ``--check-paths-strict`` is given.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
from collections.abc import Mapping
from typing import Any

import mcp_control_plane as control


DEFAULT_ROOT = pathlib.Path(r"C:\Users\Prekzursil\.agents")
# The Windows prefix the registry uses for repo-held code. ``--root`` maps it, so
# the check can run in cloud against the checkout or a fixture tree; the default
# root is the prefix itself (identity mapping on the box).
DEFAULT_TOOLCHAIN_ROOT = pathlib.Path(
    r"C:\Users\Prekzursil\source\agent-skills-toolchain"
)
TOOLCHAIN_PREFIX = "c:/users/prekzursil/source/agent-skills-toolchain"
SCRIPT_SUFFIXES = (".py", ".js", ".mjs", ".ps1")
DIRECTORY_FLAG = "--directory"
PATHS_MISSING_EXIT = 3


@dataclasses.dataclass(frozen=True)
class PathReport:
    """Outcome of the L0 path check over the enabled stdio servers."""

    checked: int
    unmapped: int
    missing: tuple[tuple[str, str], ...]

    @property
    def missing_servers(self) -> list[str]:
        return sorted({name for name, _path in self.missing})


def map_toolchain_path(raw: str, root: pathlib.Path) -> pathlib.Path | None:
    """Map a registry path under the toolchain prefix to ``root``; else ``None``.

    Accepts the backslash and forward-slash spellings, case-insensitively, and
    refuses sibling directories that merely share the prefix as a substring.
    """
    normalized = raw.replace("\\", "/")
    lowered = normalized.lower()
    if lowered.rstrip("/") == TOOLCHAIN_PREFIX:
        return root
    if not lowered.startswith(TOOLCHAIN_PREFIX + "/"):
        return None
    remainder = normalized[len(TOOLCHAIN_PREFIX) + 1 :]
    return root.joinpath(*[part for part in remainder.split("/") if part])


def candidate_paths(server: Mapping[str, Any]) -> list[str]:
    """Registry strings the L0 rung inspects for one stdio server.

    The command counts only when it is spelled as a path (contains a separator),
    so bare launchers such as ``npx`` never inflate the unmapped count. Every arg
    following ``--directory`` counts, and so does every arg ending in a script
    suffix (``.py`` / ``.js`` / ``.mjs`` / ``.ps1``, case-insensitive).
    """
    found: list[str] = []
    command = server.get("command")
    if isinstance(command, str) and ("\\" in command or "/" in command):
        found.append(command)
    args = [str(arg) for arg in server.get("args") or []]
    for index, arg in enumerate(args):
        if index > 0 and args[index - 1] == DIRECTORY_FLAG:
            found.append(arg)
        elif arg.lower().endswith(SCRIPT_SUFFIXES):
            found.append(arg)
    return found


def check_registry_paths(config: Mapping[str, Any], root: pathlib.Path) -> PathReport:
    """Existence check for every mapped path of every ENABLED stdio server."""
    checked = 0
    unmapped = 0
    missing: list[tuple[str, str]] = []
    for raw_name, server in config["mcp"]["servers"].items():
        if server.get("transport") != "stdio" or server.get("enabled", True) is False:
            continue
        for raw in candidate_paths(server):
            mapped = map_toolchain_path(raw, root)
            if mapped is None:
                unmapped += 1
                continue
            checked += 1
            if not mapped.exists():
                missing.append((str(raw_name), str(mapped)))
    return PathReport(checked=checked, unmapped=unmapped, missing=tuple(missing))


def format_paths_line(report: PathReport) -> str:
    return (
        f"PATHS:mcp-registry checked={report.checked} missing={len(report.missing)} "
        f"unmapped={report.unmapped} missing_servers={','.join(report.missing_servers)}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agents-config",
        default=str(DEFAULT_ROOT / "agents.json"),
    )
    parser.add_argument(
        "--rotation-manifest",
        default=str(DEFAULT_ROOT / "scripts" / "credential_rotation_manifest.json"),
    )
    parser.add_argument(
        "--check-paths",
        action="store_true",
        help="L0 rung: report registry paths under the toolchain prefix that do "
        "not exist under --root (report-only)",
    )
    parser.add_argument(
        "--check-paths-strict",
        action="store_true",
        help=f"imply --check-paths and exit {PATHS_MISSING_EXIT} when any path is missing",
    )
    parser.add_argument(
        "--root",
        default=str(DEFAULT_TOOLCHAIN_ROOT),
        help="directory the Windows toolchain prefix maps to (default: the prefix "
        "itself, i.e. the live checkout on the box)",
    )
    args = parser.parse_args(argv)

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
    # not a broken control plane -- do not require the deleted file.
    if not manifest_path.is_file():
        summary = (
            "SUCCESS:mcp-control-plane-validate "
            f"servers={server_count} "
            f"claude_targets={claude_count} codex_targets={codex_count} "
            "rotation_providers=0 rotation_policy=never"
        )
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        control.validate_rotation_manifest(manifest)
        summary = (
            "SUCCESS:mcp-control-plane-validate "
            f"servers={server_count} "
            f"claude_targets={claude_count} codex_targets={codex_count} "
            f"rotation_providers={len(manifest['providers'])}"
        )

    if args.check_paths or args.check_paths_strict:
        report = check_registry_paths(config, pathlib.Path(args.root))
        print(format_paths_line(report))
        if args.check_paths_strict and report.missing:
            print(
                "FAILED:mcp-control-plane-validate "
                f"paths_missing={len(report.missing)} "
                f"missing_servers={','.join(report.missing_servers)}"
            )
            return PATHS_MISSING_EXIT

    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
