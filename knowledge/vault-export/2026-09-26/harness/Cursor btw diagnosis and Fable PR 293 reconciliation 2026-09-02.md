---
title: Cursor btw diagnosis and Fable PR 293 reconciliation 2026-09-02
type: note
permalink: main/harness/cursor-btw-diagnosis-and-fable-pr-293-reconciliation-2026-09-02
valid_as_of: '2026-09-02'
status: active
tags:
- cursor
- btw
- basic-memory
- fable
- reconcile
- tui
---

- [fact] Cursor CLI has a native /btw side-question command since the April 2026 release; the "internal blob error in long or compacted sessions" fix shipped in the 13.07.2026 release.
- [fact] This session runs build 2026.08.28-50f0823 (three node processes, resumed session); the updated launcher resolves 2026.09.01-cd08a95. Both postdate the July fix.
- [fact] 68 recent Cursor CLI log files contain no /btw entries and the session transcript holds only a plain-text "btw" message, so no native /btw invocation is evidenced in this session; the reported "does not work properly" symptom remains unreproduced.
- [decision] /btw side questions are scheduled for the universal TUI as TUI-G-9D in CURSOR-TUI-GRILL_2026-09-01.md: read-only snapshot semantics, never appended to the agent transcript, mid-turn, overlay UI, works for local and cloud workers with capability grading.
- [fact] Fable cloud agent bc-48aeb78a merged PR #293 into agent-skills-toolchain main at 22:05Z on 01.09.2026 (merge shown under the owner identity; the same agent later ran gh pr merge itself), then continued: merged #296, opened #297 (TypeScript 7, 71/71 tests), closed four superseded PRs, deleted 14 fully-contained branches (tip SHAs recorded), Dependabot alerts 0. First run settled at 99.84 USD; eight follow-up runs unsettled.
- [bug] Conflict to reconcile: PR #293 makes merge_generated_cursor_mcp.py registry-authoritative so Cursor would get the direct HTTP URL for basic-memory, dropping the stdio bridge. The bridge exists specifically to survive Cursor's stale mcp-session-id after :8765 daemon restarts. Running sync_shared_state.ps1 with the new merge script would discard the repaired bridge unless the bridge is registered as the Cursor transport.
- [fact] The live bridge C:\Users\Prekzursil\.agents\scripts\bm_cursor_http_session.py and its tests are untracked in the live .agents repo and absent from agent-skills-toolchain; they are at risk from any repo-to-live sync until committed by the owner.
- relates_to [[Basic Memory Cursor bridge resilient repair 2026-09-02]]
- relates_to [[Memory contract SSOT]]
- relates_to [[Cursor MCP integration]]

## Final ledger (agent idle 23:02Z, 01.09.2026)
- [fact] 12 runs over 2h26m (19.2, 2.0, 12.9, 2.4, 8.8, 8.4, 20.4, 17.3, 32.8, 1.5, 5.5, 14.6 min); settled charge 113.04 USD; 151.7M total tokens, 288k output tokens.
- [fact] Outcome: 9 PRs merged (#288 #293 #294 #295 #296 #297 #298 #299 #300), 2 closed as superseded (#286 #290), 14 fully-contained branches deleted with tip SHAs recorded, 0 open PRs, 0 open Dependabot alerts; all 8 main workflows green at 5c6e1bae, the first fully green main since 26.08.2026.
- [fact] Fable's own report states a GitHub PAT appeared in its cloud transcript. Blast radius: the Cursor Cloud transcript store for agent bc-48aeb78a, readable by the account and subject to Cursor retention; the agent says it did not persist it. Per the standing NEVER-ROTATE rule, no rotation was performed or proposed; owner decision.
- [fact] Surfaced, not gated: tools/editor/ralph-orchestrator/vendor/package-lock.json carries 17 npm-audit findings (1 critical, 10 high); fix is re-vendoring.
- [decision] Deploy of PR #293 to the live box is NOT done. Before running merge_generated_cursor_mcp.py --check / sync_shared_state.ps1, decide bridge-vs-direct-HTTP for basic-memory so the repaired stdio bridge is not silently dropped.
- [fact] Owner items left by Fable: re-vendor ralph-orchestrator; intake #288 questions into REGISTER.md; the 4 contested #290 files; the two diverged harness lineages and missing Cursor hook provider; the 74 July branches (deleting them loses history).