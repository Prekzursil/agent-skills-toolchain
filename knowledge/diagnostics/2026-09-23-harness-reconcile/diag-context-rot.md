# Diagnosis: context rot that ate usage — the EXISTING fix and how to apply it on the VM

Wave: DIAGNOSIS (READ-ONLY). Author: VM subagent. Date: 2026-09-23.
Machines: VM = offload-w2025 (this box). HOME = desktop-a60s9gp (read via rclone remote `homeC:`).

## TL;DR
The fix already exists and is CODE + SETTINGS that live on HOME's `~/.claude/settings.json` and on the
shared toolchain. It was never copied to the VM. The VM's `~/.claude/settings.json` is a 758-byte stub with
NO env block, NO hooks, NO skill-listing budget cap, and NO MCP curation, while it loads a full **418-skill**
tree and a large MCP fleet. HOME's settings.json is **26,038 bytes** and carries every context-rot lever.
Applying the fix = port HOME's `skillListingBudgetFraction`, `env` block, `deniedMcpServers`, and hook wiring
into the VM settings.json. The hook scripts and router the fix depends on already exist on the VM disk
(`~/.agents/harness/dispatcher.py`, `~/.claude/hooks/semantic-router/route.py`), just unwired.

This is NOT a new design. It is a port of an already-shipped configuration.

---

## What "context rot that ate usage" actually is (root cause per owner's own notes)
- MEMORY.md index (VERIFIED, C:\Users\prekzursil\.claude\projects\C--Users-prekzursil\memory\MEMORY.md):
  - "Harness health verdict 2026-07-04 — naive-sessions root cause = **skills-context-budget overflow**;
    fix: **curated daily skills + vault lazy via router**."
  - "Harness drift fix 2026-07-04 — behavior-drift root cause = calibrated-silence suppressing the router;
    floor patch applied."
  - "Estate MCP/TUI audit 2026-09-19 — a huge always-on MCP tool count is itself a context-bloat source;
    output-size discipline (400 [1210] kill)."
- Mechanism: at session start the CLI charges the frontmatter (name+description) of every skill in the skill
  roots, plus every connected MCP server's tool schemas, into the window. With 418 skills and a large MCP
  fleet and no budget cap, that fixed overhead is huge every turn — that is the "rot" that eats usage.

## The fix, named precisely (three layers, all already existing)

### Layer 1 — native skill-listing budget cap (the primary lever). VERIFIED.
- Key: `"skillListingBudgetFraction": 0.04` — present in HOME settings.json (line 3), ABSENT on VM
  (VM grep count = 0). This caps the skill LISTING to 4% of the context window; the CLI samples/truncates
  the listing to stay under budget instead of dumping all 418 descriptions.
- Companion: `"cleanupPeriodDays": 365` (HOME) — housekeeping, minor.

### Layer 2 — env block: tool-search deferral + output-size discipline. VERIFIED (present HOME, absent VM).
HOME `env` block (VM has NO `env` block at all):
- `"ENABLE_TOOL_SEARCH": "auto:5"` — defers MCP tool schemas behind ToolSearch (lazy-load) instead of
  loading all schemas at start. (Note: the VM session already shows deferred tools, so a newer CLI default
  is partially deferring — but the VM still connects the full fleet; setting this explicitly + Layer 3 is the
  intended state.)
- `"MAX_MCP_OUTPUT_TOKENS": "50000"`, `"CLAUDE_CODE_MAX_OUTPUT_TOKENS": "64000"`,
  `"BASH_MAX_OUTPUT_LENGTH": "150000"` — cap runaway tool/command output (the "400 [1210] kill" discipline).
- `"ECC_CONTEXT_MONITOR_COST_WARNINGS": "0"`, `"ECC_GATEGUARD": "off"` — silence the ECC cost-warning noise
  the owner's memory flagged as itself contributing to drift.
- `"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "90"` — push autocompact later so usage is not spent on premature
  compaction churn.
- Plus operational env: `CLAUDE_CODE_USE_POWERSHELL_TOOL`, `CLAUDE_CODE_FORK_SUBAGENT`,
  `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`, MCP timeouts, `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH: 5`, etc.

### Layer 3 — MCP curation (reduce the connected fleet). VERIFIED present HOME, absent VM.
- HOME `"deniedMcpServers": [...]` denies claude-code-mcp, markitdown, rdkit, serena, gitlab, meta-tool
  (list continues). VM settings.json has no `deniedMcpServers`. Fewer connected servers = fewer tool schemas
  charged. (Deeper MCP-fleet reconciliation is a sibling lane — the `/mcp-fleet-curation` skill and
  `scripts/reap_orphan_mcp.ps1`, `scripts/mcp_ram_audit.ps1`, `scripts/apply-mcp-health-fixes.ps1`.)

### The router + curated-skills machinery the notes call for (already on VM disk, unwired). VERIFIED.
- "vault lazy via router" = `~/.claude/hooks/semantic-router/route.py` (16,149 bytes, present on VM),
  wired on HOME as a `UserPromptSubmit` hook. It routes each prompt to relevant skills/rules on demand
  instead of front-loading them.
- "curated daily skills" mechanism = `scripts/deploy-skills-daily.py` in the toolchain — deploys the repo
  `.agents/skills` to `~/.claude/skills.daily` as "the ONE tree Claude Code reads" (the last-hop deployer).
  NOTE: neither VM nor HOME currently has a populated `skills.daily` (both = 0), so the ACTIVE lever on HOME
  today is Layer 1 (`skillListingBudgetFraction`) + Layer 2 (`ENABLE_TOOL_SEARCH`), not a physical
  skills.daily tree. `skills.daily` is the available deeper option, not the currently-relied-on one.
- The shared harness dispatcher `~/.agents/harness/dispatcher.py` (28,962 bytes, present on VM) is wired on
  HOME across SessionStart/UserPromptSubmit/PreToolUse — it owns goal re-injection + event-ledger replay
  (the anti-drift / anti-usage-waste behaviors). Wiring it is primarily the "harness wiring" lane, but its
  SessionStart replay is part of why HOME does not re-spend usage re-explaining state.

- `/context-budget` command (VERIFIED at C:\Users\prekzursil\.claude\commands\context-budget.md) is the
  MEASUREMENT tool, not the fix. It is self-contained (an earlier revision pointed at a non-existent
  `skills/context-budget/SKILL.md`). Reference budget-split implementation:
  `ci/check_skill_context_budget.py` (8,000-char per-skill trigger ceiling).

## Current bloat, quantified (VERIFIED)
- VM `~/.claude/skills` = **418 skill entries**; `~/.agents/skills` = **418**. No `skills.daily`. No budget cap.
- VM settings.json = **758 bytes** (grep for skillListingBudgetFraction / ENABLE_TOOL_SEARCH / deniedMcpServers
  = 0 hits). HOME settings.json = **26,038 bytes** with all three.
- MCP fleet: ~30+ servers reported failing to connect this session (system reminder); prior audit put the
  estate at ~81 servers / 14 surfaces. Each connected server's schemas are session-start tax.
- Exact token cost is NOT-CHECKED here (would require running `/context-budget` after resolving the window;
  out of scope for this read-only lane). The 418-skill listing with no 4% cap is the dominant term.

## Exact ordered steps to apply on the VM (for the implementation wave — DO NOT run now)
1. Back up VM `~/.claude/settings.json` (it is only 758 bytes).
2. Read HOME's full settings.json: `rclone cat homeC:/Users/prekzursil/.claude/settings.json`
   (saved this session to /tmp/home_settings.json, 26,038 bytes).
3. Merge into VM settings.json, in priority order:
   a. `"skillListingBudgetFraction": 0.04`  (Layer 1 — biggest single win).
   b. The entire `env` block (Layer 2) — especially `ENABLE_TOOL_SEARCH: "auto:5"`,
      `MAX_MCP_OUTPUT_TOKENS`, `CLAUDE_CODE_MAX_OUTPUT_TOKENS`, `BASH_MAX_OUTPUT_LENGTH`,
      `ECC_CONTEXT_MONITOR_COST_WARNINGS: "0"`, `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE: "90"`.
   c. `"deniedMcpServers": [...]` (Layer 3) — but reconcile against which servers the VM actually needs;
      coordinate with the MCP-fix lane before adopting HOME's exact deny list verbatim.
   d. The `hooks` block (SessionStart / UserPromptSubmit / PreToolUse …) — the scripts it references already
      exist on the VM (`~/.agents/harness/dispatcher.py`, `~/.claude/hooks/semantic-router/route.py`, etc.).
      Verify each referenced path resolves on the VM before wiring; this overlaps the "harness wiring" lane.
4. Keep the VM's own `permissions.additionalDirectories` (C:\, C:\suite, etc.) and its model rows — merge,
   do not blindly overwrite with HOME's.
5. Restart Claude Code on the VM (settings.json + env + skill-budget take effect at session start).
6. Verify: run `/context-budget --verbose` after restart; confirm the skill listing is now capped and the
   fixed overhead dropped. Confirm SessionStart hook fires (durationMs in transcript) per the metaswarm
   latency note.

## Provenance / label
- VERIFIED (paths + byte counts + grep): VM settings 758B no keys; HOME settings 26,038B with all three
  layers; VM 418 skills; router.py + dispatcher.py present on VM disk; /context-budget is measurement-only.
- INFERRED: exact token savings (not measured here); that HOME's active lever is the budget-fraction rather
  than a physical skills.daily (both skills.daily = 0, so inferred from what is present).
- The precise "harness health verdict" / "drift fix" note bodies were NOT found as discrete files on the VM
  local memory dir or the D:\basic-memory vault (basic-memory daemon is DOWN); the citations above are from
  the MEMORY.md index lines, which are on-disk and VERIFIED.
