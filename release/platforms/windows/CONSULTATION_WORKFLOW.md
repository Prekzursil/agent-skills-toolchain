---
title: CONSULTATION_WORKFLOW
type: note
permalink: dqverify-repo-20261013/release/platforms/windows/consultation-workflow
---

<!-- promptbridge-managed -->
# PromptBridge Desktop Codex Workflow

## Active profiles
- Canonical managed profile: C:\Users\Prekzursil\.codex
- Legacy migration input only: C:\Users\Prekzursil\.codex-vscode

## Supported paths
- Start PromptBridge Desktop and keep it signed in to ChatGPT.
- Codex CLI is supported from the active Windows CODEX_HOME and from explicitly supplied custom CODEX_HOME values.
- The OpenAI Codex VS Code extension is a configured target through the shared canonical profile and still requires a fresh-chat smoke proof.
- Generic VS Code mcpServers integrations are optional / best-effort and are not the primary proof path.

## Lane B flow
1. codex_consult should start or reuse PromptBridge Desktop / Agentify and wait for a ready authenticated session.
2. Reuse or create a stable dedicated tab for the current workspace or task.
3. After the plan is written, choose the execution path: subagent-driven execution (recommended) or inline execution.
4. Execute the plan and normalize the result into:
   - problem
   - assumptions
   - options
   - recommended_option
   - risks
   - verification_plan
   - confidence

## Verification contract
- CLI proof requires in-session visibility of codex_consult plus one of promptbridge_status / agentify_status.
- VS Code proof requires canonical-profile extension preflight plus a fresh Codex chat that can surface codex_consult and one of the PromptBridge status tools.
- If PromptBridge tools are not visible in-session, continue in Lane A and emit fallback_to_lane_a = true.

## Required reset after profile-affecting changes
After any of these changes:
- bootstrap install/update
- canonical profile regeneration
- canonical SQLite reset
- codex_consult path/env change

You must:
1. reload the VS Code window / OpenAI Codex extension host
2. start a fresh Codex chat thread
3. run a sidecar status smoke prompt before claiming Lane B is live in-session