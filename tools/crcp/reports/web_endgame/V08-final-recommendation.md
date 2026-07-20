# V08 — Final recommendation: durable ChatGPT web-account access for CRCP

## Decision

**Recommend one rail: an owner-operated, dedicated Windows VM (or dedicated Windows local account) running a dedicated Chrome user-data directory signed into `chatgpt.com`, with a same-host UI broker and human reauthentication.** **[Medium]** The durable identity is the browser/device session plus owner-held passkey/security key—not an exported cookie, JWT, Codex token, or Desktop credential. CRCP should send narrowly typed jobs to an outbound-polling broker; the broker drives the supported web UI and returns sanitized task results. Do not make Chrome DevTools Protocol (CDP) a network service.

This survives expiration of the current Codex access token because OpenAI documents ChatGPT web as retaining its own browser session. Its lifetime is nevertheless **opaque and revocable**, not a promised long-lived token. Plan for attended re-login after logout-all, password/security changes, risk challenges, cookie clearing, browser/profile loss, or provider policy changes. **[High]**

## Ranked findings

1. **Dedicated browser-profile rail is the only candidate that directly remains bound to the human's web account while decoupling from Codex OAuth. [Medium]** It is operationally durable, not contractually permanent.
2. **There is no documented general-purpose refresh token, service credential, or API for automating a consumer ChatGPT web account. [High]** Enterprise Codex access tokens authorize trusted Codex workflows, not the ChatGPT web account plane.
3. **Cookie/JWT copying and private `backend-api` calls are rejected as the endgame. [High]** They create bearer-secret sprawl, couple CRCP to undocumented sentinel/PoW/SSE behavior, and risk violating the prohibition on bypassing protective measures.
4. **ChatGPT Desktop/Chrome grants are useful first-party controls, not documented credentials for an external controller. [High]** Do not scrape their stores.
5. **Official export is recovery evidence, not live access. [High]** It is delayed, point-in-time, and its email download link expires.

## Candidate matrix

| Rank | Path | Expected lifetime | Requires browser | Survives Codex expiry | Principal risk | Next experiment |
|---:|---|---|:---:|:---:|---|---|
| 1 | Dedicated Windows Chrome profile + local UI broker | Until session revocation/reauth; TTL unpublished | Yes | Yes | CDP/session compromise; UI drift; terms | Owner-attended canary below |
| 2 | ChatGPT Desktop / official Chrome extension | First-party session; unpublished | Yes | Yes | No documented CRCP control interface; broad browser permissions | Validate only as supervised fallback |
| 3 | Enterprise Codex access token | Admin/issuer-controlled | No | Yes | Wrong plane: Codex, not ChatGPT web | Ask workspace admin about scope; do not assume web access |
| 4 | Official account export | Point-in-time; link 24 hours | For request | Yes | Up to 7 days; read-only; plan limitations | Quarterly recovery drill |
| 5 | `~/.codex/auth.json` refresh state | Auto-refresh while valid/revocable | Setup only | No endgame | Plaintext option, dual-write/token coupling | Retain only as temporary consumer |
| 6 | Copied cookies or direct private `backend-api` | Opaque/revocable | No after theft/export | Temporarily | Critical bearer leakage; unsupported defenses; policy risk | **Do not pursue** |

# EVIDENCE

## Recommended architecture and controls

**Identity boundary. [High]** The owner performs an interactive login in the dedicated profile, selecting the intended workspace and verifying the account/workspace visually. Use a passkey or FIDO security key; keep two recovery methods and recovery codes offline. Never transmit cookies, local-storage values, full JWTs, browser databases, or private keys to Databricks. Never clone the browser profile.

**Host isolation. [High]** Use a patched dedicated Windows VM or dedicated non-admin local account, full-disk encryption, Secure Boot, screen lock, EDR, and ACLs limited to that user for the custom Chrome user-data directory. Keep personal browsing, email, password-manager extensions, developer extensions, downloads, and unrelated accounts out of this profile. Disable clipboard, drive, printer, and credential redirection where practical. Snapshot only while signed out; a signed-in snapshot is a credential copy.

**CDP boundary. [High]** Prefer a launcher-owned local pipe. If CDP-over-TCP is unavoidable, bind only to loopback, add a host firewall deny rule for every non-loopback interface, use a random ephemeral port, start/stop it per job, and ensure the broker never returns the DevTools WebSocket URL. Chrome explicitly identifies remote debugging as a cookie-theft path; since Chrome 136, debugging switches require a non-default user-data directory, and Chrome recommends custom profiles for isolation. A custom directory is necessary here but is not, by itself, a security boundary.

**Control-plane boundary. [High]** Run the broker under the same low-privilege Windows identity as Chrome. It should poll outbound over TLS for signed, expiring, single-use jobs; expose no inbound listener, RDP, raw browser primitives, arbitrary JavaScript, arbitrary URL navigation, or shell. Allowlist `https://chatgpt.com/` and the minimum OpenAI authentication hosts. Define typed operations (for example, open conversation, submit owner-approved prompt, wait for rendered completion, return bounded text). Apply per-job idempotency keys, rate limits, concurrency 1, timeouts, content-size limits, and an owner-visible kill switch.

**Databricks boundary. [High]** The existing `codex-harness-prekzursil` scope should hold only a rotatable broker client credential or job-signing key—not OpenAI session material. Grant READ to only the CRCP job service principal and MANAGE to a separate administrator; audit ACLs. Databricks warns that redaction covers literal secrets only, not transformations, so never log derived tokens, headers, CDP URLs, DOM dumps, screenshots, or full response bodies. Policy job clusters should have egress limited to the broker rendezvous service and required telemetry destinations.

**Transaction correctness. [High]** For a paid write, success means the browser visibly renders the completed assistant turn and the conversation persists after reload. If a temporary compatibility adapter still observes SSE, require terminal `DONE`; HTTP 200 alone is not success. Never solve, suppress, replay, or route around sentinel/PoW challenges. Surface the challenge for owner action or fail closed.

**Terms gate. [High]** OpenAI's Terms of Use prohibit automatically/programmatically extracting data or Output and bypassing protective measures. Therefore, before unattended production use, obtain written confirmation from OpenAI or controlling enterprise contract counsel that the intended owner automation is permitted. Until then, restrict the rail to an owner-supervised canary with no bulk extraction. If approval is denied, there is no verified compliant programmable web-plane substitute in the public documentation; use an official API/product surface even though it is not the same plane.

## Failure model and mitigations

| Failure | Detection | Response |
|---|---|---|
| Session expired/revoked | Login page, challenge, account mismatch | Stop; owner reauthenticates locally with passkey/security key |
| Wrong account/workspace | Profile/workspace label differs from pinned expectation | Fail closed; never auto-switch into an unknown workspace |
| UI or policy changed | Selector/rendered-state canary fails | Quarantine write path; update after owner review |
| Partial/charged write | No rendered terminal answer or no persistence after reload | Mark indeterminate; do not blind-retry; reconcile by conversation/idempotency marker |
| Suspicious-activity alert | Banner, forced challenge, repeated 401/403 | Stop automation; review Active sessions; use one trusted device/network; contact Support if persistent |
| Broker compromise | Attestation/health failure, unexpected job or egress | Kill broker, revoke its credential, log out that ChatGPT session/all sessions as warranted, rebuild VM |
| Host/profile loss | Browser profile unavailable | Rebuild clean host and owner-login; do not restore signed-in profile backup |

## Owner-attended next experiment

1. On the Windows owner system—not this Linux job node—create the isolated VM/local account and non-default Chrome user-data directory. Enroll strong account security and preserve recovery material offline.
2. Owner signs into `chatgpt.com`, confirms exact account/workspace, and records only non-secret labels plus the Active sessions entry.
3. Launch Chrome with local-pipe control; confirm no listening CDP socket with an OS network check. Run three canaries through UI only: list one known conversation, fetch its title/visible text, send a zero-cost benign prompt. Verify rendered terminal completion and persistence after reload.
4. Expire/remove the current Codex credential from the canary worker (without touching the browser session) and repeat. Passing proves independence from Codex expiry; it does not prove a fixed session lifetime.
5. Reboot Windows and repeat; then exercise intentional session revocation and owner re-login. Record timestamps, failure classes, and recovery time—never credential values.
6. Do not enable unattended paid writes until the terms gate and a 7-day soak (daily canary, reboot, UI-change failure, kill-switch, and revoke/recover drill) pass.

This Linux unit did not inspect or claim access to a live Windows browser profile, Desktop store, extension state, or local MCP process. Those checks belong to the owner-attended experiment.

## Primary-source support (retrieved 2026-07-20)

- OpenAI Codex authentication docs: ChatGPT web keeps authentication in the browser; Codex caches credentials separately, may store them in plaintext `~/.codex/auth.json`, and refreshes ChatGPT-sign-in tokens during use. <https://learn.chatgpt.com/docs/auth.md>
- OpenAI active-session management: browser and first-party app sessions are separately visible/revocable where supported; logout-all may take up to 30 minutes, and Codex CLI sessions are not shown there. <https://help.openai.com/en/articles/20001257-managing-active-sessions-in-chatgpt>
- OpenAI passkeys and Advanced Account Security: device/security-key credentials, multi-method recovery requirements, and stronger consumer-account safeguards. <https://help.openai.com/en/articles/20001039> and <https://help.openai.com/en/articles/20001221-advanced-account-security>
- OpenAI account sharing policy: the account is for its owner; multiple owner devices are allowed, while credential sharing is not. <https://help.openai.com/en/articles/10471989-openai-account-sharing-policy>
- OpenAI data export: export may take up to seven days; the emailed download link expires after 24 hours; Business/Enterprise export availability differs. <https://help.openai.com/en/articles/7260999-how-do-i-export-my-chatgpt-history-and-data>
- OpenAI Terms of Use: prohibits automatic/programmatic extraction and bypassing protective measures. <https://openai.com/policies/terms-of-use/>
- OpenAI browser documentation: the Desktop built-in browser has its own browser state; the official Chrome extension uses an existing Chrome profile/session, with site approvals and broad browser permissions. <https://learn.chatgpt.com/docs/browser.md> and <https://learn.chatgpt.com/docs/chrome-extension.md>
- Chrome security guidance: remote debugging has been used for cookie theft; Chrome 136 requires a non-standard user-data directory for the switches and recommends profile isolation. <https://developer.chrome.com/blog/remote-debugging-port>
- Databricks secret management: scope ACLs control access, while redaction protects literal values only and cannot prevent deliberate transformations. <https://docs.databricks.com/aws/en/security/secrets/>

## Confidence note

**High** means directly documented or a standard security consequence of the documented mechanism. **Medium** means the architecture is technically well-grounded but depends on unpublished ChatGPT session lifetime, UI stability, and contractual permission. No claim is made that a browser session is permanent or that consumer web automation is officially supported. No live secret or Windows state was accessed.

UNIT-COMPLETE: V08-final-recommendation
