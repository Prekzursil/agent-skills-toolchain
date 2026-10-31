---
title: README
type: note
permalink: dqverify-repo-20261013/readme
---

# agent-skills-toolchain

Full configuration and toolchain repo for all my AI agents: Codex CLI, Claude Code, and Gemini CLI. Contains 370+ skills, 40+ MCP server configs, shared tool libraries, and platform config snapshots - all plug-and-play.

## Quick Start

```bash
# Clone
git clone https://github.com/Prekzursil/agent-skills-toolchain.git
cd agent-skills-toolchain

# Register and install the single Claude Code skill surface
claude plugin marketplace add Prekzursil/agent-skills-toolchain --sparse .claude-plugin .agents/skills skills skills-claude-only
claude plugin install agent-skills-toolchain@agent-skills-toolchain

# Unlock encrypted credential stores (accounts.json) for plug-and-play MCP hubs.
# Needs git-crypt + the exported key from your password manager. See docs/SECRETS.md.
git-crypt unlock /path/to/agent-skills-toolchain.gitcrypt.key

# Install dependencies
npm install

# Verify the node workspaces
npm test

# Mount Codex as an MCP server (replaces the retired in-repo orchestrator)
claude mcp add --scope user codex -- codex mcp-server
claude mcp get codex          # expect: Connected
```

## What This Repo Contains

| Surface | Count | Description |
|---------|-------|-------------|
| `skills/` | 372 | Shared skills for Codex + Claude (see `SKILLS-MANIFEST.md`); incl. game-RE (`game-re-binary`, `game-frida-trace`, `game-find-anticheat`, `game-unpack-pe`) + SWFOC + Battle Cats |
| `skills-claude-only/` | 35 | Claude Code exclusive skills (Azure, metaswarm, Ralph, etc.) |
| `tools/mcp/` | 24 | MCP server projects (workstation bundle, cloud-hub, search-hub, hexstrike-ai, etc.) |
| `tools/web/` | 0 | Empty since the 2026-08-09 ChatGPT-web retirement; reserved surface |
| `tools/lib/` | 6 | Dependency-free shared ES modules extracted from the retired trees |
| `tools/editor/` | 2 | Metaswarm + Ralph Orchestrator |
| `release/platforms/windows/` | 8 | Config snapshots: Codex (40 MCPs), Claude (39 MCPs), Gemini (33 MCPs) |
| `docs/` | — | Architecture docs, codex-consult analysis, plans, dated session reconciliations |

> **2026-06-10 session:** added 4 game-RE skills; new MCP servers **`ocr`**
> (multi-engine OCR + accuracy eval — separate repo
> [`Prekzursil/abbyy-finereader-ocr-mcp`](https://github.com/Prekzursil/abbyy-finereader-ocr-mcp)), **`basic-memory`**
> (durable vector memory + compaction-survival hooks), **`firefox-devtools`**; and a
> cross-AI **mcp-funnel single-source** setup (dedup + switchable profiles, skills
> unified across Claude Code + Codex). See
> [`docs/SESSION-RECONCILIATION-2026-06-10.md`](docs/SESSION-RECONCILIATION-2026-06-10.md).

## Scholarly Access MCP (open-access paper retrieval)

`tools/scholarly-access-mcp/` is a scholarly-retrieval MCP server — the compliant
replacement for a Sci-Hub MCP. It resolves DOI / PMID / arXiv / title queries, classifies access
honestly, and routes **only** to available open-access and rights-holder-entitled sources
(Crossref, OpenAlex, Unpaywall, Europe PMC, arXiv, Semantic Scholar, CORE, DOAJ, PubMed, Zenodo).

> No silent fallback. `paper_download_oa_pdf` only fetches allowlisted hosts that serve a real `%PDF`.

8 tools: `paper_resolve`, `paper_fetch_metadata`, `paper_find_oa_pdf`, `paper_access_status`,
`paper_citation_graph`, `paper_download_oa_pdf`, `paper_summarize`, `paper_batch_resolve`.

```bash
cd tools/scholarly-access-mcp
python -m venv .venv && .venv/Scripts/python -m pip install -e .
.venv/Scripts/python -m pytest tests/test_policy.py -q   # 24 offline policy/gate tests
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

## Codex consultation

**Retired 2026-08-09.** This section used to document `codex_consult`: a two-lane
consultation stack where Lane B drove the ChatGPT web UI through a local Electron app
(Agentify Desktop) and Lane A fell back to `codex exec`. Five trees implemented it and all
five were deleted — `tools/mcp/codex-orchestrator`, `tools/mcp/agent-lanes-codex`,
`tools/web/agentify-desktop`, `tools/web/promptbridge-talk-lane`,
`tools/web/agent-lanes-chatgpt-web` — together with the root `mcp-server.mjs` shim, the
`npm run mcp:serve` / `talk:serve` / `orchestration:*` scripts, and the two npm workspaces.

Why: the orchestration half is delivered natively by OpenAI's own `codex mcp-server`, and
the web half had already stopped working — the runtime directory it deployed
(`CODEX_HOME/promptbridge-runtime/`), its config (`~/.codex/promptbridge-orchestration.toml`)
and its state directory (`~/.promptbridge-desktop`) were all absent, and no live agent config
registered the server.

**Use instead:**

```bash
claude mcp add --scope user codex -- codex mcp-server
```

Then call `mcp__codex__codex` to start a Codex thread and `mcp__codex__codex-reply` to
continue one by `threadId`. There is no per-mode tool — consult / brainstorm / review /
discuss / coordinate / curate are framings inside the prompt, and parallel calls replace the
orchestration server's fan-out. See [`docs/multi-agent-quickstart.md`](docs/multi-agent-quickstart.md)
for the mapping from each retired tool to its replacement.

The pre-retirement architecture is recorded, unedited, in
[`docs/codex-consult-analysis.md`](docs/codex-consult-analysis.md) (dated 2026-04-04).
Reusable code extracted before the delete lives in [`tools/lib/`](tools/lib/README.md).

## Purpose

This repo is the working home for four kinds of agent assets plus the docs and validation needed to keep them bounded:

- `skills/` for installable, validated skills (372 shared + 35 Claude-only)
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

### 2. Agent Lanes — RETIRED 2026-08-09

**Agent Lanes** was the replacement name for the older PromptBridge-style label: a Codex-side
orchestration lane, a direct ChatGPT web lane, and skills that chose between them. All of it
was deleted — `tools/mcp/agent-lanes-codex/`, `tools/web/agent-lanes-chatgpt-web/` and the
`agent-lanes-*` skills. The lane concept is gone, not renamed: there is one rail now, the
official `codex mcp-server`.

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

Live installable skills currently ship from the authoritative `.agents/skills/` tree:

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
- `using-superpowers`, `brainstorming`, `writing-plans`, `executing-plans`, `systematic-debugging`, `test-driven-development`, `verification-before-completion`, `dispatching-parallel-agents`, `subagent-driven-development`, `requesting-code-review`, `receiving-code-review`, and `using-git-worktrees` - general-purpose workflow skills promoted from the current local Codex skill set.
- `codex-orchestrate` - the one skill for reaching Codex on the MCP rail (`mcp__codex__codex` / `mcp__codex__codex-reply`); the mode (brainstorm / discuss / coordinate / review / audit / curate / governance / triage) is a prompt framing, not a tool name.
- `codex-invoke` - the exec rail, and the only way to scope a Codex run (model, sandbox, MCP allowlist, skills allowlist, `--output-schema`).
- `multi-agent-quickstart` - the beginner mental model for those two.
- **Dead but still present (2026-08-09):** nine one-line per-mode wrappers — `codex-audit`, `codex-brainstorm`, `codex-coordinate`, `codex-curate`, `codex-discuss`, `codex-fix`, `codex-governance`, `codex-review`, `codex-triage` — each point at a `codex_*` MCP tool that no longer exists, and `codex-orchestrate` supersedes all of them. They could **not** be removed in this pass: they are canonical-only (no `skills/` projection), and `ci/check_skill_dual_write.py --strict-parity` rejects a canonical deletion unless the projection counterpart is deleted in the same diff — a counterpart that never existed. Blocker documented; they are not deployed to the live harness, since `scripts/sync-skills.ps1` deploys from `skills/`.
- **Retired 2026-08-09:** `codex-consult` is now a redirect tombstone (kept, not deleted, because that name *is* deployed live). `chatgpt5-web` survives but carries a warning: its `chatgpt5_web_*` bridge tools have no in-repo implementation.

### Tools

The live tool surfaces are first-class repo homes for bounded tool projects and contracts:

- [`tools/mcp/`](tools/mcp/README.md)
- [`tools/editor/`](tools/editor/README.md)
- [`tools/web/`](tools/web/README.md)

### Userscripts

Browser userscripts (Tampermonkey/Violentmonkey) live in [`userscripts/`](userscripts/README.md):

- `github-pat-quick-fill.user.js` - one-click **max all** GitHub fine-grained PAT permissions; DOM-driven (no hardcoded permission list), survives GitHub adding/removing permissions, handles every permission category.

Current bounded projects:

- [`tools/mcp/workstation-codex-bundle/`](tools/mcp/workstation-codex-bundle/README.md)
- [`tools/mcp/cheatengine-mcp-bridge/`](tools/mcp/cheatengine-mcp-bridge/README.md) - thin wrapper around the upstream Cheat Engine MCP Bridge with local install and validation helpers.
- [`tools/mcp/hexstrike-ai/`](tools/mcp/hexstrike-ai/README.md) - thin wrapper around the upstream HexStrike AI runtime with localhost bootstrap and client registration helpers.
- [`tools/editor/metaswarm/`](tools/editor/metaswarm/README.md) - vendored upstream metaswarm workspace.
- [`tools/lib/`](tools/lib/README.md) - dependency-free shared ES modules (path containment, workspace detection, git-diff review packets, an idempotency ledger, a loopback-only address allowlist, Windows Codex-binary resolution).

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

## Reaching Codex at a glance

There is one rail, and one choice on it: MCP or exec.

### MCP rail — `codex-orchestrate`

Use for intent-routed orchestration: analysis, review, audit, curation, triage. Tools:
`mcp__codex__codex` (start a thread) and `mcp__codex__codex-reply` (continue by `threadId` —
hyphenated). The mode lives in the prompt; there is no per-mode tool. Multi-peer modes are
parallel calls you synthesize yourself.

### Exec rail — `codex-invoke`

Use whenever the run must be **scoped**: a specific model or reasoning effort, a sandbox or
approval policy, an MCP allowlist or sealed base, a skills allowlist, or structured
`--output-schema` output. The MCP rail inherits the full base and cannot scope. Never
hand-roll `codex exec` argv.

### Retired 2026-08-09 — the two-lane "Agent Lanes" model

The `codex_local_*` / `codex_orchestrator_*` Codex lane and the browser-mediated ChatGPT web
lane are both gone; so are the `agent-lanes-*` skills that chose between them. `codex-consult`
remains only as a redirect tombstone.

The ChatGPT web side keeps one consolidated skill name — the six per-mode aliases it replaced
stay retired:

- skills: `chatgpt5-web` (modes: query / discuss / curate)

but its `chatgpt5_web_*` bridge tools are supplied by an external bridge, not by this repo,
so verify they are mounted in your session before relying on it.

## Working rules

- `skills/` only contains tested, installable skills.
- `tools/mcp/`, `tools/editor/`, and `tools/web/` only contain real runnable or clearly bounded tool projects.
- Future ideas stay under `docs/incubating/skills/` or `docs/incubating/tools/` until they are proven enough to promote.
- Derived summaries are allowed in references; raw session or chat exports are not.