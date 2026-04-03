<!-- promptbridge-managed -->
# PromptBridge Codex Consultation Contract

## Profile ownership
- Canonical managed profile: C:\Users\Prekzursil\.codex
- Legacy migration input only: C:\Users\Prekzursil\.codex-vscode
- Treat C:\Users\Prekzursil\.codex as the only editable source of truth. C:\Users\Prekzursil\.codex-vscode is read only for migration or comparison and is not an active second home.

## Lane A (default)
- Use native Codex workflow for implementation.
- For complex work, draft the plan first, then choose an execution path: subagent-driven execution (recommended) or inline execution.
- Suggested flow: Draft -> Review (gpt-5.4) -> Reconcile -> Choose execution path -> Execute -> Verify.

## Lane B (policy-driven sidecar)
- codex_consult is the single managed MCP lane.
- codex_* execution tools and promptbridge_* / agentify_* talk tools are exposed from that same managed server.
- Use codex_consult automatically for:
  - ambiguous requirement
  - security-sensitive change
  - repeated test failure loop
  - architecture tradeoff decision

## Lane B operating model
- Prefer codex_* tools for orchestration and promptbridge_* / agentify_* tools for talk-only discussion/curation.
- codex_consult should launch or reuse the Agentify desktop lane first, then fall back to native Lane A only if the desktop path is unavailable.
- Keep agentify_* aliases for compatibility during 0.1.x.
- Ensure a ready desktop session before submitting consultation context:
  - promptbridge_ensure_ready / agentify_ensure_ready
  - promptbridge_status / agentify_status
  - codex_consult / codex_brainstorm / codex_review / codex_discuss / codex_coordinate / codex_curate

## Required consultation output schema
Every consultation result must include:
- problem
- assumptions
- options
- recommended_option
- risks
- verification_plan
- confidence

## Redaction policy
- Never send secrets, tokens, passwords, API keys, customer identifiers, or private credentials to sidecar tools.
- Sanitize context before sidecar submission.

## Fallback behavior
- If Lane B is unavailable or unauthenticated, continue in Lane A.
- Mark fallback explicitly in output/logs (fallback_to_lane_a = true).

## Support contract
- Supported: Codex CLI from the active Windows CODEX_HOME and from any explicitly provided custom CODEX_HOME.
- Guided / proof-required: OpenAI Codex VS Code extension through the shared canonical profile.
- Optional / best-effort only: generic VS Code mcpServers chat integrations.
