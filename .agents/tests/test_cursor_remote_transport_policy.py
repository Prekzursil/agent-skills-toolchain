from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
from copy import deepcopy
from typing import Any

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_script(name: str) -> Any:
    path = SCRIPTS / f"{name}.py"
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def live_registry() -> dict[str, Any]:
    return json.loads((ROOT / "agents.json").read_text(encoding="utf-8"))


def test_context7_is_remote_https_credentialed_http_not_per_session_npx() -> None:
    server = live_registry()["mcp"]["servers"]["context7"]
    assert server["transport"] == "http"
    assert server["url"] == "https://mcp.context7.com/mcp"
    assert server["headers"] == {"Authorization": "Bearer ${CONTEXT7_API_KEY}"}
    assert "CONTEXT7_API_KEY" in server["requiredEnv"]
    assert server["x_codex"]["bearer_token_env_var"] == "CONTEXT7_API_KEY"
    assert "command" not in server
    assert "args" not in server
    assert "stdio" not in server["tags"]
    assert "http" in server["tags"]
    assert "remote" in server["tags"]
    assert "remote-required" in server["tags"]


def test_firecrawl_is_local_loopback_http_credentialless_not_per_session_npx() -> None:
    # 2026-09-24: firecrawl was repointed to a local self-host gateway
    # (mcp-proxy :31114 -> firecrawl docker stack :3002, no credits), so it is a
    # loopback HTTP endpoint that carries no credential. It is still a resident
    # HTTP server, never a per-session npx process tree, and -- because it holds
    # no secret and never leaves the loopback interface -- it is exempt from the
    # remote-TLS requirement that credential-bearing servers (e.g. context7) keep.
    server = live_registry()["mcp"]["servers"]["firecrawl"]
    assert server["transport"] == "http"
    assert server["url"] == "http://127.0.0.1:31114/mcp"
    assert server["url"].startswith("http://127.0.0.1")
    assert server.get("credentialNames", []) == []
    assert "headers" not in server
    assert "requiredEnv" not in server
    assert "command" not in server
    assert "args" not in server
    assert "stdio" not in server["tags"]
    assert "http" in server["tags"]


def test_cursor_renderer_preserves_context7_remote_http_and_secret_reference() -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    servers = live_registry()["mcp"]["servers"]
    entry = cursor.build_cursor_server("context7", servers["context7"])
    assert entry is not None
    assert entry["url"].startswith("https://")
    assert entry["headers"]["Authorization"] == "Bearer ${env:CONTEXT7_API_KEY}"
    assert "command" not in entry
    assert "args" not in entry


def test_cursor_renderer_projects_firecrawl_local_http_without_credential() -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    servers = live_registry()["mcp"]["servers"]
    entry = cursor.build_cursor_server("firecrawl", servers["firecrawl"])
    assert entry is not None
    assert entry["url"] == "http://127.0.0.1:31114/mcp"
    # credential-less local gateway: the renderer injects no Authorization header
    assert "headers" not in entry
    assert "command" not in entry
    assert "args" not in entry


def test_core_local_process_budget_is_two_browser_servers_plus_bm_proxy() -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    servers = live_registry()["mcp"]["servers"]
    rendered = {
        name: cursor.build_cursor_server(name, servers[name])
        for name in cursor.CURSOR_DEFAULT_APPROVED_SERVERS
    }
    local = {
        name
        for name, entry in rendered.items()
        if isinstance(entry, dict) and "command" in entry
    }
    assert local == {"basic-memory", "chrome-devtools", "playwright"}


@pytest.mark.parametrize("name", ["context7", "firecrawl"])
@pytest.mark.parametrize("drop_tag", [False, True])
def test_remote_required_transport_drift_fails_registry_validation(
    name: str,
    drop_tag: bool,
) -> None:
    control = load_script("mcp_control_plane")
    config = deepcopy(live_registry())
    server = config["mcp"]["servers"][name]
    server["transport"] = "stdio"
    server["command"] = "npx"
    server["args"] = ["-y", "package"]
    server.pop("url", None)
    server.pop("headers", None)
    if drop_tag:
        server["tags"].remove("remote-required")

    with pytest.raises(
        control.RegistryError,
        match="remote-required server must use http transport",
    ):
        control.validate_registry(config)


@pytest.mark.parametrize("name", ["context7", "firecrawl"])
def test_http_transport_rejects_leftover_stdio_fields(name: str) -> None:
    control = load_script("mcp_control_plane")
    config = deepcopy(live_registry())
    server = config["mcp"]["servers"][name]
    server["command"] = "npx"
    server["args"] = ["-y", "stale-package"]

    with pytest.raises(
        control.RegistryError,
        match="http transport cannot declare command or args",
    ):
        control.validate_registry(config)


# firecrawl dropped from this parametrize on 2026-09-24: it is now a
# credential-less loopback gateway (credentialNames == []), so the
# credential-bearing-http-requires-TLS rule does not apply to it. context7 remains
# the remote, credential-bearing http server the rule must keep guarding.
@pytest.mark.parametrize("name", ["context7"])
def test_credential_bearing_http_server_requires_tls(name: str) -> None:
    control = load_script("mcp_control_plane")
    config = deepcopy(live_registry())
    config["mcp"]["servers"][name]["url"] = "http://example.invalid/mcp"

    with pytest.raises(
        control.RegistryError,
        match="credential-bearing http server must use https",
    ):
        control.validate_registry(config)


@pytest.mark.parametrize(
    "literal",
    ["ctx7sk-test-literal-not-a-real-key", "fc-test-literal-not-a-real-key"],
)
def test_provider_key_prefixes_are_rejected_in_any_header(literal: str) -> None:
    control = load_script("mcp_control_plane")
    config = deepcopy(live_registry())
    config["mcp"]["servers"]["context7"]["headers"]["X-Extra-Cookie"] = literal

    with pytest.raises(control.RegistryError, match="literal credential"):
        control.validate_registry(config)
