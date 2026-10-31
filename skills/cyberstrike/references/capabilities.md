---
title: capabilities
type: note
permalink: dqverify-repo-20261013/skills/cyberstrike/references/capabilities
---

# CyberStrike capability and surface reference

This is a durable operator reference, not a substitute for executable enforcement.
Every name, limit, and correction below is load-bearing; preserve them verbatim.
Use only explicitly authorized targets and the external signed engagement guard.
Passive/public data never authorizes active probing.

## Invocation and interface map

Use the installed `cyberstrike` executable, never repository scripts.

| Purpose | Supported invocation | Required truth |
|---|---|---|
| Interactive OpenTUI | `cyberstrike [project] [--model provider/model] [--continue] [--session ID] [--fork] [--prompt TEXT] [--agent NAME]` | Sessions, providers/models, agents, MCP/Bolt, permissions, methodology, findings, HackBrowser state, reports. Starts API + SPA on `127.0.0.1:4096`, with ephemeral fallback, and stops it with the TUI. |
| Headless/automation | `cyberstrike run "<request>" [--model provider/model] [--agent NAME] [--format default\|json] [--file PATH ...] [--continue\|--session ID] [--fork] [--attach URL] [--dir PATH]` | JSON event streaming. Interactive permission requests are auto-rejected, so this is not unattended exploitation unless the operation was explicitly pre-authorized. A subagent passed to `--agent` is rejected and falls back to the primary. |
| Full web UI | PowerShell: `$env:CYBERSTRIKE_SERVER_PASSWORD = '<secret>'; cyberstrike web --hostname 127.0.0.1 --port 4096` / Git Bash: `CYBERSTRIKE_SERVER_PASSWORD='<secret>' cyberstrike web --hostname 127.0.0.1 --port 4096` | Backend plus bundled SolidStart SPA and browser. Password is mandatory. Use the printed URL after port fallback. Do not put a real password in documentation or shell history. |
| API-only backend | `cyberstrike serve --hostname 127.0.0.1 --port 4096` with the same password variable | No SPA (`webUI:false`); never call this the web UI. |
| Attach TUI | `cyberstrike attach <URL> [--dir REMOTE_PATH] [--session ID] [--password SECRET]` | Reuses remote server/session. Current attach hard-codes username `cyberstrike`, so it cannot match a server override made with `CYBERSTRIKE_SERVER_USERNAME`. Prefer environment/secret injection; never use `--password` in normal operation. |
| Dedicated crawl | `cyberstrike hackbrowser <TARGET_URL> [--scope PATTERN ...] [--exclude LABEL ...] [--steps 1..200] [--credential ID ...] [--headfull]` | Creates session, starts crawl, opens TUI. Credentials force visible manual login. It tries 4096 then ephemeral despite a source comment saying random. |
| Agent inventory | `cyberstrike agent list` | Enumerates configured agents; not every listed subagent is a valid direct `run --agent` value. |

Every `[project]`, `--dir`, attachment, report, and runtime-state path must resolve through the supervisor to the dedicated external engagement workspace or an explicitly approved read-only input; never to either repository/target checkout.

Bare `cyberstrike` technically does not require `CYBERSTRIKE_SERVER_PASSWORD`, but the sterile supervisor must supply one because the TUI also starts API + SPA. Reject `0.0.0.0`, mDNS, and non-loopback binds. Basic auth over direct LAN HTTP is plaintext, and bare loopback bypasses auth. Use loopback or a CA-valid authenticated TLS proxy/private VPN. Never put target cookies, bearer tokens, reports, Bolt admin tokens, or tool output in URLs, argv, logs, or untrusted tunnels.

## Agent topology and methodology

The built-in primary is `cyberstrike`. It delegates through the `task` tool or explicit `@agent-name` mention to:

```text
general
explore
web-application
mobile-application
cloud-security
internal-network
proxy-agent
```

Hidden proxy internals are:

```text
proxy-analyzer
proxy-tester-idor
proxy-tester-authz
proxy-tester-mass-assignment
proxy-tester-injection
proxy-tester-authn
proxy-tester-business-logic
proxy-tester-ssrf
proxy-tester-file-attacks
```

Do not expose hidden nodes as direct CLI entry points. `cyberstrike run --agent web-application ...` is not a valid forcing mechanism at this revision; use primary delegation or `@web-application` interactively. Tab/Shift-Tab cycles non-subagent agents, not every specialist.

Expose and persist all 13 phases:

```text
scope_analysis
passive_recon
active_recon
technology_profiling
authentication_testing
session_management
authorization_testing
input_validation
business_logic
data_protection
api_security
infrastructure
reporting
```

Phase meaning:

1. scope/attack surface: wildcard, host, CIDR, mobile, asset inventory, exact in-scope checks;
2. passive recon: certificates, DNS/OSINT, subdomains, historical URLs, public code/search, technology hints;
3. active recon: live hosts, ports/services, crawling, paths/parameters, JavaScript endpoints, screenshots, enumeration;
4. profiling: frameworks, versions, dependencies, exposed config, CVE correlation;
5. authentication/session: login/signup/reset/MFA, default/weak credentials, brute-force resistance, cookies, fixation, JWT, CSRF, OAuth state/PKCE, logout/expiry;
6. authorization: horizontal/vertical access, IDOR/BOLA, role/object/function maps, mass assignment, credential-to-credential comparison;
7. input/data/API: SQL/NoSQL/command/LDAP/template/XML injection, XSS, SSRF, traversal/include/upload, GraphQL/REST authorization/schema behavior, CORS/TLS/secrets/errors;
8. business logic: workflow skipping, price/quantity, negative/overflow, rate limits, race/TOCTOU, verified server impact;
9. infrastructure/domain: mobile static/dynamic, AWS/Azure/GCP identity/posture, Kubernetes, internal network, AD/Kerberos, services, privilege escalation, lateral movement/pivots;
10. reporting: evidence validation, duplicate triage, coverage, compound chains, final Markdown report, and separate generic session export.

Methodology tools:

```text
add_intel
update_vrt_check
record_coverage_note
get_coverage_notes
scope_check
methodology_status
```

Web-context/entity tools:

```text
web_write_role
web_write_object
web_write_object_value
web_write_function
web_get_session_context
web_get_detail
web_get_request_detail
web_get_vulnerabilities
web_get_vuln_detail
web_update_credential_claims
```

These retain endpoints/functions, roles, credentials/claims, objects/values, request observations, findings/evidence/retest state, per-asset coverage, notes, VRT checks, timeline, and agent performance. Track compound patterns including credential-to-account-takeover, disclosure-to-SSRF, redirect-to-OAuth-token theft, IDOR-to-bulk leak, XSS+CSRF, SSTI-to-RCE, and race-condition-to-financial-impact.

Security-specific built-ins:

```text
hackbrowser
report_vulnerability
triage_vulnerability
attack_script
generate_report
ebpf
winhook
machook
awshook
azurehook
kubehook
cipipe
ensure_tools
```

`ensure_tools` mutates the host through package managers. Keep it discoverable but baseline-denied and require separate reviewed setup approval. Its exact allowlist is:

```text
nmap nuclei ffuf httpx subfinder amass waybackurls gau hakrawler katana
dalfox sqlmap nikto wpscan gospider arjun paramspider commix ssrfmap
nosqlmap crlfuzz gitdumper
```

The exact `attack_script` programs are:

```text
jwt_tamper race_tester ssti_tester ssrf_listener idor_tester cors_checker
graphql_tester file_upload_tester oauth_tester rate_limit_bypass waf_bypass
cloud_storage_enum subdomain_takeover github_dorker wayback_endpoints
response_diff
```

Its model schema is `{script, args[], timeout_seconds}`. These are validation/differencing helpers, never proof by scanner output alone. A finding still needs reproducible request/response evidence, reasoning, scope confirmation, and duplicate triage.

## HackBrowser

Describe HackBrowser accurately as Playwright Chromium browser-integrated page request/response interception with LLM-guided accessibility/DOM navigation, posting normalized observations to `/session/ingest`. It is not a transparent, system-wide, or Burp-compatible proxy.

Expose all three integrated entry points:

1. the dedicated CLI command above;
2. TUI `/hackbrowser` and `/hackbrowser-stop`, whose dialog accepts target, comma-separated credential IDs, hostname scope patterns, semantic label exclusions, 1–200 pages (50 default), and headless/visible mode; it creates a session from home or reuses the current session;
3. the model tool:

   ```text
   hackbrowser {
     target: URL,
     credentials?: string[],
     scope?: string[],
     exclude?: string[],
     steps?: 1..200,
     headless?: boolean
   }
   ```

The tool permission is target-based, returns “started” asynchronously, and must be observed with `web_get_session_context`; reinvocation is not polling, and only one crawl runs per CyberStrike session.

Capture behavior:

- request method/URL/headers/body and response status/headers/body, with response body capped at 500 KiB;
- form values/validation, readonly/disabled/hidden/display-only fields, request-only parameters, mutating trigger, and navigation provenance;
- cookie/authorization/token extraction into credential records—always secret/redacted;
- BFS navigation, path-shape dedup/caps, DOM fill/click/select/submit/upload, live telemetry;
- one context per credential, sequential visible manual logins, per-role page/element availability/access diffs in one session;
- request-shape dedup while preserving per-credential observations, sequential `proxy-agent` queueing, analysis, then focused testers.

Proxy testers require a baseline, an attack request, and a measurable response difference before confirmation. Their scope includes IDOR/BOLA, horizontal/vertical auth, mass assignment, auth/session/JWT/reset, SQL/NoSQL/XSS/SSTI/XXE/command/LDAP injection, workflow/pricing/race/rate limits, SSRF/internal/cloud metadata, and upload/traversal/include/webshell/SVG/zip-slip. Preserve the injection tester’s explicit denial of destructive SQL DDL, filesystem writes, and OS-shell/RCE primitives.

Scope caveats are load-bearing:

- Patterns are hostname suffixes. Protocol, port, and path are removed. `example.test` and `*.example.test` each include the base and subdomains; multiple patterns are OR. This is not path allowlisting.
- `exclude` is a semantic UI-label hint, not network/change control. The browser can click/submit, automatically accept dialogs, and supply bundled samples to file choosers. Independently enforce exact target hosts, disposable data/accounts, and forbidden actions.
- A credential ID forces visible manual login, then autonomous crawling. Roles are sequential. Cancellation may require closing the browser.
- The visible Shadow-DOM panel mutates the target DOM and can perturb fragile applications; headless mode has no panel.
- The JSONL worker inherits the parent environment. Use minimal credentials and a disposable host.
- Provision a pinned reviewed Playwright/Chromium build. Reject the fallback installer, which sets `NODE_TLS_REJECT_UNAUTHORIZED=0`.
- The worker’s provider envelope is narrower than the main “150+ providers” claim; use a verified API-key provider, supported Anthropic auth, or supported GitHub Copilot route.
- `packages/hackbrowser/README.md` saying `bun start` is stale; no `start` script exists. `bun --cwd packages/hackbrowser src/index.ts ...` is development-only, with separate auth and stale/partial flags. The integrated entry points are canonical.

Every run needs fresh human approval binding target, exact hostname list, credential alias, exclusions, page limit, allowed mutations, and denied endpoints. Default scope can expand to `*.{eTLD+1}`; reject implicit broad scope. Use synthetic least-privilege accounts in a reversible tenant, block destructive routes server-side, and snapshot the lab.

## TUI and web application

Core TUI commands:

```text
/sessions
/new
/models
/agents
/mcps
/bolt
/connect
/status
/themes
/help
/exit
```

Security/session views:

```text
/hackbrowser
/hackbrowser-stop
/vulnerabilities   (aliases /vuln, /vulns)
/web               (endpoints, roles, credentials)
/methodology       (intel, VRT, chains, coverage)
/report            (alias /export)
```

The web app exposes session/chat creation/continuation/sharing, provider/model/agent choice, permissions, tool output, PTY, files, diffs/review, navigation, panels for MCP/Bolt/vulnerabilities/web context/to-dos/signed skills, entity/observation/finding views, Bolt lifecycle and “From Bolt” inventory, and Markdown report download.

Do not claim a dedicated web HackBrowser control; none existed in `packages/app/src` at the reviewed commit. The web chat can ask the agent to call the tool, while CLI/TUI are direct controls. A “signed skills” panel also does not prove authenticity.

The web report download route chooses the lexicographically latest `report-*.md` in the project report directory and does not truly filter by the session route parameter. Verify the file before delivery. If local SPA assets are absent, the backend can proxy to `app.cyberstrike.io`; disclose this privacy/egress fallback and provide a require-local-assets/offline mode that fails instead. A separately hosted HTTPS app may be blocked from plain HTTP localhost by mixed-content/private-network rules; same-origin local UI or authenticated HTTPS is predictable.

For every TUI/web/API path, set a strong unique server password, bind `127.0.0.1`, keep mDNS off, and never expose `0.0.0.0` bare HTTP. The API includes PTY, file, auth, session, and execution controls and is RCE-equivalent. Password checks are bypassed for bare loopback and static assets bypass auth; CORS intrinsically trusts localhost/127 origins and HTTPS `*.cyberstrike.io`, and merely adding a narrower list does not remove those built-ins. Treat same-user processes and allowed local origins as inside the threat boundary. Enforce a smaller origin/network policy at the authenticated reverse proxy. Remote access is loopback behind authenticated TLS plus private VPN/Access, MFA/rate limiting, and exact proxy origin policy. Use a dedicated browser profile; the app stores server connection/password data in browser storage and embeds credentials in PTY WebSocket URLs. Clear site data after the engagement.

## Bolt client/server and fan-out

CyberStrike is a Bolt client. The server is separately deployed. Use the strict top-level map and base URLs with no `/mcp` suffix:

```jsonc
{
  "bolt": {
    "bolt-lab": {
      "url": "http://127.0.0.1:3001",
      "enabled": true,
      "timeout": 900000
    },
    "bolt-east": {
      "url": "https://bolt-east.example.test",
      "enabled": true,
      "timeout": 900000
    }
  }
}
```

Only `url`, `enabled`, and a positive integer `timeout` are accepted. Default 30000 ms is valid but too short for full approved remote operations, so use 900000 ms where justified. Reserve unique `bolt-...` names; do not reuse MCP names because internal maps overlap. Stale docs showing `mcp: {bolt:true,url:".../mcp"}` are invalid. There is no `cyberstrike bolt add` shell command.

Pair/control through TUI `/bolt`, web `/bolt`, or these API routes:

```text
GET    /bolt
POST   /bolt                         {"name":"bolt-east","config":{"url":"...","enabled":true,"timeout":900000}}
POST   /bolt/{name}/pair             {"url":"...","adminToken":"..."}
POST   /bolt/{name}/connect
POST   /bolt/{name}/disconnect
DELETE /bolt/{name}
GET    /mcp/bolt-tools
```

Pairing calls server `POST /pair` with the one-time admin bearer token, generates a local Ed25519 client key, then calls `POST /pair/exchange` with the code/public key. Normal requests use `X-Client-Id`, `X-Timestamp`, `X-Nonce`, and `X-Signature`; clocks must stay within the server’s 30-second window. The client private key is under CyberStrike data `bolt-keys/<entry-name>.json`, requested with mode `0600`; Windows must additionally enforce the user-profile ACL because POSIX mode is insufficient there. The server `/data` volume holds server keys/authorized clients. Ed25519 authenticates but does not encrypt. Use loopback, private VPN, or CA-valid HTTPS.

Removing a CyberStrike entry neither revokes the server client nor deletes the local key. A complete removal separately calls `DELETE /pair/clients/<clientId>` with the admin token, then deletes only the exact resolved credential file after confirming the entry. Never recursively delete a data root. Connect/disconnect is runtime state, not a durable `enabled` edit.

Windows single-node deployment must not use the mutable `:latest`/secret-in-argv `docker run` form as production acceptance. Resolve and record an immutable reviewed image digest, prefer a Docker secret or ACL-restricted env-file rather than secret argv, and run the digest-pinned equivalent. If no approved digest/secret mechanism exists, report the Bolt deployment gap instead of claiming reproducibility. Never print/commit the admin token. Use unique node names, ports, volumes, tokens, config names, client keys, and network positions. Confirm each node routes only to the authorized target network; Docker Desktop does not guarantee Windows VPN route parity. Only estate-owned nodes in the engagement record may connect. Require HTTPS/private VPN/firewall, per-node or per-engagement keys, restrictive ACLs, rotation/revocation, audit, kill switch, and node-to-target mapping. Never expose Bolt directly to the Internet or use one fleet-wide key.

A healthy default node has 45 source tools. Native 10:

```text
subfinder
nmap
nuclei
nuclei_update_templates
httpx
ffuf
run_command
wordlist_list
wordlist_search
wordlist_recommend
```

Nested MCP 35 before the outer node prefix:

```text
dnsx_dnsx_resolve
alterx_do-alterx
amass_amass
arjun_do-arjun
assetfinder_do-assetfinder
cero_do-cero
commix_do-commix
crtsh_crtsh
http-headers_analyze-http-header
katana_do-katana
masscan_do-masscan
shuffledns_shuffledns
smuggler_do-smuggler
sqlmap_do-sqlmap
sslscan_do-sslscan
waybackurls_do-waybackurls
wpscan_do-wpscan
scoutsuite_do-scoutsuite-aws
gobuster_gobuster_dir
gobuster_gobuster_dns
rustscan_rustscan
hydra_hydra
medusa_medusa
kerbrute_kerbrute_userenum
kerbrute_kerbrute_passwordspray
hashcat_hashcat_crack
hashcat_hashcat_show
john_john_crack
john_john_show
john_john_list_formats
impacket_impacket_asreproast
impacket_impacket_exec
impacket_impacket_kerberoast
impacket_impacket_lookupsid
impacket_impacket_secretsdump
```

`gowitness-mcp` and `mobsf-mcp` directories exist but are not enabled by default; do not count or promise them. CyberStrike exposes `<bolt-entry-name>_<Bolt-exposed-tool-name>`, for example `bolt-east_nmap`, `bolt-east_nuclei`, `bolt-east_run_command`, `bolt-east_sqlmap_do-sqlmap`, `bolt-east_impacket_impacket_secretsdump`.

Tools are lazy-loaded:

```text
tool_search("capability needed on bolt-east")
load_tools(["exact returned namespaced ID", ...])
call the loaded tool on the following turn
unload_tools([...]) when no longer needed
```

Fan-out is explicit calls to several node-prefixed tools; no broadcast, scheduler, load balancer, automatic retry/reconnect, cross-node reducer, or “run on all Bolts” exists. Provider behavior determines concurrency. Label every result with node, target, time, tool, and authorization scope before synthesis. Bolt buffers stdout/stderr until exit and caps each at 100 KiB; do not claim real-time streaming. Client timeout can expire while the server process continues. `run_command` is broad root remote shell: require important-action confirmation or deny it when a dedicated tool suffices. Current rate middleware/logs are not complete authorization/audit.

## Platform-routed post-exploitation

These are model tools with common shape `{program, args[], timeout_seconds}`, not top-level `cyberstrike <program>` commands. They execute where CyberStrike runs. Bolt does not automatically transport them. Keep all discoverable and default-denied. Require exact action, matching authorization, platform/identity probe, evidence decision, disposable host, and human confirmation.

`ebpf`, Linux/root, 30 source programs (not the README’s 29):

```text
pam_sniff ssl_sniff dep_scan proc_hide file_hide conn_hide execve_sniff
dns_sniff keylog cleanup io_uring_sniff memfd_exec ptrace_sniff
crossmem_sniff userfaultfd_sniff bpf_integrity netlink_sniff seccomp_sniff
mmap_sniff zerocopy_sniff vdso_sniff keyring_sniff namespace_sniff
ioctl_sniff mount_sniff fuse_sniff perf_sniff bpfmap_sniff
ldpreload_sniff futex_sniff
```

`winhook`, native Windows/Administrator, 12:

```text
lsass_dump sam_dump dpapi_extract credential_prompt keylog_win etw_process
etw_network clipboard_sniff amsi_bypass etw_blind defender_exclude
cleanup_win
```

`machook`, macOS/usually root, 12:

```text
keychain_dump chrome_creds ssh_keys tcc_bypass keylog_mac dtrace_exec
dtrace_net dtrace_file xprotect_check gatekeeper_bypass log_clear
cleanup_mac
```

DTrace may require SIP/entitlement changes; never weaken a host without a separate approved plan.

`awshook`, authorized AWS identity, 10:

```text
iam_enum iam_privesc s3_dump lambda_backdoor ssm_exec metadata_harvest
cloudtrail_blind secrets_dump ec2_snapshot cleanup_aws
```

`azurehook`, authorized Azure identity, 8:

```text
entra_enum entra_privesc keyvault_dump storage_dump managed_identity
runbook_backdoor azuread_token cleanup_azure
```

`kubehook`, authorized kube context, 7:

```text
k8s_enum k8s_secrets k8s_escape k8s_privesc etcd_dump k8s_backdoor
cleanup_k8s
```

`cipipe`, authorized CI/CD context, 5:

```text
gh_secrets jenkins_creds pipeline_inject gitlab_tokens cleanup_ci
```

These include credential dumping, keylogging, stealth/hiding, defense/log bypass, remote execution, persistence/backdoors, and cleanup. Cleanup is a scoped destructive operation even when upstream text says to “ALWAYS” run it: snapshot and record evidence first, preview the exact cleanup delta, require a named cleanup grant, and verify restoration without erasing evidence the RoE requires.

## Findings and reporting

`report_vulnerability` records severity (`critical`, `high`, `medium`, `low`, `info`), title/description, CWE, location, endpoint/attack vector, reproduction, business impact, recommendation, PoC, and VRT category. New unique findings are accepted. Similar findings remain candidates until `triage_vulnerability` approves or marks duplicate; duplicates stay in history but are excluded from confirmed output. Preserve baseline/attack/response evidence and the role/credential alias used.

`generate_report` deterministically compiles:

```text
executive_summary
findings
coverage
methodology
chains
attack_surface
timeline
agent_performance
validation
```

It includes severity-sorted confirmed findings, reproduction/PoC/remediation, VRT/per-asset coverage, untested/red-flag notes, phases/blockers, chains, intelligence/request inventory, timeline, metrics, and validation. It leaves AI placeholders for executive summary, risk assessment, and remediation priorities. TUI `/report` (alias `/export`) asks the primary to fill them and save `.cyberstrike/reports/report-<timestamp>.md`.

That path must be under the external engagement workspace, never a target/toolchain checkout. `cyberstrike export [sessionID]` is generic session-message JSON, not the professional report; the shared word “export” is a naming collision, not equivalence. Require final human review of original scope, secrets/redaction, safe reproduction, severity, duplicates, blockers, false-positive evidence, and destination. Do not overclaim validation: source checks evidence/request count/reproduction/scope/duplicates/coverage including a 60% threshold, but `generate_report` passes an empty scope list into its aggregate gate. Independently compare every finding and asset with the signed authorization.

## Capability tiers (fail-closed)

1. Offline code review, CVE lookup, reporting, and passive defensive analysis may run without a live target.
2. Active recon, `attack_script`, Bash, browser crawl/interception, exploit validation, and active MCP tools require a current exact-scope grant and bounded rate.
3. Credential dumping/phishing, keylogging, LSASS/SAM/DPAPI/Keychain/browser-secret access, secret extraction, privilege escalation, container escape, persistence/backdoors, AMSI/ETW/TCC/Gatekeeper bypass, eBPF hiding/sniffing, CloudTrail/log deletion or blinding, CI injection, C2 callbacks, and Bolt fan-out are default `DENY`. Enable only a named technique explicitly permitted by the RoE, inside a disposable engagement VM/lab/node, with a per-run human confirmation and cleanup/evidence plan.

CyberStrike’s primary agent defaults to `"*":"allow"`, and `scope_check` only reports YES/NO plus a warning — it is not enforcement. These nine tools execute without their own `ctx.ask` and MUST be explicitly denied in the baseline:

```text
attack_script
ensure_tools
ebpf
winhook
machook
awshook
azurehook
kubehook
cipipe
```

Platform support truth: native Windows 11 x64 supports the core CLI/TUI/web and `winhook` (Administrator required). Native Windows cannot run Linux/eBPF or macOS hooks. There is no reviewed win32-arm64 build. WSL2 eBPF is unproven until a real probe. Linux/eBPF needs a separately authorized compatible Linux host, kernel at least 4.7, root, Python, BCC/`python3-bpfcc`, and `CAP_SYS_ADMIN`. CyberStrike has 103 tracked `.py` files (including 30 eBPF programs); resolve `python3` explicitly on Windows before advertising those paths.