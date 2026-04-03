# agent-skills-toolchain

Private Windows-first platform repo for the installable skills, MCP-side contracts, editor-local tools, and browser-mediated agent tooling I use and evolve together.

The repo now centers on three primary execution surfaces that work together:

- `.agents/skills/` for canonical repo-published skills and operator wrappers
- `tools/mcp/` for raw Codex orchestration tools and other MCP-native projects
- `tools/web/` for browser- or session-mediated talk-only tooling

It also retains `skills/` as a temporary compatibility layout and `tools/editor/` as the bounded home for editor-local integrations.

This repo is intentionally opinionated about boundaries. Codex orchestration is the structured execution and planning lane. PromptBridge is a talk-only discussant and curator lane. The beginner path is the skill layer; the advanced path is the raw tool layer.

## What is live now

### Lane 1: Codex orchestration

`tools/mcp/codex-orchestrator/` exposes these MCP tools:

- `codex_consult`
- `codex_brainstorm`
- `codex_review`
- `codex_discuss`
- `codex_coordinate`
- `codex_curate`

Mental model:

- `codex_consult` = one expert Codex answer
- `codex_brainstorm` = two idea-generating peers plus synthesis
- `codex_review` = one critic pass
- `codex_discuss` = two peers argue before synthesis
- `codex_coordinate` = split roles and consolidate
- `codex_curate` = final selector, optionally with talk-only curation

All orchestration tools return the same result shape:

- `problem`
- `assumptions`
- `options`
- `recommended_option`
- `risks`
- `verification_plan`
- `confidence`
- `mode`
- `participants`
- `curator_used`

### Lane 2: PromptBridge talk-only lane

`tools/web/promptbridge-talk-lane/` exposes:

- `promptbridge_discuss`
- `promptbridge_curate`
- readiness/status/session tools
- `agentify_*` compatibility aliases during `0.1.x`

PromptBridge is not the execution authority. It can discuss and curate, but it does not own repo-changing behavior.

### Desktop surface

`tools/web/agentify-desktop/` now vendors the local desktop control-center app source that backs the PromptBridge / Agentify session layer.

It contains the Electron app, local HTTP/MCP bridge entrypoints, UI assets, orchestrator helpers, and tests, but does not include build artifacts or `node_modules`.

### Skill layer

Repo-local skills now include the multi-agent/orchestration wrappers:

- `multi-agent-quickstart`
- `promptbridge-codex-consult`
- `codex-brainstorm`
- `codex-review`
- `codex-discuss`
- `codex-coordinate`
- `codex-curate`
- `codex-audit`
- `codex-triage`
- `codex-fix`
- `codex-governance`

These sit alongside the existing live specialist skills already in the repo, including:

- `digitalocean-mcp-setup`
- `digitalocean-app-platform-ops`
- `quality-gate-automation-architect`
- `quality-zero-platform-control-plane`
- `format-codex-sessions`
- `ralph-hats`
- `ralph-loop`
- `ralph-orchestrator-setup`
- `mcp-graphql`
- the existing Windows, WSL, VMware, and Codex recovery skill wave
- the explicit `agent-lanes-*` lane-selection skills
- a reverse-engineering skill wave covering HexStrike AI MCP, IDA Pro MCP, Ghidra MCP, Frida MCP, Binary Ninja MCP, Repomix, Frida, radare2, angr, Binary Ninja, and Volatility 3
- a SWFOC-focused reverse-engineering extension covering `reverse-engineering-toolkit`, `swfoc-reverse-engineering`, `x64dbg`, `windbg-preview`, `ret-sync`, `bindiff`, `binexport`, `apply-callee-type-ex`, `binja-sigmaker`, `peutils`, and `ghidra-bridge`
- a second SWFOC artifact workflow wave covering `cheat-engine-workflow`, `windbg-command-cookbook`, `dump-to-signature-workflow`, `swfoc-runtime-address-hunting`, and the repo-published `swfoc-modding` skill
- a third static-analysis and handoff wave covering `ida-decompiler-cleanup`, `binary-ninja-diff-signatures`, `ghidra-automation-recipes`, and `cheat-engine-x64dbg-ida-handoff`

### Editor-local frameworks

`tools/editor/` now also carries vendored host-local orchestration frameworks that are not best modeled as MCP-native services.

- `ralph-orchestrator` - vendored upstream Ralph Orchestrator snapshot plus repo-owned install, MCP registration, and mirrored-skill rollout helpers for Codex, Claude, and Gemini.

### MCP-native integrations

- `tools/mcp/digitalocean-mcp` - thin Windows-first wrapper around the archived `@digitalocean/mcp` package with env-only token wiring and Codex / Claude / Gemini registration helpers.

## Canonical environment model

- Canonical root is the active Windows `CODEX_HOME`
- Default is `%USERPROFILE%\.codex`
- `.codex-vscode` is legacy migration input only
- `config.toml` remains the place for Codex defaults and MCP registration
- `promptbridge-orchestration.toml` stores named profiles, lane defaults, allowed overrides, and skill mappings

## Beginner quickstart

If you are new to multiple agents, use this order:

1. Start with `multi-agent-quickstart`
2. Use `codex_consult` when you want one strong answer
3. Use `codex_brainstorm` when you want alternatives
4. Use `codex_review` before a risky implementation
5. Use `codex_curate` when you already have options and want a final selection
6. Add PromptBridge only when you want a talk-only second opinion or curator

A longer walkthrough lives in [docs/multi-agent-quickstart.md](docs/multi-agent-quickstart.md).

## Layout

- `.agents/skills/`
  - canonical repo-published skills and workflow guidance
- `skills/`
  - transitional compatibility copy during migration to `.agents/skills/`
- `tools/mcp/`
  - MCP-native orchestration and other bounded server-side tool projects
- `tools/mcp/graphql-mcp-bundle/`
  - shared manifest and notes for wiring `mcp-graphql` into Codex, Claude Code, and Gemini CLI
- `tools/mcp/reverse-engineering-mcp-bundle/`
  - shared manifests, wrapper sync helpers, and client registration scripts for reverse-engineering MCP servers
- `tools/editor/`
  - editor-local tools with explicit installation and validation paths
- `tools/web/`
  - PromptBridge/Agentify talk-only tooling, the vendored Agentify Desktop source, and other browser/session-bounded projects
- `docs/`
  - roadmap, design notes, and operator docs
- `scripts/`
  - repo-level validation helpers
- `release/`
  - packaging-only workspace for future bundle artifacts

## Community

- Upstream Superpowers is built by Jesse Vincent and the rest of the folks at Prime Radiant.
- For community support, questions, and sharing what you're building with Superpowers, join us on [Discord](https://discord.gg/Jd8Vphy9jq).

## Support

- Issues: https://github.com/Prekzursil/agent-skills-toolchain/issues

## Validation

From the repo root:

```powershell
npm ci --ignore-scripts
npm test
npm run validate:skills
npm run orchestration:status
npm run orchestration:probe
npm run orchestration:self-test
```

Smoke-test the helper scripts shipped with the current live scripted skills:

```powershell
python .\scripts\test-live-skill-helpers.py
```

The validator prefers `.agents/skills/` and falls back to `skills/` during migration. The smoke test covers the current live scripted skills. Tool-specific validation should stay with the tool projects themselves.

## Working rules

- `.agents/skills/` is the canonical repo-published skill root.
- `skills/` remains a temporary compatibility layer while migration completes.
- `tools/mcp/`, `tools/editor/`, and `tools/web/` stay separated because they have different runtime, auth, packaging, and validation models.
- PromptBridge stays talk-only unless a future design explicitly changes that contract.
- Generic VS Code `mcpServers` support is optional; the primary target is the shared Codex config path for CLI and the OpenAI Codex IDE surface.
