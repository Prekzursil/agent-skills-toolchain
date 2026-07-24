# CyberStrike harness bridge, plugin, and companion-MCP reference

Durable operator reference for the license-isolated integration boundary. Not a
substitute for executable enforcement. The private gateway and the external AGPL
plugin are SEPARATE artifacts. Never point CyberStrike at the private worktree as
its config or skill root.

## License and separation boundary (no legal opinion)

CyberStrike, `@cyberstrike-io/plugin`, and `@cyberstrike-io/sdk` are `AGPL-3.0-only` (version 3 only). A true in-process plugin dynamically imported into CyberStrike is not made license-isolated by calling it a wrapper. Keep that adapter as a separately installed CyberStrike-side artifact under an explicitly reviewed AGPL-compatible license, or obtain written alternative commercial terms. Do not import or vendor those packages into proprietary toolchain code. Process separation reduces combined-work risk; it is not a judicial safe harbor.

Use this wording in durable documentation: "CyberStrike may be used commercially under AGPL if its obligations are satisfied. An alternative commercial license is advertised through `contact@cyberstrike.io`; obtain and review its written terms before relying on it for proprietary embedding, distribution, or a modified hosted service." Do not say AGPL forbids commercial use, that commercial use always requires payment, or that payment automatically covers this integration. Before distributing a bundle, modifying CyberStrike, exposing a modified network service to other users, or shipping an in-process plugin while keeping it proprietary, stop at a license decision gate.

The private toolchain remains Node 22 + Python 3.11. Do NOT add Bun, `@cyberstrike-io/*`, CyberStrike source/binary/asset/lock/patch/generated-SDK, or a gitlink to the monorepo, its lockfiles, or the QZP workflow. Toolchain CI attests only to repository-owned wrapper/config/gateway code; a green run does not prove CyberStrike passed any of its own gates.

## Topology

```text
CyberStrike Bun process
  └─ external reviewed config/plugin/harness-bridge.ts (AGPL-side, owner-ACL, off-repo)
       ├─ harness_bridge_status
       ├─ harness_capabilities
       ├─ harness_invoke
       ├─ redacted hook/audit envelopes
       └─ scope + approved-skill enforcement
                     │ HMAC-authenticated loopback HTTP/JSON v1
                     ▼
private agent-skills-toolchain
  └─ tools/mcp/cyberstrike-harness-bridge/ (license-neutral, no CyberStrike import)
       ├─ strict capability registry
       ├─ replay-resistant protocol
       ├─ shared lifecycle-harness provider
       ├─ independent skill/trust-lock verifier
       ├─ narrow Codex orchestrator adapter
       ├─ narrow Databricks fan-out adapter
       ├─ allowlisted CyberStrike REST client
       └─ append-only redacted audit
```

The gateway package under `tools/mcp/cyberstrike-harness-bridge/` is license-neutral (no CyberStrike source/import) and MAY live in the private repo. The SDK-importing plugin (`plugin/harness-bridge.ts`) may NOT live there; it stays in the external CyberStrike-owned config tree, e.g. `%LOCALAPPDATA%\CyberStrike\agent-skills-toolchain-bridge\`.

## Gateway protocol (`ast.cyberstrike.bridge/v1`)

Bind only `127.0.0.1`. Refuse `0.0.0.0`, non-loopback `Host`, every `Origin`, all `Forwarded`/`X-Forwarded-*`, query strings, non-JSON bodies, chunked input, and oversized input. Emit no CORS headers. Loopback scopes transport but is not authentication; a same-user process is inside the threat boundary.

Generate a random 256-bit per-install HMAC key. Supply it to both processes through an ACL-restricted file or process environment — never argv, JSONC, Markdown, logs, prompts, Git, or the server password. Reject decoded length other than exactly 32 bytes. Every route, including `/health`, requires:

```text
X-AST-Timestamp: <Unix seconds>
X-AST-Nonce: <32 random bytes, base64url>
X-AST-Body-SHA256: <lowercase hex SHA-256 of exact request bytes; empty-body digest for GET>
X-AST-Signature: <base64url HMAC-SHA256>
```

Signed bytes are exactly `UPPERCASE_METHOD + "\n" + pathname + "\n" + timestamp + "\n" + nonce + "\n" + bodySha256`. Verify with constant-time comparisons, permit at most ±30 seconds, retain accepted nonces in a bounded cache for at least 60 seconds, and reject duplicate nonce before routing. Rotate by restarting both processes; never accept old and new keys indefinitely.

Routes:

```text
GET  /health
GET  /v1/capabilities
GET  /v1/scope
POST /v1/invoke
POST /v1/hooks/:hookName
POST /v1/skills/authorize
```

`/health` returns only `{"protocol":"ast.cyberstrike.bridge/v1","status":"ok","version":"<gateway-version>"}` and never capabilities, paths, policy, key state, or arguments. Every `/v1/*` request/response carries `protocol`, `requestId` (uuid), `timestamp` (RFC3339 UTC), `correlationId` (uuid), `origin` (`cyberstrike-plugin|harness-reverse`), and `hopCount` (0). Reject `hopCount > 1`. Never serialize `PluginInput.client`, Bun `$`, `AbortSignal`, callbacks, parent environment, auth objects, provider options, raw headers, or browser/session credentials.

Hook responses contain only `protocol`, `requestId`, `decision` (`observe|continue|deny`), and `reasonCode`. There is no general JSON Patch; the gateway never rewrites message history, provider headers/options, environment, tool schemas, or permissions. Scope/compaction fragments come only from `/v1/scope`, generated from the owner-approved engagement, and are data not executable code.

Timeouts/circuit: observation hooks 250 ms (max 128 queued/process, 16/session, drop oldest, catch, never break CyberStrike); prompt/pre-tool 1.5–2 s; scope/skill 2 s; high-risk tools, `harness_invoke`, `skill load`, and bridge-owned actions fail closed; ordinary read-only observation may fail open; capability timeouts max 15 minutes locally (long Databricks work returns a run ID polled with `fanout.status`); after three consecutive transport failures pause observation POSTs 30 s while keeping health/status probeable; never cache an allow decision beyond engagement expiry. Hard-cap HTTP body and response at 65,536 bytes; return an opaque private artifact receipt for larger output. Deep-redact before enqueue/persistence. Append one NDJSON audit record per request with UTC, request/correlation IDs, engagement, session/call, capability/hook, decision/result, duration, and hashes/lengths — never raw prompts, tool output, shell command, environment, auth header, token, cookie, provider key, full file content, exception body, or stderr.

## The three plugin tools

The external adapter imports exactly `import { tool, type Plugin } from "@cyberstrike-io/plugin"` and registers exactly:

```text
harness_bridge_status   read-only gateway health/protocol/version; never paths/policy/keys/secrets
harness_capabilities    read-only allowlisted capability manifest + canonical-JSON SHA-256 revision
harness_invoke          exactly one validated invocation after permission+manifest+schema+engagement+risk+confirmation+idempotency+workspace checks
```

`harness_invoke.execute` must be async and must not contact the gateway until `ctx.ask({permission:"harness_invoke", patterns:[capability], always: riskClass==="read" ? [capability] : [], metadata:{capability, manifestRevision, idempotencyKey}})` resolves successfully. Rejection or cancellation denies. Empty `always` for write/billable prevents session-wide always-allow. Invoke arguments: `capability` (enum), `manifestRevision` (64-hex), `arguments` (record, default `{}`), `idempotencyKey` (uuid), `confirm` (bool, default false). Invoke must supply the exact current manifest revision or fail `capability_manifest_changed`.

The ten capabilities (real per-capability strict schemas with `additionalProperties:false`; never a shared permissive `arguments` schema; disabled+recorded if the live branch has no real contract):

```text
codex.consult        read              -> codex_consult
codex.brainstorm     read              -> codex_brainstorm
codex.review         read              -> codex_review
codex.discuss        read              -> codex_discuss
codex.coordinate     write             -> codex_coordinate
codex.curate         write             -> codex_curate
fanout.prepare       write             -> fanout_prepare
fanout.submit        external_billable -> fanout_submit (permission + current engagement + confirm:true)
fanout.status        read              -> fanout_status
fanout.harvest       write             -> fanout_harvest
```

The six `codex.*` handlers wrap only `codex_consult`, `codex_brainstorm`, `codex_review`, `codex_discuss`, `codex_coordinate`, `codex_curate`; do NOT register the root orchestrator wholesale (manager writes and PromptBridge browser/session actions stay absent). Map fan-out narrowly to the current `.agents/skills/codex-databricks-fanout/scripts/harness/` contract: `fanout.prepare` validates units and builds a batch locally; `fanout.submit` submits only a prepared batch preserving frozen `RAIL`, concurrency 48, stagger 3.0, and removal of ambient `DATABRICKS_TOKEN`; `fanout.status` reads lifecycle/per-unit classification; `fanout.harvest` uses `fs cat` then the canonical artifact/sentinel/schema five-clause gate (read the clauses from the current canonical harness and test them; mark a residual gap if absent). Do not expose raw `databricks jobs ...` or a generic Python-module runner. Scope `MSYS_NO_PATHCONV=1` only to Databricks CLI children.

## Shared lifecycle mapping and 17 hook slots

`src/harness-provider.mjs` invokes the absolute reviewed Python 3.11 and `agent-self/harness/dispatcher.py` with literal argv `--provider cyberstrike --event <allowlisted-event>`, one bounded JSON object on stdin, minimal fixed environment, enforced deadline, and validates stdout against unchanged `HookResult`. Use `spawn`/`execFile` with an argv array; never `cmd /c`, shell strings, or Git Bash interpolation. No request field selects executable, argv, module, cwd, environment, or provider.

Extend, do not fork: add `"cyberstrike"` to `SUPPORTED_PROVIDERS`, `normalize_event`, dispatcher CLI choices, and the hook-event schema provider enum. Only for CyberStrike, `render_output()` emits `HookResult.to_dict()` unchanged; Node validates and translates it. Add no CyberStrike-only field to `HookEvent`, `HookResult`, or `hook-result.schema.json`. Do not add CyberStrike to `registration.build_hooks()` or `install.desired_documents()`. Claude/Codex registrations must remain byte-for-byte unchanged and an unsupported fourth provider must fail.

Event translation (only these): `chat.message`→`UserPromptSubmit`; `command.execute.before`→`PreToolUse`; `tool.execute.before`→`PreToolUse`; successful `tool.execute.after`→`PostToolUse`; `experimental.session.compacting`→`PreCompact`; bus `session.created`→`SessionStart`; bus `session.compacted`→`PostCompact`; bus `session.status` idle / deprecated `session.idle`→`Stop`; bus `permission.asked`/rejected `permission.replied`→`PermissionRequest`/`PermissionDenied`; bus `session.deleted`/`session.error`→lifecycle audit. Do not invent `SessionEnd`/`StopFailure`. For `HookResult`: `allow` is no-op; honor `block` only at synchronous chat/command/tool-before; queue `inject` in a bounded per-session queue consumed by the immediately following system transform; CyberStrike has no native `continue`, so record unsupported and queue text for the next genuine turn.

All 17 top-level slots, required treatment:

```text
event                                  catch every failure internally; translate only listed lifecycle/permission; audit-or-ignore others; never block policy
config                                 force harness_invoke to ask unless explicit deny (top-level+each agent); validate skill is ask|deny; names/counts only; fail startup if not ask/deny
tool                                   register exactly the three harness_* tools
auth                                   disabled; no provider-key/OAuth brokerage
chat.message                           current redacted text to UserPromptSubmit; honor block/queue; never send history/files/images/synthetic parts
chat.params                            observe model IDs/numeric sampling only; no mutation
chat.headers                           disabled
permission.ask                         legacy/unreachable; if activated allow only keeping ask or downgrading to deny, never allow; pin a reachability regression test
command.execute.before                 map to policy with name + allowlisted/redacted args; block/queue; no mutation
tool.execute.before                    map with tool/call IDs + schema-allowlisted targets; enforce skills/high-risk/bridge; no generic argument rewrite
shell.env                              disabled
tool.execute.after                     successful bounded receipt only, guard undefined; after skill load rehash locked tree and replace output with stable denial on TOCTOU mismatch
experimental.chat.messages.transform   disabled; never expose full history
experimental.chat.system.transform     local-only; append validated authorized-target fragment + queued context in place, consume queue; never send existing system prompt
experimental.session.compacting        append bounded harness context + engagement ID/allowlist/expiry/correlation; never replace default prompt
experimental.text.complete             length/hash metadata only; no text forwarding/mutation; not Stop
tool.definition                        local-only authorization wording on the three bridge tools; no gateway schema rewrite
```

Plugins execute serially in load order against shared mutable output; enabled mutation must change nested fields/arrays in place (replacing `output.args`/`output.parts`/`output.messages`/`output.system` may be ignored). Include a static authorized-targets-only system fragment even when the gateway is offline. `/v1/scope` returns validated engagement ID, exact target allowlist, allowed/denied action classes, issuer, and expiry. No valid manifest means offensive actions and `harness_invoke` are unavailable.

## External config, plugin discovery, and secrets

The approved plugin must NOT implement `shell.env`. A plugin is same-process arbitrary code; its initializer receives project/worktree paths, a local API client, server URL, and unrestricted `Bun.$`, and top-level code runs before a hook filter can protect anything. If `shell.env` ever became unavoidable, allow only additive namespaced keys from a fixed list, reject collisions, and categorically reject `PATH`, `PATHEXT`, `COMSPEC`, `BASH_ENV`, `ENV`, `NODE_OPTIONS`, `BUN_INSTALL`, `LD_*`, `DYLD_*`, `HTTP*_PROXY`, `NO_PROXY`, `NODE_TLS_REJECT_UNAUTHORIZED`, Git config variables, and every credential variable.

Discovery is exactly one directory level of `{plugin,plugins}/*.{ts,js}` per config directory, resolved to `file://` URLs. Only `plugin/harness-bridge.ts` may match the auto-loader glob, with exactly one runtime export (the default plugin function); helpers belong under sibling `lib/`. Do not both auto-discover the file and list it in a config plugin array (arrays concatenate; an inline `plugin: []` cannot subtract an inherited plugin). Permit only the intentional bridge by exact resolved external path, installed version, and SHA-256. Quarantine project `.cyberstrike/command` and `.cyberstrike/commands` Markdown: raw shell fragments can execute before `command.execute.before`.

Sterile launch environment (set before CyberStrike imports):

```text
CYBERSTRIKE_CONFIG_DIR=<dedicated external root>
CYBERSTRIKE_DISABLE_PROJECT_CONFIG=1
CYBERSTRIKE_DISABLE_CLAUDE_CODE=1
CYBERSTRIKE_DISABLE_EXTERNAL_SKILLS=1
CYBERSTRIKE_DISABLE_DEFAULT_PLUGINS=1
CYBERSTRIKE_HARNESS_URL=http://127.0.0.1:<fixed bridge port>
CYBERSTRIKE_HARNESS_HMAC_KEY_B64=<exactly 32 random bytes, base64>
CYBERSTRIKE_SERVER_PASSWORD=<separate server password>
HUSKY=0
```

Reject inherited `CYBERSTRIKE_CONFIG`, `CYBERSTRIKE_CONFIG_DIR`, `CYBERSTRIKE_CONFIG_CONTENT` before setting the reviewed dir. `CYBERSTRIKE_DISABLE_PROJECT_CONFIG` is necessary but not sufficient; `CYBERSTRIKE_DISABLE_DEFAULT_PLUGINS` gates only the empty `BUILTIN` list, not configured or internally imported plugins. Never use `CYBERSTRIKE_TEST_HOME` as a production shortcut (it also suppresses built-in skills). The baseline permission map is `"*":"ask"` with `read/glob/grep/list` allowed, `harness_invoke` and `skill` as `{"*":"ask"}`, and the nine direct-spawn tools `deny`. The real key is `harness_invoke` (a historical `"harness":"ask"` reference was a typo).

## Skill hashing, authenticity, staging, and loading

Implement an INDEPENDENT trust-lock verifier. CyberStrike's verifier removes the first line matching each `^sha256:.*`, `^signature:.*`, and `^signed_by:.*`, trims, SHA-256 hashes to lowercase hex, and for official skills verifies Ed25519 over the UTF-8 bytes of that hex string using embedded raw public key `qC5noNpNWhgt8fyKZyc9p6kXOHvsHDDO4GCqfDHJ/RA=`. It classifies: no hash `unverified`; mismatched hash `tampered`; matching hash with no signature or a non-official signer `community`; official signer + valid signature `official`; invalid official signature `tampered`. It blocks only `tampered`; `community` and `unverified` remain loadable upstream.

At the pin, recursive `SKILL.md` total is 7656 with 0 sha256/signature/signed_by fields, 0 official, 0 community, 7656 unverified, 0 tampered. `.cyberstrike/skill/index.json` has 129 entries labeled official but runtime ignores the label; the signing script reaches only 27 one-level files and misses 7,629. Report the "7,600+ signed" marketing claim as blocked upstream authenticity, not success. Never stamp `signed_by: cyberstrike-official`, run `cyberstrike skill sign` with a custom key, run `packages/cyberstrike/script/sign-skills.ts`, use `--generate`, or generate a replacement official key.

Source order: global/project `.claude` and `.agents` roots (unless disabled), CyberStrike config skill roots, built-ins, installed XDG data skills, `skills.paths`, then `skills.urls`. Later duplicate names overwrite earlier ones with only a debug warning; `skills.disabled` is schema/UI-only and ignored by the loader. Keep `skills.urls` empty (remote discovery ignores declared digest, uses untrusted names/files, extracts via system `tar` before verification). Stage only an explicit unique-name allowlist into external `approved-skills`, recording source commit, relative path, SHA-256, reviewer, and staged hash in `skills.lock.json`; preserve LF; reserve the three signing field names. Fail closed in `tool.execute.before` on `skill load` unless `/v1/skills/authorize` matches exact name, source path/hash, engagement, and accepted status; rehash the locked tree after load to detect TOCTOU. Gate on per-skill REST status, not CLI totals (`cyberstrike skill verify` counts every non-tampered item, including unverified, as "passed").

## Reverse control (CyberStrike REST allowlist)

Do not invent plugin RPC and do not import the AGPL SDK into the private gateway. Compile an exact REST allowlist:

```text
GET  /global/health
GET  /experimental/tool/ids
GET  /mcp/
POST /session/
POST /session/ingest
POST /session/:sessionID/message
GET  /skill/
GET  /skill/:name
POST /skill/:name/verify
GET  /global/event
```

Send `x-cyberstrike-directory` on project-scoped calls and Basic auth using username `cyberstrike` (or configured username) plus the separate server password, even though loopback currently bypasses it. Never use the public web tunnel as bridge transport. The checked-in OpenAPI has skill routes but the generated client lacks `.skill`; use direct REST. This allowlist is NOT a generic proxy: accept no caller URL, path template, HTTP verb, headers, credential object, or arbitrary body. For ingest, permit only bounded `text`, an owned session, approved agent, and approved model. Never expose skill install/remove/enable/disable, arbitrary command, PTY, auth/provider, share, shell, or browser routes. Prevent recursion: reverse calls carry `{origin:"harness-reverse",hopCount:1}` and a correlation ID (reject above one); bind every created session to owner/engagement/directory; add `(sessionID,correlationID)` to a bounded suppression set before a reverse prompt; prohibit all three bridge tools in reverse-owned sessions; require idempotency on each reverse mutation; validate session ownership and `x-cyberstrike-directory` against configured real roots on every call.

## Companion MCP servers (out-of-process, MIT, external)

Four independent MIT stdio servers are declared in `tools/mcp/canonical-mcp-servers.json`. Their SOURCE is never vendored under `tools/`. Exact launch and truth:

| Fleet ID | Exact launch | Truth |
|---|---|---|
| `cloud-audit` | `bun run <USERPROFILE>/.local/opt/cloud-audit-mcp/src/index.ts` | `badchars/cloud-audit-mcp` @ `e32c53a1b02df50e4a1ba072da17b00dc971bb15`; no npm package/bin/build; Bun source only; requires external user-scoped Bun 1.3.9. 38 tools (AWS 13, Azure 13, GCP 8, meta 4). |
| `github-security` | `npx -y github-security-mcp@0.1.0` | Published npm bin; 39 tools; meaningful private/org coverage needs `GITHUB_TOKEN` (map `${GITHUB_MCP_PAT}`, prefer fine-grained read-only). |
| `cve-mcp` | `npx -y cve-mcp@0.2.0` | Published npm bin; 41 tools; update the existing canonical entry in place, do NOT add a second `cve` alias. All five keys startup-optional; the three Shodan CVE tools are zero-auth CVEDB/InternetDB (do NOT add `SHODAN_API_KEY` here); npm 0.2.0 reports internal protocol 0.1.0 (metadata drift). |
| `osint` | `npx -y osint-mcp-server@0.2.0` | Published npm bin; 37 tools (23 keyless + 14 key-gated). Never run `npx osint-mcp` (unrelated EdamAme-x package). `vt_url` discloses the URL to VirusTotal. |

Never run `npx cloud-audit-mcp` (npm 404). Never inline a token/key or a `"optional"` sentinel. The exact tool counts to assert at handshake are `38`, `39`, `41`, `37` respectively. Default-off alone is not authorization: CyberStrike's plugin cannot see a direct Claude Code call to these stdio servers, so the shared Claude `PreToolUse` guard must recognize every actual tool ID from `mcp__cloud-audit__*`, `mcp__github-security__*`, `mcp__cve-mcp__*`, `mcp__osint__*` (record exact normalized IDs at handshake; unknown/renamed denies), load and verify the same signed engagement record, classify tier, validate schema-allowlisted arguments, perform the ambient read-only identity probe for cloud/GitHub calls, deny on missing/expired scope or identity mismatch or `vt_url` confidential submission or guard outage, and attach only a redacted decision receipt. If that guard cannot mechanically cover direct MCP tools, keep all four servers effective-project-disabled.

## Promotion and default-off (operator, Claude-closed)

The only allowed one-way chain: `tools/mcp/canonical-mcp-servers.json` → `%USERPROFILE%\.mcp.json` → `hooks/mcp-userscope-sync/promote-mcp-userscope.ps1` → `%USERPROFILE%\.claude.json` top-level `mcpServers`. This cannot be completed while Claude Code runs (live processes rewrite `.claude.json`). Prepare and parse the candidate, then close every Claude window and run the promoter with `-DryRun -PruneExtraUserServers`, review, then `-PruneExtraUserServers -Yes`; never `-Force`. Do NOT add `"disabled":true` to promoted entries, do NOT rely on root `.claude.json.disabledMcpServers` (measured inert), do NOT park in `.mcp.disabled.json`. Merge/sort/dedup the four IDs into `%USERPROFILE%\.claude\.mcp-disabled-defaults.json` `disabledMcpServers`, verify SessionStart wires `python {{USER_HOME}}/.claude/hooks/mcp-defaults/enforce-mcp-defaults.py`, and pre-seed the four IDs into each known project's effective disabled list while Claude is closed. After restart, prove for one existing and one new project that `/mcp` reports all four disabled and no companion child process spawned; then enable one at a time in an authorized test project, MCP `initialize` + `tools/list`, assert the exact count, disable, restart before the next.
