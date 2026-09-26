---
title: Route workflow subagents through ANTHROPIC_API_KEY (2026-07-24)
type: reference
permalink: main/reference/auth/route-workflow-subagents-through-anthropic-api-key-2026-07-24
tags:
- anthropic
- api-key
- billing
- subagents
- workflow
- claude-code
- auth
---

Owner wants workflow/agent subagents to bill to an ANTHROPIC_API_KEY (pay-per-token) instead of the Claude Max subscription. Investigated 2026-07-24.

## Observations

- [api_behavior] Subagent auth is SESSION-level, not per-agent. #no-per-subagent-key — Workflow agent() / the Agent tool run IN the orchestrating Claude Code process, so they use whatever provider the SESSION selected. There is NO per-subagent api-key override (agent() opts = label/phase/schema/model/effort/isolation/agentType — no auth field). So "agents on the API key" = the whole session runs on the key. Confidence: high (inferred — subagent auth not doc-documented, but they are in-process).

- [api_behavior] ANTHROPIC_API_KEY drives Claude Code "provider selection". #provider-select — code.claude.com/docs/en/settings confirms it: "Set a variable to '' ... which Claude Code treats as unset FOR PROVIDER SELECTION." So a non-empty ANTHROPIC_API_KEY selects the API provider (pay-per-token) over the subscription. The EXACT precedence when BOTH an OAuth login (.credentials.json) and the key exist is NOT explicitly documented — the empty-string note strongly implies the key wins, but verify before relying. Confidence: high the key selects the provider; medium on both-exist precedence.

- [decision] Setup to route future workflows through the key. #setup — Two documented mechanisms: (a) `apiKeyHelper` in ~/.claude/settings.json = a shell command that emits the key, sent as X-Api-Key + Authorization: Bearer, RELOAD-FRIENDLY (no restart), TTL via CLAUDE_CODE_API_KEY_HELPER_TTL_MS — best for a rotating/scoped key; (b) `env: {"ANTHROPIC_API_KEY": "..."}` in settings.json. Then launch a FRESH session; that session + all its subagents bill to the key. To GUARANTEE the key wins over the subscription, the cleanest is a session where only the key is present (or set the subscription creds aside). Cannot retroactively switch a running session's subagents.

- [reference] As of 2026-07-24 NO key is configured (env clean, settings.env clean, no apiKeyHelper); current auth = OAuth subscription (.credentials.json present). Owner must supply a key first. #current-state

## Relations
- relates_to [[GitHub auth- GITHUB_LEGACY_TOKEN is READ-ONLY for git (2026-07-24)]]
- relates_to [[529 overload mitigation]]


## SETUP DONE 2026-07-24 (surgical per-session launcher)

- [milestone] Key stored + validated + launcher built. #done — Owner-provided key stored at `~/.claude/.anthropic-api-key` (icacls owner-only, 108 bytes clean). VALIDATED live: GET api.anthropic.com/v1/models -> HTTP 200, 9 models. Launcher `claude-api` created: `~/.local/bin/claude-api.cmd` (on PATH) + a `claude-api()` function in `~/.bashrc` — both read the key from the file and `ANTHROPIC_API_KEY=<key> claude "$@"`. **settings.json UNCHANGED** (no global apiKeyHelper) so normal `claude` stays on the Max subscription; only `claude-api` sessions bill to the key. This matches the "next WORKFLOWS on the key, not all usage" intent.

- [gotcha] Whether the env var actually OVERRIDES the active OAuth subscription is NOT doc-confirmed. #verify — I validated the KEY works, not that a `claude-api` session bills to it vs the subscription winning. Definitive test (owner): open a fresh terminal, `claude-api`, run a small task, check console.anthropic.com usage for a charge. If the subscription still wins, force it via `forceLoginMethod`/logout, or set the global apiKeyHelper.

- [reference] Key EXPOSED in the 2026-07-24 chat transcript (owner pasted plaintext) -> recommend rotation after setup (§9b: compromised regardless of brevity). #rotate