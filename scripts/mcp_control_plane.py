#!/usr/bin/env python3
"""Validation and publication primitives for the shared MCP control plane."""

from __future__ import annotations

import json
import os
import pathlib
import re
import tempfile
from collections.abc import Iterable, Mapping
from typing import Any


VALID_TARGETS = frozenset({"claude", "codex", "zcode", "hermes", "gemini"})
VALID_APPROVAL_MODES = frozenset({"native", "allow", "deny"})
VALID_HEALTH_PROBES = frozenset({"mcp-tools-list", "http", "command", "none"})
MAX_STARTUP_TIMEOUT_MS = 30_000
DEFAULT_SERVER_PRIVATE_BYTES = 512 * 1024 * 1024
DEFAULT_TOTAL_PRIVATE_BYTES = 6 * 1024 * 1024 * 1024
# Owner decision (live, 2026-08-28): these run as the vendors' hosted HTTP MCPs,
# never as per-session npx process trees. A registry that drifts them back to
# stdio fails validation, tag or no tag.
REMOTE_REQUIRED_SERVERS = frozenset({"context7", "firecrawl"})
CLAUDE_PLUGIN_PROVIDED_SERVERS = frozenset(
    {
        "aws-serverless",
        "deploy-on-aws",
        "firebase",
        "gitlab",
        "microsoft-learn",
        "mintlify",
        "pinecone",
        "sourcegraph",
        "supabase",
    }
)
ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
ENV_REFERENCE_RE = re.compile(r"^\$\{([A-Z][A-Z0-9_]*)\}$")
KEYRING_REFERENCE_RE = re.compile(r"^keyring://([A-Za-z0-9_.:/-]+)$")
SECRET_NAME_RE = re.compile(
    r"(?:^|_)(?:API_?KEY|ACCESS_?KEY|AUTH(?:ORIZATION)?|BEARER|CREDENTIAL|"
    r"PASSWORD|PAT|PRIVATE_?KEY|SECRET|TOKEN)(?:$|_)",
    re.IGNORECASE,
)
LITERAL_SECRET_RE = re.compile(
    r"^(?:gh[pousr]_|github_pat_|hf_|sk-|ctx7sk-|fc-|apify_api_|do[op]_v1_)",
    re.IGNORECASE,
)


class RegistryError(ValueError):
    """Raised when the MCP registry violates the shared contract."""


def _servers(config: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    mcp = config.get("mcp")
    if not isinstance(mcp, Mapping):
        raise RegistryError("registry must contain an mcp object")
    servers = mcp.get("servers")
    if not isinstance(servers, Mapping):
        raise RegistryError("registry must contain mcp.servers")
    return servers


def _policy(config: Mapping[str, Any]) -> Mapping[str, Any]:
    mcp = config.get("mcp")
    if not isinstance(mcp, Mapping):
        raise RegistryError("registry must contain an mcp object")
    policy = mcp.get("policy")
    if not isinstance(policy, Mapping):
        raise RegistryError("registry must contain mcp.policy defaults")
    return policy


def _supervision(config: Mapping[str, Any]) -> Mapping[str, Any]:
    mcp = config.get("mcp")
    if not isinstance(mcp, Mapping):
        raise RegistryError("registry must contain an mcp object")
    supervision = mcp.get("supervision")
    if not isinstance(supervision, Mapping):
        raise RegistryError("registry must contain mcp.supervision")
    return supervision


def _is_reference(value: object, expected_env: str | None = None) -> bool:
    if not isinstance(value, str):
        return False
    match = ENV_REFERENCE_RE.fullmatch(value)
    if match:
        return expected_env is None or match.group(1) == expected_env
    return KEYRING_REFERENCE_RE.fullmatch(value) is not None


def is_credential_name(name: str) -> bool:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", name)
    return SECRET_NAME_RE.search(normalized) is not None


def is_credential_reference(value: object) -> bool:
    if _is_reference(value):
        return True
    if not isinstance(value, str):
        return False
    match = re.fullmatch(r"Bearer \$\{([A-Z][A-Z0-9_]*)\}", value)
    return match is not None


def environment_reference(name: str) -> str:
    if not ENV_NAME_RE.fullmatch(name):
        raise RegistryError(f"invalid environment variable name: {name}")
    return f"${{{name}}}"


def _validate_reference_map(
    server_name: str,
    field_name: str,
    values: object,
    required_env: set[str],
) -> None:
    if values is None:
        return
    if not isinstance(values, Mapping):
        raise RegistryError(f"{server_name}: {field_name} must be an object")
    for raw_key, value in values.items():
        key = str(raw_key)
        is_sensitive = is_credential_name(key) or key in required_env
        is_reference = (
            _is_reference(value, key)
            if field_name == "env"
            else is_credential_reference(value)
        )
        if is_sensitive and not is_reference:
            raise RegistryError(
                f"{server_name}: {field_name}.{key} must be a credential reference"
            )
        if isinstance(value, str) and LITERAL_SECRET_RE.search(value):
            raise RegistryError(
                f"{server_name}: {field_name}.{key} contains a literal credential"
            )


def validate_registry(config: Mapping[str, Any]) -> None:
    """Validate target, transport, singleton, and credential invariants."""
    policy = _policy(config)
    supervision = _supervision(config)
    required = policy.get("required")
    startup_timeout = policy.get("startupTimeoutMs")
    tool_timeout = policy.get("toolTimeoutMs")
    health_probe = policy.get("healthProbe")
    tool_allowlist = policy.get("toolAllowlist")
    approval_mode = policy.get("approvalMode")
    max_private_bytes = policy.get("maxPrivateBytes")
    if not isinstance(required, bool):
        raise RegistryError("mcp.policy.required must be boolean")
    if (
        not isinstance(startup_timeout, int)
        or not 1 <= startup_timeout <= MAX_STARTUP_TIMEOUT_MS
    ):
        raise RegistryError("mcp.policy.startupTimeoutMs must be within 1..30000")
    if not isinstance(tool_timeout, int) or tool_timeout < 1:
        raise RegistryError("mcp.policy.toolTimeoutMs must be positive")
    if (
        not isinstance(health_probe, Mapping)
        or health_probe.get("kind") not in VALID_HEALTH_PROBES
    ):
        raise RegistryError("mcp.policy.healthProbe.kind is unsupported")
    probe_timeout = health_probe.get("timeoutMs")
    if (
        not isinstance(probe_timeout, int)
        or not 1 <= probe_timeout <= MAX_STARTUP_TIMEOUT_MS
    ):
        raise RegistryError("mcp.policy.healthProbe.timeoutMs must be within 1..30000")
    if (
        not isinstance(tool_allowlist, list)
        or not tool_allowlist
        or any(not isinstance(tool, str) or not tool for tool in tool_allowlist)
    ):
        raise RegistryError("mcp.policy.toolAllowlist must be a nonempty string list")
    if approval_mode not in VALID_APPROVAL_MODES:
        raise RegistryError("mcp.policy.approvalMode is unsupported")
    if not isinstance(max_private_bytes, int) or max_private_bytes < 1:
        raise RegistryError("mcp.policy.maxPrivateBytes must be positive")

    total_private_bytes = supervision.get("totalIdlePrivateBytes")
    if total_private_bytes != DEFAULT_TOTAL_PRIVATE_BYTES:
        raise RegistryError("mcp.supervision.totalIdlePrivateBytes must be 6 GiB")
    if supervision.get("failureThreshold") != 3:
        raise RegistryError("mcp.supervision.failureThreshold must be 3")
    if supervision.get("failureWindowSeconds") != 600:
        raise RegistryError("mcp.supervision.failureWindowSeconds must be 600")
    if supervision.get("quarantineScope") != "session":
        raise RegistryError("mcp.supervision.quarantineScope must be session")

    servers = _servers(config)
    seen_singletons: dict[str, str] = {}
    for raw_name, server in servers.items():
        name = str(raw_name)
        if not isinstance(server, Mapping):
            raise RegistryError(f"{name}: server definition must be an object")

        targets = server.get("targets")
        if not isinstance(targets, list) or not targets:
            raise RegistryError(f"{name}: server must declare nonempty targets")
        if any(target not in VALID_TARGETS for target in targets):
            raise RegistryError(f"{name}: unsupported target in {targets!r}")
        if len(targets) != len(set(targets)):
            raise RegistryError(f"{name}: duplicate targets are not allowed")

        transport = server.get("transport")
        if transport == "stdio":
            if (
                not isinstance(server.get("command"), str)
                or not server["command"].strip()
            ):
                raise RegistryError(f"{name}: stdio server requires command")
        elif transport == "http":
            url = server.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                raise RegistryError(f"{name}: http server requires an HTTP(S) URL")
            if server.get("command") is not None or server.get("args") is not None:
                raise RegistryError(
                    f"{name}: http transport cannot declare command or args"
                )
        else:
            raise RegistryError(f"{name}: transport must be stdio or http")

        singleton_key = server.get("singletonKey", name)
        if not isinstance(singleton_key, str) or not singleton_key.strip():
            raise RegistryError(f"{name}: singletonKey must be a nonempty string")
        if singleton_key in seen_singletons:
            raise RegistryError(
                f"{name}: duplicate singletonKey also used by {seen_singletons[singleton_key]}"
            )
        seen_singletons[singleton_key] = name

        required_env_raw = server.get("requiredEnv", [])
        if not isinstance(required_env_raw, list) or any(
            not isinstance(item, str) or not ENV_NAME_RE.fullmatch(item)
            for item in required_env_raw
        ):
            raise RegistryError(f"{name}: requiredEnv must contain environment names")
        required_env = set(required_env_raw)
        credential_names = server.get("credentialNames")
        expected_credentials = {
            item for item in required_env if is_credential_name(item)
        }
        if not isinstance(credential_names, list) or any(
            not isinstance(item, str) or not ENV_NAME_RE.fullmatch(item)
            for item in credential_names
        ):
            raise RegistryError(
                f"{name}: credentialNames must contain environment names"
            )
        if set(credential_names) != expected_credentials:
            raise RegistryError(
                f"{name}: credentialNames must exactly name sensitive requiredEnv entries"
            )
        if (
            transport == "http"
            and credential_names
            and not str(server.get("url", "")).startswith("https://")
        ):
            raise RegistryError(
                f"{name}: credential-bearing http server must use https"
            )
        tags = server.get("tags")
        if (
            not isinstance(tags, list)
            or not tags
            or any(not isinstance(tag, str) or not tag.strip() for tag in tags)
        ):
            raise RegistryError(f"{name}: tags must be a nonempty string list")
        if name in REMOTE_REQUIRED_SERVERS and (
            transport != "http" or "remote-required" not in tags
        ):
            raise RegistryError(
                f"{name}: remote-required server must use http transport"
            )
        server_private_bytes = server.get("maxPrivateBytes", max_private_bytes)
        if not isinstance(server_private_bytes, int) or server_private_bytes < 1:
            raise RegistryError(f"{name}: maxPrivateBytes must be positive")
        if server_private_bytes > DEFAULT_SERVER_PRIVATE_BYTES:
            exception = server.get("resourceException")
            if not isinstance(exception, str) or len(exception.strip()) < 20:
                raise RegistryError(
                    f"{name}: resourceException is required above the 512 MiB default"
                )
        _validate_reference_map(name, "env", server.get("env"), required_env)
        _validate_reference_map(name, "headers", server.get("headers"), set())

        x_codex = server.get("x_codex", {})
        if x_codex is not None and not isinstance(x_codex, Mapping):
            raise RegistryError(f"{name}: x_codex must be an object")
        if isinstance(x_codex, Mapping):
            bearer_env = x_codex.get("bearer_token_env_var")
            if bearer_env is not None and (
                not isinstance(bearer_env, str) or not ENV_NAME_RE.fullmatch(bearer_env)
            ):
                raise RegistryError(
                    f"{name}: bearer_token_env_var must name an environment variable"
                )
            if bearer_env is not None and bearer_env not in credential_names:
                raise RegistryError(
                    f"{name}: bearer_token_env_var must be declared in credentialNames"
                )
            startup_seconds = x_codex.get("startup_timeout_sec")
            if startup_seconds is not None and (
                not isinstance(startup_seconds, int) or not 1 <= startup_seconds <= 30
            ):
                raise RegistryError(f"{name}: startup_timeout_sec must be within 1..30")

        _validate_x_cursor(name, server)


def _validate_x_cursor(name: str, server: Mapping[str, Any]) -> None:
    """``x_cursor.stdio_bridge``: a per-session stdio shim Cursor runs in front of
    an http server, rendered by ``merge_generated_cursor_mcp.py`` with the
    registry URL appended as ``--url``. Closed schema: the only key is
    ``stdio_bridge``; rationale lives in ``.provenance``, not here."""
    x_cursor = server.get("x_cursor")
    if x_cursor is None:
        return
    if not isinstance(x_cursor, Mapping):
        raise RegistryError(f"{name}: x_cursor must be an object")
    unknown = sorted(str(key) for key in x_cursor if key != "stdio_bridge")
    if unknown:
        raise RegistryError(f"{name}: unknown x_cursor key {unknown[0]!r}")
    bridge = x_cursor.get("stdio_bridge")
    if bridge is None:
        return
    if server.get("transport") != "http":
        raise RegistryError(
            f"{name}: x_cursor.stdio_bridge is only valid for http servers"
        )
    if not isinstance(bridge, Mapping):
        raise RegistryError(f"{name}: x_cursor.stdio_bridge must be an object")
    command = bridge.get("command")
    if not isinstance(command, str) or not command.strip():
        raise RegistryError(f"{name}: x_cursor.stdio_bridge requires command")
    args = bridge.get("args", [])
    if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
        raise RegistryError(f"{name}: x_cursor.stdio_bridge.args must be a string list")
    x_codex = server.get("x_codex")
    bearer = (
        x_codex.get("bearer_token_env_var") if isinstance(x_codex, Mapping) else None
    )
    if server.get("headers") or bearer:
        # The shim dials the URL bare; a server that needs auth has no bridge.
        raise RegistryError(
            f"{name}: x_cursor.stdio_bridge cannot carry headers or bearer credentials"
        )
    for arg in [command, *args]:
        if LITERAL_SECRET_RE.search(arg):
            raise RegistryError(
                f"{name}: x_cursor.stdio_bridge contains a literal credential"
            )


def effective_server_contract(config: Mapping[str, Any], name: str) -> dict[str, Any]:
    """Return the decision-complete public contract for a registry entry."""
    validate_registry(config)
    server = _servers(config)[name]
    policy = _policy(config)
    return {
        "id": name,
        "transport": server["transport"],
        "command": server.get("command"),
        "url": server.get("url"),
        "targets": list(server["targets"]),
        "enabled": server.get("enabled", True),
        "required": server.get("required", policy["required"]),
        "credentialNames": list(server["credentialNames"]),
        "startupTimeoutMs": server.get("startupTimeoutMs", policy["startupTimeoutMs"]),
        "toolTimeoutMs": server.get("toolTimeoutMs", policy["toolTimeoutMs"]),
        "healthProbe": server.get("healthProbe", policy["healthProbe"]),
        "toolAllowlist": server.get("toolAllowlist", policy["toolAllowlist"]),
        "approvalMode": server.get("approvalMode", policy["approvalMode"]),
        "singletonKey": server.get("singletonKey", name),
        "tags": list(server["tags"]),
        "maxPrivateBytes": server.get("maxPrivateBytes", policy["maxPrivateBytes"]),
    }


def select_target_servers(
    config: Mapping[str, Any],
    target: str,
    *,
    plugin_provided: Iterable[str] = (),
) -> dict[str, Mapping[str, Any]]:
    """Return a deterministic, per-target, singleton-deduplicated server map."""
    if target not in VALID_TARGETS:
        raise RegistryError(f"unsupported target: {target}")
    validate_registry(config)
    plugin_names = set(plugin_provided)
    selected: dict[str, Mapping[str, Any]] = {}
    seen_singletons: set[str] = set()
    for name in sorted(_servers(config)):
        server = _servers(config)[name]
        if server.get("enabled", True) is False or target not in server["targets"]:
            continue
        if name in plugin_names:
            continue
        singleton_key = str(server.get("singletonKey", name))
        if singleton_key in seen_singletons:
            continue
        seen_singletons.add(singleton_key)
        selected[name] = server
    return selected


def expected_target_names(
    config: Mapping[str, Any],
    target: str,
    *,
    plugin_provided: Iterable[str] = (),
) -> set[str]:
    return set(select_target_servers(config, target, plugin_provided=plugin_provided))


def assert_exact_target_parity(
    config: Mapping[str, Any],
    target: str,
    generated_names: Iterable[str],
    *,
    plugin_provided: Iterable[str] = (),
) -> None:
    expected = expected_target_names(config, target, plugin_provided=plugin_provided)
    actual = set(generated_names)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise RegistryError(
            f"{target}: generated target parity mismatch; "
            f"missing={missing!r}, unexpected={unexpected!r}"
        )


def atomic_write_text(path: pathlib.Path | str, content: str) -> None:
    """Publish text with an fsync + same-directory atomic replacement."""
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = pathlib.Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_json(path: pathlib.Path | str, payload: Mapping[str, Any]) -> None:
    content = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    atomic_write_text(path, content)


def validate_rotation_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schemaVersion") != 1:
        raise RegistryError("rotation manifest schemaVersion must be 1")
    providers = manifest.get("providers")
    if not isinstance(providers, list) or not providers:
        raise RegistryError("rotation manifest must contain providers")

    def reject_value_keys(value: object, path: str) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if str(key).lower() in {"value", "secret", "credential"}:
                    raise RegistryError(
                        f"rotation manifest contains forbidden key at {path}"
                    )
                reject_value_keys(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                reject_value_keys(child, f"{path}[{index}]")

    reject_value_keys(manifest, "manifest")
    for record in providers:
        if not isinstance(record, Mapping) or not record.get("provider"):
            raise RegistryError("rotation manifest provider record is invalid")
        env_names = record.get("environmentVariables")
        paths = record.get("affectedPaths")
        if (
            not isinstance(env_names, list)
            or not env_names
            or any(
                not isinstance(name, str) or not ENV_NAME_RE.fullmatch(name)
                for name in env_names
            )
        ):
            raise RegistryError("rotation manifest environmentVariables are invalid")
        if (
            not isinstance(paths, list)
            or not paths
            or any(not isinstance(path, str) or not path for path in paths)
        ):
            raise RegistryError("rotation manifest affectedPaths are invalid")
