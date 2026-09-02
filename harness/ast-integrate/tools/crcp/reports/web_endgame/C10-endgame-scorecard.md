# C10 — Endgame scorecard: durable ChatGPT web-account access

Date: 2026-07-20 UTC  
Scope: owner-authorized access to the same consumer ChatGPT account; no credential values inspected or reproduced.

## Executive digest (≤500 words)

**Finding 1 — [High]: Make the web plane primary.** The best endgame is an owner-controlled Windows web executor that keeps the authenticated browser profile on that device and exposes only narrow CRCP operations. It survives a Codex access-token expiry because it uses an independent first-party browser session. It does **not** survive ChatGPT logout, server expiry, account suspension, password/security events, profile loss, or explicit session revocation.

**Finding 2 — [High]: `auth.json` is a renewable consumer, not the root.** OpenAI Codex persists an ID/access/refresh token set, refreshes it, and can revoke a superseded grant. That can outlive one access token, but refresh rotation, concurrent writers, logout/revocation, client entitlement, endpoint changes, or loss of the local store can end it. A bearer accepted by Codex/backend routes is not evidence that the browser session remains alive; OpenAI’s session UI explicitly excludes Codex CLI sessions.

**Finding 3 — [High]: Never export browser cookies to Databricks.** Cookies are bearer-equivalent session identifiers whose lifetime is server-controlled and may be device/risk-bound. Copying a browser profile into `codex-harness-prekzursil` expands the account-takeover boundary to workspace admins, secret readers, job code, logs, and cluster operators. Databricks redaction is best-effort and cannot defeat deliberate transformation.

**Finding 4 — [Medium]: Desktop is a useful independent lane, not yet a headless API.** ChatGPT Desktop and its built-in browser have their own first-party/app and browser state. A local approval-driven executor could remain usable after Codex OAuth dies, but no public evidence establishes a long-lived programmable Desktop grant for CRCP.

**Finding 5 — [High]: Durable means recoverable, observable, and revocable.** Use passkeys/MFA as the human root of reauthentication; continuously health-check each lane without exposing secrets; record session fingerprints only as salted hashes; and treat HTTP 200 as provisional. Paid writes remain `prepare → owner policy/sentinel → PoW → execute → SSE DONE`, with idempotency and an auditable receipt.

**Recommendation:** implement web-first routing now: `CRCP controller (Databricks) → mTLS/capability queue → owner Windows browser broker → ChatGPT web`, retain Codex OAuth only as a degraded secondary lane, and use official exports as read-only recovery snapshots.

## EVIDENCE

### Ranked scorecard

Ranking weights same-account fidelity and read/write utility first, then independence from Codex, recoverability, isolation, and public support. “Survives Codex expiry” means independence from expiration of the current Codex access token; it does not mean immortality.

| Rank | Candidate / path | Expected lifetime and revoke/expire behavior | Requires browser | Survives Codex expiry | Principal risk | Next experiment | Confidence |
|---:|---|---|:---:|:---:|---|---|---|
| 1 | **Local owner web profile + narrow broker**: dedicated Windows browser profile; automation attaches locally and returns typed results, never cookies | Session-defined: may persist across browser restarts, but OpenAI may expire it; owner logout, “log out all,” password/security events, account restriction, cookie clearing, or profile loss terminate it | Yes | **Yes** | Broker compromise equals web-account control; UI/backend changes; bot/risk challenges | On the owner Windows box, create a dedicated profile and prove list/fetch/send plus a forced Codex-token-expiry test. Do not extract cookie values | **High** architecture; **UNVERIFIED** live CRCP integration |
| 2 | **ChatGPT Desktop first-party lane**: local app session / built-in browser, with owner approvals and host allowlist | First-party app session; separately visible/revocable when supported. Built-in browser state can be cleared. No published fixed lifetime | Yes (Desktop UI/browser) | **Yes** | No documented general headless grant; prompt injection and overbroad website permission | Validate whether Desktop can execute the exact CRCP read/write flow and expose a safe local handoff without exporting state | **Medium** |
| 3 | **Passkey/MFA reauthentication root**: owner-held synced passkey plus hardware/recovery method recreates lane 1 or 2 | Authentication factor persists until removed/lost; it creates a new session rather than providing unattended requests. Account/IdP policy can revoke it | Yes, for sign-in | **Yes** | Human availability; device loss; synced-provider compromise; SSO rules | Enroll two independent secure methods; rehearse browser re-login and document account/workspace verification | **High** |
| 4 | **Dedicated owner-controlled Windows VM / remote browser service**: persistent encrypted profile plus broker | Same server-side web-session limits as rank 1; VM/profile lifecycle adds failure points. Revoke via ChatGPT session controls and destroy VM key material | Yes | **Yes** | Remote-control surface, snapshots/backups, admin plane, IP/device anomaly, supply chain | Build an isolated non-shared VM; test reboot continuity and kill-switch revocation before any paid write | **Medium** |
| 5 | **Official ChatGPT data export**: verified owner request → email/SMS link → encrypted archive | Point-in-time, read-only. Export may take up to 7 days; download link expires after 24 hours; archive persists under owner retention policy | Browser or Privacy Portal to request | **Yes** | Stale snapshot, sensitive archive, no sends, unavailable for Business/Enterprise per current help page | Request one owner export, inventory conversation identifiers/schema, encrypt, and test restore/indexing | **High** |
| 6 | **Workspace-side cookie/profile snapshot in a secret scope** | Only until server/session expiry, rotation, logout, risk reauthentication, device binding, or profile-format/encryption changes | Initially yes | **Yes, nominally** | High-value replay secret on shared cloud compute; browser state may be OS-bound; redaction/ACLs are not a complete defense | **Do not productionize.** If risk acceptance demands a lab, use a sacrificial account and dedicated compute only | **High** risk; **Low** durability |
| 7 | **Independent Codex managed OAuth/device grant in a vault**: stop copying a live access token; let an official Codex client own refresh | Access token is short-lived by design; refresh grant extends it but is rotating/revocable and client/entitlement-bound. Superseded grants may be revoked | Browser/device approval for enrollment | **Yes** for one token expiry; **No** for Codex grant death | Still Codex plane, refresh races/dual-writes, unsupported reuse by CRCP, broad bearer theft | Isolate one official client/store and test rotation under concurrency; use only as fallback | **High** mechanism; **High** that it is not endgame |
| 8 | **OpenAI API project key/service identity as a parallel archive/write plane** | Until key revocation, project removal, quota/billing failure, or policy change; independently rotatable | No | **Yes** | It is a different product/account-data plane and does not confer access to the human’s ChatGPT web history | Prove non-equivalence with a harmless API-created conversation and record it only as a separate CRCP lane | **High** independence; **High** non-equivalence |

### Codex-only baseline and the gap

**Baseline — `~/.codex/auth.json` + Codex/backend API: [High].** The official Codex app-server documentation says “ChatGPT managed” mode owns the OAuth flow and refresh tokens, persists tokens to disk, and refreshes automatically. The source shows the stored shape—ID token, access token, refresh token, account identifier, last-refresh metadata—and best-effort revocation of superseded tokens. This is stronger than copying only the current access token, but it is still one OAuth client grant and local mutable store, not the browser’s durable account-control root. Sources: [Codex app-server authentication modes](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md#auth-endpoints), [Codex login persistence and revocation source](https://github.com/openai/codex/blob/main/codex-rs/login/src/server.rs).

**Isolation/revocation distinction — [High].** OpenAI describes active sessions as browser or first-party app sessions but says the session screen does not show Codex CLI sessions. “Log out of all” invalidates active browser/app sessions and may take up to 30 minutes. Therefore, health and revocation must be tracked per lane; CRCP must not infer web validity from Codex validity or vice versa. Source: [OpenAI: Managing active sessions in ChatGPT](https://help.openai.com/en/articles/20001257-managing-active-sessions-in-chatgpt/).

**Failure modes — [Medium].** A refresh token can bridge access-token expiry, but it can itself expire, be revoked, be replaced, or fail under concurrent rotation. The official source’s explicit refresh/revoke behavior supports this model; an open Codex issue documents a cross-process “refresh token already used” race, but issue reports are operational evidence rather than a guarantee of current behavior. Sources: [Codex login source](https://github.com/openai/codex/blob/main/codex-rs/login/src/server.rs), [OpenAI Codex issue #10332](https://github.com/openai/codex/issues/10332).

### Why the web/desktop lanes are materially different

**First-party state — [High].** OpenAI states that ChatGPT active sessions can represent a signed-in browser or first-party app and can be individually revoked. It also states that the Desktop built-in browser has its own state, while the Codex Chrome extension can use the existing Chrome profile, signed-in session, tabs, and extensions. The same guidance says to enter credentials in the browser, not chat, and to review the active account. Sources: [active sessions](https://help.openai.com/en/articles/20001257-managing-active-sessions-in-chatgpt/), [built-in browser in ChatGPT Desktop](https://help.openai.com/en/articles/20001277-using-the-built-in-browser-in-the-chatgpt-desktop-app).

**No fixed “long-lived cookie” promise — [High].** A browser cookie is only a client handle to server-side session state. OWASP documents idle, absolute, renewal, and manual expiration and stresses that server-side invalidation is decisive. Thus CRCP must discover health, not assume a cookie’s disk expiry equals usable lifetime. Log only a salted hash or opaque local session label, never the session identifier. Source: [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).

**OS/profile binding — [High for Edge; Medium when generalized].** Microsoft documents that Edge encrypts sensitive browser data including cookies and protects the profile encryption key using Chromium OSCrypt and Windows DPAPI. Copying raw browser databases to Linux is therefore neither a sound portability plan nor a safe secret-management plan. It also widens the theft boundary beyond the logged-in Windows user. Source: [Microsoft Edge password-manager and profile encryption security](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-security-password-manager-security).

**Reauthentication durability — [High].** OpenAI passkeys are device- or security-key-held cryptographic credentials and may be device-local or synced. MFA applies across OpenAI services, but enabling MFA does not revoke existing sessions; logout controls remain separate. The account owner should keep at least two recovery methods and rehearse them. Sources: [OpenAI passkeys](https://help.openai.com/en/articles/20001039), [OpenAI MFA](https://help.openai.com/en/articles/7967234).

### Workspace isolation conclusion

Databricks secret scopes are encrypted and ACL-controlled, but Databricks explicitly warns that workspace admins, scope creators, and permitted users can read secrets; output redaction is best-effort and cannot prevent deliberate transformation. Standard compute provides multi-user data isolation, while dedicated compute is assignable to a single user/group. These controls are useful for a **broker credential**, not justification for placing a full ChatGPT browser session in the workspace. Sources: [Databricks secret management](https://docs.databricks.com/aws/en/security/secrets/), [Databricks compute access modes](https://docs.databricks.com/aws/en/compute/configure#access-modes).

For `codex-harness-prekzursil`, store only: a broker endpoint identifier, a narrowly scoped client credential or public-key reference, a rotation version, and optionally a salted session-health fingerprint. Do not store cookies, browser databases, passkeys, refresh-token copies, local-storage dumps, private keys, or Desktop profile material. Use a separate CRCP principal with least-privilege `READ` on the broker secret and policy job compute; deny notebook users and unrelated plugins.

### Target CRCP architecture

1. **Web session custodian (Windows owner boundary).** Dedicated browser/Desktop profile, patched OS, disk encryption, owner login, no unrelated extensions. It alone holds ChatGPT session state and completes risk/MFA prompts.
2. **Narrow browser broker.** Allow only typed operations (`health`, `list`, `fetch`, `prepare_send`, `commit_send`, `export_status`). Enforce origin/host allowlists, account/workspace checks, request size limits, nonces, idempotency keys, and local owner kill switch. Treat page content as untrusted input.
3. **Control plane (Databricks).** Route web first, Codex second, export third. Send signed intents over mutually authenticated transport. Never accept raw arbitrary URLs, JavaScript, headers, cookie operations, or general remote desktop commands from a plugin/agent.
4. **Paid-write state machine.** `PREPARED` records content hash, destination/account, quoted cost, expiry, and sentinel result; `AUTHORIZED` records owner/policy decision; `POW_OK` records challenge binding; `SUBMITTED` is nonterminal even on HTTP 200; only parsed SSE `DONE` or an independently verified terminal UI state yields `COMMITTED`. Ambiguous outcomes are reconciled by idempotency/read-back, never blind retry.
5. **Observability and revocation.** Record lane, opaque session label, timestamps, status code/event class, request hash, and terminal receipt—no secrets. Alert on account/workspace drift, login UI, CAPTCHA/risk challenge, session change, unexpected redirect/origin, 401/403, missing SSE DONE, or duplicate commit. Kill switch disables broker, ends the ChatGPT session from Security settings, and rotates the broker credential.

### Acceptance experiments (owner-operated)

This Linux job node has no Windows profile or local Desktop process; no live browser claims were fabricated. The scorecard itself is complete and does not require those assets. Execute these later on the owner Windows box:

1. Establish a dedicated owner profile; verify the displayed account/workspace without recording identifiers; run read-only list/fetch.
2. Expire or isolate the Codex access-token consumer without logging out of ChatGPT; confirm the web lane still reads. Then revoke the browser session and confirm immediate fail-closed behavior without Codex fallback for paid writes.
3. Reauthenticate through passkey/MFA; confirm broker recovery requires no cookie export and session label changes.
4. Perform a zero-cost or explicitly approved sentinel write; inject cases for HTTP 200 without SSE DONE, stream truncation, duplicated idempotency key, risk challenge, and account drift.
5. Reboot browser host and broker; confirm expected persistence. Clear browser/Desktop state and confirm deterministic loss and documented recovery.
6. Audit the Databricks scope ACL and job policy; demonstrate that the job can invoke only broker methods and cannot obtain browser/session material.
7. Request an official export, verify its archive shape and encryption/retention path, and measure staleness. OpenAI says delivery can take up to seven days and the link expires in 24 hours. Source: [OpenAI ChatGPT data export](https://help.openai.com/en/articles/7260999-how-do-i-export-my-chatgpt-history-and-data).

### Decision

**Adopt ranks 1 + 3 + 5, evaluate rank 2, and use rank 4 only if a continuously available local owner machine is infeasible. Reject rank 6 for production. Retain rank 7 strictly as a monitored fallback and rank 8 as a separate API plane. [High]**

The durable asset is not any particular token: it is the owner’s recoverable account identity plus an isolated first-party web/app session and a narrow, observable execution boundary. Codex OAuth remains useful, but CRCP should be able to delete every copied `auth.json` consumer and continue through the web lane after owner reauthentication.

UNIT-COMPLETE: C10-endgame-scorecard
