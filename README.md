# agent-skills-toolchain

Private platform repo for the skills, MCP-native tools, and web-agent tooling I use and deploy together.

## Purpose

This repo keeps three live surfaces separated on purpose:

- `skills/` for installable, validated skills
- `tools/mcp/` for MCP-native tools and adapters
- `tools/web/` for browser- or web-mediated agent tooling

The split matters because these surfaces have different runtime models, auth expectations, validation paths, and deployment risks. Shared docs, incubation notes, and validation helpers live around them without blurring the install or execution boundaries.

## Layout

- `skills/`
  - installable, validated skills only
- `tools/mcp/`
  - MCP-native tools and adapters that are runnable or otherwise clearly bounded
- `tools/web/`
  - browser- or web-mediated tools that are runnable or otherwise clearly bounded
- `docs/plans/`
  - repo-level design documents and implementation notes
- `docs/incubating/skills/`
  - future skill concepts that are not installable yet
- `docs/incubating/tools/`
  - future MCP or web-tool concepts that are not runnable yet
- `scripts/`
  - repo-level helpers such as validation

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

### Tools

The tool surfaces are first-class repo homes, even though they do not have a shipped runnable tool yet:

- [`tools/mcp/`](tools/mcp/README.md)
- [`tools/web/`](tools/web/README.md)

Speculative tool ideas do not live here. They stay under `docs/incubating/tools/` until they become real bounded projects.

## Validation

Validate all live skills from the repo root:

```powershell
pwsh -File .\scripts\validate-all-skills.ps1
```

That helper validates the live `skills/` surface only. MCP and web-tool validation will be added per tool when those surfaces gain runnable projects.

## Working rules

- `skills/` only contains tested, installable skills.
- `tools/mcp/` and `tools/web/` only contain real runnable or clearly bounded tool projects.
- Future ideas stay under `docs/incubating/skills/` or `docs/incubating/tools/` until they are proven enough to promote.
- Derived summaries are allowed in references; raw session or chat exports are not.
