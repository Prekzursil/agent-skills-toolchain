# agent-skills-toolchain

Private platform repo for the installable skills, MCP-side contracts, editor-local tools, and browser-mediated agent tooling I use and evolve together.

## Purpose

This repo is the working home for four kinds of agent assets plus the docs and validation needed to keep them bounded:

- `skills/` for installable, validated skills
- `tools/mcp/` for MCP-native contracts, adapters, and promoted tool projects
- `tools/editor/` for editor-local tools such as VS Code extensions
- `tools/web/` for browser- or web-mediated tool projects with explicit session boundaries

The split matters because these surfaces have different runtime models, auth expectations, failure modes, packaging rules, and validation paths. Shared docs, incubation notes, and validation helpers live around them without blurring install, execution, and promotion boundaries. Future cross-platform packaging belongs in a packaging-only `release/` workspace so it does not become a fifth live execution surface or pollute the default runtime graph.

## Layout

- `skills/`
  - installable, validated skills only
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
- `scripts/`
  - repo-level helpers such as validation
- `release/`
  - packaging-only workspace for future Windows/Linux/macOS bundles; not a live execution surface

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

## Live surfaces

### Skills

Live installable skills currently ship from `skills/`:

- `quality-gate-automation-architect` - safe automation architecture for PR repair, coverage ratchets, analyzer debt burn-down, and merge governance.
- `codex-runtime-recovery` - diagnose split `CODEX_HOME`, state DB churn, and cross-host launch drift before destructive repair.
- `codex-session-reunion` - inventory, compare, and safely promote the best session copies into one canonical store.
- `format-codex-sessions` - render Codex rollout JSONL into readable Markdown transcripts without leaking prompt bulk or token-like data.
- `long-copy-orchestrator` - choose the right copy mechanism and monitor progress during large cross-host transfers.
- `wsl-vmware-cutover` - stage WSL-to-VMware migrations with D:-first backups and rollback checkpoints.
- `offline-linux-disk-surgery` - inspect, grow, or repair Linux guest disks offline.
- `windows-virtualization-conflict-triage` - classify Hyper-V, VBS, VMware, and `vmrun` conflict patterns safely.
- `codex-vscode-host-routing` - keep VS Code Codex hosted on Windows by default.
- `reboot-safe-ops-continuation` - capture resumable machine state before forced reboots.
- `agent-lanes-codex-consult` - explicitly select the Codex-side consultation lane.
- `agent-lanes-codex-review` - explicitly select the Codex-side review lane.
- `agent-lanes-codex-curate` - explicitly select the Codex-side curation lane.
- `agent-lanes-chatgpt-web-query` - explicitly select the direct ChatGPT web query lane.
- `agent-lanes-chatgpt-web-discuss` - explicitly select the direct ChatGPT web discussion lane.
- `agent-lanes-chatgpt-web-curate` - explicitly select the direct ChatGPT web curation lane.

### Tools

The live tool surfaces are first-class repo homes for bounded tool projects and contracts:

- [`tools/mcp/`](tools/mcp/README.md)
- [`tools/editor/`](tools/editor/README.md)
- [`tools/web/`](tools/web/README.md)

Current bounded projects:

- [`tools/mcp/agent-lanes-codex/`](tools/mcp/agent-lanes-codex/README.md)
- [`tools/mcp/workstation-codex-bundle/`](tools/mcp/workstation-codex-bundle/README.md)
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

- skills: `agent-lanes-codex-consult`, `agent-lanes-codex-review`, `agent-lanes-codex-curate`
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
