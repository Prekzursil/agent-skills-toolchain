---
title: Reconciliation wave dispatch 2026-09-02
type: note
permalink: main/harness/reconciliation-wave-dispatch-2026-09-02
status: active
valid_as_of: '2026-09-02'
tags:
- reconcile
- cloud-workers
- fable
- basic-memory
- harness
---

- [decision] Item 2 deploy path: surgical (copy only the three MCP merge/supervisor scripts + tests repo-to-live after diff review, then --check, sync_shared_state.ps1, Cursor session restart); no full repo-to-live sync.
- [decision] Item 3 executions dispatched 02.09.2026 ~02:50 as six Cursor Cloud workers on claude-fable-5-1 (thinking, 1m, max), one PR per item, owner merges, workers forbidden to merge/delete/force-push: W1 BM transport best-of-best (proxy vs registry bridge vs stateless vs direct), W2 harness reunion, W3 ralph vendor, W4 #288 register intake, W5 #290 four files, W6 July branches (archive tags first, delete script only).
- [fact] Live ~/.agents is a checkout of agent-skills-toolchain; its working tree (167 files incl. the repaired bridge and tests) was captured to branch live-capture/2026-09-02 at 726687ec after gitleaks protect --staged reported 0 leaks; trash/ excluded; disk unchanged.
- [fact] Owner chose the model explicitly (Fable 1M max) for all six workers; prior Fable repo-repair run cost 113.04 USD over 2h26m, so six workers may cost several hundred USD; per-run cost is being tracked by the monitor.
- relates_to [[Cursor btw diagnosis and Fable PR 293 reconciliation 2026-09-02]]
- relates_to [[Basic Memory Cursor bridge resilient repair 2026-09-02]]

## Outcomes (02.09.2026 ~03:50)
- [fact] All six lanes finished; PRs opened owner-side (cloud agents hold PR creation for approval): #301 ralph lockfile (W3, 25 min, 20.22 USD), #302 #288 intake OQ-11..OQ-26 (W4, 18 min, 13.48), #303 July branch retirement report + 74 archive tags pushed, no deletions (W6, 40 min, 27.44), #304 #290 four files (W5, 3 runs, 22.68; Windows-only tests 35/35 verified locally), #305 BM transport (W1, 48 min, 32.93), #306 harness reunion 834->926 passed (W2, 58 min, 52.77). Wave total 169.52 USD, ~1h wall-clock.
- [decision] W1 chose the registry-declared per-session stdio bridge (x_cursor.stdio_bridge); the :8765 healing proxy stays a written proposal needing explicit owner approval. Evidence: TS MCP client stuck on stale sessions (typescript-sdk#1708), Basic Memory has no stateless flag, direct URL fails the dead-port window; bridge ~17 MiB private per Cursor window.
- [fact] W3 refuted re-vendoring: upstream v2.10.1 lockfile has 22 findings vs vendored 17; lockfile patched in place (16/17 cleared, residual esbuild dev-only ignored with dated reason) and gated.
- [fact] Open after the wave: merge_generated_cursor_mcp.py diverged both ways (26 live tests fail on main copy, 6 main tests fail on live copy) and #305 changes it further -> needs a reunion after #305 merges before live deploy; 17 non-July unmerged branches (9,781 absent lines) have no archive tags; the 74-branch delete script is owner-invoked only.
- [fact] Live box unchanged so far; surgical deploy waits for owner merges of #305 and #306.

## Checkpoint 02.09.2026 06:20 EEST
- [fact] All six wave-1 PRs merged owner-approved in order #303,#302,#301,#304,#305,#306 (main 72120810); July branches: 74 deleted after tag verification, 74 archive/2026-07 tags intact; remote branches 110 -> 34.
- [fact] Terminal storm root cause: retired AgentBridge enabled as Grok plugin user/0aaa06d9/agentbridge; its bridge-server crash-looped under grok.exe spawning a Windows Terminal window every ~20 s. Fixed: plugin moved to disabled in ~/.grok/config.toml (backup config.toml.bak-20260902-agentbridge), Grok sessions ended, npm package uninstalled. Cursor-Grok path is auth2api :8317 (config.toml [model."cursor-grok-4.6"]), not AgentBridge.
- [fact] Goose: hub extensions (:8765, :8812) enabled and a one-shot run via goose-cursor-proxy returned OK; ~/.config/goose is now a junction to %APPDATA%/Block/goose/config (XDG SSOT path = real file). Fabric: plain fabric OK via OpenRouter free; fabric-cursor OK on cursor-grok-4.6 after adding Gemini isolation to ~/.local/bin/fabric-cursor.ps1; new skill .agents/skills/fabric-patterns.
- [fact] Browser-bridge hub was killed by my orphan sweep (its 121 h old node/python looked orphaned) and restarted with Start-Hub.ps1 -Mode agent (ws 127.0.0.1:8770). Lesson: allowlist browser-bridge in any reaper.
- [fact] Claude MCP health (claude mcp list): 15 connected, 1 failed (fiddler :8868, only when Fiddler runs), ~50 disabled-for-project by design, 3 pending approval (playwright-extension, playwright-cdp, brightdata). Registry validates 42 servers; doctor false-positives "secret literal" on Bearer ${VAR} headers.
- [fact] P2 stage 1 done by this session: handoff/cloud-agent-2026-09-02 at f3a65022 with harness/ast-integrate (45,306 tracked files, 221 MB pack) captured via new sync-from-live -Only filter; W12 P2 loop-to-green lane dispatched from it on Fable 1M max.
- [fact] Wave-2/3 PRs open: #307 non-July branches (17 tags; worker briefly deleted 12 branches then restored them within 22 s - recorded), #308 BM healing proxy, #309 Cursor merge reunion, #310 search stack reunion (W11 still running extra runs). W10 OOM permanent fix still running.
- [decision] Cloud lanes this session: only claude-fable-5-1 thinking/1m/max, never Auto.