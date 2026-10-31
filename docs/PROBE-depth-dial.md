# PROBE — G-7a: CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH functional probe — COMPLETE

- Date: 2026-09-22 (runs 20:15–20:21 local)
- Build under test: Claude Code 2.1.277 — **CONFIRMED** (`claude --version` → `2.1.277 (Claude Code)`; native install `C:\Users\Prekzursil\.local\bin\claude.exe`, 237,195,936 bytes; sibling versions 2.1.273/2.1.274 in `C:\Users\Prekzursil\.local\share\claude\versions\`)
- Program: workflow-delegation grill (owner GO 2026-09-22); decision log: `C:\Users\Prekzursil\.agents\GRILL-DECISIONS_workflow-delegation_2026-09-22.md` (G-7=a verify+adopt, G-4=5 native max + RAM gate control, G-12=nested=fleet RAM pre-flight)
- Probe author: workflow subagent (G-7a lane). Sentinel: this file reached COMPLETE; all sections carry measurements.

## 0. Verdict summary

| Question | Verdict | Confidence |
|---|---|---|
| Does the env var exist in 2.1.277? | **YES** — 5 string occurrences in binary | high (binary grep) |
| Read precedence | env var → GrowthBook flag `tengu_hazel_trellis` → fallback default `3` | high (minified source) |
| Does cap=1 block a depth-2 spawn? | **YES** — empirically refused | high (3 independent signals) |
| Does cap=1 still allow main→depth-1? | **YES** — LEVEL1-OK returned | high (2 independent signals) |
| Enforcement mechanism observed | **Tool-catalog omission** (capped subagent has NO spawn tool, so cannot even attempt); runtime error string exists in binary as backstop, NOT observed live | high for omission (hooklog+transcript+model report), UNVERIFIED-live for the error path |
| Subagent-vs-main signal in hook stdin | **`agent_id` (+ `agent_type`) present in subagent-context entries; absent in main. `session_id`/`transcript_path` are ALWAYS the main session's** | high (captured payloads, both states) |
| Publicly documented? | NO — absent from code.claude.com/docs/en/settings snapshot (other CLAUDE_CODE_* vars present there; detector control passed) | high for that page; UNVERIFIED for other docs pages |

**G-4 FLAG (load-bearing for the program):** owner decision G-4 = "5 — native max … No env set; document."
Measured: with env UNSET the effective cap is the GrowthBook value or the hardcoded fallback **3** (binary:
`var o=3,_="tengu_hazel_trellis"`), and empirically ≥2 (Test A spawned depth 2 fine). **"No env set" therefore
yields 3 nesting levels, NOT 5.** To actually run at depth 5 the env var must be set to 5 (or GrowthBook must
deliver it). This is a discrepancy the T0/`delegate()` phase must resolve (owner decision needed: accept 3, or
set 5 explicitly per-workflow after RAM pre-flight). [high confidence on mechanism; the live GrowthBook value
is unknowable statically — settling experiment in §8]

## 1. Method

1. Static: `claude --version`; `claude --help` scan; `grep -a` string-search of `claude.exe` (bun-native, JS embedded).
2. Empirical: nested `claude -p` runs, isolated via `CLAUDE_CONFIG_DIR` → scratch copy (settings + creds copy),
   `--strict-mcp-config`, `--settings` scratch file. Isolation note: `--settings` is ADDITIVE per `claude --help`
   and cannot remove user-scope hooks — `CLAUDE_CONFIG_DIR` relocation is what actually prevents estate
   hooks/plugins/user-settings from loading. Prompts delivered via stdin files (no shell quoting hazards).
3. Hook capture: PreToolUse dump-hook in the isolated config's settings.json appends raw stdin JSONL per run.
4. RAM gate (G-12): free-RAM before each spawn; sequential only; no fleet.

## 2. Static evidence

### 2.1 Version — CONFIRMED 2.1.277
`claude --version` → `2.1.277 (Claude Code)`.

### 2.2 CLI flags — no depth flag exists
Help scan (depth|spawn|nest|subagent|mcp-config|settings): only `--forward-subagent-text` (unrelated).
`--strict-mcp-config`, `--settings <file-or-json>` present. **Dial is env-var-only.** [high]

### 2.3 Binary string evidence — read logic and refusal site (verbatim minified)

```js
var o=3,_="tengu_hazel_trellis";
function fS(){let n=a.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH;if(n!==void 0)return n;
  let t=ps();if(t.maxSubagentSpawnDepthFromGrowthBook===void 0){ ...getFeatureValue_CACHED_MAY_BE_STALE(_,o)... }
```

```js
wt=Cc(e.agentContext),bt=fS();
if(wt>=bt)throw m("subagent_launch","subagent_depth_cap"),
  yve.of(e.session).recordRefused("depth_limit"),
  new K(`Subagent nesting limit reached (depth ${wt} of ${bt}). Complete this task directly using your
   tools instead of spawning another agent. If the user explicitly requested deeper nesting, ask them
   to raise CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH.`);
```

Semantics: refusal when `currentAgentContextDepth >= cap`. [high; cross-checked empirically — B/C boundary matches]

### 2.4 Sibling dials / related identifiers
- `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` — exists, own refusal text ("Do not retry… increase …"). Directly
  useful to G-12 (native concurrency cap for RAM gating).
- `subagent_nested_teammate` — "Teammates cannot spawn other teammates — the team roster is flat. To spawn a
  subagent instead, omit the `name` parameter." (TeamCreate/SendMessage roster flat; nesting is Agent-tool only.)
- `subagent_spawner_stop_pending` — stopped agent cannot launch agents (`e.agentId!==void 0&&iI(e.agentId)`).
- Hook-adjacent: `parentSessionId`, `agentType`, `agentTypesInvokedThisSession`, hook matcher `subagentType`
  ("a hook's subagentType '…' names no agent this call can dispatch"), `subagent_type_denied` ("Agent type '…'
  has been denied by permission rule '…'") — G-8b restricted agentTypes has native support.

### 2.5 Public docs
Absent from `https://code.claude.com/docs/en/settings` snapshot (fetched 2026-09-22; page contains other
`CLAUDE_CODE_*` entries, e.g. `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST` — detector control). UNVERIFIED whether
another docs page mentions it. Binary remains SSOT.

## 3. Empirical results

RAM pre-flight (G-12): freeRAM measured before each spawn: **1.81 GB** (pre-rig) → **3.42** (pre-A) →
**2.33** (pre-B) → **2.93 GB** (pre-C) of 31.63 GB total. Below fleet thresholds, but spawns were
registry-free single processes (strict-mcp-config + isolated config dir), strictly sequential — the
task-sanctioned pattern. No freezes, no reaper needed. [measured]

| Run | Env var | Chain attempted | Outcome | Independent signals |
|---|---|---|---|---|
| smoke | unset | — | `SMOKE-OK`, exit 0 | stdout |
| A control | unset | main→L2→L3 | ALL spawned; L3 replied `LEVEL3-OK`; default cap ≥2 | hooklog: 2 entries (2nd carries `agent_id`); session dir has L2+L3 agent files; metas `spawnDepth:1` and `spawnDepth:2` (`parentAgentId` chain); `LEVEL3-OK` grep-hit in main transcript |
| B treatment | `=1` | main→L2→L3 | L2 spawned; **L3 never spawned** — L2 reported the launch tool absent from its catalog ("no Task and no ToolSearch to surface one") and refused to fabricate L3 output | hooklog: exactly 1 entry (main only — L2 never called Agent); session dir has ONLY the L2 agent file (meta `spawnDepth:1`); `nesting limit` string absent from ALL transcripts |
| C boundary | `=1` | main→L1 | `MAIN-REPORT:LEVEL1-OK`, exit 0 — main (depth 0) still spawns one level | hooklog: 1 entry (main Agent call); L1 meta `spawnDepth:1` |

Conclusion: **cap semantics = max subagent nesting depth below main; refusal when current depth ≥ cap.**
Enforcement observed as catalog gating (the capped context never receives the spawn tool — stronger than a
runtime error: no attempt, no PreToolUse hook fires for it). The binary's runtime error is the backstop path
(not exercised in these runs). [high]

### 3.1 Test-A behavioral finding (delegation program input)
The L3 completion notification surfaced in the MAIN session, not back in L2 (which had already ended its turn
awaiting it) — L2's `L2-REPORT:` line was never produced by L2 itself; MAIN reconstructed the chain from the
notification. Meta confirms `requestShape:"background"`. Implication: nested chains route leaf results to the
ROOT, not the spawning parent — `delegate()` must aggregate at root or resume via SendMessage. [likely —
single run, model-reported routing + one consistent meta field; settling experiment: repeat A once and watch
notification addressing]

## 4. Subagent-vs-main hook signal (the G-3b/G-2c input)

Captured PreToolUse hook stdin keysets (both states measured, Test A):

- MAIN context: `cwd, effort, hook_event_name, permission_mode, prompt_id, session_id, tool_input, tool_name, tool_use_id, transcript_path`
- SUBAGENT context (L2): same keyset **plus `agent_id`** (e.g. `a56f73158ab7e18ea`, 16 hex) **and `agent_type`** (e.g. `general-purpose`)

Critical negatives:
- `session_id` is ALWAYS the root session id (subagent shares it) — session_id does NOT distinguish.
- `transcript_path` is ALWAYS the ROOT transcript (`…/<session_id>.jsonl`) — **the `\subagents\` path does NOT
  appear in hook stdin**, so the estate's historical transcript-path heuristic FAILS for hook payload
  discrimination (it remains valid for finding subagent transcript FILES on disk).
- No `spawnDepth`, no env marker in the payload.

**Recommended discriminator for the Hook phase: `payload.agent_id !== undefined` → subagent context**
(plus `payload.agent_type` for type-restricted rules). Depth, when needed, is readable from the sidecar:
`<dirname(transcript_path)>/<session_id>/subagents/agent-<agent_id>.meta.json` → `spawnDepth`, `parentAgentId`,
`agentType`, `toolUseId`, `requestShape`, `requestNonInteractive`. UNVERIFIED whether meta.json exists DURING
execution vs only at completion (settling experiment: hook reads own sidecar live). [high on keysets]

Other hook-phase facts measured:
- The spawn tool is named **`Agent`** in hook payloads this build (`tool_name:"Agent"`), NOT "Task" — matchers
  and fleet-lint (G-13) must audit `Agent` (keep `Task` as legacy alias).
- Subagent transcripts live at `<project>/<session_id>/subagents/agent-<agent_id>.jsonl` (+`.meta.json`).

## 5. Isolation recipe receipt (reusable for T0 / G-1c)

`CLAUDE_CONFIG_DIR` → scratch dir containing `settings.json` (+ a copy of `~/.claude/.credentials.json`
for auth) + `--strict-mcp-config` + `--settings <scratch>` ⇒ zero MCP servers, zero estate hooks, zero
plugins, no `.claude.json` state pollution (state lands in scratch). Child inherits gateway env if set
(observed: `ANTHROPIC_MODEL=glm-5.3[1m]` overrode `--model`; harmless for harness-mechanics probes).
The credentials copy was **deleted after the runs** (transient duplicate created and shredded by this probe;
original untouched — NEVER-ROTATE respected).

## 6. Reproduction

Scratch: `C:\Users\Prekzursil\.agents\docs\probe-g7a-scratch\` (cfg/, out/, hooklog/, prompts, parser).
Canonical run shape (bash):

```
cat prompt-chain.txt | CLAUDE_CONFIG_DIR='<scratch>\cfg' PROBE_HOOK_LOG='<scratch>\hooklog\testX.jsonl' \
  [CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1] \
  /c/Users/Prekzursil/.local/bin/claude -p --strict-mcp-config --settings '<scratch>\cfg\settings.json' --max-turns 12
```

## 7. Reconcile items (VCS hygiene)

- `PROBE-depth-dial.md` mirrored to `C:\Users\Prekzursil\source\agent-skills-toolchain\docs\PROBE-depth-dial.md`
  + evidence pack (hooklogs, prompts, parser, settings, hook script) under
  `docs\probe-g7a-evidence\`. **NOT committed — orchestrator commits (per task NEVER rule).**
- Scratch transcripts (cfg/projects/) stay live-only (runtime data, not repo material).

## 8. Residual UNVERIFIED items + settling experiments

1. **Exact live default cap when env unset** (GrowthBook `tengu_hazel_trellis` may override the `3` fallback).
   Settling experiment: 4-level chain (main→L2→L3→L4) with env unset; if L4 refused, message reads
   "depth 3 of 3" → default is 3.
2. **Runtime refusal path** ("Subagent nesting limit reached (depth X of Y)") never fired live (catalog gating
   preempts it). Settling experiment: force the path where a capped context still holds the tool (e.g.
   teammate spawn, or mid-session env change via a wrapper that mutates env between spawns).
3. **meta.json availability during agent execution** (needed if hooks read spawnDepth live). Settling
   experiment: dump-hook also stats its own sidecar and records existence.
4. Test-A notification-routing finding is single-run — repeat once before encoding in delegate().
