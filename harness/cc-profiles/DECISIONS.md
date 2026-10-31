---
title: DECISIONS
type: note
permalink: dqverify-repo-20261013/harness/cc-profiles/decisions
---

# cc-profiles — resolved decision log (grill 2026-10-24, program depth)

| # | Decision |
|---|---|
| G-1 | Claude profile auth = subscription OAuth primary (API-key variant documented in claude.profile.json.auth) |
| G-2 | GLM profile default model = glm-5.3[1m]; tiered aliases fix the /model haiku no-op (haiku -> glm-5.3-flash[1m]) |
| G-3 | Claude profile default model = claude-opus-5-5 (docs-verified current Opus); fallback ["claude-sonnet-5"] |
| G-4 | User-scope ANTHROPIC_API_KEY shadow DELETED (was forcing API-key auth over OAuth); cc-status watches for its return |
| G-5 | glm-plan-bug stays GLM-profile-only; history-cap patch applied to the re-homed vendor copy (fixes Windows argv-length failure, trims transcript shipment) |
| G-6 | Unified dual-provider profile (local per-model router) deferred pending deep feasibility fleet (estate-health-audit, unified-router finder) |
| G-7 | Marketplace re-homed to profiles/vendor/zai-coding-plugins; both registrations re-pointed (settings.json + known_marketplaces.json) |
| G-8 | Failover guard patch applied to zai_key_failover.py (sentinel check, fails open to glm behavior; nuance: explicit --probe-only under an active claude sentinel is also suppressed — pass CC_ACTIVE_PROFILE=glm to force) |
| D9 | Chelper stays installed; `chelper auth reload claude` RETIRED (cc-use is the only config writer; cc-status detects chelper stomps) |
| D10 | Statusline shows a dim `claude` segment ONLY on claude-profile sessions (silent-until-deviation, per the statusline's own design doctrine); glm stays the untagged default |
| D11 | cc-cc always launches with --strict-mcp-config --mcp-config clean-mcp.json (19 neutral servers); cc-glm never strips |
| D12 | First `cc-use claude` flip is OWNER-RUN, between sessions (live TUIs hot-reload settings) |

## Rollback
- Level 1 (seconds): `cc-use glm`
- Level 2 (full uninstall): restore all four files from backups/premigration-20261024-023146/, revert zai_key_failover.py from the same snapshot, delete ~/.claude/profiles + the 8 ~/.local/bin/cc-* files, revert the two statusline-command.sh edits. Scheduled task and ZAI_* env vars were never touched.

## Pending verification (owner smoke test, step 10)
- (a) empty-string env values in claude-session.json act as unset for provider selection;
- (b) enabledPlugins:false in a --settings payload disables a plugin (only matters for overlay use).
If (a) fails: switch cc-cc to a CLAUDE_CONFIG_DIR junction-overlay root whose settings.json simply lacks the GLM keys (estate-verified removal mechanism).