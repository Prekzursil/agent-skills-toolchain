---
title: research Cursor SDK hybrid bridge 2026-08-28
type: report
permalink: main/research/research-cursor-sdk-hybrid-bridge-2026-08-28
tags:
- research-report
- high-confidence
- cursor-sdk
- auth2api
- grok-build
- security
---

# Cursor SDK hybrid bridge — research report

*Generated: 28.08.2026 | Confidence: High on architecture/policy boundaries; Medium on live SDK workflow concurrency and RAM*

## Executive summary

- [decision] Keep `auth2api` as the sole client-facing gateway on `127.0.0.1:8317`.
- [decision] Use an embedded official Cursor SDK backend as the primary agentic path, with a gateway-owned suspended-tool state machine so [[Grok Build]] and [[Claude Code]] remain outer tool owners.
- [decision] Retain legacy ChatService only as a run-pinned compatibility fallback after strict declared-tool allowlist/schema hardening. Never fallback on policy, auth, quota, schema, safety, or tool-denial errors.
- [decision] Keep raw `AgentService/Run` for diagnostics only; it is private, version-gated, stateful, and duplicates SDK-maintained transport logic.
- [fact] Current team/account catalogs legitimately expose Cursor Grok 4.6 low/medium/high/xhigh and Grok 4.5 low/medium/high. Claude Fable/Opus/Sonnet 5 stop at high; forced ChatService max/xhigh terminates with `ERROR_MODEL_BLOCKED`.
- [fact] V-008 found no identity-binding bypass: direct existing user `crsr_` authentication to ChatService terminates `ERROR_NOT_LOGGED_IN` before PEP evaluation; ChatService has no caller-controlled team-policy field; BYOK ordering remains unverified; PORTAL issuance was not called.

## Architecture

```text
Grok/Claude -> auth2api :8317 -> central policy/routing PEP
  -> embedded Cursor SDK (primary agentic)
  -> restricted ChatService (compatibility fallback)
  -> explicit isolated search provider
```

SDK custom tools return unresolved Promises. The gateway emits native outer-client `tool_use`/`function_call`, validates the later result request, and resolves the original SDK callback. Pending state binds principal, session, credential fingerprint, SDK agent/run, call id, tool, normalized-argument hash, model params, policy hash, and backend. Duplicate, partial, mixed-session, expired, or policy-mismatched completion fails closed.

## Capability conclusions

- [fact] SDK model params provide exact account/team-specific effort, context, fast, and Router controls. Proxy `Cursor.models.list()` unchanged and validate every `{id,value}` pair; never infer effort from display names.
- [fact] SDK emits thinking deltas and per-turn input/output/cache/reasoning usage. Raw thinking is untrusted sensitive data and must not enter ordinary logs.
- [fact] Grok/Claude workflows remain outer-native. Each workflow child maps to an isolated gateway session; same-session turns serialize; Cursor inner `task` remains denied.
- [fact] Native xAI search uses a separate SuperGrok allowance and is currently quota-blocked, not auth-broken. Prefer outer TUI/MCP search fallback with explicit provider identity and citations. Cursor SDK `webSearch` is Cursor-owned and does not suspend to the outer client.
- [fact] Grok 500k metadata controls local compaction. Cursor remains the final server-side context limit; catalog variants are authoritative.

## Product bug conclusion

The Claude throttle is consistent with catalog/policy migration drift: a custom explicit `{low,medium,high}` restriction remained frozen when later xhigh/max parameter values were introduced. `newModelDefault=ENABLED` concerns new models, not new values on an existing model. SDK/CLI discovery and runtime enforcement have documented consistency defects. This supports a product migration/discovery bug hypothesis, not a MEMBER-to-admin bypass.

## Security findings

- [high] Legacy text shim can synthesize executable tool calls from model prose without enforcing the current request's declared-tool allowlist and JSON schema. Fix before write-capable fallback.
- [high] Suspended SDK calls require one-time capability binding, atomic state transitions, TTL, cancellation, replay protection, and immutable resume policy.
- [medium] Current local client key is shared/static; body limit is 200 MB; rate limiting is loopback-IP based; token files rely on POSIX modes that do not create Windows ACLs; deterministic prompt-derived conversation IDs can collide; debug capture may retain prompts.
- [fact] AgentShield bounded scan found 0 critical and no secrets; most high/medium findings were intentional full-power permissions or platform false positives.
- [fact] HexStrike-driven Semgrep ran 302 rules over 48 tracked files and reported 11 findings; trusted-path warnings were mostly false positives, while the text-to-tool trust boundary is substantive.
- [fact] `npm ci` plus production audit still reports 2 high and 4 moderate advisories; no dependency upgrades were applied.
- [fact] HexStrike was not reconfigured or stopped per owner direction.

## Acceptance gates

1. Catalog/parameter validation against the active credential/team.
2. PEP parity with no policy-error fallback.
3. MCP-only SDK tools and exact declared-tool schema validation.
4. Principal/session/run/call ownership and one-time completion.
5. TTL/cancel/replay/restart recovery.
6. Backend pinning for the full run.
7. Thinking/log redaction and honest usage (`unknown` for ChatService).
8. Search provider isolation and citations.
9. Workflow concurrency, effort-per-child, visible `/workflows`, and process cleanup.
10. One client-facing listener and measured RAM before increasing concurrency.

## Artifacts

- `Cowork/tools/auth2api/docs/cursor-sdk-hybrid-architecture_2026-08-28.md`
- `Cowork/tools/auth2api/docs/security-best-practices_cursor-bridge_2026-08-28.md`
- `Cowork/output/cursor-team-policy-threat-model.md`
- `Cowork/output/cursor-v008-identity-binding_2026-08-28.md`

## Sources

1. https://cursor.com/docs/sdk/typescript
2. https://cursor.com/docs/sdk/changelog
3. https://cursor.com/docs/cloud-agent/api/endpoints
4. https://cursor.com/docs/enterprise/model-and-integration-management
5. https://cursor.com/docs/account/organizations/organization-admin-api
6. https://github.com/Sunnyender-org/cursor-sdk2api/blob/1e18349f556efde716634f6368fe8bd9532e06eb/docs/ARCHITECTURE.md
7. https://github.com/Sunnyender-org/cursor-sdk2api/blob/1e18349f556efde716634f6368fe8bd9532e06eb/docs/PROTOCOL_COMPATIBILITY.md
8. https://cheatsheetseries.owasp.org/cheatsheets/gRPC_Security_Cheat_Sheet.html
9. https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html

## Methodology

Official documentation, commit-pinned bridge source/tests, local static RE of Cursor Desktop/Agent descriptors, account-holder catalog reads and minimal identity-path probes, existing enforcement receipts, AgentShield, npm audit, local OWASP/security corpora, and HexStrike-driven Semgrep. No policy was modified, no key was minted or rotated, and no external HexStrike scan was performed.