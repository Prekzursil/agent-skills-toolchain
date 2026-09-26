---
name: agent-skills-toolchain-mechanics
description: How to author/add a skill to the agent-skills-toolchain repo — canonical
  checkout, propagation to live dirs, manifest, and validator location/rules
metadata:
  node_type: memory
  type: reference
  originSessionId: 9c274ad5-1d28-40fd-bfc0-e434ac596a9c
permalink: main/claude-memory/root/reference-agent-skills-toolchain
---

Operational map for adding skills to **Prekzursil/agent-skills-toolchain** (GitHub).

**Canonical checkout (use this one):** `~/source/agent-skills-toolchain` — main, cleanest, most recent. TRAP: there are ~5 duplicate clones (`~/Desktop/...`, `~/Downloads/...`, `~/work/agent-skills-toolchain-re`, `~/Desktop/uber_decompialtion/...`) all pointing at the same remote but **months stale**. Always work in `~/source/`.

**Skill layout:** `skills/<name>/SKILL.md` (shared: Codex+Claude+Gemini, ~135) vs `skills-claude-only/<name>/SKILL.md` (~35). Platform-agnostic CLIs go in `skills/`.

**Propagation to live (manual copy, NOT symlink/auto-sync):** repo `skills/` is the source of truth; live skills live in `~/.agents/skills/` (a *copy* — repo is often newer). `~/.claude/skills` → symlink → `~/.agents/skills`. To make a new skill live for Claude: `Copy-Item repo\skills\<name> ~\.agents\skills\<name> -Recurse -Force`. It then shows in the Skill tool list.

**Bulk deploy (2026-06-09, replaces one-by-one):** (1) `scripts/sync-skills.ps1` copies ALL repo skills → `~/.agents/skills` in one pass (`-IncludeClaudeOnly`, `-Prune` to drop deleted ones, `-WhatIf` dry-run). (2) Declarative path: root `.claude-plugin/{marketplace.json,plugin.json}` (marketplace name `agent-skills-toolchain`, plugin `agent-skills-toolchain`, source `./`, default `./skills` discovery = 152 skills) → `claude plugin marketplace add .` then `claude plugin install agent-skills-toolchain@agent-skills-toolchain` deploys all at once; works on Claude Code web when the repo is connected. Caveats: default discovery covers `skills/` only (not `skills-claude-only/` — add a `skills` override later); bundling all 152 includes vendored superpowers/voice/humanizer copies → may collide with the superpowers marketplace. The paper/scholarly MCP under `tools/` is NOT in the bundle (skills-only).

**codex skill consolidation (2026-06-09):** the 7 redundant local lanes (`codex-local-{consult,curate,review}` + `agent-lanes-codex-{consult,curate,review}` + `promptbridge-codex-consult`) were deleted and replaced by ONE `codex-consult` skill (modes consult/curate/review → `codex_local_*`/`codex_orchestrator_*`). The 9 "good" codex-as-MCP critic skills (`codex-review`, `codex-brainstorm`, `codex-discuss`, `codex-audit`, `codex-curate`, `codex-coordinate`, `codex-fix`, `codex-governance`, `codex-triage`) and infra skills (`codex-runtime-recovery`, `codex-session-reunion`, `format-codex-sessions`, `codex-vscode-host-routing`) were kept. Also fixed: the 4 scholarly skills (`scholarly-literature-review`, `oa-pdf-retrieval`, `biomedical-paper-triage`, `drug-discovery-literature-bridge`) had NO `description:` frontmatter (invalid/non-loadable) → added + registered in manifest.

**Manifest:** `skills/SKILLS-MANIFEST.md`, hand-maintained (no generator). Add a row `| name | custom | Use when... |` in alphabetical order + bump `> Last updated:`.

**Validator:** `~/.codex/skills/.system/skill-creator/scripts/quick_validate.py <skill-dir>` (needs Python w/ PyYAML). Frontmatter rules: only `name`/`description`/`license`/`allowed-tools`/`metadata`; `name` hyphen-case ≤64; `description` ≤1024 chars and **no `<`/`>` angle brackets**. Repo batch runner `scripts/validate-all-skills.ps1` only validates a fixed ~67-skill subset (NOT manifest-driven), so new dirs won't appear there — rely on `quick_validate.py` directly. **WINDOWS GOTCHA: always run it with `PYTHONUTF8=1`** — `quick_validate.py` does `read_text()` without encoding, so any SKILL.md with non-ASCII (curly quotes, em-dash) throws `UnicodeDecodeError: cp1252` on Windows; it's NOT a skill defect. The repo's `validate-all-skills.ps1` sets PYTHONUTF8=1 for this reason. **When VENDORING external skills** (e.g. 2026-05-30: ghostwriter voice-*/humanizer/slopornot agentic-humanizer+slop-check), upstream frontmatter often has `version`/`platforms`/`compatibility` → move under `metadata:` (validator rejects them); keep each upstream LICENSE per-skill + add `metadata.source`/`upstream_author`; keep co-dependent skills siblings (voice-* reference `../voice-apply/references/ai-tells.md`).

**Conventions:** conventional commits (`feat(skills): add <name> skill`), attribution disabled, no pre-commit hooks. Related: [[feedback_peer_review]] (2 reviewers caught/were-rejected here), [[feedback_full_rigor]].