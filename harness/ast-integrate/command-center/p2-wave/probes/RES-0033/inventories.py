#!/usr/bin/env python3
"""Reconstructed sibling vendor maps for RES-0023..RES-0032.

Live command-center/research/RES-0023.json .. RES-0032.json are absent on this
worktree. These files are the mechanical inputs the intersection script reads.
Each primitive is a first-class native surface, not an advertised slogan.
When a live sibling later appears and yields a vendors[] array, engine.py
prefers that file.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIBLING_DIR = HERE / "siblings"

# Planted vendor-unique control (Codex-only). Must not survive intersection.
CONTROL = "codex-hooks-deny-unknown-fields"

P_INSTRUCTION = "natural-language-instruction-file"
P_MCP = "mcp-server-declaration"
P_TOOLS = "tool-permission-policy"
P_HOOKS = "hooks-lifecycle"
P_PLUGIN = "plugin-or-extension-manifest"
P_CONFIG = "structured-agent-config-file"
P_MODEL = "model-selection-in-config"
P_IGNORE = "ignore-or-exclude-file"
P_SANDBOX = "sandbox-or-container-runtime"
P_REPOMAP = "repo-map-or-context-pack"
P_MEMORY = "memory-or-persistent-notes"
P_SUBAGENT = "subagent-or-custom-agent-def"
P_SKILL = "slash-command-or-skill"
P_RULES_MDC = "rules-with-glob-frontmatter"
P_HTTP = "http-task-session-api"
P_FIREWALL = "copilot-server-enforced-firewall"
P_ESCALATE = "goose-lead-worker-escalation"


def prim(pid: str, native: str, citation: str) -> dict:
    return {"id": pid, "native_name": native, "citation": citation}


def vendor(
    vendor_id: str,
    display: str,
    source_unit: str,
    inclusion: str,
    family: str,
    primitives: list[dict],
    note: str = "",
) -> dict:
    return {
        "vendor_id": vendor_id,
        "display_name": display,
        "source_unit": source_unit,
        "inclusion": inclusion,
        "artifact_family": family,
        "note": note,
        "primitive_ids": sorted({p["id"] for p in primitives}),
        "primitives": primitives,
    }


def sibling(unit_id: str, title: str, vendors: list[dict], evidence: list[str]) -> dict:
    return {
        "unit_id": unit_id,
        "title": title,
        "source_kind": "reconstruction",
        "live_research_sibling_present": False,
        "reconstruction_reason": (
            f"command-center/research/{unit_id}.json is absent; this file is "
            "the labeled reconstruction the RES-0033 script reads."
        ),
        "evidence": evidence,
        "vendors": vendors,
    }


SIBLINGS: dict[str, dict] = {
    "RES-0023": sibling(
        "RES-0023",
        "OpenAI Codex CLI configuration, AGENTS.md and plugin surface",
        [
            vendor(
                "openai-codex-cli",
                "OpenAI Codex CLI",
                "RES-0023",
                "supported",
                "file-contract",
                [
                    prim(
                        P_INSTRUCTION,
                        "AGENTS.md",
                        "https://developers.openai.com/codex/guides/agents-md",
                    ),
                    prim(
                        P_CONFIG,
                        "config.toml / .codex/config.toml",
                        "https://learn.chatgpt.com/docs/config-file/config-advanced",
                    ),
                    prim(
                        P_HOOKS,
                        "hooks.json or inline [hooks] in config.toml",
                        "https://developers.openai.com/codex/hooks",
                    ),
                    prim(
                        P_PLUGIN,
                        ".codex-plugin/plugin.json",
                        "https://developers.openai.com/codex/plugins/build",
                    ),
                    prim(
                        P_MCP,
                        ".mcp.json / mcpServers in plugin manifest",
                        "https://developers.openai.com/codex/plugins/build",
                    ),
                    prim(
                        P_TOOLS,
                        "plugin-scoped MCP tool approval in config.toml",
                        "https://developers.openai.com/codex/plugins/build",
                    ),
                    prim(
                        P_MODEL,
                        "model / profile keys in config.toml",
                        "https://learn.chatgpt.com/docs/config-file/config-advanced",
                    ),
                    prim(
                        P_SANDBOX,
                        "Codex sandbox / approval policy",
                        "https://developers.openai.com/codex/cloud",
                    ),
                    prim(
                        P_SKILL,
                        "skills/ directory bundled with a plugin",
                        "https://developers.openai.com/codex/plugins/build",
                    ),
                    prim(
                        CONTROL,
                        "hooks file reject-unknown / deny extra keys (Codex-only control)",
                        "catalog RES-0023: HooksFile deny_unknown_fields; extra $schema key unloads hooks",
                    ),
                ],
                note="CONTROL primitive is Codex-only on purpose.",
            )
        ],
        [
            "https://developers.openai.com/codex/hooks",
            "https://developers.openai.com/codex/plugins/build",
            "catalog RES-0023 question_or_target (deny_unknown_fields HooksFile)",
        ],
    ),
    "RES-0024": sibling(
        "RES-0024",
        "Gemini CLI extension manifest and GEMINI.md surface",
        [
            vendor(
                "google-gemini-cli",
                "Google Gemini CLI",
                "RES-0024",
                "supported",
                "file-contract",
                [
                    prim(
                        P_INSTRUCTION,
                        "GEMINI.md (also configurable as AGENTS.md)",
                        "command-center/p2-wave/probes/RES-0024/captures/gemini_md_doc.body",
                    ),
                    prim(
                        P_PLUGIN,
                        "gemini-extension.json",
                        "command-center/p2-wave/probes/RES-0024/captures/extension_ref_md.body",
                    ),
                    prim(
                        P_MCP,
                        "mcpServers in gemini-extension.json / settings.json",
                        "command-center/p2-wave/probes/RES-0024/captures/extension_ref_md.body",
                    ),
                    prim(
                        P_TOOLS,
                        "excludeTools in gemini-extension.json",
                        "command-center/p2-wave/probes/RES-0024/captures/extension_ref_md.body",
                    ),
                    prim(
                        P_CONFIG,
                        "settings.json / extension settings",
                        "command-center/p2-wave/probes/RES-0024/captures/extension_ref_md.body",
                    ),
                    prim(
                        P_MEMORY,
                        "MemoryDiscovery of GEMINI.md context files",
                        "command-center/p2-wave/probes/RES-0024/captures/memory_discovery.body",
                    ),
                    prim(
                        P_SKILL,
                        "custom-commands extension template",
                        "command-center/p2-wave/probes/RES-0024/captures/extension_ref_md.body",
                    ),
                    prim(
                        P_MODEL,
                        "model selection in Gemini CLI settings",
                        "https://github.com/google-gemini/gemini-cli",
                    ),
                ],
                note=(
                    "Pinned to live captures at google-gemini/gemini-cli@"
                    "af687798afe3b83fd8bf46e91d659c88347427ba (fetched 2026-08-24)."
                ),
            )
        ],
        [
            "command-center/p2-wave/probes/RES-0024/captures/gemini_md_doc.body",
            "command-center/p2-wave/probes/RES-0024/captures/extension_ref_md.body",
            "command-center/p2-wave/probes/RES-0024/captures/github_main_commit.json",
        ],
    ),
    "RES-0025": sibling(
        "RES-0025",
        "Cursor .cursor/rules (.mdc) and agent-configuration surface",
        [
            vendor(
                "cursor",
                "Cursor",
                "RES-0025",
                "supported",
                "file-contract",
                [
                    prim(P_INSTRUCTION, "AGENTS.md / .cursorrules", "https://docs.cursor.com/context/rules"),
                    prim(P_RULES_MDC, ".cursor/rules/*.mdc frontmatter globs", "https://docs.cursor.com/context/rules"),
                    prim(P_MCP, ".cursor/mcp.json", "https://docs.cursor.com/context/mcp"),
                    prim(P_HOOKS, "Cursor hooks", "https://docs.cursor.com/agent/hooks"),
                    prim(P_TOOLS, "tool allow/deny in Cursor settings", "https://docs.cursor.com/agent"),
                    prim(P_CONFIG, ".cursor/cli.json / project settings", "https://docs.cursor.com/cli"),
                    prim(P_MODEL, "model picker in project/user settings", "https://docs.cursor.com/models"),
                    prim(P_SUBAGENT, "custom subagents / parallel agents", "https://docs.cursor.com/agent"),
                    prim(P_SKILL, "skills / slash commands", "https://docs.cursor.com"),
                    prim(P_IGNORE, ".cursorignore", "https://docs.cursor.com/context/ignore-files"),
                    prim(P_PLUGIN, "Cursor extension / plugin surface", "https://docs.cursor.com"),
                ],
            )
        ],
        ["catalog RES-0025", "https://docs.cursor.com/context/rules"],
    ),
    "RES-0026": sibling(
        "RES-0026",
        "GitHub Copilot coding-agent customization surface",
        [
            vendor(
                "github-copilot-coding-agent",
                "GitHub Copilot coding agent / Copilot CLI",
                "RES-0026",
                "supported",
                "file-contract",
                [
                    prim(
                        P_INSTRUCTION,
                        ".github/copilot-instructions.md and *.instructions.md",
                        "https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot",
                    ),
                    prim(
                        P_MCP,
                        "MCP servers in Copilot VS Code / Copilot CLI config",
                        "https://docs.github.com/en/copilot/customizing-copilot/using-model-context-protocol-mcp",
                    ),
                    prim(
                        P_TOOLS,
                        "allowed tools for coding agent",
                        "https://docs.github.com/en/copilot/concepts/coding-agent",
                    ),
                    prim(
                        P_CONFIG,
                        "Copilot custom agents YAML / repository agent files",
                        "https://docs.github.com/en/copilot/customizing-copilot",
                    ),
                    prim(
                        P_MODEL,
                        "model choice for Copilot coding agent",
                        "https://docs.github.com/en/copilot/using-github-copilot",
                    ),
                    prim(
                        P_FIREWALL,
                        "GitHub-hosted coding-agent firewall (server-enforced, not portable)",
                        "https://docs.github.com/en/copilot/concepts/coding-agent",
                    ),
                ],
                note="Firewall is server-enforced; it is listed so the classifier keeps a non-portable unique.",
            )
        ],
        [
            "catalog RES-0026 (server-enforced controls must be labelled)",
            "https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot",
        ],
    ),
    "RES-0027": sibling(
        "RES-0027",
        "Continue.dev assistant blocks and config composition",
        [
            vendor(
                "continue-dev",
                "Continue.dev",
                "RES-0027",
                "supported",
                "file-contract",
                [
                    prim(P_INSTRUCTION, "rules blocks / .continue/rules", "https://docs.continue.dev/customize/deep-dives/rules"),
                    prim(P_MCP, "MCP blocks", "https://docs.continue.dev/customize/deep-dives/mcp"),
                    prim(P_PLUGIN, "hub blocks (models, rules, prompts, context, MCP)", "https://docs.continue.dev/customize/overview"),
                    prim(P_CONFIG, "config.yaml / .continuerc.json", "https://docs.continue.dev/reference/config"),
                    prim(P_MODEL, "models blocks", "https://docs.continue.dev/customize/deep-dives/models"),
                    prim(P_SKILL, "prompts / slash commands", "https://docs.continue.dev/customize/deep-dives/prompts"),
                ],
            )
        ],
        ["catalog RES-0027", "https://docs.continue.dev/customize/overview"],
    ),
    "RES-0028": sibling(
        "RES-0028",
        "Aider repo-map and conventions surface",
        [
            vendor(
                "aider",
                "Aider",
                "RES-0028",
                "supported",
                "file-contract",
                [
                    prim(
                        P_INSTRUCTION,
                        "CONVENTIONS.md loaded via --read / .aider.conf.yml read:",
                        "https://aider.chat/docs/usage/conventions.html",
                    ),
                    prim(
                        P_CONFIG,
                        ".aider.conf.yml",
                        "https://aider.chat/docs/config.html",
                    ),
                    prim(
                        P_MODEL,
                        "model: in .aider.conf.yml / --model",
                        "https://aider.chat/docs/llms.html",
                    ),
                    prim(
                        P_IGNORE,
                        ".aiderignore",
                        "https://aider.chat/docs/config.html",
                    ),
                    prim(
                        P_REPOMAP,
                        "repo map (graph ranking over symbol references)",
                        "catalog RES-0028; https://aider.chat/docs/repomap.html",
                    ),
                ],
                note=(
                    "MCP is omitted. Native MCP is an open PR (Aider-AI/aider#3937, #3672), "
                    "not a first-class documented contract. Counting it would inflate the core."
                ),
            )
        ],
        [
            "catalog RES-0028",
            "https://aider.chat/docs/usage/conventions.html",
            "https://github.com/Aider-AI/aider/pull/3937",
        ],
    ),
    "RES-0029": sibling(
        "RES-0029",
        "OpenHands runtime isolation and microagent trigger model",
        [
            vendor(
                "openhands",
                "OpenHands (OpenHands/All-Hands)",
                "RES-0029",
                "supported",
                "file-contract",
                [
                    prim(P_INSTRUCTION, "microagents markdown / repo instructions", "https://docs.all-hands.dev/usage/microagents"),
                    prim(P_CONFIG, "config.toml", "https://docs.all-hands.dev/usage/configuration"),
                    prim(P_SANDBOX, "container runtime / action-observation loop", "catalog RES-0029"),
                    prim(P_MODEL, "llm model in config.toml", "https://docs.all-hands.dev/usage/llms"),
                    prim(P_SUBAGENT, "microagents with triggers", "catalog RES-0029"),
                    prim(P_MCP, "MCP integration in OpenHands config", "https://docs.all-hands.dev"),
                ],
            )
        ],
        ["catalog RES-0029", "https://docs.all-hands.dev/usage/microagents"],
    ),
    "RES-0030": sibling(
        "RES-0030",
        "Goose recipes and lead/worker escalation (canonical repo relocated)",
        [
            vendor(
                "goose",
                "Goose (block/goose -> aaif-goose/goose)",
                "RES-0030",
                "supported",
                "file-contract",
                [
                    prim(P_INSTRUCTION, ".goosehints / AGENTS.md-style hints", "https://block.github.io/goose/docs/guides/using-goosehints"),
                    prim(P_CONFIG, "Goose config / profiles", "https://block.github.io/goose/docs/guides/configuring-goose"),
                    prim(P_MCP, "extensions including MCP servers", "https://block.github.io/goose/docs/getting-started/using-extensions"),
                    prim(P_MODEL, "provider/model in Goose config", "https://block.github.io/goose/docs/getting-started/providers"),
                    prim(P_SKILL, "recipes (YAML)", "catalog RES-0030"),
                    prim(P_ESCALATE, "lead-to-worker escalation threshold", "catalog RES-0030"),
                    prim(P_PLUGIN, "Goose extensions", "https://block.github.io/goose/docs/getting-started/using-extensions"),
                ],
            )
        ],
        ["catalog RES-0030 (repo redirect)", "https://block.github.io/goose/docs/guides/using-goosehints"],
    ),
    "RES-0031": sibling(
        "RES-0031",
        "Cline / Roo Code / Windsurf rule, memory and MCP surfaces",
        [
            vendor(
                "cline",
                "Cline",
                "RES-0031",
                "supported",
                "file-contract",
                [
                    prim(P_INSTRUCTION, ".clinerules / .clinerules/*.md", "https://docs.cline.bot/features/cline-rules"),
                    prim(P_MCP, "Cline MCP servers", "https://docs.cline.bot/mcp/mcp-overview"),
                    prim(P_MEMORY, "Cline memory bank", "https://docs.cline.bot/features/memory-bank"),
                    prim(P_CONFIG, "Cline VS Code settings / .cline/", "https://docs.cline.bot"),
                    prim(P_MODEL, "Cline API provider + model", "https://docs.cline.bot/getting-started/model-selection"),
                    prim(P_SUBAGENT, "custom modes", "https://docs.cline.bot"),
                    prim(P_TOOLS, "auto-approve / mode tool policy", "https://docs.cline.bot"),
                ],
            ),
            vendor(
                "roo-code",
                "Roo Code",
                "RES-0031",
                "supported",
                "file-contract",
                [
                    prim(P_INSTRUCTION, ".roo/rules / .roorules", "https://docs.roocode.com/features/custom-instructions"),
                    prim(P_MCP, "Roo MCP servers", "https://docs.roocode.com/features/mcp/using-mcp-in-roo"),
                    prim(P_MEMORY, "Roo memory bank", "https://docs.roocode.com"),
                    prim(P_CONFIG, ".roo/ + VS Code settings", "https://docs.roocode.com"),
                    prim(P_MODEL, "Roo API provider + model", "https://docs.roocode.com"),
                    prim(P_SUBAGENT, "custom modes / .roomodes", "https://docs.roocode.com/features/custom-modes"),
                    prim(P_TOOLS, "mode tool groups", "https://docs.roocode.com/features/custom-modes"),
                ],
            ),
            vendor(
                "windsurf",
                "Windsurf (Cascade)",
                "RES-0031",
                "supported",
                "file-contract",
                [
                    prim(P_INSTRUCTION, "Windsurf memories / rules files", "https://docs.windsurf.com/windsurf/cascade/memories"),
                    prim(P_MCP, "Windsurf MCP", "https://docs.windsurf.com/windsurf/cascade/mcp"),
                    prim(P_MEMORY, "Cascade memories", "https://docs.windsurf.com/windsurf/cascade/memories"),
                    prim(P_CONFIG, "Windsurf settings JSON", "https://docs.windsurf.com"),
                    prim(P_MODEL, "Cascade model selector", "https://docs.windsurf.com"),
                    prim(P_SKILL, "workflows / slash commands", "https://docs.windsurf.com/windsurf/cascade/workflows"),
                ],
            ),
        ],
        ["catalog RES-0031 three-way intersection requirement"],
    ),
    "RES-0032": sibling(
        "RES-0032",
        "Hosted-agent platforms: public-versioned-API vs UI-only",
        [
            vendor(
                "cognition-devin",
                "Devin (Cognition)",
                "RES-0032",
                "out-of-scope-ui-only",
                "ui-only",
                [
                    prim(P_HTTP, "Devin web session (no portable file contract)", "https://devin.ai"),
                ],
                note="UI-only control: at least one hosted platform is out of adapter scope.",
            ),
            vendor(
                "factory-ai",
                "Factory",
                "RES-0032",
                "public-api-only",
                "http-api",
                [
                    prim(P_HTTP, "Factory session/droid API", "https://docs.factory.ai"),
                ],
                note=(
                    "Public API without a shared file-contract family. Recorded on the "
                    "matrix; excluded from the file-contract intersection so HTTP-only "
                    "surfaces do not silently empty the portable core."
                ),
            ),
            vendor(
                "github-copilot-workspace",
                "Copilot Workspace (legacy hosted UI)",
                "RES-0032",
                "out-of-scope-ui-only",
                "ui-only",
                [],
                note="UI-only / superseded hosted surface; out of adapter scope.",
            ),
        ],
        ["catalog RES-0032 (at least one UI-only verdict required)"],
    ),
}


def dump_siblings(directory: Path | None = None) -> list[Path]:
    directory = directory or SIBLING_DIR
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for uid, doc in SIBLINGS.items():
        path = directory / f"{uid}.json"
        text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


def main() -> int:
    paths = dump_siblings()
    for p in paths:
        print(f"wrote {p.relative_to(HERE.parent.parent.parent.parent)}")
    print(f"SUCCESS:RES-0033 dumped {len(paths)} sibling inventories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
