---
title: Gem-hunt D4-D6 hub-hardening staged 2026-07-12
type: report
permalink: main/projects/gem-hunt-d4-d6-hub-hardening-staged-2026-07-12
tags:
- gem-hunt
- cloud-hub
- social-hub
- mcp-hardening
- staged
---

# Gem-hunt D4-D6 hub-hardening (STAGED, not applied) — 2026-07-12

STAGE-class build for gem-hunt item **D4-D6-hub-hardening**. Package at
`C:/Users/Prekzursil/.claude/gem-hunt-2026-07-12/staging/D4-D6-hub-hardening/`
(APPLY.md, hub-hardening.patch, artifact/, worktree/). **Live target never touched.**

## Key architectural finding
cloud-hub + social-hub are **lazy name-preserving MULTIPLEXERs** at
`agent-skills-toolchain/tools/mcp/{cloud,social}-hub/hub.py` (NOT `source/cloud-hub`).
Tool defs come from committed per-backend **caches**, not hand-written in hub.py. So the ONE
uniform place to harden owned+external backends is the hub's two seams: `HubServer.all_tools`
(advertised surface) and `handle_call` (dispatch). Owned FastMCP backends (modal/databricks/
compute/ovh) already carry `outputSchema` + some already have `confirm`/`dry_run` params;
NONE carry `annotations`. RunPod `delete-pod` already ships its own `annotations` (additive
merge must preserve it).

## What was built
- New shared module `_shared/hardening.py` (stdlib-only, like accounts.py) + 4 tiny seams in each hub.py.
- **D6 enrich_tools** (pure, additive): readOnly/destructive/idempotent annotations by
  token-boundary lexical classifier; schema-derived `Examples:` in descriptions (param-accuracy
  lever); `additionalProperties:false`+outputSchema on hub-owned `*_account_*` tools;
  structuredContent in `_handle_account`. Runtime: 409 tools → 46 destructiveHint / 157
  readOnlyHint / 142 examples.
- **D4 ConfirmGate**: 34 irreversible cloud tools (derived from DESTRUCTIVE class + extras
  ovh_vps_stop/reboot/stop-pod − core_stats_*). SHADOW by default (`HARNESS_HUB_CONFIRM_MODE`,
  value-free bounded rotating sink), enforce = block-unless-confirm + strips hub-native `_confirm`.
  social-hub has 0 confirm-gated (no irreversible tools — correct).

## Gotchas / lessons
- Substring keyword bug: `bm_list_skills`/`bm_set_skill_status` read "kill" out of "skills" →
  fixed with token-split equality (split on `_`/`-`, match by token, not substring).
- MCP has NO standard `input_examples` field → examples ride the `description` (master queue's own
  "examples in descriptions" phrasing). enums N/A at hub level (can't infer backend param enums).
- Shadow-default reconciles the build rail ("every gate ships shadow") with council C5 safety-tier:
  a live SHARED multi-session MCP server must not hard-block by default; enforce is 1 env-var away;
  native destructiveHint gives always-on client-side confirm meanwhile. Anti-zombie contract in
  `hardening.SHADOW_CONTRACT` (30-day promote-or-retire).

## Evidence
cloud-hub 96 passed, social-hub 38 passed (new suites + regression). Runtime tools/list enrichment
+ enforce-mode delete-pod block both proven through real hub.py stdio. `git apply --check` exit 0;
live `git status` clean. Bash tool was broken this session (profile EOF) → used PowerShell + python.
