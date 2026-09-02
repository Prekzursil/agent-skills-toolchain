# S12 — Next 10 experiments for durable ChatGPT WEB access

## Decision digest (≤500 words)

**Recommended endgame [Medium]:** an owner-attended bootstrap into a dedicated, encrypted Windows ChatGPT browser profile, retained on that same owner-controlled device/network. A least-privilege local **session broker** should accept authenticated CRCP jobs, drive the first-party UI, return typed results, and require the human to reauthenticate when the server revokes or steps up the session. Databricks stores only a broker credential, never browser cookies. This survives Codex token expiry by construction and avoids treating copied cookies as durable credentials.

OpenAI documents browser and first-party-app sessions, trusted devices, per-session revocation, and global logout, but does **not** document an API for exporting/refreshing a ChatGPT web session. Codex managed OAuth refresh is durable for Codex, not evidence of web-plane interchangeability. ChatGPT Desktop may maintain an independent first-party session, but no documented grant-export interface was found. [High]

Official MCP apps are the safest durable complement: they let ChatGPT call CRCP, not CRCP list/fetch/send the owner’s ChatGPT history. Data Export is a recovery/read archive, not live access (up to seven days; download link 24 hours). [High]

Direct `backend-api` remains an unsupported compatibility adapter. Do not implement PoW/sentinel bypasses as the endgame: consumer terms prohibit programmatic extraction and bypassing protective measures. Prefer browser-mediated actions, conservative rates, explicit owner intent, and terminal success evidence. [High]

### Candidate matrix

| Candidate | Observed/expected lifetime | Browser? | Survives Codex expiry? | Risk | Next experiment |
|---|---|---:|---:|---|---:|
| Dedicated Windows browser + local broker | Server-controlled; renewable while valid | Bootstrap + UI | Yes | Medium | 1–4 |
| Copied Playwright `storageState` in Databricks | Until server expiry/revocation; incomplete state possible | Bootstrap | Yes | Critical impersonation/device/IP drift | 5 |
| ChatGPT Desktop session/grant | Undocumented | Yes/app | Likely | High; no supported export | 7 |
| Codex managed OAuth refresh | Auto-refreshed by Codex | Attended/device code | No: wrong plane | Medium | 6 |
| Custom MCP app | OAuth lifetime; `offline_access` enables refresh | Setup | Yes | Low; reverse direction | 8 |
| Official Data Export | Snapshot; link 24h, generation ≤7d | Usually | Yes | Low; not live/write | 9 |

**Implement next:** broker protocol, dedicated-profile adapter, health state machine (`AUTH_OK`, `STEP_UP`, `REVOKED`, `CHALLENGED`, `DONE`), idempotency keys, audit metadata without secrets, and a human rebootstrap queue. Live Windows/profile experiments cannot be run on this Linux node; no Windows state is inferred.

## EVIDENCE

### EVPI-ranked falsifiable experiments

EVPI ranks uncertainty reduction × architecture consequence, not convenience. Each experiment uses only the owner’s account and records cookie **names/attributes and hashes**, never values.

1. **Dedicated-profile survival baseline — EVPI Very High [Medium].** On the Windows owner box, create a new OS account or tightly ACLed browser profile, sign in interactively, and record an account fingerprint (stable internal account/workspace identifiers, plan, and a known conversation—not email alone). At T0/T+1d/T+7d/T+30d, restart browser and machine, then list/fetch one canary via UI. **Pass:** identity and canary survive without reading `~/.codex/auth.json`. **Falsifier:** Codex logout/expiry or browser restart ends the web session. **Changes CRCP:** commit the Windows broker architecture if passed; otherwise require attended bootstrap per run.

2. **Codex-death independence — EVPI Very High [High].** After experiment 1, isolate/rename the Codex credential file and let a captured Codex access token expire; do not log the browser out. **Pass:** broker still reads the canary and creates a zero-cost test chat through UI. **Falsifier:** web access depends on Codex credentials. Restore the local file after the test. This is the mission’s decisive boundary.

3. **Renewal and absolute-lifetime map — EVPI High [Medium].** Daily, capture redacted cookie inventory (`domain`, `path`, `Secure`, `HttpOnly`, `SameSite`, expiry), account-session status, and hashes before/after one normal UI action. Include a seven-day idle arm. **Pass:** a stable renewal pattern predicts a safe rebootstrap threshold. **Falsifier:** silent unpredictable invalidation or mandatory step-up. **Changes CRCP:** schedule health probes and warn the owner before observed renewal/absolute boundaries; never promise “long-lived.” OWASP notes idle, absolute, and renewal timeouts are server-side concepts.

4. **Local broker/UI terminal semantics — EVPI High [Medium].** Implement a throwaway loopback-only broker prototype with one allowlisted operation: create an explicitly labeled canary chat through the UI. Require visible DOM completion, conversation identifier/URL, subsequent list/fetch verification, and idempotency key; HTTP 200 alone is failure. **Pass:** 20/20 terminally verified writes without challenge. **Falsifier:** duplicated messages, challenge loops, or no durable read-back. **Changes CRCP:** UI adapter becomes primary; existing backend/SSE path remains quarantined compatibility code.

5. **Session portability kill test — EVPI High [Low].** In a disposable, encrypted test context, export owner-authorized browser state and try exactly one read-only canary from a second Windows profile, then (only if approved) Linux/Databricks. Revoke immediately afterward. **Pass:** same account plus canary with no step-up; **falsifier:** login redirect, device verification, Cloudflare/challenge, missing IndexedDB/session storage, or suspicious-activity alert. Expected result is failure/unsafe. **Changes CRCP:** even on pass, do not centralize cookies unless security review accepts bearer-session blast radius. Playwright warns saved state can impersonate the account; Chrome 136+ blocks remote debugging of the default profile and recommends a separate data directory.

6. **Codex refresh is not web refresh — EVPI Medium-High [High].** Use the official app-server `account/read` with forced refresh, logging only token metadata/fingerprints. Compare account identity and permitted audiences/issuers structurally; never replay a token into an undocumented plane. **Pass:** Codex continues after access-token expiry while the browser experiment remains independent. **Falsifier:** refresh fails or rotates/revokes browser state. **Changes CRCP:** retain Codex OAuth only as a bounded consumer adapter, never source-of-truth web credential.

7. **Desktop session/grant boundary — EVPI Medium [Low/UNVERIFIED].** On Windows, sign into the official ChatGPT Desktop app, confirm it appears as a distinct first-party active session, then log the browser out individually and test whether Desktop still accesses the same canary. Inspect only documented app interfaces and session metadata—no credential extraction. **Pass:** independent same-account session survives browser logout. **Falsifier:** shared revocation or no independent session. **Changes CRCP:** Desktop can be an owner recovery/approval surface only; absent a supported automation interface, it is not a broker credential.

8. **Official MCP inversion fit — EVPI Medium [High].** Publish a minimal CRCP MCP endpoint with one harmless read tool and OAuth including `offline_access`; connect it from the correct ChatGPT account/workspace. **Pass:** after access-token expiry, ChatGPT refreshes and calls CRCP without reconnection. **Falsifier:** plan/admin restrictions or forced reauth. **Changes CRCP:** use MCP for durable ChatGPT→CRCP commands and attended approvals, while retaining the browser broker for CRCP→ChatGPT plane operations.

9. **Export recovery RTO/RPO — EVPI Medium [High].** Owner requests an official export, records arrival latency, verifies account ownership gating, checksum, conversation coverage, and canary presence; delete the downloaded archive after the approved retention test. **Pass:** canary is recoverable within seven days. **Falsifier:** workspace plan excludes export or archive omits required objects. **Changes CRCP:** add an optional owner-run backup/import parser; never treat export as authentication or write transport.

10. **Revocation and secret-containment drill — EVPI Medium [High].** With the dedicated session, revoke its row in ChatGPT Active sessions and measure broker fail-closed latency; separately test global logout. Confirm logs contain no cookie/JWT/body secrets. Store only a rotated broker credential in `codex-harness-prekzursil`, with job-principal READ and owner MANAGE. **Pass:** broker halts before another operation, reports `REVOKED`, and rebootstrap is human-only. **Falsifier:** continued writes, ambiguous identity, or secret leakage. Databricks redaction covers literal secret values only; ACLs and output discipline remain mandatory.

### Architecture and failure model

`CRCP on Databricks → mTLS/short-lived broker capability → owner Windows broker → dedicated browser profile → ChatGPT web UI`. The broker binds requests to operation allowlists, account/workspace fingerprint, idempotency key, deadline, and owner policy. It serializes mutations, applies low rates, and returns evidence (`conversation_id`, timestamps, DOM completion, read-back hash), not session material. Inbound connectivity should use an owner-approved private channel; do not expose a remote-debugging port.

Fail closed on account/workspace mismatch, login redirect, MFA/OTP/push, CAPTCHA/Cloudflare, suspicious-activity banner, changed UI contract, missing terminal marker, or ambiguous write. The owner resolves step-up in the visible browser. Global logout, individual revocation, password/security changes, server expiry, device/IP reputation, browser updates, and profile corruption are expected lifecycle events—not bugs to bypass.

The broker is still browser automation and may conflict with applicable consumer terms. Legal/policy review is a release gate. OpenAI’s individual Terms prohibit automatic/programmatic extraction and bypassing protective measures; therefore CRCP must not synthesize or defeat sentinel/PoW, evade limits, or perform bulk history extraction. A supported enterprise/API path should supersede the broker if OpenAI offers one.

### Source anchors

- OpenAI, [Managing active sessions in ChatGPT](https://help.openai.com/en/articles/20001257-managing-active-sessions-in-chatgpt/): browser and first-party app sessions, trusted devices, individual/global revocation, Codex CLI exclusion. [High]
- OpenAI Codex, [app-server authentication modes](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#auth-endpoints): managed ChatGPT OAuth owns and automatically refreshes Codex tokens; device-code flow and forced refresh are documented. [High]
- OpenAI, [Moving to the new ChatGPT desktop app](https://help.openai.com/en/articles/20001276-moving-to-the-new-chatgpt-desktop-app): official Windows/macOS app and same-account sign-in; no grant-export interface is documented. [High for existence; UNVERIFIED for CRCP usability]
- OpenAI, [Why login verification occurs](https://help.openai.com/en/articles/9889414-why-am-i-being-asked-to-verify-my-login): new devices/locations can trigger OTP or mobile approval. [High]
- OpenAI, [Suspicious Activity Alert](https://help.openai.com/en/articles/10471992): unexpected locations, concurrent sessions, automation tools, VPN/proxy, and usage spikes are risk signals. [High]
- OpenAI, [Developer mode and MCP apps](https://help.openai.com/en/articles/12584461-developer-mode-and-full-mcp-connectors-in-chatgpt-beta): custom MCP, plan/admin constraints, and `offline_access` refresh implications. [High]
- OpenAI, [ChatGPT data export](https://help.openai.com/en/articles/7260999-how-do-i-export-my-chatgpt-history-and-data): ownership verification, up-to-seven-day delivery, 24-hour link, and plan exclusions. [High]
- OpenAI, [Account Sharing Policy](https://help.openai.com/en/articles/10471989-openai-account-sharing-policy/): one individual may use multiple devices; account sharing is not allowed. The broker must act only for the owner. [High]
- OpenAI, [Terms of Use](https://openai.com/en-GB/policies/terms-of-use/): prohibits automatic/programmatic extraction and bypassing protective measures. [High]
- Playwright, [Authentication](https://playwright.dev/docs/auth): state may include cookies/local storage/IndexedDB and can impersonate an account; do not commit it. [High]
- Chrome for Developers, [Remote debugging security change](https://developer.chrome.com/blog/remote-debugging-port): Chrome 136+ requires a non-default user-data directory for remote-debugging switches and recommends isolation. [High]
- OWASP, [Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html): server-side idle/absolute/renewal expiry, secure cookie handling, and session-event logging. [High]
- Databricks, [Secret management](https://docs.databricks.com/aws/en/security/secrets): scope ACLs and the limitation that redaction protects literal values, not transformed secrets. [High]

UNIT-COMPLETE: S12-experiment-plan
