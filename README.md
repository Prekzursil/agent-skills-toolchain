# agent-skills-toolchain

Full configuration and toolchain repo for all my AI agents: Codex CLI, Claude Code, and Gemini CLI. Contains 169+ skills, 40+ MCP server configs, the codex_consult orchestration engine, Agentify Desktop, and platform config snapshots - all plug-and-play.

## Quick Start

```bash
# Clone
git clone https://github.com/Prekzursil/agent-skills-toolchain.git
cd agent-skills-toolchain

# Unlock encrypted credential stores (accounts.json) for plug-and-play MCP hubs.
# Needs git-crypt + the exported key from your password manager. See docs/SECRETS.md.
git-crypt unlock /path/to/agent-skills-toolchain.gitcrypt.key

# Install dependencies
npm install

# Bootstrap codex_consult into your CODEX_HOME
node tools/mcp/codex-orchestrator/integrations/codex/cli.mjs install

# Verify the stack
node tools/mcp/codex-orchestrator/integrations/codex/cli.mjs probe
node tools/mcp/codex-orchestrator/integrations/codex/cli.mjs self-test

# Start Agentify Desktop (for PromptBridge/ChatGPT web lane)
cd tools/web/agentify-desktop && npm install && npm start
```

## What This Repo Contains

| Surface | Count | Description |
|---------|-------|-------------|
| `skills/` | 158 | Shared skills for Codex + Claude (see `SKILLS-MANIFEST.md`); incl. game-RE (`game-re-binary`, `game-frida-trace`, `game-find-anticheat`, `game-unpack-pe`) + SWFOC + Battle Cats |
| `skills-claude-only/` | 35 | Claude Code exclusive skills (Azure, metaswarm, Ralph, etc.) |
| `tools/mcp/` | 6 | MCP server projects (codex-orchestrator, agent-lanes, workstation bundle, etc.) |
| `tools/web/` | 2 | Agentify Desktop + PromptBridge talk lane |
| `tools/editor/` | 2 | Metaswarm + Ralph Orchestrator |
| `release/platforms/windows/` | 8 | Config snapshots: Codex (41 MCPs), Claude (40 MCPs), Gemini (25+ MCPs) |
| `docs/` | — | Architecture docs, codex-consult analysis, plans, dated session reconciliations |

> **Latest (2026-06-10):** added 4 game-RE skills; new MCP servers **`ocr`**
> (multi-engine OCR + accuracy eval — separate repo
> [`Prekzursil/abbyy-finereader-ocr-mcp`](https://github.com/Prekzursil/abbyy-finereader-ocr-mcp)), **`basic-memory`**
> (durable vector memory + compaction-survival hooks), **`firefox-devtools`**; and a
> cross-AI **mcp-funnel single-source** setup (dedup + switchable profiles, skills
> unified across Claude Code + Codex). See
> [`docs/SESSION-RECONCILIATION-2026-06-10.md`](docs/SESSION-RECONCILIATION-2026-06-10.md).

replacement for a Sci-Hub MCP. It resolves DOI / PMID / arXiv / title queries, classifies access
honestly, and routes **only** to available open-access and rights-holder-entitled sources
(Crossref, OpenAlex, Unpaywall, Europe PMC, arXiv, Semantic Scholar, CORE, DOAJ, PubMed, Zenodo).

> no silent fallback. `paper_download_oa_pdf` only fetches allowlisted hosts that serve a real `%PDF`.

8 tools: `paper_resolve`, `paper_fetch_metadata`, `paper_find_oa_pdf`, `paper_access_status`,
`paper_citation_graph`, `paper_download_oa_pdf`, `paper_summarize`, `paper_batch_resolve`.

```bash
cd tools/scholarly-access-mcp
python -m venv .venv && .venv/Scripts/python -m pip install -e .
.venv/Scripts/python -m pytest tests/test_policy.py -q   # 22 offline policy/gate tests
.venv/Scripts/python tests/test_live.py                  # 10 live end-to-end checks
.venv/Scripts/python list_tools.py                       # the 8-tool surface
```

Details: [`tools/scholarly-access-mcp/README.md`](tools/scholarly-access-mcp/README.md) ·
[`docs/mcps/scholarly-access-mcp.md`](docs/mcps/scholarly-access-mcp.md) ·
[`docs/workflows/deep-research-literature-workflow.md`](docs/workflows/deep-research-literature-workflow.md) ·
skills: `scholarly-literature-review`, `oa-pdf-retrieval`, `citation-mapping`, `biomedical-paper-triage`, `drug-discovery-literature-bridge`.

## Quality & Security

A single lean, deterministic **`quality`** CI workflow ([`.github/workflows/quality.yml`](.github/workflows/quality.yml))
enforces a closed set of 6 gates — every tool version-pinned and configured from an in-repo file
(no SaaS platform, no `--config auto`, no baseline files). This is the toolchain's adoption of the
[quality-zero-platform](https://github.com/Prekzursil/quality-zero-platform) lean-gate model, as
proven in [reframe](https://github.com/Prekzursil/reframe).

| Gate | Tool (pinned) | Enforces |
|------|---------------|----------|
| lint-format | ruff 0.15.17 | `ruff check` + `ruff format --check` (honors `ruff.toml`) |
| types | basedpyright 1.39.8 | per-package source type-check (`mcp-manager`, `scholarly-access-mcp`) |
| tests-coverage | pytest + node | 100% branch coverage for the two Python packages + node tests |
| sast | opengrep 1.23.0 | curated in-repo ruleset [`.quality/opengrep/`](.quality/opengrep) (clean-zero) |
| secrets | gitleaks | committed `.gitleaks.toml` allowlist |
| deps | osv-scanner | known-CVE scan of the npm lockfiles ([`osv-scanner.toml`](osv-scanner.toml)) |

Full charter and rules: [`QUALITY-CHARTER.md`](QUALITY-CHARTER.md); machine-readable gate
declaration: [`.quality/charter.yml`](.quality/charter.yml) (kept in sync with the workflow by
`.quality/charter_check.sh`).

### Run the gates locally

```bash
# 1. lint-format (ruff, pinned via uv — or `pip install ruff==0.15.17`)
uvx ruff@0.15.17 check .
uvx ruff@0.15.17 format --check .

# 4. sast (semgrep CE is rule-compatible with opengrep)
semgrep scan --config .quality/opengrep --error --metrics off \
  --exclude node_modules --exclude .venv --exclude vendor \
  --exclude dist --exclude out --exclude build .

# charter <-> workflow consistency
bash .quality/charter_check.sh

# 2 + 3. per-package types + 100% coverage
( cd tools/mcp-manager && pip install -e ".[dev]" \
    && basedpyright core ui app.py \
    && pytest --cov=. --cov-branch --cov-fail-under=100 )
( cd tools/scholarly-access-mcp && pip install -e . \
    && basedpyright scholarly_access \
    && pytest --cov=scholarly_access --cov-branch --cov-fail-under=100 )
```

**Security policy** — how to report a vulnerability (private), scope, and disclosure
expectations: [`SECURITY.md`](SECURITY.md).

## codex_consult: Plug-and-Play Consultation

The codex_consult system provides AI consultation via two lanes:

- **Lane B (PromptBridge/Agentify)**: Routes queries through Agentify Desktop to ChatGPT web UI with your logged-in subscription. Supports extended thinking, web search, and all ChatGPT Pro models.
- **Lane A (Codex CLI)**: Falls back to `codex exec` with session reuse. Automatic fallback when Lane B is unavailable.

### Architecture

```
codex_consult MCP tool
    |
    v
codex-orchestrator (tools/mcp/codex-orchestrator/)
    |-- reads profiles from promptbridge-orchestration.toml
    |-- resolves model, timeout, capabilities per profile
    |
    +-- Lane B: PromptBridge talk lane (tools/web/promptbridge-talk-lane/)
    |       |-- connects to Agentify Desktop
    |       |-- workspace-aware session keys (pb-{project})
    |       |-- extended thinking + web search support
    |       |-- 480s query timeout for long responses
    |       +-- auto-detects and launches desktop app
    |
    +-- Lane A fallback: Codex CLI exec
            |-- session reuse via SQLite routes table
            |-- per-profile model selection
            +-- health events recorded on fallback
```

### Profiles

| Profile | Model | Thinking | Web Search | Timeout |
|---------|-------|----------|------------|---------|
| consult | chatgpt-5-latest-pro | max (extended) | yes | 480s |
| brainstorm | gpt-5.4 | high (extended) | yes | 480s |
| review | chatgpt-5-latest-pro | high (extended) | no | default |
| discuss | gpt-5.4 (default) | high | no | default |
| coordinate | gpt-5.4 (default) | high | no | default |
| curate | gpt-5.4 (default) | high | no | default |

### Install Flow

The entire stack is self-installing:

1. **`cli.mjs install`** — copies the orchestration runtime into `CODEX_HOME/promptbridge-runtime/`, registers the `codex_consult` MCP server in `config.toml`, and writes `promptbridge-orchestration.toml`
2. **`cli.mjs probe`** — validates MCP server connectivity, PromptBridge desktop state, and session store
3. **`cli.mjs self-test`** — runs a live consultation round-trip and verifies the response schema
4. **Agentify Desktop** — standalone Electron app in `tools/web/agentify-desktop/` that provides the ChatGPT web automation layer

### Management Commands

```bash
node tools/mcp/codex-orchestrator/integrations/codex/cli.mjs status     # Check bootstrap state
node tools/mcp/codex-orchestrator/integrations/codex/cli.mjs probe      # Probe consultation stack
node tools/mcp/codex-orchestrator/integrations/codex/cli.mjs self-test  # Live round-trip test
node tools/mcp/codex-orchestrator/integrations/codex/cli.mjs update     # Update to latest
node tools/mcp/codex-orchestrator/integrations/codex/cli.mjs uninstall  # Remove bootstrap
```

## Purpose

This repo is the working home for four kinds of agent assets plus the docs and validation needed to keep them bounded:

- `skills/` for installable, validated skills (134 shared + 35 Claude-only)
- `tools/mcp/` for MCP-native contracts, adapters, and promoted tool projects
- `tools/editor/` for editor-local tools such as VS Code extensions plus vendored host-local agent frameworks
- `tools/web/` for browser- or web-mediated tool projects with explicit session boundaries
- `release/platforms/` for sanitized config snapshots (Codex, Claude, Gemini)

The split matters because these surfaces have different runtime models, auth expectations, failure modes, packaging rules, and validation paths.

## Layout

- `skills/`
  - installable, validated skills only
- `hooks/`
  - canonical copy of the session-built *agentic-perfection* hook set (dispatcher + durability spine + anti-slop + wildcard gems + infra); synced to `~/.claude/hooks` via `scripts/sync-hooks.ps1`
- `tools/mcp/`
  - MCP-native tool contracts and promoted bounded tool projects
- `tools/editor/`
  - editor-local tools with explicit installation and validation paths
- `tools/web/`
  - browser- or web-mediated tool contracts and promoted bounded tool projects
- `docs/plans/`
  - repo-level design documents and implementation notes
- `docs/incubating/skills/`
  - future skill concepts that are not installable yet
- `docs/incubating/tools/`
  - future MCP, editor, or web-tool concepts that are not ready for promotion yet
- `docs/agentic-perfection/`
  - the agentic-perfection / proactive-partner program: CHANGELOG + plan + the unlocking prompts + open-threads snapshot
- `scripts/`
  - repo-level helpers such as validation, `sync-skills.ps1`, and `sync-hooks.ps1`; `scripts/agentic-perfection/` holds the program's host-side scripts (basic-memory launcher/watchdog, world-watch, resource-guard)
- `release/`
  - packaging-only workspace for future Windows/Linux/macOS bundles; not a live execution surface
- `userscripts/`
  - browser Tampermonkey/Violentmonkey userscripts (personal `*.user.js` conveniences); see [`userscripts/README.md`](userscripts/README.md)

## Current repo themes

### 1. Ops and recovery skills

These are the host, VM, repo-quality, and session-repair skills already shipping from `skills/`.

### 2. Agent Lanes

**Agent Lanes** is the replacement name for the older PromptBridge-style label.

The old name implied one vague bridge. The actual system is clearer than that: it is a set of explicit lanes with explicit routing.

- a Codex-side orchestration lane
- a direct ChatGPT web lane
- installable skills that explicitly choose the intended lane

That stack spans both live tool surfaces plus explicit routing skills:

- [`tools/mcp/agent-lanes-codex/`](tools/mcp/agent-lanes-codex/README.md)
- [`tools/web/agent-lanes-chatgpt-web/`](tools/web/agent-lanes-chatgpt-web/README.md)
- `skills/agent-lanes-*`

### 3. Windows-first workstation bundle

This repo now also carries the current Windows-first MCP/editor bundle I actively use:

- `tools/mcp/workstation-codex-bundle` - curated MCP selections with explicit self-made vs curated provenance.
- `tools/mcp/cheatengine-mcp-bridge` - thin wrapper around the upstream Cheat Engine MCP Bridge with local install and validation helpers.
- `tools/mcp/hexstrike-ai` - thin wrapper around the upstream HexStrike AI runtime with localhost bootstrap and Codex / Claude / Gemini registration helpers.

### 4. Vendored host frameworks

This repo can also carry exact upstream snapshots when I need the full project in-tree instead of just a thin wrapper:

- `tools/editor/metaswarm` - vendored upstream `dsifry/metaswarm` workspace for Claude Code, Gemini CLI, and Codex CLI orchestration.

## Live surfaces

### Skills

Live installable skills currently ship from `skills/`:

- `quality-gate-automation-architect` - safe automation architecture for PR repair, coverage ratchets, analyzer debt burn-down, and merge governance.
- `hexstrike-ai-setup` - install, wire, and validate the local HexStrike runtime for Codex, Claude, and Gemini.
- `hexstrike-ai-authorized-engagement` - route authorized security work through the local HexStrike runtime with explicit scope checks.
- `codex-runtime-recovery` - diagnose split `CODEX_HOME`, state DB churn, and cross-host launch drift before destructive repair.
- `codex-session-reunion` - inventory, compare, and safely promote the best session copies into one canonical store.
- `format-codex-sessions` - render Codex rollout JSONL into readable Markdown transcripts without leaking prompt bulk or token-like data.
- `competitive-programming-solver` and `pbinfo-python-jit` - solve online judge problems and escalate pbinfo Python TLE cases with static helper tooling.
- `long-copy-orchestrator` - choose the right copy mechanism and monitor progress during large cross-host transfers.
- `wsl-vmware-cutover` - stage WSL-to-VMware migrations with D:-first backups and rollback checkpoints.
- `offline-linux-disk-surgery` - inspect, grow, or repair Linux guest disks offline.
- `windows-virtualization-conflict-triage` - classify Hyper-V, VBS, VMware, and `vmrun` conflict patterns safely.
- `codex-vscode-host-routing` - keep VS Code Codex hosted on Windows by default.
- `reboot-safe-ops-continuation` - capture resumable machine state before forced reboots.
- `codex-consult` - one skill, three modes (consult / review / curate) for the Codex-side orchestration lane; replaces the former `codex-local-*` and `agent-lanes-codex-*` per-mode skills.
- `agent-lanes-chatgpt-web-query` / `chatgpt5-web-query` - explicitly select the direct ChatGPT web query lane.
- `agent-lanes-chatgpt-web-discuss` / `chatgpt5-web-discuss` - explicitly select the direct ChatGPT web discussion lane.
- `agent-lanes-chatgpt-web-curate` / `chatgpt5-web-curate` - explicitly select the direct ChatGPT web curation lane.
- `using-superpowers`, `brainstorming`, `writing-plans`, `executing-plans`, `systematic-debugging`, `test-driven-development`, `verification-before-completion`, `dispatching-parallel-agents`, `subagent-driven-development`, `requesting-code-review`, `receiving-code-review`, and `using-git-worktrees` - general-purpose workflow skills promoted from the current local Codex skill set.
- `codex-orchestrate` (one skill for all codex-as-MCP modes — brainstorm/discuss/coordinate/review/audit/curate/governance/triage), `codex-consult` (the local PromptBridge consult/curate/review lanes), and `multi-agent-quickstart` - orchestration and lane-helper skills promoted from the current local Codex skill set. The former per-mode wrappers (`codex-audit`, `codex-brainstorm`, `codex-coordinate`, `codex-curate`, `codex-discuss`, `codex-fix`, `codex-governance`, `codex-review`, `codex-triage`) are consolidated into `codex-orchestrate`.

### Tools

The live tool surfaces are first-class repo homes for bounded tool projects and contracts:

- [`tools/mcp/`](tools/mcp/README.md)
- [`tools/editor/`](tools/editor/README.md)
- [`tools/web/`](tools/web/README.md)

### Userscripts

Browser userscripts (Tampermonkey/Violentmonkey) live in [`userscripts/`](userscripts/README.md):

- `github-pat-quick-fill.user.js` - one-click **max all** GitHub fine-grained PAT permissions; DOM-driven (no hardcoded permission list), survives GitHub adding/removing permissions, handles every permission category.

Current bounded projects:

- [`tools/mcp/agent-lanes-codex/`](tools/mcp/agent-lanes-codex/README.md)
- [`tools/mcp/workstation-codex-bundle/`](tools/mcp/workstation-codex-bundle/README.md)
- [`tools/mcp/cheatengine-mcp-bridge/`](tools/mcp/cheatengine-mcp-bridge/README.md) - thin wrapper around the upstream Cheat Engine MCP Bridge with local install and validation helpers.
- [`tools/mcp/hexstrike-ai/`](tools/mcp/hexstrike-ai/README.md) - thin wrapper around the upstream HexStrike AI runtime with localhost bootstrap and client registration helpers.
- [`tools/editor/metaswarm/`](tools/editor/metaswarm/README.md) - vendored upstream metaswarm workspace.
- [`tools/web/agent-lanes-chatgpt-web/`](tools/web/agent-lanes-chatgpt-web/README.md)

Speculative tool ideas do not live here. They stay under `docs/incubating/tools/` until they become clearly bounded enough to promote.

## Validation

Validate all live skills from the repo root:

```powershell
pwsh -File .\scripts\validate-all-skills.ps1
```

Smoke-test the helper scripts shipped with the live scripted skills:

```powershell
python .\scripts\test-live-skill-helpers.py
```

The validator covers the live `skills/` surface only. The smoke test covers the current live scripted skills, including the formatter regression fixture. MCP, editor, and web-tool validation should be added per tool as those surfaces become more runnable in-repo.

## Agent Lanes at a glance

Use `Agent Lanes` when you need one of these explicit paths:

### Codex lane

Use this when you want MCP-side orchestration, structured analysis, review, or curation with bounded fallback behavior.

Recommended explicit names:

- skills: `codex-consult` (modes: consult / review / curate)
- tools: `codex_local_consult`, `codex_local_review`, `codex_local_curate`

### ChatGPT web lane

Use this when you want direct browser-mediated ChatGPT interaction, session-aware operations, or an explicit ChatGPT-web-side response.

Recommended explicit names:

- skills: `agent-lanes-chatgpt-web-query`, `agent-lanes-chatgpt-web-discuss`, `agent-lanes-chatgpt-web-curate`
- tools: `chatgpt5_web_query`, `chatgpt5_web_discuss`, `chatgpt5_web_curate`

### Routing rule

The naming rule is intentional:

- `agent-lanes-codex-*` means "prefer the Codex-side lane"
- `agent-lanes-chatgpt-web-*` means "prefer the direct ChatGPT web lane"

## Working rules

- `skills/` only contains tested, installable skills.
- `tools/mcp/`, `tools/editor/`, and `tools/web/` only contain real runnable or clearly bounded tool projects.
- Future ideas stay under `docs/incubating/skills/` or `docs/incubating/tools/` until they are proven enough to promote.
- Derived summaries are allowed in references; raw session or chat exports are not.

