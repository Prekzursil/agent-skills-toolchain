from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"\{([A-Z0-9_]+)\}")


def default_config_path(client: str) -> Path:
    home = Path.home()
    if client == "codex":
        return home / ".codex" / "config.toml"
    if client == "claude":
        return home / ".claude.json"
    if client == "gemini":
        return home / ".gemini" / "settings.json"
    raise ValueError(f"unknown client: {client}")


def load_manifest(
    path: Path, repo_root: Path, overrides: dict[str, str] | None = None
) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    variables = {
        "USER_HOME": str(Path.home()).replace("\\", "/"),
        "REPO_ROOT": str(repo_root).replace("\\", "/"),
    }
    if overrides:
        variables.update({k: v.replace("\\", "/") for k, v in overrides.items()})

    def expand(value):
        if isinstance(value, str):

            def repl(match):
                key = match.group(1)
                if key not in variables:
                    raise KeyError(key)
                return variables[key]

            return PLACEHOLDER_RE.sub(repl, value)
        if isinstance(value, list):
            return [expand(v) for v in value]
        if isinstance(value, dict):
            return {k: expand(v) for k, v in value.items()}
        return value

    try:
        return expand(data)
    except KeyError as exc:
        raise SystemExit(
            f"Missing placeholder value for {exc.args[0]}. Supply it with --var NAME=VALUE."
        )


def build_json_entry(manifest: dict, client: str) -> dict:
    entry = {"command": manifest["command"]}
    if manifest.get("args"):
        entry["args"] = manifest["args"]
    if manifest.get("env"):
        entry["env"] = manifest["env"]
    if client == "claude":
        entry.setdefault("type", "stdio")
    if client == "gemini":
        entry.setdefault("trust", True)
    return entry


def upsert_json_client(config_path: Path, server_name: str, entry: dict) -> None:
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        data = {}
    data.setdefault("mcpServers", {})
    data["mcpServers"][server_name] = entry
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _is_target_header(line: str, name: str) -> bool:
    stripped = line.strip()
    return stripped in {f"[mcp_servers.{name}]", f'[mcp_servers."{name}"]'}


def _is_target_nested(line: str, name: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(f"[mcp_servers.{name}.") or stripped.startswith(
        f'[mcp_servers."{name}".'
    )


def render_codex_section(server_name: str, manifest: dict) -> str:
    lines = [
        f'[mcp_servers."{server_name}"]',
        f"command = {json.dumps(manifest['command'])}",
    ]
    if manifest.get("args"):
        args = ", ".join(json.dumps(arg) for arg in manifest["args"])
        lines.append(f"args = [{args}]")
    if manifest.get("env"):
        lines.append("")
        lines.append(f'[mcp_servers."{server_name}".env]')
        for key, value in manifest["env"].items():
            lines.append(f"{key} = {json.dumps(value)}")
    return "\n".join(lines).rstrip() + "\n"


def upsert_codex_config(config_path: Path, server_name: str, manifest: dict) -> None:
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    lines = existing.splitlines(keepends=True)
    output: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _is_target_header(line, server_name):
            i += 1
            while i < len(lines):
                probe = lines[i]
                if probe.lstrip().startswith("["):
                    if _is_target_nested(probe, server_name):
                        i += 1
                        continue
                    break
                i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            continue
        output.append(line)
        i += 1
    text = "".join(output).rstrip()
    if text:
        text += "\n\n"
    text += render_codex_section(server_name, manifest)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(text, encoding="utf-8")


def parse_overrides(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"Invalid --var value: {value}. Expected NAME=VALUE.")
        key, val = value.split("=", 1)
        result[key] = val
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Register an MCP server manifest into Codex, Claude, or Gemini config."
    )
    parser.add_argument(
        "--client", required=True, choices=["codex", "claude", "gemini"]
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[4]
    )
    parser.add_argument("--var", action="append", default=[])
    args = parser.parse_args()

    manifest = load_manifest(args.manifest, args.repo_root, parse_overrides(args.var))
    server_name = manifest["name"]
    config_path = args.config or default_config_path(args.client)

    if args.client == "codex":
        upsert_codex_config(config_path, server_name, manifest)
    else:
        upsert_json_client(
            config_path, server_name, build_json_entry(manifest, args.client)
        )

    print(f"Updated {args.client} config: {config_path}")
    print(f"Registered MCP server: {server_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
