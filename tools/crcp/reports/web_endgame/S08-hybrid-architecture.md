# S08 — CRCP hybrid: web-session primary, Codex AT secondary

## Digest (≤500 words)

### Ranked findings

1. **[High] Keep the primary credential on an owner-controlled Windows device.** CRCP should delegate typed operations to a local browser broker; it should never export raw ChatGPT cookies to Databricks. The browser remains the credential boundary and executes the first-party web flow, including any sentinel/PoW work. This survives a Codex token failure because the ChatGPT browser session is separately managed and separately revocable.

2. **[High] Make durability a re-bootstrap workflow, not a promise of immortal cookies.** OpenAI publishes session review/revocation, but no fixed ChatGPT cookie lifetime. A passkey-backed, owner-attended login plus health checks and a “needs owner” state is durable operationally. Never auto-enter passwords, MFA, or passkey assertions.

3. **[High] Codex OAuth is a secondary adapter, not a synchronized credential store.** Its local record contains access/ID/refresh token shapes and refresh metadata. Use it for read continuity and narrowly controlled fallback writes; do not copy tokens between adapters or dual-write. Refresh reuse/invalidation, 401s, account/workspace mismatch, and endpoint drift must open the circuit.

4. **[High] A successful write is a terminal protocol event, not HTTP 200.** Assign an operation UUID, persist intent before dispatch, accept only SSE `DONE` or an equivalent browser-observed terminal state, then reconcile by conversation/message identity. Retries are read-before-write; ambiguous outcomes go to owner review.

5. **[Medium] This remains an unsupported-interface strategy.** No official OpenAI source found exposes a durable API for a consumer’s ChatGPT web history/write plane. OpenAI terms restrict programmatic extraction and bypassing safeguards. Legal/product-owner approval is therefore a release gate; CRCP must not reverse-engineer or bypass sentinel, PoW, rate limits, or safety controls.

### Candidate ranking

| Rank/path | Lifetime | Requires browser | Survives Codex AT expiry | Risk | Next experiment |
|---|---|---:|---:|---|---|
| 1. Dedicated owner browser profile + local broker | Server-managed; unpublished | Yes | Yes | Medium: bearer/session theft, UI drift, policy | Attended Windows canary; login, read, one write, revoke session |
| 2. ChatGPT Desktop browser / Codex Chrome grant | App/browser-state; unpublished | Yes | Likely | Medium; account-plane controllability **UNVERIFIED** | Test whether an owner-approved grant can drive ChatGPT itself and report terminal state |
| 3. Official data export | Point-in-time; link 24h | Yes/email | Yes | Low; delayed, read-only | Quarterly recovery export and restore drill |
| 4. Codex OAuth token set | AT short-lived; RT rotates/invalidates | Bootstrap only | AT: yes via RT; auth death: no | High if copied; endpoint coupling | Fault-inject expired AT/used RT and confirm circuit breaker |
| 5. Raw cookies in Databricks secrets | Unpublished/revocable | Bootstrap | Yes | **Very high; reject** | None—test broker delegation instead |

### Implement next

Build `WebSessionAdapter`, `CodexAdapter`, an auth-state router (`HEALTHY/DEGRADED/NEEDS_OWNER/REVOKED`), operation journal, terminal-event verifier, and reconciliation worker. Run the browser broker under a dedicated OS account/profile; loopback-only control plus outbound mTLS queue; host/action allowlist; signed results; no arbitrary browser commands. Databricks stores only broker-channel credentials in `codex-harness-prekzursil`, with job-principal READ only—never web cookies. Log salted credential fingerprints, not values. Ship revoke-all, broker kill, token rotation, and owner notification runbooks before paid writes.

## EVIDENCE

### Proposed component and trust architecture

```text
Databricks CRCP (no ChatGPT session secret)
  operation journal -> policy/approval -> auth router
       |                                  | fallback
       | typed, nonce-bound job           v
       v                             CodexAdapter
outbound/mTLS queue                  ~/.codex/auth.json-derived token
       ^
       | signed terminal result
Windows owner device
  Local Broker -> dedicated persistent browser profile -> chatgpt.com
     allowlisted verbs     first-party JS performs challenges/SSE
```

The broker API should be semantic (`list`, `fetch`, `send`, `reconcile`, `health`), not “execute JavaScript” or a generic URL fetcher. It should accept an operation ID, account/workspace expectation, target conversation, content hash, deadline, and approval class. The result should contain identifiers/status/timestamps and a salted session fingerprint only. This limits prompt-injection and credential-exfiltration paths while keeping the web credential out of cluster memory, Spark configuration, notebooks, DBFS, and logs.

For writes, the browser adapter should let the first-party client perform its normal protective protocol. CRCP may observe the resulting terminal event; it must not synthesize, defeat, or reuse protective challenges. A native UI acknowledgement alone is insufficient when the stream is ambiguous. On timeout or transport loss, reconcile the target before retrying. Paid actions default to owner approval until duplicate-prevention and terminal verification pass fault tests.

### Why the primary is a device session, not a cookie vault

OpenAI now describes active browser and first-party app sessions as account-managed objects, sometimes associated with trusted devices, and permits individual or global revocation. “Log out all” can take up to 30 minutes. Codex CLI sessions are explicitly not shown in this view, supporting the architectural conclusion that web/app sessions and Codex CLI auth are distinct failure/revocation domains. **[High]**  
Source: [OpenAI — Managing active sessions in ChatGPT](https://help.openai.com/en/articles/20001257-managing-active-sessions-in-chatgpt/)

OpenAI documents passkeys as device- or security-key-held cryptographic credentials, optionally synced, protected by biometric/PIN/touch, and usable for sign-in or MFA. This is an excellent owner-attended recovery root, but not an automation secret: CRCP should pause for the owner when reauthentication is required. **[High]**  
Source: [OpenAI — Passkeys to secure your OpenAI account](https://help.openai.com/en/articles/20001039)

The ChatGPT Desktop built-in browser uses its own browser state; the Codex Chrome extension can use an existing Chrome profile, cookies, signed-in session, and tabs. OpenAI advises entering credentials only in the browser and reviewing the active account. This establishes viable owner-approved browser-state containers, but does **not** document that either can serve as an API/control channel for ChatGPT’s own account plane. That capability is **UNVERIFIED** pending a Windows experiment. **[Medium]**  
Source: [OpenAI — Using the built-in browser in the ChatGPT desktop app](https://help.openai.com/en/articles/20001277-using-the-built-in-browser-in-the-chatgpt-desktop-app)

OWASP treats session IDs as bearer-equivalent sensitive material, recommends server-enforced idle/absolute expiry and renewal, warns against logging session IDs, and suggests salted hashes for correlation. Thus copying a cookie jar to Databricks increases the blast radius and still cannot guarantee lifetime; it is not the durable endgame. **[High]**  
Source: [OWASP — Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)

### Codex secondary behavior and isolation

The OpenAI Codex source constructs an auth record with ChatGPT mode, access token, ID token, refresh token, account ID, and `last_refresh`. This proves refreshable credential shape, not guaranteed longevity. Treat the whole set as one rotating security principal; a refresh failure or account-claim change invalidates the adapter until attended login. **[High]**  
Source: [openai/codex — login server implementation](https://github.com/openai/codex/blob/main/codex-rs/login/src/server.rs)

The Codex app-server protocol documents a ChatGPT device-code login with an OpenAI verification URL, login ID, and short user code. This is a supported attended bootstrap option for Codex, but remains Codex auth—not a documented replacement for the web browser session. **[High]**  
Source: [openai/codex — app-server README](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)

Failure policy:

- `401/403`, refresh-token reuse/invalidation, missing account claim, or wrong workspace: open circuit and set `NEEDS_OWNER`; never fall through to another identity silently.
- Web session login/interstitial/challenge requiring human presence: preserve the operation, notify owner, and stop. No cookie harvesting or identity-provider automation.
- UI/backend schema drift: fail closed; browser canary runs read-only first after every detected version change.
- HTTP 200 without terminal stream state: `AMBIGUOUS`, followed by read reconciliation; never blind retry.
- Web and Codex disagree on conversation state: web is authoritative for the ChatGPT account plane; quarantine the Codex result for review.
- Revocation/incident: stop queue, terminate broker, invoke ChatGPT session revocation, rotate broker mTLS credentials and Codex auth independently, then reconcile all in-flight writes.

### Databricks handling

Databricks secret scopes provide READ/WRITE/MANAGE ACLs and redact literal secret values, but transformed or indirectly referenced values can escape redaction. Therefore the job principal should receive READ on only the broker-channel secret(s); humans/groups with cluster attach or notebook run rights must not inherit ChatGPT bearer material because none should be stored there. **[High]**  
Sources: [Databricks — Secret management](https://docs.databricks.com/aws/en/security/secrets), [Databricks — Access control lists](https://docs.databricks.com/aws/en/security/auth/access-control)

Databricks warns that cluster environment variables can be read by users with attach/run permissions. Do not place a browser cookie, Codex token set, or browser-profile encryption key in cluster environment variables or Spark configuration. Resolve the broker-channel secret just-in-time in the driver, avoid executor distribution, and zero references after use where practical. **[High]**  
Source: [Databricks — Secrets in Spark configuration or environment variables](https://docs.databricks.com/aws/en/security/secrets/secrets-spark-conf-env-var)

### Recovery, compliance, and experiment gates

Official ChatGPT export is a recovery snapshot, not a live credential: it can take up to seven days, its download link expires after 24 hours, and availability varies by workspace type. Use it for owner-controlled backups and restoration drills, never for transaction continuity. **[High]**  
Source: [OpenAI — Exporting your ChatGPT history and data](https://help.openai.com/en/articles/7260999-how-do-i-export-my-chatgpt-history-and-data)

OpenAI’s individual Terms of Use prohibit automatic/programmatic extraction and bypassing rate limits, restrictions, protective measures, or safety mitigations. The Services Agreement similarly restricts extraction and bypass. Because `backend-api`, sentinel, PoW, and web DOM/network automation are not documented public account APIs, owner/legal approval and a narrow non-bypass interpretation are mandatory before production. Prefer first-party UI behavior; do not reverse-engineer challenges. **[High]**  
Sources: [OpenAI — Terms of Use](https://openai.com/en-GB/policies/terms-of-use/), [OpenAI — Services Agreement](https://openai.com/policies/services-agreement/)

Minimum Windows canary (must be performed on the owner device; this Linux node has no Windows profile and none was inspected):

1. Create a dedicated profile/OS account; owner signs in with the original account method and verifies expected account/workspace.
2. Confirm web read and one low-value write through typed broker verbs; record only identifiers/fingerprints; require a terminal stream event and read-back.
3. Expire the Codex AT and demonstrate uninterrupted web-adapter operation; then break Codex refresh and demonstrate clean circuit opening.
4. Revoke only the browser session in ChatGPT Security and verify broker transition to `NEEDS_OWNER`; verify Codex state is independently handled.
5. Re-bootstrap with passkey/owner presence, then run duplicate, disconnect, SSE-without-`DONE`, UI-drift, and wrong-workspace tests.
6. Run “log out all,” validate shutdown within the documented propagation window, rotate channel credentials, and reconcile the journal.

Go-live requires: no raw ChatGPT credential in Databricks, deterministic identity checks, zero blind retries, browser and Codex independent revocation, an owner-visible reauth path, and written approval for the unsupported web interface. Until then, paid writes remain canary-only and owner-approved. **[High]**

UNIT-COMPLETE: S08-hybrid-architecture
