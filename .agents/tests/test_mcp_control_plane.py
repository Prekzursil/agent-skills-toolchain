from __future__ import annotations

import importlib.util
import json
import pathlib
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
            sorted(
                item
                for item in required
                if "TOKEN" in item or "KEY" in item or "SECRET" in item
            ),
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


def test_rotation_manifest_contains_references_but_never_values() -> None:
    control = load_script("mcp_control_plane")
    path = SCRIPTS_ROOT / "credential_rotation_manifest.json"
    if not path.is_file():
        # The manifest is a live-estate artifact that the 2026-08-28 harness fold
        # never captured: `.agents/.gitignore`'s `*credential*` rule matched its
        # name. That rule now carries an explicit negation for this one file, so a
        # future capture can commit it; until then there is nothing to validate.
        pytest.skip(f"estate-only artifact not captured in this checkout: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))

    control.validate_rotation_manifest(manifest)
    assert manifest["schemaVersion"] == 1
    assert all(record.get("environmentVariables") for record in manifest["providers"])
    assert all(record.get("affectedPaths") for record in manifest["providers"])
    assert all("value" not in record for record in manifest["providers"])
    providers = {
        record["provider"]: set(record["environmentVariables"])
        for record in manifest["providers"]
    }
    assert providers["Exa"] == {"EXA_API_KEY", "EXA_API_KEY_2"}
    assert providers["Jina Reader"] == {"JINA_API_KEY"}
    assert providers["OpusClip"] == {"OPUSCLIP_API_KEY"}


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
        json.dumps(registry({"active": stdio_server("codex")})),
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


CURSOR_G3D_KEEP = frozenset(
    {
        "agent-mail",
        "basic-memory",
        "chrome-devtools",
        "context7",
        "firecrawl",
        "playwright",
    }
)


def test_cursor_g3d_enabled_allowlist_matches_locked_keep_list() -> None:
    cursor = load_script("merge_generated_cursor_mcp")

    assert cursor.CURSOR_ENABLED_SERVERS == CURSOR_G3D_KEEP
    assert "chrome-devtools-mcp" not in cursor.CURSOR_ENABLED_SERVERS
    assert "mixpanel" not in cursor.CURSOR_ENABLED_SERVERS
    assert "mixpanel-mcp" not in cursor.CURSOR_ENABLED_SERVERS


def test_cursor_g6b_merge_emits_only_keep_list() -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    live = {
        "agent-mail": {"url": "http://127.0.0.1:8812/mcp/"},
        "firecrawl": {"command": "npx", "args": ["-y", "firecrawl-mcp@latest"]},
        "hexstrike-ai": {
            "command": "python",
            "args": ["hexstrike.py"],
            "disabled": True,
        },
        "mixpanel-mcp": {"command": "npx", "args": ["mixpanel-mcp"]},
        "sonarqube": {
            "command": "docker",
            "args": ["run", "-i", "--rm", "mcp/sonarqube"],
        },
    }
    generated = {
        "agent-mail": {"url": "http://127.0.0.1:8812/mcp/"},
        "firecrawl": {
            "command": "cmd",
            "args": ["/c", "npx", "-y", "firecrawl-mcp@latest"],
        },
        "hexstrike-ai": {"command": "python", "args": ["hexstrike.py"]},
        "playwright": {
            "command": "cmd",
            "args": ["/c", "npx", "-y", "@playwright/mcp@latest"],
        },
        "sonarqube": {
            "command": "docker",
            "args": ["run", "-i", "--rm", "mcp/sonarqube"],
        },
    }

    merged = cursor.merge_cursor_mcp_servers(live, generated)

    assert set(merged) <= CURSOR_G3D_KEEP
    assert set(merged) == {"agent-mail", "firecrawl", "playwright"}
    for name, entry in merged.items():
        assert entry.get("disabled") is not True
    assert "hexstrike-ai" not in merged
    assert "sonarqube" not in merged
    assert "mixpanel-mcp" not in merged
    assert "mixpanel" not in merged
    assert merged["firecrawl"]["command"] == "cmd"
    assert merged["playwright"]["args"] == ["/c", "npx", "-y", "@playwright/mcp@latest"]


def test_cursor_g6b_second_merge_does_not_reinsert_parked_servers() -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    generated = {
        "context7": {"command": "npx", "args": ["@upstash/context7-mcp"]},
        "docker": {"command": "uvx", "args": ["docker-mcp"]},
    }

    first = cursor.merge_cursor_mcp_servers({}, generated)
    second = cursor.merge_cursor_mcp_servers(first, generated)

    assert set(first) == {"context7"}
    assert set(second) == {"context7"}
    assert "docker" not in first
    assert "docker" not in second
    assert second["context7"].get("disabled") is not True
    assert second["context7"]["command"] == "npx"


def test_cursor_g6b_write_emits_only_keep_list(tmp_path: pathlib.Path) -> None:
    live = tmp_path / "mcp.json"
    live.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "agent-mail": {"url": "http://127.0.0.1:8812/mcp/"},
                    "docker": {
                        "command": "uvx",
                        "args": ["docker-mcp"],
                        "disabled": True,
                    },
                    "mixpanel-mcp": {"command": "npx", "args": ["mixpanel-mcp"]},
                }
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "agents.json"
    config_path.write_text(
        json.dumps(
            registry(
                {
                    "agent-mail": {
                        "enabled": True,
                        "targets": ["claude"],
                        "transport": "http",
                        "url": "http://127.0.0.1:8812/mcp/",
                    },
                    "docker": stdio_server(
                        "claude", command="uvx", args=["docker-mcp"]
                    ),
                    "playwright": stdio_server(
                        "claude", command="npx", args=["-y", "@playwright/mcp@latest"]
                    ),
                }
            )
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_ROOT / "merge_generated_cursor_mcp.py"),
            "--live",
            str(live),
            "--agents-config",
            str(config_path),
            "--write",
            "--no-backup",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    written = json.loads(live.read_text(encoding="utf-8"))["mcpServers"]
    assert set(written) <= CURSOR_G3D_KEEP
    assert set(written) == {"agent-mail", "playwright"}
    assert written["agent-mail"].get("disabled") is not True
    assert written["playwright"].get("disabled") is not True
    assert "docker" not in written
    assert "mixpanel-mcp" not in written
    assert "mixpanel" not in written
    assert "enabled=2" in completed.stdout
    assert "disabled=0" in completed.stdout
    assert "added=1" in completed.stdout
    assert "updated=1" in completed.stdout
    assert "parked_skips=" in completed.stdout


# The exact off-registry shape found in the live ~/.cursor/mcp.json on 2026-09-01:
# a per-session stdio wrapper standing in front of the ONE shared HTTP daemon the
# registry declares. It exists nowhere in this repo and no script here emits it.
CURSOR_STDIO_BRIDGE = {
    "command": r"C:\Python314\python.exe",
    "args": [
        r"C:\Users\Prekzursil\.agents\scripts\bm_cursor_http_session.py",
        "--stdio",
    ],
}


def test_cursor_renders_live_basic_memory_as_the_shared_http_singleton() -> None:
    cursor = load_script("merge_generated_cursor_mcp")
    config = json.loads((AGENTS_ROOT / "agents.json").read_text(encoding="utf-8"))

    generated = cursor.build_managed_servers_from_agents(config)

    assert generated["basic-memory"] == {"url": "http://127.0.0.1:8765/mcp"}
    assert "command" not in generated["basic-memory"]
    assert "args" not in generated["basic-memory"]


def test_cursor_merge_replaces_a_hand_edited_stdio_bridge_with_the_registry_entry() -> (
    None
):
    cursor = load_script("merge_generated_cursor_mcp")
    live = {"basic-memory": dict(CURSOR_STDIO_BRIDGE)}
    generated = {"basic-memory": {"url": "http://127.0.0.1:8765/mcp"}}

    merged = cursor.merge_cursor_mcp_servers(live, generated)

    assert merged["basic-memory"] == {"url": "http://127.0.0.1:8765/mcp"}
    assert "command" not in merged["basic-memory"]


def test_cursor_merge_drops_a_keep_list_server_the_registry_no_longer_generates() -> (
    None
):
    """A keep-list name the registry stopped emitting must not survive from live.

    ``.cursor/mcp.json`` is registry-rendered. Adopting the live entry as a fallback
    source blessed whatever a hand edit left behind — and ``stamp_cursor_g3d`` then
    stripped ``disabled``, force-enabling it.
    """
    cursor = load_script("merge_generated_cursor_mcp")
    live = {
        "basic-memory": dict(CURSOR_STDIO_BRIDGE, disabled=True),
        "playwright": {"command": "npx", "args": ["-y", "@playwright/mcp@latest"]},
    }
    generated = {
        "playwright": {"command": "npx", "args": ["-y", "@playwright/mcp@latest"]}
    }

    merged = cursor.merge_cursor_mcp_servers(live, generated)

    assert "basic-memory" not in merged
    assert set(merged) == {"playwright"}


def _cursor_drift_fixture(
    tmp_path: pathlib.Path, live_servers: dict[str, Any]
) -> tuple[pathlib.Path, pathlib.Path]:
    live = tmp_path / "mcp.json"
    live.write_text(json.dumps({"mcpServers": live_servers}), encoding="utf-8")
    config_path = tmp_path / "agents.json"
    config_path.write_text(
        json.dumps(
            registry(
                {
                    "basic-memory": {
                        "enabled": True,
                        "targets": ["claude", "codex"],
                        "transport": "http",
                        "url": "http://127.0.0.1:8765/mcp",
                        "singletonKey": "basic-memory/http",
                    }
                }
            )
        ),
        encoding="utf-8",
    )
    return live, config_path


def _run_cursor_check(
    live: pathlib.Path, config_path: pathlib.Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_ROOT / "merge_generated_cursor_mcp.py"),
            "--live",
            str(live),
            "--agents-config",
            str(config_path),
            "--check",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cursor_check_reports_live_drift_and_writes_nothing(
    tmp_path: pathlib.Path,
) -> None:
    live, config_path = _cursor_drift_fixture(
        tmp_path, {"basic-memory": dict(CURSOR_STDIO_BRIDGE)}
    )
    before = live.read_bytes()

    completed = _run_cursor_check(live, config_path)

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "FAILED:mcp-cursor-check" in completed.stdout
    assert "basic-memory" in completed.stdout
    assert live.read_bytes() == before
    assert not list(tmp_path.glob("mcp.json.bak-*"))


def test_cursor_check_is_green_when_the_live_file_matches_the_registry(
    tmp_path: pathlib.Path,
) -> None:
    live, config_path = _cursor_drift_fixture(
        tmp_path, {"basic-memory": {"url": "http://127.0.0.1:8765/mcp"}}
    )

    completed = _run_cursor_check(live, config_path)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "SUCCESS:mcp-cursor-check" in completed.stdout
    assert "drift=0" in completed.stdout


def test_cursor_check_refuses_to_run_together_with_write(
    tmp_path: pathlib.Path,
) -> None:
    live, config_path = _cursor_drift_fixture(
        tmp_path, {"basic-memory": dict(CURSOR_STDIO_BRIDGE)}
    )
    before = live.read_bytes()

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_ROOT / "merge_generated_cursor_mcp.py"),
            "--live",
            str(live),
            "--agents-config",
            str(config_path),
            "--check",
            "--write",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "SUCCESS:" not in completed.stdout
    assert live.read_bytes() == before
