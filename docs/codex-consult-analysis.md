# codex_consult MCP Server & PromptBridge Consultation System -- Analysis Report

**Date**: 2026-04-04
**Scope**: Full investigation of the codex-orchestrator MCP server, PromptBridge talk lane, session management, model selection, and Agentify integration.

---

## 1. Current Architecture

### 1.1 Entry Point Chain

The MCP server entry point is a one-line re-export:

- `~/.codex/promptbridge-runtime/mcp-server.mjs` (line 1) -- imports the real server at:
- `~/.codex/promptbridge-runtime/tools/mcp/codex-orchestrator/src/mcp-server.mjs`

### 1.2 Tool Registration

The MCP server registers three families of tools:

| Family | Registration Source | Tools |
|---|---|---|
| Orchestration tools | `mcp-server.mjs` lines 53-64 | `codex_consult`, `codex_brainstorm`, `codex_review`, `codex_discuss`, `codex_coordinate`, `codex_curate` |
| Codex management tools | `register-management-tools.mjs` | `codex_account_read`, `codex_model_list`, `codex_config_read`, `codex_feature_list`, `codex_mcp_status`, `codex_thread_name_set` |
| Manager tools | `manager/register-tools.mjs` | `manager_workspace_bind`, `manager_thread_metadata_set`, `manager_route_read`, `manager_route_write`, `manager_health_read`, `manager_health_record` |
| PromptBridge talk tools | `register-tools.mjs` (talk lane) | `promptbridge_query`/`agentify_query`, `promptbridge_status`/`agentify_status`, `promptbridge_session_configure`, etc. (18 base names x 2 prefixes = 36 tools) |

### 1.3 Two-Lane Architecture

The system has two execution lanes:

- **Lane B (PromptBridge/Agentify Desktop)**: Routes queries through a local Electron-based browser automation layer that drives the ChatGPT web UI. Used as the primary lane for `codex_consult`.
- **Lane A (Codex CLI exec)**: Falls back to spawning `codex exec --ephemeral --json` subprocesses. Used for all other orchestration tools (`codex_brainstorm`, `codex_review`, etc.) and as a fallback when Lane B fails.

### 1.4 Orchestration Flow for `codex_consult`

1. `buildHandler()` in `mcp-server.mjs` (line 27) receives the call
2. Loads config from `promptbridge-orchestration.toml`
3. Calls `runCodexOrchestration()` in `codex-orchestration.mjs` (line 377)
4. For `codex_consult` specifically (line 392): tries PromptBridge first via `defaultPromptbridgeConsult()`
5. On PromptBridge failure, falls back to `runCodexExec()` (Lane A) and wraps result with `laneAFallbackFrom()`

### 1.5 Session & State Persistence

- **PromptBridge Desktop state**: `~/.promptbridge-desktop/` (state.json, token.txt, settings.json)
- **Manager SQLite database**: `~/.codex/promptbridge/manager.sqlite` with tables for workspaces, thread_metadata, routes, health_events
- **Orchestration config**: `~/.codex/promptbridge-orchestration.toml`

---

## 2. Identified Issues

### Issue 1: Model Selection is Non-Authoritative and Effectively Ignored

**Files**: `codex-orchestration.mjs` lines 285-298, `register-tools.mjs` lines 52-72

The `configurePromptbridgeSession()` function (codex-orchestration.mjs:285) sends a model hint to PromptBridge with `confirmModelHintNotAuthoritative: true`. This means:

```javascript
body: {
  key,
  expectedVendorId: 'chatgpt',
  modelHint: requestedModel,
  confirmModelHintNotAuthoritative: true  // <-- The hint is advisory only
}
```

The system explicitly acknowledges that **model hints do not actually switch the backend model**. The `session_configure` tool description (register-tools.mjs:277) confirms: "Model hints remain non-authoritative and require explicit confirmation." There is no code anywhere that actually switches the ChatGPT model in the web UI -- the "modelHint" is metadata tagging only.

For Lane A (Codex CLI), the model is passed via `-m` flag to `codex exec` (codex.mjs:83), which does work. But the config hardcodes `gpt-5.4` as the default (codex-orchestration.mjs:30), and no profile in the TOML overrides this, so every Codex exec call uses the same model regardless of task type.

**Impact**: The `model` parameter on `codex_consult` is misleading. Lane B ignores it entirely. Lane A always uses the same model.

### Issue 2: Session Continuity is Broken -- Every Codex Exec is Ephemeral

**File**: `codex-orchestration.mjs` lines 392-456, `codex.mjs` lines 66-161

Every orchestration call passes `ephemeral: true` to `runCodexExec()`:

```javascript
const execResult = await runCodexExecImpl({
  workspaceDir,
  prompt: participantPrompt,
  ephemeral: true,        // <-- Always ephemeral
  skipGitRepoCheck: true,
  model: resolved.model,
  configOverrides: configOverrideArgs(resolved.reasoningEffort)
});
```

In `codex.mjs` line 81-89, ephemeral mode explicitly prevents session reuse:

```javascript
if (ephemeral) args.push('--ephemeral');
// ...
if (!ephemeral && sessionId) args.push('resume', sessionId);
```

The `sessionId` parameter exists in `runCodexExec()` but is never passed by any orchestration caller. The session ID extracted from Codex output (lines 114-117) is captured but only returned -- never stored for future reuse.

**Impact**: Every consultation is a fresh, isolated session. There is no mechanism to continue a conversation about the same project or topic, and no mechanism to switch sessions when the topic changes. The manager SQLite store has `thread_metadata` and `routes` tables that could support this, but they are never queried during orchestration.

### Issue 3: No Session Routing Logic Exists

**Files**: `manager/store.mjs`, `manager/register-tools.mjs`, `codex-orchestration.mjs`

The manager store has tables for:
- `workspaces` -- workspace path to alias mapping
- `thread_metadata` -- thread ID to workspace, label, tags, pinned state
- `routes` -- arbitrary key-value routing rules

The `manager_route_read` and `manager_route_write` tools expose this, but **no orchestration code reads from these tables**. The routing system is infrastructure without consumers. The `runCodexOrchestration()` function has no concept of "find the right session for this workspace" or "switch session when topic changes."

**Impact**: The session management database exists but is dead code from the orchestration perspective. A caller could manually write routes and thread metadata, but the orchestration tools never consult them.

### Issue 4: PromptBridge Desktop Launch is Fragile

**File**: `mcp-lib.mjs` lines 145-311

The `ensureDesktopRunning()` function has multiple fragility points:

1. **Launcher detection is order-dependent but not existence-checked** (lines 148-161): `detectInstalledDesktopLauncher()` returns the first candidate path without checking if the file exists:
   ```javascript
   for (const candidate of candidates) {
     return { command: candidate, args: [] };  // Returns first candidate, no existence check
   }
   ```

2. **Poll-based readiness check** (lines 299-310): After spawning, it polls every 300ms for up to `timeoutMs` (default 30s). If the desktop app is slow to start or the state file is slow to write, this silently times out with `desktop_start_timeout`.

3. **Server ID mismatch handling** (lines 183-186): If a stale `state.json` references a dead server ID while a new instance is starting, `validateConn` rejects the connection. The code then spawns a new instance, but there is no cleanup of the stale state file.

4. **No health check retry after spawn** (lines 250-251): If the initial `validateConn` after `loadConnection` fails with a transient error (not just null conn), it falls through to spawn a new instance even if one is already running but momentarily unhealthy.

**Impact**: Starting PromptBridge Desktop from `codex_consult` is unreliable. Race conditions between stale state files and new processes, lack of file existence checks on launcher paths, and aggressive timeout behavior all contribute.

### Issue 5: No Agentify Health Check Before Consultation

**File**: `codex-orchestration.mjs` lines 300-336

The `defaultPromptbridgeConsult()` function calls:
1. `ensureDesktopRunning()` -- waits for desktop to be reachable
2. `/ensure-ready` -- waits for ChatGPT textarea to be visible
3. `configurePromptbridgeSession()` -- sets non-authoritative model hint
4. `/query` -- sends the prompt

There is no explicit health check between steps 1 and 2. The `/ensure-ready` endpoint implicitly validates readiness, but:
- There is no check that the Agentify automation layer is functional (page loaded, no CAPTCHA, correct account)
- There is no check that the session matches the expected workspace/project
- If `/ensure-ready` succeeds but the session is on the wrong model or in the wrong chat, the query proceeds anyway

**Impact**: Queries can be sent to stale or wrong sessions without detection.

### Issue 6: Duplicate Code Between Main and Local-Override Orchestration Files

**Files**:
- `tools/mcp/codex-orchestrator/src/codex-orchestration.mjs` (544 lines)
- `tools/mcp/agent-lanes-codex/local-overrides/codex-orchestration.mjs` (407 lines)

The local-overrides file is a near-complete copy of the main orchestration module but with key differences:

1. **Missing PromptBridge consult lane**: The local-overrides version of `runCodexOrchestration()` (line 308) has no special `codex_consult` handling -- it treats all tools the same way via Codex exec. The main version (line 392) has the Lane B try/fallback logic.
2. **Missing `reasoningEffort` in prompts**: The local-overrides `buildStructuredPrompt()` (line 235) does not include the `reasoningEffort` parameter that the main version does (line 242).
3. **Missing `parseConsultationJsonText` helper**: The main version has a dedicated helper for extracting JSON from text that may contain markdown fencing. The local-overrides version inlines a simpler extraction in `defaultPromptbridgeCurate()`.

**Impact**: Behavioral drift between the two copies. If someone fixes a bug in one, the other remains broken. It is unclear which one is actually loaded at runtime.

### Issue 7: `codex_consult` Treats PromptBridge Failure as Silent Fallback

**File**: `codex-orchestration.mjs` lines 392-456

When PromptBridge fails, the code catches the error and falls back to Lane A:

```javascript
try {
  const promptbridgeResult = await promptbridgeConsultImpl({ ... });
  // ... return PromptBridge result
} catch (promptbridgeError) {
  // Falls back to codex exec
  const execResult = await runCodexExecImpl({ ... });
  // ...
  return {
    ...laneAFallbackFrom(normalized, promptbridgeError),
    // ...
  };
}
```

The fallback appends a risk note ("PromptBridge lane unavailable: ...") but does not log, record a health event, or notify the caller in any prominent way. The `fallback_to_lane_a: true` flag is buried in the result metadata.

**Impact**: The caller may not realize they are getting Lane A results instead of Lane B. No health event is recorded for monitoring, so repeated failures are invisible.

### Issue 8: No Workspace-Aware Session Selection for PromptBridge

**File**: `codex-orchestration.mjs` lines 300-336

The `defaultPromptbridgeConsult()` function always uses the same `key` for the PromptBridge session:

```javascript
async function defaultPromptbridgeConsult({
  prompt,
  key = 'promptbridge-consult',  // <-- Always the same key
  // ...
}) {
```

The consult profile in `promptbridge-orchestration.toml` line 18 also hardcodes `promptbridge_key = "promptbridge-consult"`. This means every consultation, regardless of workspace or topic, uses the same browser tab/session.

**Impact**: Switching between projects does not create a new session. Asking about a different topic reuses a conversation that may have stale context. There is no mechanism to create workspace-specific sessions.

### Issue 9: Tab/Session Key is Not Derived from Workspace

**Files**: `register-tools.mjs` lines 26-32, `codex-orchestration.mjs` lines 300-306

The `resolveAutomationTarget()` function defaults to the static key `promptbridge-consult`:

```javascript
function resolveAutomationTarget({ tabId, key }) {
  if (tabId && key) return { tabId, key };
  if (tabId) return { tabId };
  if (key) return { key };
  return { key: DEFAULT_AUTOMATION_KEY };  // Always 'promptbridge-consult'
}
```

The `workspaceDir` parameter is available in the orchestration call chain but is never used to derive a session key. A natural mapping would be `key = sanitize(workspaceDir)` or `key = routeLookup(workspaceDir)`.

**Impact**: All workspaces share one session, preventing proper context isolation.

---

## 3. Session Management Gaps

| Gap | Description | Where |
|---|---|---|
| No session reuse | Every Codex exec is `ephemeral: true` | `codex-orchestration.mjs:427-430` |
| No session-per-workspace | PromptBridge always uses `key = 'promptbridge-consult'` | `codex-orchestration.mjs:301` |
| No session switching | No code reads routes or thread metadata before dispatching | `codex-orchestration.mjs:377-544` |
| Dead routing tables | `routes` and `thread_metadata` in SQLite are never queried by orchestration | `manager/store.mjs` |
| No session cleanup | Old sessions are never closed when topic changes | Nowhere implemented |
| No conversation threading | The `sessionId` extracted from Codex output is captured but never stored or reused | `codex.mjs:114-117` |

---

## 4. Model Selection Gaps

| Gap | Description | Where |
|---|---|---|
| Non-authoritative hints | PromptBridge model hints are explicitly advisory-only | `codex-orchestration.mjs:289-293` |
| No actual model switching | No code manipulates the ChatGPT web UI model selector | Nowhere implemented |
| Hardcoded default model | `gpt-5.4` is hardcoded in both TOML and JS defaults | `codex-orchestration.mjs:30`, TOML line 6 |
| No per-profile model override | No profile in the TOML specifies a `model` key | `promptbridge-orchestration.toml` |
| Model list unused | `codex_model_list` tool exists but is never called by orchestration to validate model availability | `register-management-tools.mjs:32-41` |

---

## 5. Agentify Integration Gaps

| Gap | Description | Where |
|---|---|---|
| No launcher existence check | `detectInstalledDesktopLauncher()` returns first candidate without checking file exists | `mcp-lib.mjs:148-161` |
| No pre-query health check | No Agentify health/status call before sending consultation query | `codex-orchestration.mjs:300-336` |
| Silent fallback on Agentify failure | Lane A fallback does not record health events | `codex-orchestration.mjs:419-455` |
| No CAPTCHA detection before query | `/ensure-ready` waits for textarea but does not verify the session is authenticated | `codex-orchestration.mjs:309-315` |
| Stale state file race | Old `state.json` can cause connection to wrong/dead server | `mcp-lib.mjs:241-249` |
| Legacy dir migration during hot path | `loadConnection()` may trigger a filesystem copy during a consultation request | `mcp-lib.mjs:96-105` |

---

## 6. Specific Improvement Recommendations

### R1: Implement Workspace-Aware Session Keys

In `codex-orchestration.mjs`, derive the PromptBridge session key from the workspace directory:

```javascript
// Before calling defaultPromptbridgeConsult:
const sessionKey = `pb-${path.basename(workspaceDir)}`;
```

This ensures different projects get different ChatGPT sessions.

### R2: Add Session Store Lookup Before Dispatch

Before spawning a new Codex exec or PromptBridge query, check the manager SQLite for an existing session:

```javascript
const existingRoute = await readRoute({ db, routeKey: `session:${workspaceDir}` });
if (existingRoute?.value?.sessionId) {
  // Resume existing session instead of ephemeral
}
```

### R3: Store Session IDs After Successful Consultation

After `runCodexExec` returns a `sessionId`, persist it:

```javascript
if (result.sessionId) {
  await writeRoute({ codexHome, routeKey: `session:${workspaceDir}`, value: { sessionId: result.sessionId, toolName, timestamp: Date.now() } });
}
```

### R4: Remove Hardcoded `ephemeral: true` for `codex_consult`

For consultation (not brainstorm/review), allow session reuse:

```javascript
const ephemeral = toolName !== 'codex_consult';
const execResult = await runCodexExecImpl({
  workspaceDir,
  prompt: participantPrompt,
  ephemeral,
  sessionId: existingRoute?.value?.sessionId || null,
  // ...
});
```

### R5: Record Health Events on PromptBridge Fallback

In the `catch` block of the `codex_consult` Lane B try (codex-orchestration.mjs:419):

```javascript
catch (promptbridgeError) {
  await appendHealthEvent({
    codexHome,
    source: 'codex_consult',
    severity: 'warning',
    message: `PromptBridge fallback to Lane A: ${promptbridgeError.message}`,
    details: { toolName, workspaceDir }
  });
  // ... existing fallback code
}
```

### R6: Add Launcher Existence Check

In `mcp-lib.mjs` `detectInstalledDesktopLauncher()`, check file existence before returning:

```javascript
for (const candidate of candidates) {
  if (await fileExists(candidate)) {
    return { command: candidate, args: [] };
  }
}
return null;
```

Note: This requires making the function async.

### R7: Consolidate Duplicate Orchestration Files

The local-overrides copy at `tools/mcp/agent-lanes-codex/local-overrides/codex-orchestration.mjs` should either:
- Be deleted and import from the canonical source, or
- Be generated from the canonical source with explicit differences documented

### R8: Add Pre-Query Session Validation

Before sending a PromptBridge query, call `/session-state` to verify:
- The session is authenticated
- The session is on the expected model (if model selection becomes authoritative)
- The session is not blocked by CAPTCHA

### R9: Implement Topic-Change Detection

Use the manager routes table to track the last prompt topic per workspace. When the new prompt's topic diverges significantly (could be a simple keyword hash or caller-provided tag), create a new session:

```javascript
const currentRoute = await readRoute({ db, routeKey: `topic:${workspaceDir}` });
if (currentRoute && topicChanged(currentRoute.value.lastTopic, prompt)) {
  // Close old session, create new one
  await closeSession(currentRoute.value.sessionKey);
  sessionKey = `pb-${workspaceDir}-${Date.now()}`;
}
```

### R10: Make Model Selection Authoritative for Lane A

For Codex CLI (Lane A), the `-m` flag actually works. Profiles should specify per-tool models in the TOML:

```toml
[profiles.consult]
model = "o3-pro"

[profiles.brainstorm]
model = "gpt-5.4"

[profiles.review]
model = "o3-pro"
```

---

## 7. Summary of Root Causes

The reported inconsistencies trace to three fundamental design gaps:

1. **No session lifecycle management**: Sessions are always ephemeral (Codex CLI) or always reuse a single static key (PromptBridge). The infrastructure for session tracking exists (SQLite tables, route tools) but is never wired into the orchestration dispatch path.

2. **Model selection is advisory-only**: The PromptBridge lane cannot programmatically switch ChatGPT models -- it can only tag a "hint." The Codex CLI lane could use different models per profile, but the config hardcodes a single model for all profiles.

3. **Agentify launch-and-check is best-effort**: The desktop launcher detection does not verify file existence, health checks are poll-based with no retry backoff, stale state files can cause routing to dead processes, and failures are silently absorbed as Lane A fallbacks.

---

## Appendix: File Inventory

| File | Role | Lines |
|---|---|---|
| `~/.codex/promptbridge-runtime/mcp-server.mjs` | Entry point (re-export) | 1 |
| `~/.codex/promptbridge-runtime/tools/mcp/codex-orchestrator/src/mcp-server.mjs` | MCP server, tool registration | 93 |
| `~/.codex/promptbridge-runtime/tools/mcp/codex-orchestrator/src/codex-orchestration.mjs` | Core orchestration logic (Lane A + Lane B) | 544 |
| `~/.codex/promptbridge-runtime/tools/mcp/codex-orchestrator/src/orchestrator/codex.mjs` | Codex CLI exec runner | 161 |
| `~/.codex/promptbridge-runtime/tools/mcp/codex-orchestrator/src/app-server-client.mjs` | Codex app-server JSON-RPC client | 131 |
| `~/.codex/promptbridge-runtime/tools/mcp/codex-orchestrator/src/register-management-tools.mjs` | Management tool registration | 123 |
| `~/.codex/promptbridge-runtime/tools/mcp/codex-orchestrator/src/manager/register-tools.mjs` | Manager tool registration | 148 |
| `~/.codex/promptbridge-runtime/tools/mcp/codex-orchestrator/src/manager/store.mjs` | SQLite session/routing store | 148 |
| `~/.codex/promptbridge-runtime/tools/web/promptbridge-talk-lane/src/register-tools.mjs` | PromptBridge talk-lane tool registration | 513 |
| `~/.codex/promptbridge-runtime/tools/web/promptbridge-talk-lane/src/mcp-lib.mjs` | Desktop launch, connection, HTTP helpers | 311 |
| `~/.codex/promptbridge-runtime/tools/web/promptbridge-talk-lane/src/state.mjs` | State directory management | 150 |
| `~/.codex/promptbridge-runtime/tools/mcp/agent-lanes-codex/local-overrides/codex-orchestration.mjs` | Duplicate orchestration (Lane A only) | 407 |
| `~/.codex/promptbridge-runtime/tools/mcp/codex-orchestrator/integrations/codex/bootstrap.mjs` | Bootstrap installer | 400+ |
| `~/.codex/promptbridge-runtime/tools/mcp/codex-orchestrator/integrations/codex/probe.mjs` | Stack probe/self-test | 400+ |
| `~/.codex/promptbridge-runtime/tools/mcp/codex-orchestrator/integrations/codex/cli.mjs` | CLI entry for install/status/probe | 151 |
| `~/.codex/promptbridge-orchestration.toml` | Orchestration config | 90 |
| `~/.codex/CONSULTATION_WORKFLOW.md` | Workflow documentation | 43 |
| `~/.codex/skills/promptbridge-codex-consult/SKILL.md` | Skill definition | 19 |
| `~/.codex/skills/codex-local-consult/SKILL.md` | Local consult skill definition | 15 |
