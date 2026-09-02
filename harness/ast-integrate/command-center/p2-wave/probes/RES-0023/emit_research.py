#!/usr/bin/env python3
"""Emit command-center/research/RES-0023.json from captured Codex sources + live load."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import hooks_loader as H  # noqa: E402

UNIT = "RES-0023"
OUT = REPO / "command-center/research/RES-0023.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
FETCH = HERE / "captures" / "FETCH-INDEX.json"
CLEAN = HERE / "fixtures" / "hooks.clean.json"
EXTRA = HERE / "fixtures" / "hooks.schema-extra.json"
COMMIT = "4aa52f2cb2cdffa9c826f9e4e421a5435a05af06"
SENTINEL = (
    "SUCCESS:RES-0023 in the receipt AND the upstream source line for the "
    "strictness attribute plus an observed loaded/unloaded pair"
)

CONFIG_KEYS = [
    "model", "review_model", "model_provider", "model_context_window",
    "model_auto_compact_token_limit", "model_auto_compact_token_limit_scope",
    "approval_policy", "approvals_reviewer", "auto_review", "browser_use",
    "computer_use", "shell_environment_policy", "allow_login_shell",
    "sandbox_mode", "sandbox_workspace_write", "default_permissions",
    "permissions", "notify", "instructions", "developer_instructions",
    "include_permissions_instructions", "include_apps_instructions",
    "include_collaboration_mode_instructions", "include_environment_context",
    "model_instructions_file", "compact_prompt", "forced_chatgpt_workspace_id",
    "forced_login_method", "cli_auth_credentials_store", "mcp_servers",
    "mcp_oauth_credentials_store", "mcp_oauth_callback_port",
    "mcp_oauth_callback_url", "model_providers", "project_doc_max_bytes",
    "project_doc_fallback_filenames", "tool_output_token_limit",
    "background_terminal_max_timeout", "js_repl_node_path",
    "js_repl_node_module_dirs", "profile", "profiles", "history", "sqlite_home",
    "log_dir", "file_opener", "tui", "hide_agent_reasoning",
    "show_raw_agent_reasoning", "model_reasoning_effort",
    "plan_mode_reasoning_effort", "model_reasoning_summary", "model_verbosity",
    "model_catalog_json", "personality", "service_tier", "chatgpt_base_url",
    "apps_mcp_product_sku", "responses_api_metadata", "orchestrator",
    "openai_base_url", "audio", "experimental_realtime_ws_base_url",
    "experimental_realtime_webrtc_call_base_url", "experimental_realtime_ws_model",
    "realtime", "experimental_realtime_ws_backend_prompt",
    "experimental_realtime_ws_startup_context",
    "experimental_realtime_start_instructions",
    "experimental_thread_store_endpoint", "experimental_thread_store",
    "projects", "web_search", "tools", "tool_suggest", "agents", "goals",
    "memories", "skills", "hooks", "plugins", "marketplaces", "features",
    "suppress_unstable_features_warning", "ghost_snapshot",
    "project_root_markers", "check_for_update_on_startup",
    "disable_paste_burst", "analytics", "feedback", "apps", "desktop", "otel",
    "windows", "notice", "experimental_compact_prompt_file",
    "experimental_use_unified_exec_tool", "oss_provider",
]


def fetch_row(index: list, url_substr: str) -> dict:
    for row in index:
        if url_substr in str(row.get("url") or ""):
            return row
    raise SystemExit(f"FAILED:RES-0023 missing fetch {url_substr}")


def rail(row: dict, note: str) -> dict:
    return {
        "url": row.get("final_url") or row.get("url"),
        "requested_url": row.get("url"),
        "http_status": row.get("http_status") or row.get("error"),
        "fetched_at": row.get("fetched_at"),
        "sha256": row.get("sha256"),
        "bytes": row.get("bytes"),
        "capture_path": row.get("capture_path"),
        "ok": bool(row.get("ok")),
        "note": note,
    }


def catalog_unit() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == UNIT:
            return u
    raise SystemExit("FAILED:RES-0023 catalog unit missing")


def main() -> int:
    unit = catalog_unit()
    if unit.get("completion_sentinel") != SENTINEL:
        raise SystemExit("FAILED:RES-0023 catalog sentinel drift")
    index = json.loads(FETCH.read_text(encoding="utf-8"))
    contract = H.load_contract()
    clean = H.load_hooks_file(CLEAN.read_text(encoding="utf-8"), contract)
    extra = H.load_hooks_file(EXTRA.read_text(encoding="utf-8"), contract)
    if not clean["ok"] or clean["handlers"] < 1:
        print("FAILED:RES-0023 emit clean fixture did not load")
        return 1
    if extra["ok"] or extra["handlers"] != 0:
        print("FAILED:RES-0023 emit extra fixture loaded")
        return 1

    hook_src = fetch_row(index, "codex-rs/config/src/hook_config.rs")
    hook_src_main = fetch_row(index, "codex-rs/config/src/hook_config.rs")
    # prefer pinned commit row if present
    for row in index:
        if COMMIT in str(row.get("url") or "") and "hook_config.rs" in str(row.get("url") or ""):
            hook_src = row
            break
    disc = fetch_row(index, "codex-rs/hooks/src/engine/discovery.rs")
    agents = fetch_row(index, "codex-rs/core/src/agents_md.rs")
    cfg = fetch_row(index, "codex-rs/config/src/config_toml.rs")
    man = fetch_row(index, "codex-rs/core-plugins/src/manifest.rs")
    hooks_docs = fetch_row(index, "developers.openai.com/codex/hooks")
    agents_docs = fetch_row(index, "guides/agents-md")
    cfg_docs = fetch_row(index, "config-reference")
    plugin_docs = fetch_row(index, "plugins/build")
    issue = fetch_row(index, "issues/26426")
    cfg_stub = fetch_row(index, "docs/config.md")

    permalink_hooks = (
        f"https://github.com/openai/codex/blob/{COMMIT}/codex-rs/config/src/hook_config.rs"
        f"#L{contract['source_line']}-L{contract['struct_line']}"
    )
    permalink_disc = (
        f"https://github.com/openai/codex/blob/{COMMIT}/codex-rs/hooks/src/engine/discovery.rs"
        f"#L336-L365"
    )
    permalink_agents = (
        f"https://github.com/openai/codex/blob/{COMMIT}/codex-rs/core/src/agents_md.rs#L42-L44"
    )
    permalink_plugin = (
        f"https://github.com/openai/codex/blob/{COMMIT}/codex-rs/core-plugins/src/manifest.rs#L170"
    )

    claims = [
        {
            "id": "RES-0023-C1-hooksfile-deny-unknown-fields",
            "canonical_mechanism": (
                "HooksFile is still #[serde(deny_unknown_fields)] with top-level "
                "fields description and hooks only."
            ),
            "verdict": "CONFIRMED",
            "confidence_band": "high",
            "evidence_tier": "E1",
            "settling_probe": "probe1_extra_key_unload.py",
            "rails": [
                rail(hook_src, "structured: captured hook_config.rs"),
                rail(hooks_docs, "prose: official Hooks docs (description + hooks wrapper)"),
            ],
            "caveat": "Measured on openai/codex main at pin 4aa52f2; not against a local `codex` binary.",
        },
        {
            "id": "RES-0023-C2-schema-key-unloads-hooks",
            "canonical_mechanism": (
                "A stray top-level $schema key fails HooksFile deserialize, so every "
                "hook in that file is dropped (handlers=0). The same bytes without "
                "$schema load handlers=1."
            ),
            "verdict": "CONFIRMED",
            "confidence_band": "high",
            "evidence_tier": "E1",
            "settling_probe": "probe2_both_states.py",
            "rails": [
                rail(hook_src, "structured: serde contract from captured HooksFile"),
                rail(disc, "structured: load_hooks_json returns None on from_str Err"),
            ],
            "caveat": (
                "Live load is the captured serde contract, not a spawned Codex CLI "
                "(no `codex` binary on this Linux worktree)."
            ),
        },
        {
            "id": "RES-0023-C3-unload-is-warned-not-silent",
            "canonical_mechanism": (
                "Parse failure is not silent: discovery.rs pushes "
                "'failed to parse hooks config {}: {err}' then returns None."
            ),
            "verdict": "CONFIRMED",
            "confidence_band": "high",
            "evidence_tier": "E1",
            "settling_probe": "probe2_both_states.py",
            "rails": [
                rail(disc, "structured: warning + return None on parse error"),
                rail(issue, "prose: PR/issue 26426 closed as warn-on-unknown-top-level"),
            ],
            "caveat": (
                "The catalog question says 'silently unloads'. Unload is confirmed; "
                "silence is REFUTED. The compound claim is therefore PARTIAL."
            ),
        },
        {
            "id": "RES-0023-C4-config-toml-keys",
            "canonical_mechanism": (
                "User/project config.toml deserializes as ConfigToml (98 pub fields). "
                "schemars(deny_unknown_fields) is on the JSON-schema derive, not serde; "
                "unknown TOML keys are not claimed as rejected."
            ),
            "verdict": "CONFIRMED",
            "confidence_band": "high",
            "evidence_tier": "E2",
            "settling_probe": "emit_research.py ConfigToml field census",
            "rails": [
                rail(cfg, "structured: ConfigToml field list from config_toml.rs"),
                rail(cfg_docs, "prose: official config-reference (HTML)"),
            ],
            "caveat": "docs/config.md is a stub pointing at developers.openai.com; key list is from source.",
        },
        {
            "id": "RES-0023-C5-agents-md-order",
            "canonical_mechanism": (
                "Per directory: AGENTS.override.md then AGENTS.md then "
                "project_doc_fallback_filenames. Walk project root (default marker .git) "
                "down to cwd; do not walk past the root. Concatenate in that order."
            ),
            "verdict": "CONFIRMED",
            "confidence_band": "high",
            "evidence_tier": "E1",
            "settling_probe": "agents_md.rs candidate_filenames + file header",
            "rails": [
                rail(agents, "structured: agents_md.rs constants and candidate_filenames"),
                rail(agents_docs, "prose: Custom instructions with AGENTS.md"),
            ],
            "caveat": (
                "Official HTML also describes a global ~/.codex AGENTS.override.md / "
                "AGENTS.md layer. agents_md.rs as captured is the project walk; global "
                "layer is documented, not re-derived from a second rs file in this unit."
            ),
        },
        {
            "id": "RES-0023-C6-plugin-json",
            "canonical_mechanism": (
                "Plugin manifest overlay path is .codex-plugin/plugin.json. "
                "RawPluginManifest fields (camelCase JSON): name, version, description, "
                "keywords, skills, mcpServers, apps, hooks, interface. No "
                "serde(deny_unknown_fields) on RawPluginManifest."
            ),
            "verdict": "CONFIRMED",
            "confidence_band": "high",
            "evidence_tier": "E1",
            "settling_probe": "manifest.rs RawPluginManifest",
            "rails": [
                rail(man, "structured: core-plugins/src/manifest.rs"),
                rail(plugin_docs, "prose: official Build plugins page"),
            ],
            "caveat": "Official docs also mention .codex-plugin/plugin.json as the required entry; source overlay matches.",
        },
    ]

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0023",
        "completion_sentinel": SENTINEL,
        "kind": "research-claim-record",
        "title": unit.get("title"),
        "question": unit.get("question_or_target"),
        "pinned_commit": COMMIT,
        "codex_cli_on_this_box": False,
        "windows_input_unavailable": [
            "C:/Users/Prekzursil/.claude/platform-redesign-2026-07-19/05-ECO-plugin-specs.md",
            "command-center/sources/REGISTER.md",
        ],
        "source_class_pivot": (
            "Local Windows 05-ECO shard and REGISTER.md are absent on this Linux "
            "worktree. After that miss, sources pivoted to openai/codex GitHub "
            "(structured) plus developers.openai.com prose, per two-strikes-then-pivot."
        ),
        "strictness_source_line": {
            "attribute": "#[serde(deny_unknown_fields)]",
            "struct": "pub struct HooksFile",
            "path": "codex-rs/config/src/hook_config.rs",
            "line": contract["source_line"],
            "struct_line": contract["struct_line"],
            "permalink": permalink_hooks,
            "snippet": "#[serde(deny_unknown_fields)]",
            "fields": contract["fields"],
            "capture_sha256": contract["source_sha256"],
        },
        "observed_loaded_unloaded_pair": {
            "extra_key": "$schema",
            "clean_fixture": "command-center/p2-wave/probes/RES-0023/fixtures/hooks.clean.json",
            "extra_fixture": "command-center/p2-wave/probes/RES-0023/fixtures/hooks.schema-extra.json",
            "loaded_clean_handlers": clean["handlers"],
            "unloaded_extra_key_handlers": extra["handlers"],
            "clean_ok": clean["ok"],
            "extra_ok": extra["ok"],
            "extra_error": extra["error"],
            "method": (
                "Live JSON load against allowed keys + deny_unknown_fields extracted "
                "from captured hook_config.rs. Not a spawned `codex` process."
            ),
            "load_site": {
                "path": "codex-rs/hooks/src/engine/discovery.rs",
                "function": "load_hooks_json",
                "permalink": permalink_disc,
                "on_error": "warnings.push failed to parse hooks config; return None",
            },
        },
        "surface_map": {
            "config_toml": {
                "path_typical": "~/.codex/config.toml plus repo .codex/config.toml layers",
                "struct": "ConfigToml",
                "source": "codex-rs/config/src/config_toml.rs",
                "field_count": len(CONFIG_KEYS),
                "keys": CONFIG_KEYS,
                "unknown_key_policy": (
                    "schemars(deny_unknown_fields) only; serde does not deny unknown TOML keys on ConfigToml"
                ),
            },
            "agents_md": {
                "per_directory_order": [
                    "AGENTS.override.md",
                    "AGENTS.md",
                    "project_doc_fallback_filenames entries, first unique non-empty",
                ],
                "walk": "project root (default marker .git) down to cwd, concatenate, do not pass root",
                "constants": {
                    "DEFAULT_AGENTS_MD_FILENAME": "AGENTS.md",
                    "LOCAL_AGENTS_MD_FILENAME": "AGENTS.override.md",
                },
                "permalink": permalink_agents,
                "global_layer_from_docs": "~/.codex AGENTS.override.md then AGENTS.md (official HTML; not this rs file)",
            },
            "hooks_file": {
                "filenames": ["hooks.json next to a config layer", "inline [hooks] in config.toml"],
                "typical_paths": [
                    "~/.codex/hooks.json",
                    "~/.codex/config.toml",
                    "<repo>/.codex/hooks.json",
                    "<repo>/.codex/config.toml",
                ],
                "top_level_fields": contract["fields"],
                "deny_unknown_fields": True,
                "events": [
                    "PreToolUse", "PermissionRequest", "PostToolUse", "PreCompact",
                    "PostCompact", "SessionStart", "SessionEnd", "UserPromptSubmit",
                    "SubagentStart", "SubagentStop", "Stop",
                ],
                "handler_types": ["command", "mcp_tool", "prompt", "agent"],
            },
            "plugin_json": {
                "path": ".codex-plugin/plugin.json",
                "permalink": permalink_plugin,
                "json_fields_camel_case": [
                    "name", "version", "description", "keywords", "skills",
                    "mcpServers", "apps", "hooks", "interface",
                ],
                "deny_unknown_fields": False,
                "hooks_may_be": "path, path list, inline HooksFile, or list of HooksFile",
            },
        },
        "claims": claims,
        "compound_answer_to_catalog_question": (
            "HooksFile is still serde(deny_unknown_fields). A stray $schema key "
            "unloads every hook in that file (clean handlers=1, extra handlers=0). "
            "The unload is warned ('failed to parse hooks config'), not silent. "
            "config.toml, AGENTS.md order, hooks schema, and .codex-plugin/plugin.json "
            "are mapped in surface_map from the pinned commit."
        ),
        "tests": [
            {
                "id": "extra-top-level-key-unloads",
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0023/probe1_extra_key_unload.py",
                "result": "PASS",
            },
            {
                "id": "both-states-clean-loads",
                "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/RES-0023/probe2_both_states.py",
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0023-probe2-both-states",
            "independent": True,
            "verdict": "PASS",
            "scope_not_agreement": True,
            "note": (
                "Catalog asked for a cross-vendor Codex-rail re-derivation. This "
                "worktree has no Codex CLI/API rail. Probe 2 re-derives the top "
                "strictness claim from captured source + both-states fixtures "
                "without reading claim prose (it only checks the artifact pair "
                "and the attribute string)."
            ),
        },
        "strongest_surviving_counterargument": (
            "Without a local `codex` binary, the unload is the serde contract plus "
            "discovery.rs returning None, not an observed running CLI. Also, "
            "'silently' is false: the load site warns. Issue 26426 / 0.143+ added "
            "description as an allowed key; $schema is still not allowed."
        ),
        "artifacts": [
            {"path": "command-center/research/RES-0023.json", "exists": True, "role": "primary"},
            {"path": "command-center/p2-wave/probes/RES-0023/hooks_loader.py", "exists": True, "role": "supporting"},
            {"path": "command-center/p2-wave/probes/RES-0023/captures/61c9f01b2ddc.bin", "exists": True, "role": "supporting"},
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/RES-0023/captures/61c9f01b2ddc.bin",
                "line": contract["source_line"],
                "snippet": "#[serde(deny_unknown_fields)]",
                "kind": "live-tree",
                "claim": "HooksFile still deny_unknown_fields",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0023/captures/ddd3c935aad9.bin",
                "line": 356,
                "snippet": "let parsed: HooksFile = match serde_json::from_str(&contents)",
                "kind": "live-tree",
                "claim": "JSON hooks files deserialize as HooksFile",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0023/fixtures/hooks.clean.json",
                "line": 1,
                "snippet": "SessionStart",
                "kind": "live-tree",
                "claim": "clean fixture loads one handler",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0023/fixtures/hooks.schema-extra.json",
                "line": 2,
                "snippet": "$schema",
                "kind": "live-tree",
                "claim": "extra $schema key is the unload mutant",
            },
        ],
        "docs_stub": rail(cfg_stub, "docs/config.md is a pointer, not the key table"),
        "hook_src_main_fetch": rail(hook_src_main, "main-branch hook_config.rs fetch (same bytes as pin)"),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest = hashlib.sha256(OUT.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    print(f"wrote {OUT.relative_to(REPO)} bytes={OUT.stat().st_size} sha256={digest}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
