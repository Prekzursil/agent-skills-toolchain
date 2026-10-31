---
title: W02-session-vs-access
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/web-endgame/w02-session-vs-access
---

# W02 — Web session cookie vs OAuth access/refresh tokens

## Digest (2026-07-20; 493 words)

### Ranked findings

1. **[High] A ChatGPT web session is not Codex OAuth.** OpenAI says ChatGPT web keeps its authenticated session in the browser, while Codex receives credentials through a browser OAuth return and caches them in `auth.json` or an OS credential store. Codex source models access, refresh, and ID-token material and refreshes at the OAuth token endpoint. Killing or rotating Codex OAuth therefore need not kill a separate browser session; “log out all” can revoke active browser/app sessions, but OpenAI explicitly says Codex CLI sessions are not shown in ChatGPT Active sessions.

2. **[Medium] CRCP can probably consume an already-acquired web session without a full browser, but this is unsupported and brittle.** HTTP cookies are bearer-equivalent session identifiers. Historical ChatGPT reverse-engineering clients exchanged a secure session cookie for a short-lived bearer and needed Cloudflare clearance plus matching IP/User-Agent. Current cookie names, endpoints, device binding, CSRF, WAF/TLS fingerprinting, rotation, and lifetime are undocumented and **UNVERIFIED**. Thus a cookie jar may drive ordinary HTTP after browser acquisition, but cannot be treated as an autonomous refresh credential; periodic real-browser reauthentication/challenge handling may remain necessary.

3. **[High] The OAuth refresh token is the durable part of Codex OAuth, not web identity.** RFC 6749 defines refresh tokens as credentials for obtaining access tokens. Current Codex source refreshes on 401, can receive rotated refresh tokens, and distinguishes expired, reused, revoked, and account-mismatch failures. Persisting only the access token guarantees expiry; concurrent refresh writers can exhaust a rotated single-use token. This path survives one access-token expiry, not revocation, logout/account switch, refresh expiry, or Codex-specific policy changes.

4. **[High] Best supported non-browser option: a Codex access token, if CRCP’s workspace is Business/Enterprise and scope is sufficient.** It is ChatGPT-workspace-bound, works for trusted Codex CLI/app-server automation, may be finite or non-expiring, and survives `auth.json` access-token death. It is explicitly not a browser session and does not grant general ChatGPT web/backend access.

5. **[High] Authentication alone is insufficient for paid writes.** CRCP must still implement the observed sentinel/PoW flow and require terminal SSE `DONE`; HTTP 200 is not success.

### Durable-access candidates

| Rank / candidate | Path / lifetime | Browser? | Survives Codex access expiry? | Risk | Next experiment |
|---|---|---:|---:|---|---|
| 1. Official Codex access token | ChatGPT admin console → Databricks secret; chosen expiry (1 day minimum; 7/30/60/90 days suggested; optional no-expiry) | Creation only | Yes | Codex-scoped, entitlement-dependent; bearer theft | Check workspace eligibility; smoke-test list/read/write through supported Codex client |
| 2. Owner browser session broker | Owner-controlled persistent browser profile; undocumented lifetime | Yes, at acquisition/renewal | Yes | Full-account bearer; logout/WAF/device binding; ToS/fragility | Metadata-only Windows HAR/cookie-attribute study, then isolated read-only replay |
| 3. Codex OAuth refresh chain | Keyring or single-writer encrypted `auth.json`; until refresh expiry/revocation | Initial/device reauth | Yes, normally | Rotation races; still Codex-specific | Single-writer refresh lease; persist atomically; test 401 recovery without printing tokens |
| 4. Desktop app grant/profile | OS credential store/app state; undocumented | Interactive initial login | Likely | Format and reuse unsupported; platform-bound | Observe supported app-server handoff; do not scrape private app storage |
| 5. Data export | Official requested archive; point-in-time | Yes | Yes | Not live read/write access | Use only for recovery/audit baseline |

**Decision:** Do not elevate a copied web cookie into the primary Databricks secret. Prefer an official ChatGPT-workspace credential where scope fits; otherwise keep a browser session on an owner-controlled Windows broker and expose a narrow audited capability to CRCP, not the raw cookie. Databricks secret redaction is not an access boundary: users with `READ` can retrieve the value.

## EVIDENCE

### Primary sources

- **OpenAI Codex authentication**: distinguishes ChatGPT web (session stays in browser) from Codex browser OAuth; documents cached credentials, automatic token refresh, headless device login, and copying `auth.json` to trusted headless hosts. It also warns that the cache is password-equivalent. [OpenAI Authentication](https://learn.chatgpt.com/docs/auth)
- **OpenAI Codex access tokens**: Business/Enterprise only; tied to the creating ChatGPT user/workspace; intended for non-interactive Codex CLI/app-server runs. Tokens support administrator-limited expiry, with 1-day minimum, common finite choices, and optional no-expiry; they do not authenticate general browser or Workspace Agent calls. [OpenAI Access tokens](https://learn.chatgpt.com/docs/enterprise/access-tokens)
- **OpenAI Active sessions**: a session may be a browser or first-party-app session; logout can revoke individual/all sessions (propagation up to 30 minutes). The page says Codex CLI sessions are not represented in this UI. [Managing active sessions](https://help.openai.com/en/articles/20001257-managing-active-sessions-in-chatgpt/)
- **OpenAI Codex source**: `AuthDotJson` stores structured ChatGPT token data; the client uses the access token as bearer, posts a refresh-token grant to the OAuth token endpoint, persists replacement tokens, and retries after 401. Explicit terminal failures include refresh expired/reused/revoked and account mismatch. [openai/codex `auth.rs`](https://github.com/openai/codex/blob/main/codex-rs/core/src/auth.rs)
- **OAuth semantics**: an access token authorizes resource requests; a refresh token is a credential used to obtain new access tokens and is intended for the authorization server, not resource servers. [RFC 6749 §§1.4–1.5](https://www.rfc-editor.org/rfc/rfc6749.html#section-1.4)
- **Session-cookie security**: OWASP describes a session ID as temporarily equivalent to the strongest authentication used and notes that capture permits impersonation. This supports treating any web cookie jar as a top-tier account secret. [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- **Databricks secret limitation**: secret values may be redacted from display, but principals with permission can read them; redaction cannot prevent retrieval. [Databricks Secret API](https://docs.databricks.com/api/gcp/workspace/secrets)
- **Contract risk**: OpenAI’s current terms restrict reverse engineering, programmatic extraction, and bypassing rate limits/protective measures. A raw web-session client therefore has contractual as well as operational risk; obtain an approved supported path for production. [OpenAI Terms of Use](https://openai.com/policies/terms-of-use/)

### Reverse-engineering evidence and limits

- A historical `chatgpt` package API required a ChatGPT session cookie plus Cloudflare clearance, with the clearance tied to IP/User-Agent, then refreshed an approximately hour-lived access token while the session remained valid. This demonstrates feasibility of a browserless consumer **after** browser-derived acquisition, but describes the 2022-era `chat.openai.com` stack and cannot establish the 2026 cookie name or flow. **[Medium for historical behavior; UNVERIFIED current]** [Archived package type definitions](https://app.unpkg.com/chatgpt@3.3.9/files/build/index.d.ts)
- Public reports show 403 failures even when both historical session and clearance cookies were supplied, corroborating brittleness and additional fingerprint/state checks. Reports are anecdotal. **[Low]** [acheong08/ChatGPT issue #300](https://github.com/acheong08/ChatGPT/issues/300)

### Safe owner-side validation protocol (requires the real Windows owner session; not executed here)

1. In the owner’s logged-in browser, capture only cookie **names, domains, flags, creation/expiry timestamps, and rotation events** plus a redacted HAR for one read. Never export values into logs.
2. After explicit owner approval and terms review, place the minimal cookie jar in an isolated local broker process on that same Windows device/network. Replay one harmless identity/read request with redirects disabled and strict destination allowlisting. Compare status, `Set-Cookie` rotation, WAF challenge, and account/workspace identifiers; do not print bodies containing private data.
3. Repeat from a plain HTTP client with the same declared User-Agent, then after access-token expiry. Outcomes classify the design: (a) cookie-only works; (b) cookie exchanges for bearer; (c) clearance/device/TLS binding requires browser; or (d) unsupported endpoint rejects automation.
4. Test revocation with ChatGPT’s individual-session/logout-all control and verify the broker fails closed within the documented propagation window. Delete the test secret and rotate the session afterward.
5. If browser dependence remains, keep that broker on Windows. Databricks should receive a narrow mutually authenticated RPC capability (list/read/send with quotas and audit), never the browser profile or raw session material.

No live Windows browser/profile was available on this Linux job node, so current cookie names, expiry, and replayability remain **UNVERIFIED**; none were fabricated.

UNIT-COMPLETE: W02-session-vs-access