#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
import re
from dataclasses import dataclass

import mcp_control_plane as control


DEFAULT_PROJECT_ROOT = pathlib.Path(r"C:\Users\Prekzursil")
DEFAULT_LIVE_CONFIG = DEFAULT_PROJECT_ROOT / ".codex" / "config.toml"
DEFAULT_AGENTS_CONFIG = DEFAULT_PROJECT_ROOT / ".agents" / "agents.json"

SECTION_RE = re.compile(r"^\[(.+?)\]\s*$", re.MULTILINE)
MCP_RE = re.compile(r'^mcp_servers\.(?:"([^"]+)"|([^.]+))(?:\.(.+))?$')
PROMPTBRIDGE_MARKER_RE = re.compile(
    r"^# (?:>>>|<<<) promptbridge-codex managed (?:>>>|<<<)\s*$",
    re.MULTILINE,
)
RETIRED_MCP_SERVERS = frozenset({"memory", "codex_consult"})


@dataclass
class Block:
    header: str | None
    text: str


def split_blocks(content: str) -> list[Block]:
    matches = list(SECTION_RE.finditer(content))
    if not matches:
        return [Block(None, content)]
    blocks: list[Block] = []
    preamble = content[: matches[0].start()]
    if preamble:
        blocks.append(Block(None, preamble))
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        blocks.append(Block(match.group(1), content[start:end]))
    return blocks


def parse_mcp_header(header: str | None) -> tuple[str, str | None] | None:
    if not header:
        return None
    match = MCP_RE.fullmatch(header)
    if not match:
        return None
    server_name = match.group(1) or match.group(2)
    suffix = match.group(3)
    return server_name, suffix


def is_replaceable_suffix(suffix: str | None) -> bool:
    return suffix in (None, "env", "http_headers", "env_http_headers")


def render_toml_key(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_managed_blocks_from_agents(agents_config: dict) -> list[Block]:
    blocks: list[Block] = []
    servers = control.select_target_servers(agents_config, "codex")
    for name, server in servers.items():
        x_codex = (
            server.get("x_codex", {}) if isinstance(server.get("x_codex"), dict) else {}
        )
        header = f"mcp_servers.{render_toml_key(name)}"
        lines = [f"[{header}]"]

        transport = server.get("transport")
        if transport == "stdio":
            lines.append(f"command = {render_toml_string(server['command'])}")
            args = ", ".join(
                render_toml_string(str(arg)) for arg in server.get("args", [])
            )
            lines.append(f"args = [{args}]")
            if server.get("cwd"):
                lines.append(f"cwd = {render_toml_string(server['cwd'])}")
        else:
            lines.append(f"url = {render_toml_string(server['url'])}")

        lines.append(f"enabled = {'true' if server.get('enabled', True) else 'false'}")
        if "startup_timeout_sec" in x_codex:
            lines.append(f"startup_timeout_sec = {int(x_codex['startup_timeout_sec'])}")
        if "tool_timeout_sec" in x_codex:
            lines.append(f"tool_timeout_sec = {int(x_codex['tool_timeout_sec'])}")

        env_map = server.get("env", {}) if isinstance(server.get("env"), dict) else {}
        env_vars = list(
            dict.fromkeys(
                list(x_codex.get("env_vars", []))
                + list(server.get("requiredEnv", []))
                + [key for key, value in env_map.items() if value == f"${{{key}}}"]
            )
        )
        if env_vars and transport == "stdio":
            rendered = ", ".join(render_toml_string(v) for v in env_vars)
            lines.append(f"env_vars = [{rendered}]")

        bearer_env = x_codex.get("bearer_token_env_var")
        headers_map = (
            server.get("headers", {}) if isinstance(server.get("headers"), dict) else {}
        )
        static_headers: dict[str, str] = {}
        env_headers: dict[str, str] = {}
        for key, value in headers_map.items():
            if value == f"${{{key}}}":
                env_headers[key] = key
            elif (
                isinstance(value, str)
                and value.startswith("${")
                and value.endswith("}")
            ):
                env_headers[key] = value[2:-1]
            else:
                static_headers[key] = value
        if (
            bearer_env
            and static_headers.get("Authorization") == f"Bearer ${{{bearer_env}}}"
        ):
            static_headers.pop("Authorization", None)
        authorization = static_headers.get("Authorization")
        if (
            isinstance(authorization, str)
            and authorization.startswith("Bearer ${")
            and authorization.endswith("}")
        ):
            referenced_env = authorization[len("Bearer ${") : -1]
            if bearer_env and bearer_env != referenced_env:
                raise control.RegistryError(
                    f"{name}: conflicting bearer credential references"
                )
            bearer_env = referenced_env
            static_headers.pop("Authorization", None)
        if bearer_env:
            lines.append(f"bearer_token_env_var = {render_toml_string(bearer_env)}")

        blocks.append(Block(header, "\n".join(lines) + "\n"))

        static_env = {k: v for k, v in env_map.items() if k not in env_vars}
        if static_env:
            env_lines = [f"[{header}.env]"]
            for key in sorted(static_env):
                env_lines.append(
                    f"{render_toml_key(key)} = {render_toml_string(str(static_env[key]))}"
                )
            blocks.append(Block(f"{header}.env", "\n".join(env_lines) + "\n"))

        if static_headers:
            header_lines = [f"[{header}.http_headers]"]
            for key in sorted(static_headers):
                header_lines.append(
                    f"{render_toml_key(key)} = {render_toml_string(str(static_headers[key]))}"
                )
            blocks.append(
                Block(f"{header}.http_headers", "\n".join(header_lines) + "\n")
            )
        if env_headers:
            header_lines = [f"[{header}.env_http_headers]"]
            for key in sorted(env_headers):
                header_lines.append(
                    f"{render_toml_key(key)} = {render_toml_string(env_headers[key])}"
                )
            blocks.append(
                Block(f"{header}.env_http_headers", "\n".join(header_lines) + "\n")
            )

    generated_names = {
        parsed[0]
        for block in blocks
        if (parsed := parse_mcp_header(block.header)) is not None
    }
    control.assert_exact_target_parity(agents_config, "codex", generated_names)
    return blocks


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge agents-managed Codex MCP blocks into a live Codex config while preserving non-MCP settings and local-only subblocks."
    )
    parser.add_argument("--live", default=str(DEFAULT_LIVE_CONFIG))
    parser.add_argument("--agents-config", default=str(DEFAULT_AGENTS_CONFIG))
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the merged config back to the live file",
    )
    args = parser.parse_args()

    live_path = pathlib.Path(args.live)
    agents_config_path = pathlib.Path(args.agents_config)

    live_text = live_path.read_text(encoding="utf-8")
    live_text = PROMPTBRIDGE_MARKER_RE.sub("", live_text)
    live_text = re.sub(r"\n{3,}", "\n\n", live_text)
    agents_config = json.loads(agents_config_path.read_text(encoding="utf-8"))
    control.validate_registry(agents_config)

    live_blocks = split_blocks(live_text)
    generated_blocks = build_managed_blocks_from_agents(agents_config)

    managed_server_names: set[str] = set()
    for block in generated_blocks:
        parsed = parse_mcp_header(block.header)
        if parsed is not None:
            managed_server_names.add(parsed[0])

    registry_names = set(agents_config["mcp"]["servers"]) | RETIRED_MCP_SERVERS
    preserved_blocks: list[Block] = []
    removed_headers: list[str] = []
    for block in live_blocks:
        parsed = parse_mcp_header(block.header)
        if parsed is None:
            preserved_blocks.append(block)
            continue
        server_name, suffix = parsed
        if server_name in registry_names and (
            server_name not in managed_server_names or is_replaceable_suffix(suffix)
        ):
            removed_headers.append(block.header or "")
            continue
        preserved_blocks.append(block)

    out_parts: list[str] = []
    for block in preserved_blocks:
        out_parts.append(block.text.rstrip("\n"))
    for block in generated_blocks:
        out_parts.append(block.text.rstrip("\n"))
    merged_text = "\n\n".join(part for part in out_parts if part) + "\n"

    if args.write:
        control.atomic_write_text(live_path, merged_text)

    print(
        "SUCCESS:mcp-codex-merge "
        f"managed={len(managed_server_names)} removed_blocks={len(removed_headers)} "
        f"write={str(args.write).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
