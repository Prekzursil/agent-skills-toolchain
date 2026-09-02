#!/usr/bin/env python3
"""Validation and selection primitives for the hosted + local models registry.

``.agents/models.json`` is the SSOT for inference endpoints and model rows, the
sibling of ``agents.json`` (MCP servers). Renderers, the inference hub, the probe
and the routing policy read the registry only through this module. Credentials
appear by environment-variable NAME only: a literal secret anywhere in the file is
the first thing validation rejects, and no message ever echoes a value.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from typing import Any, NoReturn, TypeGuard
from urllib.parse import urlsplit

from mcp_control_plane import (
    ENV_NAME_RE,
    LITERAL_SECRET_RE,
    atomic_write_json,
    atomic_write_text,
    is_credential_name,
)


__all__ = [
    "DEFAULT_REGISTRY_PATH",
    "ENV_NAME_RE",
    "LATTICE_RANK",
    "LATTICE_STATES",
    "LITERAL_SECRET_RE",
    "MCP_ONLY_RUNTIMES",
    "NATIVE_RUNTIMES",
    "RUNTIMES",
    "RUNTIME_FLOORS",
    "ModelsRegistryError",
    "atomic_write_json",
    "atomic_write_text",
    "credential_names",
    "effective_capabilities",
    "is_credential_name",
    "lattice_at_least",
    "lattice_rank",
    "lattice_state",
    "load_registry",
    "registry_hash",
    "resolve_model",
    "routing_report",
    "select_target_endpoints",
    "select_target_models",
    "validate_registry",
]

SCHEMA_VERSION = 1
DEFAULT_REGISTRY_PATH = pathlib.Path(__file__).resolve().parents[1] / "models.json"

RUNTIMES = (
    "codex",
    "grok",
    "goose",
    "opencode",
    "aider",
    "fabric",
    "cursor",
    "claude",
    "agy",
    "gemini",
)
NATIVE_RUNTIMES = ("codex", "grok", "goose", "opencode", "aider", "fabric")
MCP_ONLY_RUNTIMES = ("cursor", "claude", "agy", "gemini")
RUNTIME_FLOORS: dict[str, dict[str, str]] = {
    runtime: ({"wire.responses": "probed"} if runtime == "codex" else {})
    for runtime in RUNTIMES
}
# The wire shape a runtime's wrapper speaks; every runtime not listed uses
# chat completions.
RUNTIME_WIRE = {"codex": "responses", "claude": "messages"}

LATTICE_STATES = ("native", "probed", "declared", "emulated", "absent")
LATTICE_RANK = {"native": 4, "probed": 3, "declared": 2, "emulated": 1, "absent": 0}
WIRE_KEYS = ("completions", "responses", "messages")
FEATURE_KEYS = (
    "streaming",
    "usage",
    "tools",
    "tool_choice",
    "structured_output",
    "vision",
    "reasoning",
)

ENDPOINT_KINDS = frozenset({"hosted", "local", "bridge"})
API_VALUES = frozenset(
    {
        "openai-completions",
        "openai-responses",
        "anthropic-messages",
        "google-generative-ai",
        "ollama-native",
    }
)
TARGET_VALUES = frozenset({"native", "fallback", "unsupported", "excluded"})
SELECTED_TARGET_VALUES = frozenset({"native", "fallback"})
COST_BASES = frozenset(
    {"provider_reported", "table_estimate", "unknown_price", "local_zero", "quota"}
)
DISCOVERY_TYPES = frozenset(
    {"ollama", "llama.cpp", "lm-studio", "openai-models-list", "proxy", "none"}
)
HEALTH_KINDS = frozenset({"openai-models-list", "http", "none"})
MODEL_STATUSES = frozenset({"live", "eval-gated", "parked", "unprobed"})
MODEL_TIERS = frozenset({"S", "M", "L", "hosted"})
SLOT_NAMES = ("large", "small", "subagent", "web_search", "summary", "embed")
QUIRK_SECTIONS = ("openai", "anthropic")

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
OWNED_PORTS = frozenset({8765, 8812, 8770})
CURSOR_BRIDGE_PORT = 8317
CURSOR_BRIDGE_ENDPOINT = "cursor-auth2api"
HUB_PORT = 8901
RESERVED_PORTS = OWNED_PORTS | {CURSOR_BRIDGE_PORT}
OPENROUTER_ENDPOINT = "openrouter"

LOCK_ID_RE = re.compile(r"^L[0-9]+$")
# Shapes the MCP sibling does not know. An AWS access key id is upper-case
# alphanumerics like an environment name, so it is matched by exact shape before
# the environment-name exemption; PEM headers contain spaces so they are matched
# against the whole string rather than per token.
AWS_ACCESS_KEY_RE = re.compile(r"^AKIA[0-9A-Z]{16}$")
EXTRA_LITERAL_SECRET_RE = re.compile(r"^xox[abp]-")
PEM_PRIVATE_KEY_RE = re.compile(r"-----BEGIN(?: [A-Z]+)* PRIVATE KEY-----")
SECRET_TOKEN_SPLIT_RE = re.compile(r"[\s\"'`=,;:()\[\]{}<>/?&#|]+")


class ModelsRegistryError(ValueError):
    """Raised when the models registry violates the shared contract."""


def _fail(owner: str, message: str) -> NoReturn:
    raise ModelsRegistryError(f"{owner}: {message}")


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> TypeGuard[int | float]:
    return _is_int(value) or isinstance(value, float)


def _is_str_list(value: object) -> TypeGuard[list[str]]:
    return isinstance(value, list) and all(
        isinstance(item, str) and bool(item.strip()) for item in value
    )


_KINDS: dict[str, tuple[str, Callable[[object], bool]]] = {
    "str": ("a nonempty string", lambda v: isinstance(v, str) and bool(v.strip())),
    "bool": ("a boolean", lambda v: isinstance(v, bool)),
    "int>=0": ("an integer >= 0", lambda v: _is_int(v) and v >= 0),
    "int>=1": ("an integer >= 1", lambda v: _is_int(v) and v >= 1),
    "number|null": ("a number or null", lambda v: v is None or _is_number(v)),
    "number|str": (
        "a number or a string",
        lambda v: _is_number(v) or (isinstance(v, str) and bool(v.strip())),
    ),
    "env": (
        "an environment variable name",
        lambda v: isinstance(v, str) and ENV_NAME_RE.fullmatch(v) is not None,
    ),
    "env[]": (
        "a list of environment variable names",
        lambda v: (
            isinstance(v, list)
            and all(
                isinstance(item, str) and ENV_NAME_RE.fullmatch(item) is not None
                for item in v
            )
        ),
    ),
    "str[]": ("a list of nonempty strings", _is_str_list),
    "str[]+": (
        "a nonempty list of nonempty strings",
        lambda v: _is_str_list(v) and bool(v),
    ),
    "list": ("a list", lambda v: isinstance(v, list)),
    "object": ("an object", lambda v: isinstance(v, Mapping)),
    "object|null": ("an object or null", lambda v: v is None or isinstance(v, Mapping)),
}

TOP_LEVEL_SPEC = {
    "schemaVersion": "int>=1",
    "description": "str",
    "policy": "object",
    "locks": "list",
    "endpoints": "object",
    "models": "object",
    "aliases": "object",
    "slots": "object",
}
POLICY_SPEC = {
    "capabilityProbe": "object",
    "localRamBudgetBytes": "int>=0",
    "defaultTimeoutMs": "int>=1",
    "hub": "object",
}
CAPABILITY_PROBE_SPEC = {"ttlHours": "int>=1"}
HUB_SPEC = {
    "host": "str",
    "port": "int>=1",
    "idleExitSeconds": "int>=0",
    "maxInFlightTotal": "int>=1",
    "ledgerPath": "str",
    "haltFile": "str",
    "haltEnv": "env",
}
LOCK_SPEC = {"id": "str", "rule": "str", "enforcedBy": "str[]+"}
ENDPOINT_REQUIRED = (
    "label",
    "description",
    "kind",
    "enabled",
    "baseUrl",
    "api",
    "auth",
    "wire",
    "features",
    "concurrency",
    "budget",
    "resource",
    "targets",
    "discovery",
    "health",
    "denyCallers",
    "locks",
    "tags",
)
ENDPOINT_SPEC = {
    "label": "str",
    "description": "str",
    "kind": "str",
    "enabled": "bool",
    "baseUrl": "str",
    "api": "str[]+",
    "auth": "object|null",
    "wire": "object",
    "features": "object",
    "concurrency": "object",
    "budget": "object",
    "resource": "object",
    "targets": "object",
    "discovery": "object",
    "health": "object",
    "denyCallers": "str[]",
    "locks": "str[]",
    "tags": "str[]+",
    "sidecarOnly": "bool",
    "singletonKey": "str",
    "retiresWhen": "str",
    "quirks": "object",
}
AUTH_SPEC = {
    "env": "env",
    "altEnv": "env[]",
    "scheme": "str",
    "header": "str",
    "issuerHosts": "str[]+",
}
CONCURRENCY_SPEC = {"maxInFlight": "int>=1"}
BUDGET_SPEC = {"dailyUsdCap": "number|null", "costBasis": "str"}
RESOURCE_SPEC = {"ramBytes": "int>=0"}
DISCOVERY_SPEC = {"type": "str", "timeoutMs": "int>=1", "injectV1": "bool"}
HEALTH_SPEC = {"kind": "str", "path": "str", "timeoutMs": "int>=1"}
PROBED_SPEC = {"state": "str", "at": "str", "version": "str", "evidence": "str"}
QUIRKS_SPEC = {"openai": "object", "anthropic": "object"}
QUIRK_SPEC = {
    "compat": "object",
    "stream_tool_calls": "bool",
    "thinking_off_for_tools": "bool",
    "tools_stream": "bool",
}
MODEL_REQUIRED = (
    "endpoint",
    "remoteId",
    "label",
    "description",
    "enabled",
    "status",
    "tier",
    "context",
    "maxOutput",
    "modalities",
    "cost",
    "denyCallers",
    "tags",
)
MODEL_SPEC = {
    "endpoint": "str",
    "remoteId": "str",
    "label": "str",
    "description": "str",
    "enabled": "bool",
    "status": "str",
    "tier": "str",
    "context": "int>=1",
    "maxOutput": "int>=1",
    "modalities": "object",
    "cost": "object",
    "resource": "object",
    "quirks": "object",
    "denyCallers": "str[]",
    "tags": "str[]+",
    "wire": "object",
    "features": "object",
    "modelsDev": "str",
}
MODALITIES_SPEC = {"input": "str[]+", "output": "str[]+"}
COST_SPEC = {"inputPer1M": "number|null", "outputPer1M": "number|null", "basis": "str"}
X_BLOCK_SPECS: dict[str, dict[str, str]] = {
    "x_codex": {
        "env_key": "env",
        "wire_api": "str",
        "http_headers": "object",
        "query_params": "object",
    },
    "x_grok": {
        "api_backend": "str",
        "context_window": "int>=1",
        "models_base_url": "str",
    },
    "x_goose": {"engine": "str", "base_path": "str", "requires_auth": "bool"},
    "x_opencode": {"npm": "str", "provider_id": "str"},
    "x_aider": {"litellm_provider": "str", "alias": "str"},
    "x_fabric": {"vendor": "str", "disable_responses_api": "bool"},
    "x_hub": {"profile_root": "str", "max_result_chars": "int>=1"},
    "x_openrouter": {"keys": "list", "guardrail": "object"},
    "x_ollama": {
        "keepAlive": "str",
        "maxLoadedModels": "int>=1",
        "numParallel": "int>=1",
        "contextLength": "int>=1",
        "kvCacheType": "str",
        "bind": "str",
        "minVersion": "str",
    },
    "x_lmstudio": {
        "daemon": "str",
        "jit": "bool",
        "autoEvict": "bool",
        "idleTtlSeconds": "int>=0",
        "bind": "str",
    },
}
OPENROUTER_KEY_SPEC = {
    "env": "env",
    "label": "str",
    "consumers": "str[]+",
    "limitReset": "str",
    "optional": "bool",
}
OPENROUTER_KEY_REQUIRED = ("env", "label", "consumers", "limitReset")
GUARDRAIL_SPEC = {
    "providerAllowlist": "str[]",
    "modelAllowlist": "str[]",
    "dataCollection": "str",
    "secretsPreset": "bool",
    "limitUsd": "number|str",
}


def _check_value(owner: str, path: str, value: object, kind: str) -> None:
    label, accepts = _KINDS[kind]
    if not accepts(value):
        _fail(owner, f"{path} must be {label}")


def _check_keys(
    owner: str,
    what: str,
    mapping: Mapping[str, Any],
    *,
    required: Iterable[str],
    allowed: Iterable[str],
) -> None:
    keys = {str(key) for key in mapping}
    missing = sorted(set(required) - keys)
    if missing:
        _fail(owner, f"{what} is missing required key {missing[0]!r}")
    unknown = sorted(keys - set(allowed))
    if unknown:
        _fail(owner, f"unknown {what} key {unknown[0]!r}")


def _check_block(
    owner: str,
    what: str,
    block: object,
    spec: Mapping[str, str],
    *,
    required: Iterable[str] = (),
) -> Mapping[str, Any]:
    if not isinstance(block, Mapping):
        _fail(owner, f"{what} must be an object")
    _check_keys(owner, what, block, required=required, allowed=spec)
    for key, kind in spec.items():
        if key in block:
            _check_value(owner, f"{what}.{key}", block[key], kind)
    return block


def _looks_like_secret(text: str) -> bool:
    if PEM_PRIVATE_KEY_RE.search(text):
        return True
    for token in SECRET_TOKEN_SPLIT_RE.split(text):
        if AWS_ACCESS_KEY_RE.fullmatch(token):
            return True
        if (
            token
            and not ENV_NAME_RE.fullmatch(token)
            and (
                LITERAL_SECRET_RE.search(token) or EXTRA_LITERAL_SECRET_RE.search(token)
            )
        ):
            return True
    return False


def _reject_literal_secrets(value: object, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _reject_literal_secrets(str(key), f"{path}.<key>")
            _reject_literal_secrets(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_literal_secrets(child, f"{path}[{index}]")
    elif isinstance(value, str) and _looks_like_secret(value):
        raise ModelsRegistryError(
            f"{path}: literal secret detected; refer to credentials by "
            "environment-variable name only (L6)"
        )


def _lattice_state(owner: str, path: str, value: object) -> str:
    if isinstance(value, str):
        if value == "probed":
            _fail(owner, f"{path} probed value requires an object with at and version")
        if value not in LATTICE_RANK:
            _fail(owner, f"{path} has unknown lattice value {value!r}")
        return value
    if not isinstance(value, Mapping):
        _fail(owner, f"{path} must be a lattice state or a probed object")
    if value.get("state") != "probed":
        _fail(owner, f"{path} object form requires state probed")
    missing = [key for key in ("at", "version") if key not in value]
    if missing:
        _fail(owner, f"{path} probed value is missing required key {missing[0]!r}")
    block = _check_block(owner, path, value, PROBED_SPEC)
    try:
        datetime.fromisoformat(block["at"])
    except ValueError:
        _fail(owner, f"{path}.at must be an ISO-8601 timestamp")
    return "probed"


def lattice_state(value: object) -> str:
    """Return the lattice state name of a wire/feature value, or raise."""
    return _lattice_state("lattice", "value", value)


def lattice_rank(value: object) -> int:
    return LATTICE_RANK[lattice_state(value)]


def lattice_at_least(value: object, floor_state: str) -> bool:
    if floor_state not in LATTICE_RANK:
        raise ModelsRegistryError(f"lattice: unknown floor state {floor_state!r}")
    return lattice_rank(value) >= LATTICE_RANK[floor_state]


def _validate_policy(config: Mapping[str, Any]) -> Mapping[str, Any]:
    policy = _check_block(
        "policy", "policy", config["policy"], POLICY_SPEC, required=POLICY_SPEC
    )
    _check_block(
        "policy",
        "capabilityProbe",
        policy["capabilityProbe"],
        CAPABILITY_PROBE_SPEC,
        required=CAPABILITY_PROBE_SPEC,
    )
    hub = _check_block("policy", "hub", policy["hub"], HUB_SPEC, required=HUB_SPEC)
    if hub["host"] not in LOOPBACK_HOSTS:
        _fail("policy", "hub.host must be a loopback address (L4)")
    if hub["port"] > 65535:
        _fail("policy", f"hub.port {hub['port']} is not a valid TCP port")
    if hub["port"] in RESERVED_PORTS:
        _fail("policy", f"hub.port {hub['port']} is owned by another process (L4)")
    return policy


def _validate_locks(config: Mapping[str, Any]) -> set[str]:
    lock_ids: set[str] = set()
    for index, lock in enumerate(config["locks"]):
        block = _check_block(
            "locks", f"locks[{index}]", lock, LOCK_SPEC, required=LOCK_SPEC
        )
        lock_id: str = block["id"]
        if not LOCK_ID_RE.fullmatch(lock_id):
            _fail("locks", f"locks[{index}].id {lock_id!r} must look like L1")
        if lock_id in lock_ids:
            _fail("locks", f"duplicate lock id {lock_id!r}")
        lock_ids.add(lock_id)
    return lock_ids


def _port_is_forbidden(owner: str, port: int | None) -> bool:
    if port is None:
        return False
    if port == CURSOR_BRIDGE_PORT:
        return owner != CURSOR_BRIDGE_ENDPOINT
    return port in OWNED_PORTS or port == HUB_PORT


def _validate_base_url(owner: str, url: str, kind: str, openai_compatible: bool) -> str:
    parsed = urlsplit(url)
    host = parsed.hostname
    if parsed.scheme not in ("http", "https") or not host:
        _fail(owner, "baseUrl must be an http(s) URL with a host")
    if kind == "hosted" and parsed.scheme != "https":
        _fail(owner, "hosted baseUrl must use https://")
    if parsed.scheme == "http" and host not in LOOPBACK_HOSTS:
        _fail(owner, "http:// baseUrl is only allowed for loopback hosts")
    try:
        port = parsed.port
    except ValueError:
        _fail(owner, "baseUrl port is invalid")
    if _port_is_forbidden(owner, port):
        _fail(owner, f"baseUrl port {port} is owned by another process (L4)")
    if openai_compatible and (
        not parsed.path.endswith("/v1") or parsed.query or parsed.fragment
    ):
        _fail(owner, "baseUrl must end in /v1 for OpenAI-compatible api values")
    return host


def _host_covered(host: str, issuer: str) -> bool:
    return issuer == host or (issuer.startswith("*.") and host.endswith(issuer[1:]))


def _validate_auth(owner: str, auth: object, host: str) -> None:
    if auth is None:
        return
    block = _check_block(owner, "auth", auth, AUTH_SPEC, required=AUTH_SPEC)
    issuers: list[str] = block["issuerHosts"]
    if not any(_host_covered(host, issuer) for issuer in issuers):
        _fail(owner, f"auth.issuerHosts {issuers!r} do not cover baseUrl host {host!r}")


def _auth_names(endpoint: Mapping[str, Any]) -> frozenset[str]:
    auth = endpoint["auth"]
    if auth is None:
        return frozenset()
    return frozenset([auth["env"], *auth["altEnv"]])


def _validate_lattice_section(
    owner: str, section: str, block: Mapping[str, Any], keys: Iterable[str]
) -> None:
    _check_keys(owner, section, block, required=keys, allowed=keys)
    for key in keys:
        _lattice_state(owner, f"{section}.{key}", block[key])


def _validate_lattice_overrides(
    model_id: str,
    endpoint_id: str,
    section: str,
    override: Mapping[str, Any],
    endpoint_section: Mapping[str, Any],
    keys: Iterable[str],
) -> None:
    _check_keys(model_id, section, override, required=(), allowed=keys)
    for key, value in override.items():
        state = _lattice_state(model_id, f"{section}.{key}", value)
        endpoint_state = lattice_state(endpoint_section[key])
        if LATTICE_RANK[state] > LATTICE_RANK[endpoint_state]:
            _fail(
                model_id,
                f"{section}.{key} {state!r} exceeds endpoint {endpoint_id} value "
                f"{endpoint_state!r} (downward overrides only)",
            )


def _validate_targets(owner: str, targets: Mapping[str, Any]) -> None:
    _check_keys(owner, "targets", targets, required=RUNTIMES, allowed=RUNTIMES)
    for runtime, value in targets.items():
        if value not in TARGET_VALUES:
            _fail(owner, f"targets.{runtime} has unsupported value {value!r}")


def _validate_quirks(owner: str, quirks: object) -> None:
    block = _check_block(owner, "quirks", quirks, QUIRKS_SPEC)
    for section in QUIRK_SECTIONS:
        if section in block:
            _check_block(owner, f"quirks.{section}", block[section], QUIRK_SPEC)


def _validate_x_codex(owner: str, block: Mapping[str, Any]) -> None:
    if block.get("wire_api", "responses") != "responses":
        _fail(owner, "x_codex.wire_api must be 'responses' (never chat)")
    for header, value in block.get("http_headers", {}).items():
        _check_value(owner, f"x_codex.http_headers.{header}", value, "env")
    for name, value in block.get("query_params", {}).items():
        kind = "env" if is_credential_name(str(name)) else "str"
        _check_value(owner, f"x_codex.query_params.{name}", value, kind)


def _validate_x_openrouter(
    owner: str, block: Mapping[str, Any], auth_names: frozenset[str]
) -> None:
    for index, entry in enumerate(block.get("keys", [])):
        key = _check_block(
            owner,
            f"x_openrouter.keys[{index}]",
            entry,
            OPENROUTER_KEY_SPEC,
            required=OPENROUTER_KEY_REQUIRED,
        )
        if key["env"] not in auth_names:
            _fail(
                owner,
                f"x_openrouter.keys[{index}].env {key['env']!r} must be declared "
                "in auth.env or auth.altEnv",
            )
    if "guardrail" in block:
        _check_block(
            owner, "x_openrouter.guardrail", block["guardrail"], GUARDRAIL_SPEC
        )


def _validate_extensions(
    owner: str, row: Mapping[str, Any], auth_names: frozenset[str]
) -> None:
    for name in sorted(key for key in row if key.startswith("x_")):
        spec = X_BLOCK_SPECS.get(name)
        if spec is None:
            _fail(owner, f"unknown extension block {name!r}")
        block = _check_block(owner, name, row[name], spec)
        if name == "x_codex":
            _validate_x_codex(owner, block)
        elif name == "x_openrouter":
            _validate_x_openrouter(owner, block, auth_names)


def _required_deny_callers(endpoint_id: str) -> tuple[str, ...]:
    if endpoint_id == OPENROUTER_ENDPOINT:
        return ("cursor", "claude")
    if endpoint_id.startswith("cursor-"):
        return ("cursor",)
    return ()


def _check_deny_callers(owner: str, endpoint_id: str, callers: list[str]) -> None:
    for caller in _required_deny_callers(endpoint_id):
        if caller not in callers:
            _fail(
                owner,
                f"denyCallers must include {caller!r} (V15, endpoint {endpoint_id})",
            )


def _validate_endpoint(endpoint_id: str, row: object, lock_ids: set[str]) -> None:
    if not isinstance(row, Mapping):
        _fail(endpoint_id, "endpoint must be an object")
    core = {
        str(key): value for key, value in row.items() if not str(key).startswith("x_")
    }
    _check_block(
        endpoint_id, "endpoint", core, ENDPOINT_SPEC, required=ENDPOINT_REQUIRED
    )
    kind: str = row["kind"]
    if kind not in ENDPOINT_KINDS:
        _fail(
            endpoint_id,
            f"kind {kind!r} must be one of {', '.join(sorted(ENDPOINT_KINDS))}",
        )
    api: list[str] = row["api"]
    unsupported_api = [value for value in api if value not in API_VALUES]
    if unsupported_api:
        _fail(endpoint_id, f"api value {unsupported_api[0]!r} is unsupported")
    if len(set(api)) != len(api):
        _fail(endpoint_id, "api must not repeat values")
    host = _validate_base_url(
        endpoint_id,
        row["baseUrl"],
        kind,
        any(value.startswith("openai-") for value in api),
    )
    _validate_auth(endpoint_id, row["auth"], host)
    _validate_lattice_section(endpoint_id, "wire", row["wire"], WIRE_KEYS)
    _validate_lattice_section(endpoint_id, "features", row["features"], FEATURE_KEYS)
    _check_block(
        endpoint_id,
        "concurrency",
        row["concurrency"],
        CONCURRENCY_SPEC,
        required=CONCURRENCY_SPEC,
    )
    budget = _check_block(
        endpoint_id, "budget", row["budget"], BUDGET_SPEC, required=BUDGET_SPEC
    )
    if budget["costBasis"] not in COST_BASES:
        _fail(endpoint_id, f"budget.costBasis {budget['costBasis']!r} is unsupported")
    _check_block(
        endpoint_id, "resource", row["resource"], RESOURCE_SPEC, required=RESOURCE_SPEC
    )
    _validate_targets(endpoint_id, row["targets"])
    discovery = _check_block(
        endpoint_id,
        "discovery",
        row["discovery"],
        DISCOVERY_SPEC,
        required=("type", "timeoutMs"),
    )
    if discovery["type"] not in DISCOVERY_TYPES:
        _fail(endpoint_id, f"discovery.type {discovery['type']!r} is unsupported")
    health = _check_block(
        endpoint_id,
        "health",
        row["health"],
        HEALTH_SPEC,
        required=("kind", "timeoutMs"),
    )
    if health["kind"] not in HEALTH_KINDS:
        _fail(endpoint_id, f"health.kind {health['kind']!r} is unsupported")
    if health["kind"] == "http" and "path" not in health:
        _fail(endpoint_id, "health.path is required when health.kind is http")
    if "path" in health and not health["path"].startswith("/"):
        _fail(endpoint_id, "health.path must start with /")
    for lock_id in row["locks"]:
        if lock_id not in lock_ids:
            _fail(endpoint_id, f"locks reference undeclared lock {lock_id!r}")
    if "quirks" in row:
        _validate_quirks(endpoint_id, row["quirks"])
    _validate_extensions(endpoint_id, row, _auth_names(row))
    if endpoint_id == OPENROUTER_ENDPOINT and row.get("sidecarOnly") is not True:
        _fail(endpoint_id, "sidecarOnly must be true (L1)")
    if row.get("sidecarOnly") is True:
        for runtime in ("cursor", "claude"):
            if row["targets"][runtime] in SELECTED_TARGET_VALUES:
                _fail(
                    endpoint_id,
                    f"targets.{runtime} must be unsupported or excluded (L1)",
                )
    if endpoint_id == CURSOR_BRIDGE_ENDPOINT and "retiresWhen" not in row:
        _fail(endpoint_id, "retiresWhen is required (L3)")
    _check_deny_callers(endpoint_id, endpoint_id, row["denyCallers"])


def _validate_singletons(endpoints: Mapping[str, Any]) -> None:
    seen: dict[str, str] = {}
    for endpoint_id, row in endpoints.items():
        key = row.get("singletonKey")
        if not row["enabled"] or key is None:
            continue
        if key in seen:
            _fail(
                endpoint_id,
                f"singletonKey {key!r} is shared with enabled endpoint {seen[key]!r} (L3)",
            )
        seen[key] = endpoint_id


def _validate_model(model_id: str, row: object, endpoints: Mapping[str, Any]) -> None:
    if not isinstance(row, Mapping):
        _fail(model_id, "model must be an object")
    core = {
        str(key): value for key, value in row.items() if not str(key).startswith("x_")
    }
    _check_block(model_id, "model", core, MODEL_SPEC, required=MODEL_REQUIRED)
    endpoint_id: str = row["endpoint"]
    endpoint = endpoints.get(endpoint_id)
    if endpoint is None:
        _fail(model_id, f"endpoint {endpoint_id!r} is not declared")
    if row["status"] not in MODEL_STATUSES:
        _fail(model_id, f"status {row['status']!r} is unsupported")
    if row["tier"] not in MODEL_TIERS:
        _fail(model_id, f"tier {row['tier']!r} is unsupported")
    _check_block(
        model_id,
        "modalities",
        row["modalities"],
        MODALITIES_SPEC,
        required=MODALITIES_SPEC,
    )
    cost = _check_block(model_id, "cost", row["cost"], COST_SPEC, required=COST_SPEC)
    if cost["basis"] not in COST_BASES:
        _fail(model_id, f"cost.basis {cost['basis']!r} is unsupported")
    if cost["basis"] == "quota" and (
        cost["inputPer1M"] is not None or cost["outputPer1M"] is not None
    ):
        _fail(model_id, "quota-billed rows must carry null cost, never 0")
    if endpoint["kind"] == "local" and "resource" not in row:
        _fail(model_id, "resource.ramBytes is required on local endpoints")
    if "resource" in row:
        _check_block(
            model_id, "resource", row["resource"], RESOURCE_SPEC, required=RESOURCE_SPEC
        )
    if "quirks" in row:
        _validate_quirks(model_id, row["quirks"])
    for section, keys in (("wire", WIRE_KEYS), ("features", FEATURE_KEYS)):
        if section in row:
            _validate_lattice_overrides(
                model_id, endpoint_id, section, row[section], endpoint[section], keys
            )
    _check_deny_callers(model_id, endpoint_id, row["denyCallers"])
    _validate_extensions(model_id, row, _auth_names(endpoint))


def _require_enabled_model(
    owner: str, key: str, model_id: str, models: Mapping[str, Any]
) -> None:
    model = models.get(model_id)
    if model is None:
        _fail(owner, f"{key} names unknown model {model_id!r}")
    if model["enabled"] is not True:
        _fail(owner, f"{key} names disabled model {model_id!r}")


def _validate_slots(slots: Mapping[str, Any], models: Mapping[str, Any]) -> None:
    _check_keys("slots", "slots", slots, required=SLOT_NAMES, allowed=SLOT_NAMES)
    for slot in SLOT_NAMES:
        if slots[slot] is None:
            continue
        _check_value("slots", slot, slots[slot], "str")
        _require_enabled_model("slots", slot, slots[slot], models)


def _ram_warnings(
    policy: Mapping[str, Any], endpoints: Mapping[str, Any], models: Mapping[str, Any]
) -> list[str]:
    budget: int = policy["localRamBudgetBytes"]
    local_enabled = {
        endpoint_id
        for endpoint_id, row in endpoints.items()
        if row["enabled"] and row["kind"] == "local"
    }
    resident = sum(
        endpoints[endpoint_id]["resource"]["ramBytes"] for endpoint_id in local_enabled
    )
    largest_id: str | None = None
    largest = 0
    for model_id, row in models.items():
        if (
            row["enabled"]
            and row["endpoint"] in local_enabled
            and row["resource"]["ramBytes"] > largest
        ):
            largest_id, largest = model_id, row["resource"]["ramBytes"]
    total = resident + largest
    if total <= budget:
        return []
    return [
        f"local RAM: enabled local endpoints ({resident} bytes) + largest enabled local "
        f"model {largest_id!r} ({largest} bytes) = {total} bytes exceeds "
        f"policy.localRamBudgetBytes ({budget})"
    ]


def validate_registry(config: Mapping[str, Any]) -> list[str]:
    """Validate the whole registry; return warnings, raise on the first error."""
    if not isinstance(config, Mapping):
        raise ModelsRegistryError("registry: must be a JSON object")
    _reject_literal_secrets(config, "registry")
    _check_block(
        "registry", "registry", config, TOP_LEVEL_SPEC, required=TOP_LEVEL_SPEC
    )
    if config["schemaVersion"] != SCHEMA_VERSION:
        _fail("registry", f"schemaVersion must be {SCHEMA_VERSION}")
    policy = _validate_policy(config)
    lock_ids = _validate_locks(config)
    endpoints: Mapping[str, Any] = config["endpoints"]
    for endpoint_id, row in endpoints.items():
        _validate_endpoint(str(endpoint_id), row, lock_ids)
    _validate_singletons(endpoints)
    models: Mapping[str, Any] = config["models"]
    for model_id, row in models.items():
        _validate_model(str(model_id), row, endpoints)
    aliases: Mapping[str, Any] = config["aliases"]
    for alias, model_id in aliases.items():
        _check_value("aliases", str(alias), model_id, "str")
        _require_enabled_model("aliases", str(alias), model_id, models)
    _validate_slots(config["slots"], models)
    return _ram_warnings(policy, endpoints, models)


def load_registry(path: pathlib.Path | str = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    """Read and parse a registry file without validating it (see validate_registry)."""
    source = pathlib.Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ModelsRegistryError(
            f"{source}: invalid JSON ({error.msg} at line {error.lineno})"
        ) from error
    if not isinstance(payload, dict):
        raise ModelsRegistryError(f"{source}: registry must be a JSON object")
    return payload


def resolve_model(
    config: Mapping[str, Any], ref: str
) -> tuple[str, Mapping[str, Any], str, Mapping[str, Any]]:
    """Resolve ``<id>``, ``<id>@<endpoint>`` or an alias to its model and endpoint rows."""
    name, _, endpoint_ref = ref.partition("@")
    model_id: str = config["aliases"].get(name, name)
    model = config["models"].get(model_id)
    if model is None:
        raise ModelsRegistryError(f"unknown model reference {ref!r}")
    endpoint_id: str = model["endpoint"]
    if endpoint_ref and endpoint_ref != endpoint_id:
        raise ModelsRegistryError(
            f"{ref!r}: model {model_id!r} is served by endpoint {endpoint_id!r}, "
            f"not {endpoint_ref!r}"
        )
    return model_id, model, endpoint_id, config["endpoints"][endpoint_id]


def effective_capabilities(
    config: Mapping[str, Any], model_ref: str
) -> dict[str, dict[str, Any]]:
    """Endpoint wire/feature values with the model's downward overrides applied."""
    _, model, _, endpoint = resolve_model(config, model_ref)
    return {
        section: {**endpoint[section], **model.get(section, {})}
        for section in ("wire", "features")
    }


def _require_runtime(runtime: str) -> None:
    if runtime not in RUNTIMES:
        raise ModelsRegistryError(
            f"unsupported runtime {runtime!r}; expected one of {', '.join(RUNTIMES)}"
        )


def _unmet_floors(endpoint: Mapping[str, Any], runtime: str) -> list[str]:
    unmet: list[str] = []
    for path, floor in RUNTIME_FLOORS[runtime].items():
        section, _, key = path.partition(".")
        value = endpoint[section][key]
        if not lattice_at_least(value, floor):
            unmet.append(f"{section}:{key}={lattice_state(value)}<{floor}")
    return unmet


def _decide(endpoint: Mapping[str, Any], runtime: str) -> tuple[str, str, str | None]:
    hub_serves = bool(endpoint["enabled"]) and runtime not in endpoint["denyCallers"]
    alternative = "inference-hub" if hub_serves else None
    if runtime in MCP_ONLY_RUNTIMES:
        return "excluded", "runtime:mcp-only", alternative
    if not endpoint["enabled"]:
        return "excluded", "enabled:false", alternative
    target = endpoint["targets"][runtime]
    if target not in SELECTED_TARGET_VALUES:
        return "excluded", f"targets:{target}", alternative
    unmet = _unmet_floors(endpoint, runtime)
    if unmet:
        return "excluded", ";".join(unmet), alternative
    return "included", f"targets:{target}", None


def _wrappers(endpoint: Mapping[str, Any], runtime: str) -> str:
    state = lattice_state(endpoint["wire"][RUNTIME_WIRE.get(runtime, "completions")])
    if state in ("native", "probed"):
        return "ok"
    if state == "absent":
        return "broken"
    return "unprobed"


def select_target_endpoints(
    config: Mapping[str, Any], runtime: str
) -> dict[str, Mapping[str, Any]]:
    """Enabled endpoints a runtime may take natively, every runtime floor met."""
    _require_runtime(runtime)
    validate_registry(config)
    endpoints: Mapping[str, Any] = config["endpoints"]
    return {
        endpoint_id: endpoints[endpoint_id]
        for endpoint_id in sorted(endpoints)
        if _decide(endpoints[endpoint_id], runtime)[0] == "included"
    }


def select_target_models(
    config: Mapping[str, Any], runtime: str
) -> dict[str, Mapping[str, Any]]:
    """Enabled models served by the endpoints ``select_target_endpoints`` returns."""
    endpoints = select_target_endpoints(config, runtime)
    models: Mapping[str, Any] = config["models"]
    return {
        model_id: models[model_id]
        for model_id in sorted(models)
        if models[model_id]["enabled"] and models[model_id]["endpoint"] in endpoints
    }


def routing_report(config: Mapping[str, Any], runtime: str) -> list[dict[str, Any]]:
    """One row per endpoint explaining why the runtime does or does not take it."""
    _require_runtime(runtime)
    validate_registry(config)
    endpoints: Mapping[str, Any] = config["endpoints"]
    rows: list[dict[str, Any]] = []
    for endpoint_id in sorted(endpoints):
        endpoint = endpoints[endpoint_id]
        decision, reason, alternative = _decide(endpoint, runtime)
        rows.append(
            {
                "endpoint": endpoint_id,
                "runtime": runtime,
                "decision": decision,
                "reason": reason,
                "alternative": alternative,
                "wrappers": _wrappers(endpoint, runtime),
            }
        )
    return rows


def credential_names(config: Mapping[str, Any]) -> list[str]:
    """Sorted union of ``auth.env`` and ``auth.altEnv`` over enabled endpoints."""
    names: set[str] = set()
    for endpoint in config["endpoints"].values():
        if endpoint["enabled"]:
            names.update(_auth_names(endpoint))
    return sorted(names)


def registry_hash(config: Mapping[str, Any]) -> str:
    """First 16 hex digits of the sha256 of the canonical JSON; the managed-by marker."""
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
