---
title: V01-top-10-plugin-vulns
type: note
permalink: dqverify-repo-20261013/tools/crcp/reports/web-endgame/v01-top-10-plugin-vulns
---

# V01 — Top 10 plugin/MCP vulnerabilities threatening the ChatGPT web session

## DIGEST (body: 451 words)

**Conclusion.** Durable owner access should mean a recoverable, phishing-resistant way to create a fresh first-party ChatGPT session—not a copied cookie or undocumented refresh token. Use two passkeys/security keys (one cross-device) and, if automation is necessary, sign the same owner account into a dedicated browser profile on an isolated owner-controlled Windows VM/account. Never give plugins, local MCP servers, Databricks jobs, or general Codex processes access to that profile or its control endpoint. **[High]**

### Ranked findings

| Rank | Vulnerability threatening the web session | Confidence | Primary defense |
|---:|---|---|---|
| 1 | Exposed Chrome DevTools/CDP lets a same-host or network process control the authenticated browser and obtain session-equivalent access. | High | Dedicated profile/OS identity; loopback only; authenticated broker; host firewall; ephemeral endpoint; never default profile. |
| 2 | A local MCP/plugin executes with client privileges and can read/control browser state, launch processes, or alter automation. | High | Do not install it on the session host; sandbox, signed allowlist, minimal filesystem/process/network access. |
| 3 | Cookies/tokens leak through plugin config, environment, prompts, traces, screenshots, errors, notebook output, or secret-scope misuse. | High | Never store browser artifacts in Databricks; least-privilege ACLs; redact and prohibit transformed-secret output; short retention. |
| 4 | Tool poisoning/indirect prompt injection pivots from untrusted tool output to a browser, secret, or outbound tool. | High | Separate read and credential-bearing planes; structured outputs; deny cross-tool secret flow; human confirmation. |
| 5 | OAuth token passthrough/audience failure creates confused-deputy and token replay paths. | High | Validate issuer/audience/resource; no passthrough; separate downstream tokens; PKCE and exact redirects. |
| 6 | Scope creep/excessive agency turns a benign connector into an account-impacting actor. | High | Read-only default; action allowlist; “always ask”; separate identities; periodic grants review. |
| 7 | Weak MCP session binding enables hijack, event injection, or cross-user actions. | High | Authorize every request; never authenticate by session ID; random rotation; bind session to user/tenant. |
| 8 | SSRF/DNS rebinding reaches localhost CDP, metadata, tunnels, or internal auth services. | High | Egress proxy; block private/reserved ranges; DNS pinning; HTTPS; redirect revalidation; Origin checks. |
| 9 | Plugin/MCP supply-chain compromise or post-review “rug pull” changes code/tool behavior. | Medium-High | Pin digest/version; reproducible build/SBOM; frozen tool manifest; diff and reapprove updates. |
| 10 | Shadow servers plus weak audit/telemetry hide grants, calls, exfiltration, and persistence. | High | Central inventory/RBAC; per-call audit; anomaly alerts; periodic revoke/test; deny unapproved servers. |

**Immediate recommendation.** Establish passkey-backed owner recovery first. Build any browser rail only after isolation controls are testable. Treat OpenAI data export as backup, not login continuity. No live Windows profile was inspected from this Linux node.

## EVIDENCE

### Method and threat boundary

This is defensive architecture research for the account owner. “Threatens the web session” includes direct cookie/session compromise and any plugin/MCP behavior that can command the already-authenticated browser or cause ChatGPT to perform owner-authorized actions. It does not assume that a ChatGPT cookie is portable, long-lived, or an official API credential. Findings are ranked by directness, expected impact on the same human-used account, and plausibility in the stated Windows + Databricks control plane.

### 1. Exposed browser control plane / CDP — **High**

**Shape.** A browser launched with remote debugging exposes a control plane with session-equivalent power: page navigation, DOM/script execution, and access to authenticated origins. Google reports attackers increasingly used remote debugging to extract cookies; Chrome 136 therefore refuses remote-debugging switches against the default data directory and requires a non-standard `--user-data-dir`. Google explicitly recommends a custom profile to isolate debugging from real profiles.

**Failure modes.** Binding beyond loopback; predictable/static port; unauthenticated port forwarding; reusing the daily human profile; leaving the endpoint alive; plugin access to localhost; copying the profile; treating Chrome 136’s restriction as a complete security boundary.

**Controls for any owner browser rail.** Dedicated VM or Windows OS account; dedicated non-default user-data directory used only for CRCP; current stable browser; loopback-only CDP or a local pipe; host firewall denying inbound access; a small authenticated broker exposing only allowlisted high-level operations; per-run capability/nonce and audit; no raw DevTools socket across Databricks/MCP; profile ACLs limited to the owner identity; terminate control after each operation; require passkey reauthentication when OpenAI expires the session. Prefer Chrome for Testing only for disposable automation profiles, never the owner’s daily profile.

Source: [Chrome remote-debugging security change](https://developer.chrome.com/blog/remote-debugging-port).

### 2. Local MCP/plugin privilege equivalence — **High**

The MCP project states that local servers are binaries executed on the user’s machine, may directly access the system, and—without sandboxing/consent—can arrive through malicious startup commands or payloads. Its security policy says STDIO process launch and same-privilege execution are intended behavior: installing a local MCP server is therefore equivalent to installing software, not granting a narrow web capability. A Bolt/Claude/Codex plugin placed on the Windows session host could become the bridge to the browser even without reading a cookie.

**Controls.** Keep untrusted and development MCP servers off the owner-session host. Run reviewed servers as separate low-privilege identities/containers with read-only filesystems, explicit egress, no browser-profile mount, no process-launch privilege, and no access to loopback endpoints in other isolation domains. Pin command, arguments, package digest, and publisher.

Sources: [MCP security best practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices), [MCP repository security and trust model](https://github.com/modelcontextprotocol/modelcontextprotocol/security).

### 3. Secret exposure in context, logs, configs, and Databricks — **High**

OWASP’s beta MCP Top 10 places token mismanagement and secret exposure first and calls out hard-coded credentials, model memory, protocol logs, prompt injection, and debug traces. Browser cookies are bearer-like session artifacts even if encrypted at rest; screenshots or response bodies may also disclose account data without exposing a cookie.

The existing Databricks secret scope is appropriate only for workspace-side service secrets, **not** a browser-cookie escrow. Databricks redacts literal values returned through supported secret APIs but warns that arbitrary transformations can bypass redaction. Scope creators receive `MANAGE` by default, which includes reading and changing secrets.

**Controls.** Do not put ChatGPT cookies, browser Local State/Profile data, passkey material, or private keys in the scope. Store only a broker credential that cannot be exchanged for raw browser state, restrict ACLs to the job service principal, rotate it, and prevent notebook attachment/interactive access. Scrub Authorization/Cookie headers, SSE bodies, URLs, screenshots, exception objects, shell history, and tracing. Alert on secret reads and ACL changes.

Sources: [OWASP MCP Top 10](https://owasp.org/www-project-mcp-top-10/), [Databricks secret management and redaction](https://docs.databricks.com/aws/en/security/secrets).

### 4. Tool poisoning and indirect prompt injection — **High**

An MCP server’s descriptions or returned content can inject instructions that redirect an agent into another tool. OWASP describes the trust gap between connect-time review and runtime results; OpenAI warns that unsafe MCP servers increase prompt-injection exposure and that responsibility for vetting custom servers remains with the workspace.

The dangerous composition is `untrusted fetch/read tool → model → browser/CDP or secret-capable tool`. Confirmation is useful but not absolute: users can be habituated, arguments can be misleading, and read operations can already disclose data.

**Controls.** Credential-bearing browser operations must not be model-addressable from arbitrary MCP output. Use typed/validated outputs, taint untrusted content, prohibit secrets in tool arguments/results, allowlist destinations and operations, and require a human to approve the fully rendered origin/account/action. Run retrieval in a separate logged-out context where possible.

Sources: [OWASP MCP tool poisoning](https://owasp.org/www-community/attacks/MCP_Tool_Poisoning), [OpenAI on prompt injections](https://openai.com/safety/prompt-injections/), [OpenAI developer mode and MCP apps](https://help.openai.com/en/articles/12584461-developer-mode-and-full-mcp-connectors-in-chatgpt-beta).

### 5. OAuth passthrough, audience confusion, and confused deputy — **High**

The MCP authorization specification requires servers to validate tokens as intended for that server and forbids passing the inbound MCP token through to an upstream API. Otherwise, a token can cross a security boundary and a proxy can become a confused deputy. This matters even when the leaked token is for Databricks or a connector rather than ChatGPT: it can provide the execution or data path used to reach the owner browser.

**Controls.** Enforce issuer, audience, signature, expiry, and `resource`; reject bearer tokens not minted for the MCP server; obtain a separate downstream token; use PKCE, exact registered redirects, state/nonce, and per-user consent; never accept a ChatGPT/Codex token as a generic upstream credential.

Sources: [MCP authorization specification](https://modelcontextprotocol.io/specification/draft/basic/authorization), [MCP security best practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices).

### 6. Scope creep and excessive agency — **High**

OAuth scope, MCP tool availability, and ChatGPT’s “ask permission” setting are distinct. OpenAI documents that app permissions only determine when ChatGPT asks; they do not reduce access already granted at the provider. “Never ask” permits automatic reads/actions, while admins separately control app actions and RBAC. A read-oriented Databricks connector that later gains write, token-management, or tunnel capability changes the risk materially.

**Controls.** Start read-only, set **Always ask** for owner-sensitive apps, disable unused actions, separate operator/read identities, and review both provider scopes and ChatGPT action controls. Never let a plugin modify OpenAI account security, active sessions, passkeys, billing, or credentials. Reauthorize instead of silently widening scopes.

Sources: [Apps in ChatGPT—permissions](https://help.openai.com/en/articles/11487775), [OpenAI app templates security notes](https://help.openai.com/en/articles/20001247), [OpenAI developer mode controls](https://help.openai.com/en/articles/12584461-developer-mode-and-full-mcp-connectors-in-chatgpt-beta).

### 7. MCP session hijacking and tenant misbinding — **High**

MCP explicitly warns that an attacker obtaining a session ID may impersonate the client when the server fails to perform additional authorization. Session IDs are routing state, not authentication. Multi-user proxies that key state only by MCP session can cross account or tenant boundaries and cause actions under the wrong owner connection.

**Controls.** Authorize every inbound request; use cryptographically random, rotated, expiring session IDs; derive user/tenant identity from the validated authorization token; bind queued state to that identity; prevent event injection; isolate caches and connection pools per account.

Sources: [MCP security best practices—session hijacking](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices), [MCP authorization tutorial](https://modelcontextprotocol.io/docs/tutorials/security/authorization).

### 8. SSRF and DNS rebinding into localhost/internal services — **High**

MCP metadata and authorization URL fetching can be abused to reach private IPs, cloud metadata, localhost services, or redirect targets. The specification calls out DNS rebinding and reflected internal responses. On a browser host, localhost may include CDP, an automation broker, or an MCP tunnel; in Databricks it may expose metadata or service credentials.

**Controls.** HTTPS-only production metadata; destination allowlists; block private, loopback, link-local, multicast, and reserved ranges after every DNS resolution and redirect; DNS pinning; egress proxy; disable redirects unless required; validate `Origin` on local HTTP servers; authenticate the broker independently. Network-isolate browser and cluster control planes.

Source: [MCP security best practices—SSRF/DNS rebinding](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices).

### 9. Plugin/MCP supply-chain compromise and rug pull — **Medium-High**

OWASP identifies dependency tampering and tool poisoning as separate MCP risks. Marketplace reputation or an initial review does not guarantee later code, transitive packages, hosted tool output, or tool metadata. OpenAI now uses a frozen snapshot of custom MCP tools after admin approval and requires review/publish for updates; this reduces metadata rug-pulls but does not attest all remote implementation behavior.

**Controls.** Prefer first-party or internally built minimal servers; pin immutable image/package digests and lockfiles; verify signatures/provenance; generate SBOM; scan dependencies; review source and network destinations; canary updates; diff tool schemas/annotations/scopes; reapprove every update; maintain a kill switch and known-good rollback.

Sources: [OWASP MCP Top 10](https://owasp.org/www-project-mcp-top-10/), [OpenAI frozen MCP tool snapshots](https://help.openai.com/en/articles/12584461-developer-mode-and-full-mcp-connectors-in-chatgpt-beta).

### 10. Shadow MCP servers and inadequate audit/telemetry — **High**

Unknown local servers, personal tunnels, stale OAuth grants, and unlogged tool calls make the preceding attacks persistent and hard to contain. OpenAI’s Active Sessions view covers browser and first-party app sessions but explicitly does **not** show third-party apps, connected apps, Sign in with ChatGPT sessions used only by third parties, or Codex CLI sessions. Therefore it cannot serve as the sole inventory.

**Controls.** Maintain separate inventories for OpenAI active sessions, connected apps, third-party OAuth grants, Codex auth, MCP servers/tunnels, browser brokers, Databricks principals/secrets, and plugins. Log tool identity/version, authenticated principal, target, action class, approval, result, and correlation ID—never secret values. Alert on new tools/scopes, off-hours access, unusual destinations, and session-security changes. Exercise revoke-all and broker shutdown.

Sources: [OpenAI Active Sessions scope and limitations](https://help.openai.com/en/articles/20001257-managing-active-sessions-in-chatgpt/), [OWASP MCP Top 10](https://owasp.org/www-project-mcp-top-10/).

## Durable-access candidates

| Path | Expected lifetime | Requires browser? | Survives Codex token expiry? | Risk / limitation | Next owner experiment |
|---|---|---:|---:|---|---|
| Two OpenAI passkeys/security keys, including one cross-device, plus recovery keys | Until revoked/lost/account policy changes | Yes for enrollment and web sign-in | **Yes** | **Low-Medium. High confidence.** Durable authentication, not unattended access. Loss risk if backups/recovery keys fail; Advanced Account Security disables weaker recovery. | On the owner Windows/browser plane, enroll two independent authenticators, escrow recovery keys offline, sign out a test session, and prove re-login to the same account/workspace. |
| Dedicated owner browser session in isolated profile/VM | Server-controlled; may be shortened/revoked | **Yes** | **Yes** | **High. High confidence.** Direct web access but bearer-session compromise impact; not a recovery method. | On Windows only, create isolated OS identity/profile, login with passkey, verify Active Sessions label, broker restrictions, logout propagation, and forced reauth. Do not export cookies. |
| First-party ChatGPT Desktop session/grant | Server-controlled; undocumented | Desktop app | Likely yes | **Medium; UNVERIFIED.** OpenAI confirms first-party app sessions exist, but storage, automation interface, and lifetime are not documented here. | **Windows-only live validation required:** inspect only UI-visible session management and supported app behavior; do not extract credentials or infer undocumented grants. |
| Organization SSO/OIDC with durable IdP ownership | IdP/account policy controlled | Yes for interactive login | **Yes** | **Medium. Medium confidence.** Strong enterprise recovery/control; OpenAI Active Sessions feature is unavailable for SSO-linked accounts. May not apply to the consumer account. | Determine whether the exact human account/workspace supports SSO without changing identity; test in a non-production member first. |
| Official ChatGPT data export / Privacy Portal | Export link 24 hours; request may take up to 7 days | Usually, or ownership verification | N/A | **Low security risk; High confidence.** Backup only; does not restore a session or provide live account-plane access; unavailable from Settings for Business/Enterprise. | Request a test export and validate encrypted offline retention, while documenting that it is not authentication continuity. |
| Codex `~/.codex/auth.json` access token | Short/issuer-controlled | No after issuance | **No** | **High operational fragility. High confidence from mission evidence.** Temporary consumer and wrong endgame. | Keep only as a monitored transitional path; prove CRCP fails closed on expiry and never copies it into browser/session storage. |
| Cookie copy or “long-lived web token” escrow in Databricks | Unknown/revocable | Source browser required | Sometimes, until revoked | **Critical risk; Low confidence as a durable mechanism.** Unsupported, replay-prone, may be device-bound, and defeats isolation. | **Do not experiment.** Replace with brokered operations and passkey reauthentication. |

Passkey and recovery evidence: [OpenAI passkeys](https://help.openai.com/en/articles/20001039), [OpenAI Advanced Account Security](https://help.openai.com/en/articles/20001221-advanced-account-security). Session evidence: [OpenAI Active Sessions](https://help.openai.com/en/articles/20001257-managing-active-sessions-in-chatgpt/). Export evidence: [OpenAI data export](https://help.openai.com/en/articles/7260999-how-do-i-export-my-chatgpt-history-and-data).

## Recommended target architecture

1. **Root of continuity:** two phishing-resistant authenticators for the same owner ChatGPT account, with offline recovery keys and a tested recovery runbook. This survives Codex token death because it creates a new first-party web session.
2. **Owner session enclave:** dedicated Windows VM or physical host identity and dedicated browser profile; no general plugins/MCPs; no shared clipboard/profile directory; patched OS/browser; full-disk encryption; screen lock; EDR; outbound allowlist where practical.
3. **Narrow browser broker:** local, loopback-only, mutually authenticated, deny-by-default, high-level operations only. It returns normalized results, never cookies, storage databases, raw DevTools targets, Authorization headers, or arbitrary JavaScript execution. Human confirmation is mandatory for paid writes, account/security changes, sharing, and new destinations. For the existing paid path, success means terminal SSE `DONE`, not HTTP 200.
4. **Databricks boundary:** the job receives only a short-lived broker capability. Store any bootstrap secret in `codex-harness-prekzursil` with a service-principal-only ACL; rotate; audit reads; never store browser/session/passkey material. Databricks recommends short-lived OAuth and service principals for automation; M2M access tokens are one hour, while the client secret can be configured for up to two years, so scope and rotation remain essential. Sources: [Databricks authentication selection](https://docs.databricks.com/aws/en/dev-tools/auth), [Databricks OAuth M2M](https://docs.databricks.com/aws/en/dev-tools/auth/oauth-m2m).
5. **Revocation and detection:** inventory all five grant planes (OpenAI sessions, ChatGPT apps, third-party OAuth, Codex tokens, MCP/tunnels); alert on changes; support immediate broker shutdown, app disconnect, individual session logout, and logout-all. OpenAI states logout-all may take up to 30 minutes, so containment must also revoke local broker access immediately.

## Practical acceptance tests

- Codex token expires while passkey-based login to the same ChatGPT account still succeeds.
- A plugin/MCP process cannot read the profile, connect to broker/CDP, reach its loopback namespace, or cause the browser to navigate.
- SSRF probes to loopback, private/link-local addresses, alternate IP encodings, DNS rebinding, and redirects are blocked and audited.
- Tool output containing adversarial instructions cannot invoke the browser rail or move secrets into another tool.
- Every broker request is bound to owner identity, narrow capability, destination, action, expiry, and confirmation record.
- Revoking a ChatGPT session plus shutting down the broker immediately prevents further work; audit shows no raw secret.
- Databricks secret redaction bypass attempts are prevented by ACL/compute isolation rather than relying on redaction alone.
- Plugin/server update changes digest or manifest, fails closed, and requires explicit reapproval.

## Limitations

This Linux Databricks node cannot inspect the live Windows browser profile, DPAPI/App-Bound Encryption state, ChatGPT Desktop, browser extensions, local MCP processes, or session inventory. None were fabricated. Those are explicitly owner-executed Windows experiments, and no experiment should copy or print credential material. OpenAI does not publicly document a supported long-lived ChatGPT-web refresh credential or cookie-export API in the reviewed sources; absence is not proof one does not exist, so that point remains **UNVERIFIED**. The OWASP MCP Top 10 source is currently beta, so it supports taxonomy rather than a claim of measured prevalence.

UNIT-COMPLETE: V01-top-10-plugin-vulns