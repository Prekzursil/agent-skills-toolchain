---
title: 'Handoff: ai-sessions-render owns the ChatGPT conversation-merge (2026-07-23)'
type: report
permalink: main/projects/session-tooling/handoff-ai-sessions-render-owns-the-chat-gpt-conversation-merge-2026-07-23
tags:
- handoff
- ai-sessions-render
- chatgpt
- agentify
- session-bridge
- compaction-checkpoint
---

# Handoff: ai-sessions-render owns the ChatGPT conversation-merge (2026-07-23)

Session `fc8aea5a` (Agentify audit / session-bridge) hands the `ai-sessions-render` +
ChatGPT-conversation-merge work to its OWN session so two sessions don't edit the same repo.
Full handoff file: `C:\Users\Prekzursil\Downloads\workflow_design\HANDOFF-ai-sessions-render-2026-07-23.md`.

## Ownership split (to avoid competing sessions)
- **ai-sessions-render session OWNS:** github.com/Prekzursil/ai-sessions-render — corpus ingest, online
  ChatGPT live-harvest, tree render, and the "reunite/merge conversation with its branch" task.
  Output dir = `Downloads\workflow_design\new_wave`.
- **Agentify session (fc8aea5a) KEEPS:** retiring the dead agentify/promptbridge Electron stack (delete +
  CI de-reference across agent-skills-toolchain/ast-sshclean) + an OPTIONAL native Codex app-server bridge.
  It will NOT touch ai-sessions-render.

## Load-bearing verified facts (2026-07-23)
- "Plugin Improvement and Workflow Expansion" (conv 6a5d2b66) full body IS local — 106,137 chars in a
  Codex rollout (rollout-2026-07-20T00-09-46-019f7c36…jsonl). Parent is on disk.
- "Branch - Plugin Improvement…" is NOWHERE local (0 hits across full 1,813 MB incl. decoded .zst) → cloud only.
- ChatGPT Data Export does NOT carry the branch→parent link (conversation_origin null). Use the LIVE harvest:
  /api/auth/session → /backend-api/conversation/{id} tree `mapping` (branches first-class). Auth via ~/.crcp/cookie-bridge.
- ai-sessions-render already has a ChatGPT adapter + branch-tree handling + 100% cov + CodeQL, BUT walks
  current_node→root DROPPING abandoned branches — the merge task must preserve them (new work).
- zstandard 0.25.0 installed. state_5.sqlite threads(1831)+thread_spawn_edges(895) = richest local index.

## Open owner decision (unresolved)
Merge semantics: navigable-tree (recommended, faithful to `mapping`) vs linear-splice vs dedup-union vs diff.

## Agentify session status (for cross-ref)
Audit done (wf_950ea2e9-e82, 5 migration options). Tier-1 detritus DELETED (332.6 MB: .agentify-desktop,
.promptbridge-desktop, Desktop clone, 18 temp dirs). Plan v2 at Downloads\workflow_design\SESSION-BRIDGE-PLAN.md
passed scope-correction (the "merge branch" task was mis-imported from the screenshot, belongs to the OTHER session).
Also unrelated-but-urgent: C: at ~9.5 GB free, dropping — DISK-GRILL parked at G-1.

Related: [[ai-conversation-harvest-complete-chat-gpt-gemini-markdown-2026-06-15]] · [[chat-gpt-web-session-multi-browser-inject-2026-07-21]]