from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import platform
import subprocess
import sys
from typing import Any

import pytest


AGENTS_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = AGENTS_ROOT / "scripts"


def load_script(name: str) -> Any:
    path = SCRIPTS_ROOT / f"{name}.py"
    assert path.is_file(), f"missing control-plane module: {path}"
    if str(SCRIPTS_ROOT) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def registry(servers: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for name, server in servers.items():
        required = set(server.get("requiredEnv", []))
        server.setdefault(
            "credentialNames",
            sorted(item for item in required if "TOKEN" in item or "KEY" in item or "SECRET" in item),
        )
        server.setdefault("tags", ["test"])
    return {
        "schemaVersion": 1,
        "mcp": {
            "policy": {
                "required": False,
                "startupTimeoutMs": 30_000,
                "toolTimeoutMs": 30_000,
                "healthProbe": {"kind": "mcp-tools-list", "timeoutMs": 30_000},
                "toolAllowlist": ["*"],
                "approvalMode": "native",
                "maxPrivateBytes": 512 * 1024 * 1024,
            },
            "supervision": {
                "totalIdlePrivateBytes": 6 * 1024 * 1024 * 1024,
                "failureThreshold": 3,
                "failureWindowSeconds": 600,
                "quarantineScope": "session",
                "duplicatePolicy": "report-unless-exact-process-tree",
            },
            "servers": servers,
        },
    }


def stdio_server(*targets: str, **extra: Any) -> dict[str, Any]:
    server: dict[str, Any] = {
        "enabled": True,
        "targets": list(targets),
        "transport": "stdio",
        "command": "example-mcp",
        "args": [],
    }
    server.update(extra)
    return server


def test_enabled_servers_require_at_least_one_explicit_target() -> None:
    control = load_script("mcp_control_plane")
    config = registry({"orphan": stdio_server()})

    with pytest.raises(control.RegistryError, match="nonempty targets"):
        control.validate_registry(config)


def test_literal_credentials_are_rejected_before_any_output_is_rendered() -> None:
    control = load_script("mcp_control_plane")
    config = registry(
        {
            "unsafe": stdio_server(
                "claude",
                env={"EXAMPLE_API_TOKEN": "literal-credential"},
                requiredEnv=["EXAMPLE_API_TOKEN"],
            )
        }
    )

    with pytest.raises(control.RegistryError, match="credential reference"):
        control.validate_registry(config)


def test_reference_only_credentials_render_without_secret_values() -> None:
    control = load_script("mcp_control_plane")
    claude = load_script("merge_generated_claude_mcp")
    codex = load_script("merge_generated_codex_mcp")
    config = registry(
        {
            "safe": stdio_server(
                "claude",
                "codex",
                env={"EXAMPLE_API_TOKEN": "${EXAMPLE_API_TOKEN}"},
                requiredEnv=["EXAMPLE_API_TOKEN"],
                x_codex={"env_vars": ["EXAMPLE_API_TOKEN"]},
            )
        }
    )

    control.validate_registry(config)
    claude_text = json.dumps(claude.build_managed_servers_from_agents(config))
    codex_text = "\n".join(
        block.text for block in codex.build_managed_blocks_from_agents(config)
    )

    assert "literal-credential" not in claude_text
    assert "literal-credential" not in codex_text
    assert "${EXAMPLE_API_TOKEN}" in claude_text
    assert 'env_vars = ["EXAMPLE_API_TOKEN"]' in codex_text


def test_claude_http_renderer_declares_http_transport() -> None:
    claude = load_script("merge_generated_claude_mcp")
    config = registry(
        {
            "agent-mail": {
                "enabled": True,
                "targets": ["claude"],
                "transport": "http",
                "url": "http://127.0.0.1:8811/mcp/",
            }
        }
    )

    rendered = claude.build_managed_servers_from_agents(config)

    assert rendered["agent-mail"] == {
        "type": "http",
        "url": "http://127.0.0.1:8811/mcp/",
    }


def test_reference_view_publisher_never_interpolates_environment_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publisher = load_script("publish_reference_views")
    config = registry(
        {
            "remote": {
                "enabled": True,
                "targets": ["claude", "codex"],
                "transport": "http",
                "url": "https://example.invalid/mcp",
                "requiredEnv": ["EXAMPLE_API_TOKEN"],
                "x_codex": {"bearer_token_env_var": "EXAMPLE_API_TOKEN"},
            }
        }
    )
    monkeypatch.setenv("EXAMPLE_API_TOKEN", "literal-secret-must-not-render")

    claude_text, codex_text = publisher.render_views(config)

    assert "literal-secret-must-not-render" not in claude_text
    assert "literal-secret-must-not-render" not in codex_text
    assert "Bearer ${EXAMPLE_API_TOKEN}" in claude_text
    assert 'bearer_token_env_var = "EXAMPLE_API_TOKEN"' in codex_text


def test_http_bearer_credentials_do_not_render_stdio_env_vars() -> None:
    codex = load_script("merge_generated_codex_mcp")
    config = registry(
        {
            "remote": {
                "enabled": True,
                "targets": ["codex"],
                "transport": "http",
                "url": "https://example.invalid/mcp",
                "requiredEnv": ["EXAMPLE_API_TOKEN"],
                "env": {"EXAMPLE_API_TOKEN": "${EXAMPLE_API_TOKEN}"},
                "x_codex": {"bearer_token_env_var": "EXAMPLE_API_TOKEN"},
            }
        }
    )

    rendered = "\n".join(
        block.text for block in codex.build_managed_blocks_from_agents(config)
    )

    assert 'bearer_token_env_var = "EXAMPLE_API_TOKEN"' in rendered
    assert "env_vars" not in rendered


def test_provider_renderers_refuse_an_unsafe_registry() -> None:
    control = load_script("mcp_control_plane")
    claude = load_script("merge_generated_claude_mcp")
    codex = load_script("merge_generated_codex_mcp")
    config = registry(
        {
            "unsafe": stdio_server(
                "claude",
                "codex",
                env={"EXAMPLE_API_TOKEN": "literal-credential"},
                requiredEnv=["EXAMPLE_API_TOKEN"],
            )
        }
    )

    with pytest.raises(control.RegistryError, match="credential reference"):
        claude.build_managed_servers_from_agents(config)
    with pytest.raises(control.RegistryError, match="credential reference"):
        codex.build_managed_blocks_from_agents(config)


def test_codex_import_replaces_literal_credentials_with_references() -> None:
    importer = load_script("import_codex_mcp")
    imported = importer.convert_server(
        "example",
        {
            "command": "example-mcp",
            "env": {
                "EXAMPLE_API_TOKEN": "literal-credential",
                "EXAMPLE_ENDPOINT": "https://example.invalid",
            },
            "http_headers": {"X-API-Key": "another-literal"},
        },
    )

    assert imported["env"]["EXAMPLE_API_TOKEN"] == "${EXAMPLE_API_TOKEN}"
    assert imported["env"]["EXAMPLE_ENDPOINT"] == "https://example.invalid"
    assert imported["headers"]["X-API-Key"].startswith("${")
    assert "literal-credential" not in json.dumps(imported)
    assert "another-literal" not in json.dumps(imported)


def test_duplicate_singleton_keys_are_rejected() -> None:
    control = load_script("mcp_control_plane")
    duplicate = stdio_server("claude", singletonKey="shared/example")
    config = registry(
        {
            "example-primary": duplicate,
            "example-alias": dict(duplicate),
        }
    )

    with pytest.raises(control.RegistryError, match="duplicate singletonKey"):
        control.validate_registry(config)


def test_effective_contract_is_decision_complete() -> None:
    control = load_script("mcp_control_plane")
    config = registry({"example": stdio_server("claude")})

    contract = control.effective_server_contract(config, "example")

    assert set(contract) == {
        "id",
        "transport",
        "command",
        "url",
        "targets",
        "enabled",
        "required",
        "credentialNames",
        "startupTimeoutMs",
        "toolTimeoutMs",
        "healthProbe",
        "toolAllowlist",
        "approvalMode",
        "singletonKey",
        "tags",
        "maxPrivateBytes",
    }
    assert contract["startupTimeoutMs"] == 30_000
    assert contract["maxPrivateBytes"] == 512 * 1024 * 1024


def test_atomic_write_never_publishes_partial_content(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    control = load_script("mcp_control_plane")
    target = tmp_path / "config.json"
    target.write_text("original\n", encoding="utf-8")

    def fail_replace(_source: object, _target: object) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(control.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        control.atomic_write_text(target, "new content\n")

    assert target.read_text(encoding="utf-8") == "original\n"
    assert not list(tmp_path.glob(".config.json.*.tmp"))


def test_generated_names_exactly_match_target_manifest_and_skip_plugins() -> None:
    control = load_script("mcp_control_plane")
    claude = load_script("merge_generated_claude_mcp")
    codex = load_script("merge_generated_codex_mcp")
    config = registry(
        {
            "both": stdio_server("claude", "codex"),
            "claude-only": stdio_server("claude"),
            "codex-only": stdio_server("codex"),
            "sourcegraph": stdio_server("claude"),
        }
    )

    claude_servers = claude.build_managed_servers_from_agents(config)
    codex_names = {
        parsed[0]
        for block in codex.build_managed_blocks_from_agents(config)
        if (parsed := codex.parse_mcp_header(block.header)) is not None
    }

    assert set(claude_servers) == control.expected_target_names(
        config, "claude", plugin_provided=claude.PLUGIN_PROVIDED_SERVERS
    )
    assert set(claude_servers) == {"both", "claude-only"}
    assert codex_names == control.expected_target_names(config, "codex")
    assert codex_names == {"both", "codex-only"}


def test_live_registry_has_shared_basic_memory_and_no_retired_sidecar() -> None:
    config = json.loads((AGENTS_ROOT / "agents.json").read_text(encoding="utf-8"))
    servers = config["mcp"]["servers"]

    assert servers["basic-memory"]["targets"] == ["codex", "claude"]
    assert "codex_consult" not in servers
    assert "memory" not in servers

    codex = load_script("merge_generated_codex_mcp")
    rendered = "\n".join(
        block.text for block in codex.build_managed_blocks_from_agents(config)
    )
    assert "codex_consult" not in rendered


def test_rotation_manifest_file_is_absent_never_rotate() -> None:
    path = SCRIPTS_ROOT / "credential_rotation_manifest.json"
    assert not path.exists(), "owner 2026-08-28: never rotate; manifest must stay deleted"


def test_validate_control_plane_missing_rotation_manifest_is_never_rotate() -> None:
    script = SCRIPTS_ROOT / "validate_mcp_control_plane.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--agents-config",
            str(AGENTS_ROOT / "agents.json"),
            "--rotation-manifest",
            str(SCRIPTS_ROOT / "credential_rotation_manifest.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "SUCCESS:mcp-control-plane-validate" in result.stdout
    assert "rotation_providers=0" in result.stdout
    assert "rotation_policy=never" in result.stdout


def test_codex_merge_removes_retired_promptbridge_sidecar(
    tmp_path: pathlib.Path,
) -> None:
    live = tmp_path / "config.toml"
    live.write_text(
        "\n".join(
            [
                'model = "gpt-5.6-sol"',
                "",
                "# >>> promptbridge-codex managed >>>",
                "[mcp_servers.codex_consult]",
                'command = "old-node"',
                'args = ["old-server.mjs"]',
                "",
                "[mcp_servers.codex_consult.env]",
                'PROMPTBRIDGE_CODEX_HOME = "old"',
                "# <<< promptbridge-codex managed <<<",
                "",
            ]
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "agents.json"
    config_path.write_text(
        json.dumps(
            registry(
                {
                    "active": stdio_server("codex")
                }
            )
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_ROOT / "merge_generated_codex_mcp.py"),
            "--live",
            str(live),
            "--agents-config",
            str(config_path),
            "--write",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    merged = live.read_text(encoding="utf-8")
    assert "promptbridge-codex managed" not in merged
    assert "codex_consult" not in merged
    assert merged.count('[mcp_servers."active"]') == 1
    assert 'model = "gpt-5.6-sol"' in merged


CURSOR_CORE_APPROVED = frozenset(
    {
        "agent-mail",
        "basic-memory",
        "chrome-devtools",
        "context7",
        "firecrawl",
        "playwright",
    }
)

CURSOR_NEVER_MOUNT = ("tavily", "markitdown", "meta-tool", "mixpanel", "mixpanel-mcp")

LINKEDIN_SERVER_ARG = (
    "C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp"
    "\\linkedin-mcp\\server.py"
)


def live_registry() -> dict[str, Any]:
    return json.loads((AGENTS_ROOT / "agents.json").read_text(encoding="utf-8"))


def approval_ids(*names: str) -> list[str]:
    """Build Cursor approval IDs (``<server>-<16 hex>``) for a fixture store."""
    return [
        f"{name}-{hashlib.sha256(name.encode('utf-8')).hexdigest()[:16]}"
        for name in names
    ]


def write_approvals(path: pathlib.Path, payload: Any) -> pathlib.Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def cursor_registry_fixture() -> dict[str, Any]:
    """Core six plus one safe non-core server plus every never-mount name."""
    servers: dict[str, Any] = {
        "agent-mail": {
            "enabled": True,
            "targets": ["claude"],
            "transport": "http",
            "url": "http://127.0.0.1:18812/mcp/",
        },
        "docker": stdio_server("claude", command="uvx", args=["docker-mcp"]),
        "markitdown": stdio_server("claude", command="markitdown-mcp.exe"),
        "meta-tool": stdio_server("claude", command="node"),
        "tavily": {
            "enabled": True,
            "targets": ["claude"],
            "transport": "http",
            "url": "https://mcp.tavily.com/mcp/",
        },
    }
    for name in sorted(CURSOR_CORE_APPROVED - {"agent-mail"}):
        if name in {"context7", "firecrawl"}:
            env_name = (
                "CONTEXT7_API_KEY" if name == "context7" else "FIRECRAWL_API_KEY"
            )
            servers[name] = {
                "enabled": True,
                "targets": ["claude"],
                "transport": "http",
                "url": f"https://mcp.{name}.example/mcp",
                "headers": {"Authorization": f"Bearer ${{{env_name}}}"},
                "requiredEnv": [env_name],
                "credentialNames": [env_name],
                "x_codex": {"bearer_token_env_var": env_name},
                "tags": ["test", "remote", "http", "remote-required"],
            }
        else:
            servers[name] = stdio_server(
                "claude", command="uvx", args=[f"{name}-mcp"]
            )
    return registry(servers)


def run_cursor_merge(*extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS_ROOT / "merge_generated_cursor_mcp.py"), *extra],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cursor_safe_default_attaches_core_plus_owner_requested_adapters() -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    generated = {
        "context7": {"command": "npx", "args": ["@upstash/context7-mcp"]},
        "docker": {"command": "uvx", "args": ["docker-mcp"]},
        "glm53-space": {"command": "python.exe", "args": ["mcp_server.py"]},
        "linkedin": {"command": "python.exe", "args": ["server.py"]},
        "sonarqube": {"command": "docker", "args": ["run", "mcp/sonarqube"]},
    }

    merged = cursor.merge_cursor_mcp_servers({}, generated)

    assert cursor.CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS == (
        CURSOR_CORE_APPROVED | {"glm53-space"}
    )
    assert cursor.CURSOR_DEFAULT_APPROVED_SERVERS == CURSOR_CORE_APPROVED
    assert set(merged) == {"context7", "glm53-space"}


def test_cursor_attach_all_safe_projects_every_safe_definition() -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    generated = {
        "context7": {"command": "npx", "args": ["@upstash/context7-mcp"]},
        "docker": {"command": "uvx", "args": ["docker-mcp"]},
        "linkedin": {"command": "python.exe", "args": ["server.py"]},
        "sonarqube": {"command": "docker", "args": ["run", "mcp/sonarqube"]},
    }

    merged = cursor.merge_cursor_mcp_servers({}, generated, attach_all_safe=True)

    assert set(merged) == set(generated)


def test_cursor_never_mounts_excluded_names_even_if_generated_regresses() -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    regressed = {name: {"command": "npx", "args": [name]} for name in CURSOR_NEVER_MOUNT}
    regressed["context7"] = {"command": "npx", "args": ["@upstash/context7-mcp"]}
    stale_live = {name: {"command": "npx", "args": [name]} for name in CURSOR_NEVER_MOUNT}

    default_merge = cursor.merge_cursor_mcp_servers(stale_live, regressed)
    attach_all = cursor.merge_cursor_mcp_servers(
        stale_live, regressed, attach_all_safe=True
    )

    assert set(default_merge) == {"context7"}
    assert set(attach_all) == {"context7"}
    for name in CURSOR_NEVER_MOUNT:
        assert name not in default_merge
        assert name not in attach_all


def test_cursor_attach_all_preserves_safe_manual_live_entries() -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    live = {
        "hand-rolled": {"command": "node", "args": ["local-server.mjs"]},
        "markitdown": {"command": "markitdown-mcp.exe", "args": []},
        "stale-disabled": {"command": "node", "args": ["x.mjs"], "disabled": True},
    }
    generated = {"context7": {"command": "npx", "args": ["@upstash/context7-mcp"]}}

    attach_all = cursor.merge_cursor_mcp_servers(live, generated, attach_all_safe=True)
    default_merge = cursor.merge_cursor_mcp_servers(live, generated)

    assert set(attach_all) == {"hand-rolled", "stale-disabled", "context7"}
    assert attach_all["hand-rolled"] == {"command": "node", "args": ["local-server.mjs"]}
    assert "disabled" not in attach_all["stale-disabled"]
    assert set(default_merge) == {"context7"}


def test_cursor_merge_never_emits_disabled_and_is_stable_in_both_modes() -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    live = {
        "context7": {"command": "npx", "args": ["@upstash/context7-mcp"], "disabled": True},
        "docker": {"command": "uvx", "args": ["docker-mcp"], "disabled": True},
    }
    generated = {
        "context7": {"command": "npx", "args": ["@upstash/context7-mcp"]},
        "docker": {"command": "uvx", "args": ["docker-mcp"]},
    }

    for attach_all_safe in (False, True):
        first = cursor.merge_cursor_mcp_servers(
            live, generated, attach_all_safe=attach_all_safe
        )
        second = cursor.merge_cursor_mcp_servers(
            first, generated, attach_all_safe=attach_all_safe
        )
        third = cursor.merge_cursor_mcp_servers(
            second, generated, attach_all_safe=attach_all_safe
        )

        assert first == second == third
        assert "disabled" not in json.dumps(third)


def test_cursor_approval_store_ids_map_to_server_names(tmp_path: pathlib.Path) -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    store = write_approvals(
        tmp_path / "mcp-approvals.json",
        approval_ids("agent-mail", "binary-ninja-mcp", "chrome-devtools"),
    )

    assert cursor.parse_cursor_approvals(store) == frozenset(
        {"agent-mail", "binary-ninja-mcp", "chrome-devtools"}
    )


def test_cursor_approval_evidence_fails_closed_when_missing(
    tmp_path: pathlib.Path,
) -> None:
    cursor = load_script("merge_generated_cursor_mcp")

    with pytest.raises(cursor.ApprovalEvidenceError, match="unreadable"):
        cursor.parse_cursor_approvals(tmp_path / "absent.json")


@pytest.mark.parametrize(
    "payload",
    [
        {"approved": ["agent-mail-0123456789abcdef"]},
        ["agent-mail-0123456789abcdef", 17],
        ["agent-mail"],
        ["agent-mail-nothexadecimal01"],
        "agent-mail-0123456789abcdef",
    ],
)
def test_cursor_approval_evidence_fails_closed_when_malformed(
    tmp_path: pathlib.Path, payload: Any
) -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    store = write_approvals(tmp_path / "mcp-approvals.json", payload)

    with pytest.raises(cursor.ApprovalEvidenceError, match="malformed"):
        cursor.parse_cursor_approvals(store)


def test_cursor_approval_evidence_fails_closed_on_invalid_json(
    tmp_path: pathlib.Path,
) -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    store = tmp_path / "mcp-approvals.json"
    store.write_text("[not json", encoding="utf-8")

    with pytest.raises(cursor.ApprovalEvidenceError, match="malformed"):
        cursor.parse_cursor_approvals(store)


def test_cursor_approval_gate_refuses_any_non_default_approval(
    tmp_path: pathlib.Path,
) -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    store = write_approvals(
        tmp_path / "mcp-approvals.json",
        approval_ids("agent-mail", "context7", "sonarqube", "docker"),
    )

    with pytest.raises(cursor.ApprovalEvidenceError, match="docker, sonarqube"):
        cursor.load_safe_default_approvals(store)


def test_cursor_approval_gate_accepts_core_and_empty_stores(
    tmp_path: pathlib.Path,
) -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    core_only = write_approvals(
        tmp_path / "core.json", approval_ids(*sorted(CURSOR_CORE_APPROVED))
    )
    empty = write_approvals(tmp_path / "empty.json", [])

    assert cursor.load_safe_default_approvals(core_only) == CURSOR_CORE_APPROVED
    assert cursor.load_safe_default_approvals(empty) == frozenset()


def test_cursor_approval_gate_accepts_owner_requested_default_adapter(
    tmp_path: pathlib.Path,
) -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    store = write_approvals(
        tmp_path / "mcp-approvals.json",
        approval_ids(*sorted(CURSOR_CORE_APPROVED | {"glm53-space"})),
    )

    assert cursor.load_safe_default_approvals(store) == (
        CURSOR_CORE_APPROVED | {"glm53-space"}
    )


def test_cursor_basic_memory_uses_session_proxy_not_raw_url() -> None:
    # Reunited contract (2026-09-02): the bridge is DECLARED in the registry
    # (``x_cursor.stdio_bridge`` on the basic-memory entry) and rendered from
    # there, instead of being a name-based special case inside the merge script.
    cursor = load_script("merge_generated_cursor_mcp")
    registry = json.loads((AGENTS_ROOT / "agents.json").read_text(encoding="utf-8"))
    declared = registry["mcp"]["servers"]["basic-memory"]
    assert declared["transport"] == "http"
    assert declared["url"] == "http://127.0.0.1:18765/mcp"
    assert "stdio_bridge" in declared.get("x_cursor", {})
    entry = cursor.build_cursor_server("basic-memory", declared)
    assert "url" not in entry
    bridge = declared["x_cursor"]["stdio_bridge"]
    assert entry["command"] == bridge["command"]
    # The renderer appends the registry URL so the bridge dials the declared
    # daemon address rather than a constant baked into the script.
    assert entry["args"][: len(bridge["args"])] == bridge["args"]
    assert entry["args"][len(bridge["args"]) :] == ["--url", declared["url"]]
    assert "--stdio" in entry["args"]
    assert pathlib.Path(bridge["args"][0]).is_file()


def test_cursor_default_dry_run_projects_core_plus_owner_adapters(
    tmp_path: pathlib.Path,
) -> None:
    live = tmp_path / "mcp.json"
    live.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")

    completed = run_cursor_merge(
        "--live", str(live), "--agents-config", str(AGENTS_ROOT / "agents.json")
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "attached=7" in completed.stdout
    assert "core_attached=6" in completed.stdout
    assert "noncore_projected=1" in completed.stdout
    assert "attach_all_safe=false" in completed.stdout
    assert "approval_proof=not-required" in completed.stdout
    assert "enabled=" not in completed.stdout
    assert json.loads(live.read_text(encoding="utf-8"))["mcpServers"] == {}


def test_cursor_attach_all_dry_run_projects_the_full_safe_surface(
    tmp_path: pathlib.Path,
) -> None:
    live = tmp_path / "mcp.json"
    live.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")

    completed = run_cursor_merge(
        "--live",
        str(live),
        "--agents-config",
        str(AGENTS_ROOT / "agents.json"),
        "--attach-all-safe",
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "attached=39" in completed.stdout
    assert "core_attached=6" in completed.stdout
    assert "noncore_projected=33" in completed.stdout
    assert "approval_proof=dry-run-unverified" in completed.stdout
    assert json.loads(live.read_text(encoding="utf-8"))["mcpServers"] == {}


def test_cursor_attach_all_write_refuses_without_approval_evidence(
    tmp_path: pathlib.Path,
) -> None:
    live = tmp_path / "mcp.json"
    live.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
    config_path = tmp_path / "agents.json"
    config_path.write_text(json.dumps(cursor_registry_fixture()), encoding="utf-8")

    completed = run_cursor_merge(
        "--live",
        str(live),
        "--agents-config",
        str(config_path),
        "--attach-all-safe",
        "--write",
        "--no-backup",
    )

    assert completed.returncode != 0
    assert "FAILED:mcp-cursor-merge" in completed.stderr
    assert "--approvals-file" in completed.stderr
    assert json.loads(live.read_text(encoding="utf-8"))["mcpServers"] == {}


def test_cursor_attach_all_write_refuses_unreadable_approval_evidence(
    tmp_path: pathlib.Path,
) -> None:
    live = tmp_path / "mcp.json"
    live.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
    config_path = tmp_path / "agents.json"
    config_path.write_text(json.dumps(cursor_registry_fixture()), encoding="utf-8")

    completed = run_cursor_merge(
        "--live",
        str(live),
        "--agents-config",
        str(config_path),
        "--attach-all-safe",
        "--write",
        "--no-backup",
        "--approvals-file",
        str(tmp_path / "absent.json"),
    )

    assert completed.returncode != 0
    assert "FAILED:mcp-cursor-merge" in completed.stderr
    assert "unreadable" in completed.stderr
    assert json.loads(live.read_text(encoding="utf-8"))["mcpServers"] == {}


def test_cursor_attach_all_write_refuses_non_core_approvals(
    tmp_path: pathlib.Path,
) -> None:
    live = tmp_path / "mcp.json"
    live.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
    config_path = tmp_path / "agents.json"
    config_path.write_text(json.dumps(cursor_registry_fixture()), encoding="utf-8")
    store = write_approvals(
        tmp_path / "mcp-approvals.json",
        approval_ids("agent-mail", "context7", "docker"),
    )

    completed = run_cursor_merge(
        "--live",
        str(live),
        "--agents-config",
        str(config_path),
        "--attach-all-safe",
        "--write",
        "--no-backup",
        "--approvals-file",
        str(store),
    )

    assert completed.returncode != 0
    assert "FAILED:mcp-cursor-merge" in completed.stderr
    assert "docker" in completed.stderr
    assert json.loads(live.read_text(encoding="utf-8"))["mcpServers"] == {}


def test_cursor_attach_all_write_permits_safe_default_approvals(
    tmp_path: pathlib.Path,
) -> None:
    live = tmp_path / "mcp.json"
    live.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
    config_path = tmp_path / "agents.json"
    config_path.write_text(json.dumps(cursor_registry_fixture()), encoding="utf-8")
    store = write_approvals(
        tmp_path / "mcp-approvals.json", approval_ids(*sorted(CURSOR_CORE_APPROVED))
    )

    completed = run_cursor_merge(
        "--live",
        str(live),
        "--agents-config",
        str(config_path),
        "--attach-all-safe",
        "--write",
        "--no-backup",
        "--approvals-file",
        str(store),
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    written = json.loads(live.read_text(encoding="utf-8"))["mcpServers"]
    assert set(written) == CURSOR_CORE_APPROVED | {"docker"}
    assert "disabled" not in json.dumps(written)
    assert "approval_proof=safe-default-only-verified" in completed.stdout
    assert "noncore_projected=1" in completed.stdout


def test_cursor_default_write_stays_core_six_without_approval_evidence(
    tmp_path: pathlib.Path,
) -> None:
    live = tmp_path / "mcp.json"
    live.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
    config_path = tmp_path / "agents.json"
    config_path.write_text(json.dumps(cursor_registry_fixture()), encoding="utf-8")

    completed = run_cursor_merge(
        "--live",
        str(live),
        "--agents-config",
        str(config_path),
        "--write",
        "--no-backup",
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    written = json.loads(live.read_text(encoding="utf-8"))["mcpServers"]
    assert set(written) == CURSOR_CORE_APPROVED
    assert "docker" not in written
    for name in CURSOR_NEVER_MOUNT:
        assert name not in written
    assert "disabled" not in json.dumps(written)
    assert "approval_proof=not-required" in completed.stdout


def test_live_cursor_attach_all_covers_parked_catalog_core_and_owner_adapters() -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    config = live_registry()
    parked = json.loads(
        (AGENTS_ROOT / "mcp-cursor-parked-31.json").read_text(encoding="utf-8")
    )["mcpServers"]

    generated = cursor.build_managed_servers_from_agents(config)
    attach_all = cursor.merge_cursor_mcp_servers({}, generated, attach_all_safe=True)

    assert set(parked) <= set(generated)
    assert CURSOR_CORE_APPROVED <= set(generated)
    assert len(generated) == len(parked) + len(CURSOR_CORE_APPROVED) + 2
    assert "glm53-space" in generated
    assert "glm53-space" not in parked
    assert "linkedin" in generated
    assert "linkedin" not in parked
    assert set(attach_all) == set(generated)
    for name in CURSOR_NEVER_MOUNT:
        assert name not in attach_all
    assert "disabled" not in json.dumps(attach_all)


def test_linkedin_is_projected_but_never_core_or_default_attached() -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    config = live_registry()

    generated = cursor.build_managed_servers_from_agents(config)
    default_merge = cursor.merge_cursor_mcp_servers({}, generated)
    attach_all = cursor.merge_cursor_mcp_servers({}, generated, attach_all_safe=True)

    assert "linkedin" not in cursor.CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS
    assert "linkedin" not in cursor.CURSOR_DEFAULT_APPROVED_SERVERS
    assert "linkedin" not in default_merge
    assert "linkedin" in attach_all
    assert "unapproved" in config["mcp"]["servers"]["linkedin"]["tags"]


def test_glm53_uses_locked_absolute_uv_and_is_owner_requested_default() -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    config = live_registry()

    generated = cursor.build_managed_servers_from_agents(config)
    entry = generated["glm53-space"]

    assert entry["command"] == r"C:\Users\Prekzursil\.local\bin\uv.exe"
    assert entry["args"][:2] == ["run", "--locked"]
    assert "glm53-space" in cursor.CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS
    assert "glm53-space" not in cursor.CURSOR_DEFAULT_APPROVED_SERVERS
    assert "owner-requested" in config["mcp"]["servers"]["glm53-space"]["tags"]
    assert entry["env"]["HUGGINGFACE_TOKEN"] == "${env:HUGGINGFACE_TOKEN}"
    assert "default-off" in config["mcp"]["servers"]["linkedin"]["tags"]


def test_linkedin_registry_entry_names_credentials_without_literal_values() -> None:
    control = load_script("mcp_control_plane")
    config = live_registry()
    server = config["mcp"]["servers"]["linkedin"]

    control.validate_registry(config)

    assert server["enabled"] is True
    assert server["targets"] == ["claude"]
    assert server["transport"] == "stdio"
    assert server["command"] == "C:\\Python314\\python.exe"
    assert server["args"] == [LINKEDIN_SERVER_ARG]
    assert set(server["env"]) == {
        "LINKEDIN_ACCESS_TOKEN",
        "LINKEDIN_CLIENT_ID",
        "LINKEDIN_CLIENT_SECRET",
        "LINKEDIN_REDIRECT_URI",
    }
    for name, value in server["env"].items():
        assert value == f"${{{name}}}"
    assert set(server["credentialNames"]) == {
        "LINKEDIN_ACCESS_TOKEN",
        "LINKEDIN_CLIENT_SECRET",
    }
    assert "approved" not in server["tags"]
    assert {"default-off", "own-feed-write", "owner-identity"} <= set(server["tags"])
    description = server["description"].lower()
    for unavailable in ("alumni", "recruiter", "sales navigator", "talent"):
        assert unavailable in description
    assert "not-checked" in description


def test_linkedin_renders_for_claude_and_cursor_with_env_references_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claude = load_script("merge_generated_claude_mcp")
    cursor = load_script("merge_generated_cursor_mcp")
    config = live_registry()
    monkeypatch.setenv("LINKEDIN_ACCESS_TOKEN", "literal-linkedin-secret")
    monkeypatch.setenv("LINKEDIN_CLIENT_SECRET", "literal-linkedin-secret")

    claude_entry = claude.build_managed_servers_from_agents(config)["linkedin"]
    cursor_entry = cursor.build_managed_servers_from_agents(config)["linkedin"]

    assert claude_entry["command"] == "C:\\Python314\\python.exe"
    assert claude_entry["args"] == [LINKEDIN_SERVER_ARG]
    assert claude_entry["env"]["LINKEDIN_ACCESS_TOKEN"] == "${LINKEDIN_ACCESS_TOKEN}"
    assert cursor_entry["env"]["LINKEDIN_ACCESS_TOKEN"] == "${env:LINKEDIN_ACCESS_TOKEN}"
    assert cursor_entry["env"]["LINKEDIN_CLIENT_SECRET"] == "${env:LINKEDIN_CLIENT_SECRET}"
    assert "literal-linkedin-secret" not in json.dumps([claude_entry, cursor_entry])
    assert "disabled" not in cursor_entry


def test_cursor_selection_excludes_plugin_denied_disabled_and_untargeted_servers() -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    config = registry(
        {
            "markitdown": stdio_server("claude", command="markitdown-mcp.exe"),
            "meta-tool": stdio_server("claude", command="node"),
            "parked-but-safe": stdio_server("claude", command="uvx", args=["docker-mcp"]),
            "switched-off": stdio_server("claude", enabled=False),
            "codex-only": stdio_server("codex"),
            "tavily": {
                "enabled": True,
                "targets": ["claude"],
                "transport": "http",
                "url": "https://mcp.tavily.com/mcp/",
            },
        }
    )

    generated = cursor.build_managed_servers_from_agents(config)

    assert set(generated) == {"parked-but-safe"}


def test_cursor_windows_command_wrapping_survives_attachment(
    tmp_path: pathlib.Path,
) -> None:
    live = tmp_path / "mcp.json"
    live.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
    config_path = tmp_path / "agents.json"
    config_path.write_text(
        json.dumps(
            registry(
                {
                    name: stdio_server(
                        "claude", command="npx", args=["-y", "@playwright/mcp@latest"]
                    )
                    for name in ("playwright",)
                }
            )
        ),
        encoding="utf-8",
    )

    completed = run_cursor_merge(
        "--live",
        str(live),
        "--agents-config",
        str(config_path),
        "--write",
        "--no-backup",
    )

    expected = (
        {"command": "cmd", "args": ["/c", "npx", "-y", "@playwright/mcp@latest"]}
        if platform.system() == "Windows"
        else {"command": "npx", "args": ["-y", "@playwright/mcp@latest"]}
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    written = json.loads(live.read_text(encoding="utf-8"))["mcpServers"]
    assert written["playwright"] == expected

