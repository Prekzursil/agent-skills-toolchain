#!/usr/bin/env python3
# WARNING: SELF-BREAKING. This script replaces agents.json["mcp"] with
# {"servers": imported_servers} and DROPS mcp.policy / mcp.supervision.
# Do not run. Use the Cursor/Claude merge scripts instead.
from __future__ import annotations

import argparse
import json
import pathlib
import re
import tomllib
from typing import Any

import mcp_control_plane as control


DEFAULT_PROJECT_ROOT = pathlib.Path(r"C:\Users\Prekzursil")
DEFAULT_CODEX_CONFIG = DEFAULT_PROJECT_ROOT / ".codex" / "config.toml"
DEFAULT_AGENTS_CONFIG = DEFAULT_PROJECT_ROOT / ".agents" / "agents.json"
DEFAULT_REPORT = (
    DEFAULT_PROJECT_ROOT / ".agents" / "generated" / "mcp-import-report-2026-04-01.json"
)
DEFAULT_SHARED_TARGETS = ["codex", "claude"]
DEFAULT_CODEX_ONLY: set[str] = set()
RETIRED_SERVERS = {"memory"}


def load_json(path: pathlib.Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    control.atomic_write_json(path, payload)


def coerce_targets(server_name: str) -> list[str]:
    if server_name in DEFAULT_CODEX_ONLY:
        return ["codex"]
    return DEFAULT_SHARED_TARGETS.copy()


def placeholder_env_map(env_names: list[str]) -> dict[str, str]:
    return {name: f"${{{name}}}" for name in env_names}


def normalize_windows_path(value: str) -> str:
    if re.match(r"^[A-Za-z]:/", value):
        return value.replace("/", "\\")
    return value


def credential_env_name(server_name: str, field_name: str) -> str:
    combined = f"{server_name}_{field_name}".upper()
    normalized = re.sub(r"[^A-Z0-9]+", "_", combined).strip("_")
    if not normalized or normalized[0].isdigit():
        normalized = f"MCP_{normalized}"
    return normalized


def convert_server(name: str, raw: dict[str, Any]) -> dict[str, Any]:
    server: dict[str, Any] = {
        "label": name,
        "description": f"Imported from .codex/config.toml ({name})",
        "targets": coerce_targets(name),
        "enabled": bool(raw.get("enabled", True)),
    }

    if "command" in raw:
        server["transport"] = "stdio"
        server["command"] = normalize_windows_path(str(raw["command"]))
        server["args"] = [
            normalize_windows_path(str(arg)) for arg in raw.get("args", [])
        ]
        if raw.get("cwd"):
            server["cwd"] = normalize_windows_path(str(raw["cwd"]))
    elif "url" in raw:
        server["transport"] = "http"
        server["url"] = raw["url"]
    else:
        raise ValueError(f"{name}: neither command nor url present")

    env: dict[str, str] = {}
    required_env: set[str] = set()
    if isinstance(raw.get("env"), dict):
        for key, value in raw["env"].items():
            key = str(key)
            if control.is_credential_name(key):
                env[key] = control.environment_reference(key)
                required_env.add(key)
            else:
                env[key] = str(value)

    env_vars = [str(v) for v in raw.get("env_vars", [])]
    env.update(placeholder_env_map(env_vars))
    required_env.update(env_vars)
    if env:
        server["env"] = env

    headers: dict[str, str] = {}
    if isinstance(raw.get("http_headers"), dict):
        for key, value in raw["http_headers"].items():
            key = str(key)
            value = str(value)
            if control.is_credential_name(key):
                if control.is_credential_reference(value):
                    headers[key] = value
                    match = re.search(r"\$\{([A-Z][A-Z0-9_]*)\}", value)
                    if match:
                        required_env.add(match.group(1))
                else:
                    env_name = credential_env_name(name, key)
                    headers[key] = control.environment_reference(env_name)
                    required_env.add(env_name)
            else:
                headers[key] = value

    bearer_token_env_var = raw.get("bearer_token_env_var")
    if bearer_token_env_var:
        headers["Authorization"] = f"Bearer ${{{bearer_token_env_var}}}"
        required_env.add(str(bearer_token_env_var))

    if headers:
        server["headers"] = headers

    if required_env:
        server["requiredEnv"] = sorted(required_env)

    if name == "hexstrike-ai":
        launcher = (
            normalize_windows_path(str(raw.get("args", [""])[0]))
            if raw.get("args")
            else normalize_windows_path(
                str(
                    DEFAULT_PROJECT_ROOT
                    / ".local"
                    / "opt"
                    / "hexstrike-ai"
                    / "hexstrike_mcp_launcher.py"
                )
            )
        )
        server["command"] = "py"
        server["args"] = ["-3", launcher]

    x_codex: dict[str, Any] = {}
    if env_vars:
        x_codex["env_vars"] = env_vars
    if bearer_token_env_var:
        x_codex["bearer_token_env_var"] = str(bearer_token_env_var)
    if "startup_timeout_sec" in raw:
        x_codex["startup_timeout_sec"] = raw["startup_timeout_sec"]
    if x_codex:
        server["x_codex"] = x_codex

    return server


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import MCP servers from Codex config into .agents/agents.json"
    )
    parser.add_argument("--codex-config", default=str(DEFAULT_CODEX_CONFIG))
    parser.add_argument("--agents-config", default=str(DEFAULT_AGENTS_CONFIG))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    args = parser.parse_args()

    codex_config_path = pathlib.Path(args.codex_config)
    agents_config_path = pathlib.Path(args.agents_config)
    report_path = pathlib.Path(args.report)

    with codex_config_path.open("rb") as f:
        codex_config = tomllib.load(f)
    agents_config = load_json(agents_config_path)

    raw_servers = codex_config.get("mcp_servers", {})
    imported_servers: dict[str, Any] = {}
    report_rows: list[dict[str, Any]] = []

    for name in sorted(raw_servers):
        if name in RETIRED_SERVERS:
            continue
        raw = raw_servers[name]
        imported = convert_server(name, raw)
        imported_servers[name] = imported
        report_rows.append(
            {
                "name": name,
                "transport": imported["transport"],
                "targets": imported["targets"],
                "requiredEnv": imported.get("requiredEnv", []),
                "had_tool_subconfig": "tools" in raw,
            }
        )

    agents_config["mcp"] = {"servers": imported_servers}
    control.validate_registry(agents_config)
    dump_json(agents_config_path, agents_config)
    dump_json(
        report_path,
        {
            "source": str(codex_config_path),
            "target": str(agents_config_path),
            "importedCount": len(imported_servers),
            "servers": report_rows,
        },
    )
    print(f"Imported {len(imported_servers)} servers into {agents_config_path}")
    print(f"Report written to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
