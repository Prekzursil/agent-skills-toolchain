---
name: delegate-primitive
description: 'Use when delegating nested work from a workflow or orchestrator session
  - spawning subagents / agents-as-tool with governance: per-level model routing,
  depth-2 provenance stamps, budget.spent() checkpoints, RAM pre-flight gate, and
  the standing claude-code-mcp ban. Triggers: delegate(), nested delegation, agent-as-tool,
  spawn a subagent from a workflow, delegation governance, RAM gate before a nested
  fleet.'
permalink: dqverify-repo-20261013/skills/delegate-primitive/skill
---

# delegate-primitive - the T0 governed delegation pattern

Status: BUILT 2026-09-22 (wf_c8e4c79c, G-1c program per owner grill decisions).
Decision record: `C:\Users\Prekzursil\.agents\GRILL-DECISIONS_workflow-delegation_2026-09-22.md` (READ IT for the adjudications; this skill encodes G-1c/G-11/G-12/G-13b).

**delegate() is NOT a runtime global.** It is this estate's name for a paste-in
composition of native primitives - the Workflow `agent()` / `pipeline()` globals,
the Task tool's `agentType` (restricted `reader`/`writer` agents), the
`nested_ram_gate.ps1` pre-flight - plus the enforced claude-code-mcp deny. It
replaces emergent nested-Claude delegation via `claude-code-mcp`, which is
**archived upstream since 2026-05-15 and bypass-permissions-by-default** - the
exact shape behind incident wf_c8e4c79c-1c8 (2/20 agents, 12 nested claude_code
calls, prompt-only guards).

---

## 0. Standing PRE line (binds before ANY delegation)

> **NEVER call `mcp__claude-code-mcp__*` - any tool with that prefix, in any
> session, workflow, or nested agent.** Estate decision G-3 (flat deny now,
> hook-gated subagent-only deny). claude-code-mcp is dead upstream and
> bypass-permissions-by-default. Nested Claude delegation goes through native
> primitives only (this skill). The G-10b fork+container is the single sanctioned
> exotic lane and is owner-directed, separate from this pattern.
>
> **Any `claude` CLI test spawn MUST use `--strict-mcp-config` with an empty/temp
> `--settings` file.** A bare spawn instantiates the ~80-server global MCP
> registry (~10-25 GB commit on a 31.6 GB box) and freezes the machine - the
> measured freeze pattern behind G-99 / `rules/common/mcp-process-hygiene.md`.

Put this PRE line verbatim into every delegation prompt that can spawn nested
agents (see the worked example's `PREAMBLE`).

## 1. Convention vs enforced (honesty table)

| Mechanism | Status | Enforced by |
|---|---|---|
| claude-code-mcp deny | ENFORCED | user-scope settings deny + hook (G-3a+b, G-2c/G-3b - hook build is a queued unit) |
| RAM pre-flight before a nested fleet | ENFORCED by contract | `nested_ram_gate.ps1` exit code - the CALLER must require exit 0 |
| `workflow()` nesting depth (max 1 level) | ENFORCED (runtime throws) | runtime: "Nesting is one level only: workflow() inside a child throws" (`docs/workflow-sota/RUNTIME-API-DUMP.txt` L53) |
| budget hard ceiling | ENFORCED (runtime throws) | `budget` global: once `spent() >= total`, further `agent()` calls throw (L52) |
| determinism bans (`Date.now` / `Math.random` / argless `new Date`) | ENFORCED (throw) | workflow sandbox (L59) |
| per-level model routing | CONVENTION | author discipline + this skill's templates (G-11 doctrine) |
| depth-2 provenance stamps | CONVENTION + lint | schema field + fan-in gate here; the transcript fleet-lint is the mechanical half (G-13b) |
| mail markers / lease hygiene | CONVENTION | agent-mail tool contract (section 7) |
| depth cap for Task nesting | ENFORCED (env now set) | `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=5` in settings env (2026-09-22, post G-4 re-adjudication). Probe G-7a COMPLETE (PROBE-depth-dial.md): unset env = GrowthBook `tengu_hazel_trellis` or fallback 3, NOT 5; refusal when current depth >= cap; enforced via tool-catalog omission (capped context never receives the spawn tool - no attempt, no PreToolUse fires); runtime error string `Subagent nesting limit reached (depth X of Y)` is the backstop. Concurrency sibling dial: section 10 |

## 2. Per-level model routing (G-11)

| level | role | model | effort |
|---|---|---|---|
| 0 | orchestrator (workflow script / session) | **inherit the session model - set NOTHING** | session |
| 1 | substantive subagents (analysis, verification, implementation) | mid model, explicit `model:` string; for verification-critical lanes OMIT `model` (inherit the session tier) | `high` |
| leaf | mechanical (grep / read / harvest / format-check) | haiku | `low` |

Grounding (all measured against the installed runtime doc, RUNTIME-API-DUMP.txt L46):

- `opts.model` is a passthrough string per call; the runtime's own advice is
  "Default to omitting it - the agent inherits the main-loop model (the resolved
  session model)... Only set it when you're highly confident a different tier
  fits the task". G-11 is exactly that confident per-level decision, pinned here.
- Known-good model strings on this build, per `skills/workflow-authoring` §1:
  `'opus'` (deepest) and `'fable'` (wide fan-out / mid tier). `'haiku'` /
  `'sonnet'` as **agent() `model:` strings are UNVERIFIED on this build** - the
  verified haiku path today is the agent-file frontmatter (below). Settling
  experiment: one `agent('ping', {model:'haiku', schema:S})` probe under
  `--strict-mcp-config` + temp `--settings`.
- **Leaf-haiku has an on-disk anchor**: `~/.claude/agents/reader.md` pins
  `model: haiku` (G-8b) - leaves reached via `agentType: 'reader'` get haiku even
  when the prompt forgets. `writer.md` OMITS model (inherits the session tier,
  G-8b) and is ownership-scoped: caller-declared root only, no git, no deletes,
  reports diffs not commits.
- effort enum: `'low' | 'medium' | 'high' | 'xhigh' | 'max'` (L46) - `'low'` for
  cheap mechanical stages, higher tiers for the hardest verify/judge stages.

## 3. Depth-2 provenance discipline (G-13b)

**Depth contract:** the delegation tree is at most 2 levels below the
orchestrator - L0 (you / the workflow script) -> L1 (substantive agent) -> leaf
(agent-as-tool inside L1, e.g. `agentType: 'reader'`). Leaves never spawn
anything. `workflow()` enforces its own one-level cap by throwing; Task-depth
beyond 2 is convention here (G-4: no env dial set).

**The stamp.** Every nested result carries one:

- `agent-claimed` - the DEFAULT. An L1 agent saying "wrote X" is a claim, not a
  receipt (fan-out contract B1: 3/3 Codex agents returned plausible digests for
  files that did not exist).
- `disk-verified` - ONLY the CALLER may set it, after an independent re-read
  (Test-Path / Read + size or completion-marker check) by the caller's own
  instrument, mechanically separate from the producer.

**The stamp travels up.** L0 reports to the user only stamps it holds: either it
re-verified itself, or an L1 returned a result already stamped `disk-verified`
by a chain in which every hop re-verified. Anything else is reported as
`agent-claimed` with the re-verification named as pending work.

Grace window: before treating an absent artifact as a lie, allow ~60s and
re-check once (transcript-flush lag under RAM pressure - verification doctrine,
`~/AGENTS.md` "disk-verified vs agent-claimed").

Schema shape (required on every delegate result):

```js
provenance: { type: 'string', enum: ['agent-claimed', 'disk-verified'] }  // REQUIRED
artifact:   { type: 'string' }   // OPTIONAL - read-only lanes never write; required[] is the FLOOR
bytes:      { type: 'integer' }  // OPTIONAL
```

## 4. Budget accounting - budget.spent() checkpoints

`budget = { total: number|null, spent(): number, remaining(): number }` - the
pool is SHARED across the main loop and all workflows, and the target is a HARD
ceiling: once `spent() >= total`, further `agent()` calls THROW (L52).
`total === null` when no target was set; `remaining()` is then `Infinity`.

Checkpoints (convention, but never skip them):

1. **Before each delegation wave:** `if (budget.total && budget.remaining() <
   WAVE_ESTIMATE) return { blocked: 'budget', ... }` - never spawn a wave you
   cannot pay for.
2. **After each phase:** `log(...)` the `[budget]` line - spent/total at every
   phase boundary is the audit trail a post-mortem reads.
3. **Guard every budget loop on `budget.total`** - unguarded, `remaining()` is
   `Infinity` and the loop runs to the 1000-agent lifetime cap.

Honest limit: an H6 timeout receipt does NOT stop spend - the dropped agent keeps
its concurrency slot and keeps spending until it dies on its own; the next
`budget.spent()` checkpoint is what surfaces it (workflow-authoring §5b).

## 5. RAM pre-flight (G-12) - nested calls count as fleet

Before ANY nested delegation wave (workflow launch, Task fan-out, nested claude
spawn), in a shell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Prekzursil\.agents\scripts\nested_ram_gate.ps1
# exit 0 = GO (or GO-under-override)
# exit 1 = GATE:FAILED-TO-RUN  (audit unreadable - fail-closed, never a pass)
# exit 2 = GATE:BLOCK          (free RAM < 8 GB after a reap attempt - do NOT launch)
```

- The gate runs `mcp_ram_audit.ps1`, reaps orphans via `reap_orphan_mcp.ps1`
  when below floor (8 GB default, `-MinFreeGB`) or over the G-99 MCP-process
  threshold (150, `-MaxMcpProcs`), re-checks, then decides.
- **`-Override` is an OWNER DIRECTIVE, not an agent convenience.** Every use
  must be recorded in the decision log (G-12). Precedent: the 2026-09-22 T0
  build wave itself ran under a recorded owner override at ~1.9 GB free.
- The workflow sandbox has NO shell - this gate cannot run inside workflow JS.
  Run it where a shell exists: (a) in the launching terminal BEFORE invoking
  Workflow (the honest pre-flight), or (b) as the first tool call of the first
  L1 agent when launching headless - that checks after one spawn has already
  happened; disclose which of the two you did.

## 6. Worked example - the delegate() composition (complete fragment)

Composes: PRE line, per-level routing, depth-2 leaves via `agentType`,
caller-side provenance upgrade, budget checkpoints, H6 timeout bound,
byte-stable preamble, `pipeline()` (no cross-stage barrier). Paste into a
workflow `.mjs` and fill `items`.

```js
// PRE-FLIGHT (launching shell - the sandbox has none):
//   powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Prekzursil\.agents\scripts\nested_ram_gate.ps1
//   exit 0 required. A non-zero exit means the wave does NOT launch.

export const meta = {
  name: 'delegate-t0-example',
  description: 'Governed depth-2 delegation: L1 agents delegate leaf reads to reader; orchestrator verifies artifacts',
  phases: [{ title: 'Delegate' }, { title: 'Verify' }],
}

// schema builder - required[] is the FLOOR, not the wishlist (workflow-authoring rule 7)
const obj = (properties, required = []) => ({
  type: 'object', additionalProperties: false, required, properties,
})
const DELEGATE_RESULT = obj({
  answer:     { type: 'string' },                                              // always fillable
  artifact:   { type: 'string' },                                              // OPTIONAL - read-only lanes never write
  bytes:      { type: 'integer' },                                             // OPTIONAL
  provenance: { type: 'string', enum: ['agent-claimed', 'disk-verified'] },    // G-13b stamp
}, ['answer', 'provenance'])
const VERIFY_RESULT = obj({
  exists:     { type: 'boolean' },
  endsMarker: { type: 'boolean' },
  provenance: { type: 'string', enum: ['agent-claimed', 'disk-verified'] },
  evidence:   { type: 'string' },                                              // path + bytes + last line
}, ['exists', 'provenance', 'evidence'])

// H6 timeout bound - minimal paste-in (typed-receipt settle() variant: workflow-authoring templates/h6-timeout-heartbeat.md)
const withTimeout = (thunk, ms, label) =>
  Promise.race([
    Promise.resolve().then(thunk).catch((e) => { log(`[h6] threw ${label}: ${e.message}`); return null }),
    new Promise((resolve) => setTimeout(() => { log(`[h6] timeout ${label} @${ms}ms`); resolve(null) }, ms)),
  ])

// Byte-stable preamble: IDENTICAL for every L1 agent (prompt-cache cliff, rule 8).
const PREAMBLE = [
  'CONTEXT: governed delegation, estate contract 2026-09-22 (G-1c/G-11/G-12/G-13b).',
  'PRE (binding): NEVER call mcp__claude-code-mcp__* tools. Any nested claude CLI spawn MUST use',
  '  --strict-mcp-config with an empty/temp --settings file.',
  'YOU ARE LEVEL 1. For mechanical reads/greps/globs, delegate to the restricted reader agent',
  '  (Task agentType reader - haiku-pinned, Read/Grep/Glob only) instead of doing them yourself.',
  '  Treat every reader result as agent-claimed until YOU re-read the file yourself.',
  'DEPTH: you may spawn leaves (depth 2). Leaves spawn nothing (no depth 3).',
  'OUTPUT: write your deliverable to the ARTIFACT path below with the Write tool, ending with the',
  '  line: DELIVERED: <path> (<n> bytes). Your digest returns answer/artifact/bytes/provenance.',
  '  Set provenance=agent-claimed - ONLY the orchestrator upgrades it after its own re-read.',
].join('\n')

const items = [ /* { id, task, artifact } - fill me */ ]
const WAVE_EST = 60_000  // rough output-token estimate for the whole wave

phase('Delegate')
// Budget checkpoint 1 - never spawn a wave you cannot pay for (guarded on budget.total).
if (budget.total && budget.remaining() < WAVE_EST) {
  return { blocked: 'budget', spent: budget.spent(), total: budget.total }
}

const results = await pipeline(
  items,
  // stage 1 - L1 substantive agent: effort high, mid model (G-11).
  //   Verification-critical lane: DELETE the model line to inherit the session tier.
  (it) => withTimeout(
    () => agent(`${PREAMBLE}\n\n=== TASK ${it.id} ===\n${it.task}\nARTIFACT: ${it.artifact}`, {
      label: `L1:${it.id}`, phase: 'Delegate', schema: DELEGATE_RESULT,
      effort: 'high', model: 'fable',
    }), 1_800_000, `L1:${it.id}`),          // 30-min bound per L1 unit
  // stage 2 - CALLER-side provenance upgrade: the orchestrator re-verifies on disk with its own
  //   cheap leaf instrument (reader = haiku-pinned + Read/Grep/Glob only), mechanically separate
  //   from the producer. This is where agent-claimed becomes disk-verified - nowhere else.
  async (res, it) => {
    if (!res) return res                    // dropped L1 -> nothing to verify, stays dropped
    if (!res.artifact) return res           // read-only lane: nothing on disk by design
    const v = await agent(
      `Read the file at ${res.artifact}. If Read errors or the file is missing, exists=false. ` +
      `Otherwise report exists=true, whether the FINAL line matches 'DELIVERED: ' (endsMarker), ` +
      `and evidence (absolute path + byte length + the final line). Set provenance='disk-verified' ` +
      `ONLY if exists AND endsMarker, else 'agent-claimed'.`,
      { label: `verify:${it.id}`, phase: 'Verify', schema: VERIFY_RESULT,
        agentType: 'reader', effort: 'low' })   // G-8b reader: haiku pinned in frontmatter
    return { ...res, provenance: v ? v.provenance : 'agent-claimed', verify: v }
  },
)

// Budget checkpoint 2 - the audit line every wave must leave behind.
log(`[budget] wave=delegate spent=${budget.spent()} total=${budget.total} ok=${results.filter(Boolean).length}/${items.length}`)

return {
  envelope: true,
  ok: results.filter(Boolean).length,
  total: items.length,
  // surface, never hide, the unverified tail - a claim without a disk receipt:
  unverified: results.filter((r) => r && r.artifact && r.provenance !== 'disk-verified')
    .map((r) => r.artifact),
  results,
}
```

Notes on the example:

- Stage-2 verify runs `agentType: 'reader'` FROM the orchestrator - that is a
  flat leaf call (depth 1), not a third level; the depth-2 leaf lives INSIDE
  stage 1 (reader spawned by the L1 agent). Both leaf shapes are shown.
- `unverified` in the return envelope is deliberate: the orchestrator reports
  the agent-claimed tail instead of silently dropping it.
- Cross-vendor (Codex) L1 units: per G-9, per-case and verification-critical
  only - see `skills/execution-grounded-bon` and `agentType: 'codex'` (never a
  `*-rescue` forwarder; workflow-authoring §12).

## 7. Cross-tree mail pattern (mcp_agent_mail, 127.0.0.1:18812)

The ONLY send/receive path between independent agent trees on this box
(always-on via the `MCPAgentMailSupervisor` scheduled task; health at
`/api/health`). Port discipline: 18812 agent-mail, 18765 basic-memory, 18317
auth2api - never collide them.

**Subject markers** (bind on every cross-tree message):

- `[IMPORTANT]` decisions, reviews, completions, blockers - what a sibling tree
  must act on or stop for.
- `[STATUS]` progress lines.
- `[FYI]` background a peer may want later.

**When to message across the tree - default is DON'T.** The orchestrator owns
fan-in; mail is for exceptions, not chatter. Message only when:

1. **Lease conflict** - you are about to edit a path another tree holds an
   exclusive reservation on.
2. **Premise invalidation** - your probe refutes a briefed ground-truth another
   subtree is building on (include the probe AND the mechanically different
   re-probe; single-signal rule).
3. **Shared dependency done** - a blocking artifact peers are polling for now
   exists (path + bytes + completion marker).
4. **Wave-stalling blocker** - you are blocked >15 min on something a peer owns.

**Lease hygiene** (advisory file reservations - the server's own Do/Don't):

- Reserve BEFORE edits: specific minimal globs (`app/api/*.py`), never `**/*`
  or a whole repository.
- TTL realistic (server enforces >= 60s); `renew_file_reservations` if work runs
  longer; `release_file_reservations` when done - never hold an exclusive lease
  you are not actively editing.
- Conflicts: coordinate with the holder or wait for expiry - never edit through
  a peer's exclusive lease.
- Server-side enforcement covers mail archive paths only; repo protection is the
  `install_precommit_guard` pre-commit hook - install it in repos where two
  trees edit concurrently.
- Leases are advisory for code files: pair them with disjoint scopes in the
  delegation plan itself (workflow-authoring rules 4/7).

## 8. Companion artifacts

- `C:\Users\Prekzursil\.agents\scripts\nested_ram_gate.ps1` - the G-12 gate (this skill's section 5). Repo-canon: `agent-skills-toolchain/scripts/nested_ram_gate.ps1`.
- `~/.claude/agents/reader.md` + `writer.md` (G-8b) - restricted agentTypes; repo-canon `agent-skills-toolchain/agents/`. Live spawn resolution UNVERIFIED (RAM gate during that unit's build).
- `C:\Users\Prekzursil\.agents\GRILL-DECISIONS_workflow-delegation_2026-09-22.md` - the decision record.
- `skills/workflow-authoring` - the runtime API, H6 timeout template, workflow lint.
- Queued sibling units (do not assume built): G-3b subagent-scoped PreToolUse hook, G-7a `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` probe (DONE 2026-09-22 - see section 10), G-10b fork+container of the shim.

## 9. Gate test receipts (this skill's own build)

Functional tests 2026-09-22 (wf_c8e4c79c build unit; live runs on this box at ~1.1-1.4 GB free RAM, 414-421 MCP-class processes):

- **PASS path:** `-MinFreeGB 0.05` -> `GATE:PASS free=1.10 GB >= 0.05 GB`, **exit 0**. Incidentally exercised the G-99 reap trigger (414 > 150): reaper ran, 0 kills (all live-rooted/whitelisted), POST re-check parsed.
- **BLOCK path:** default 8 GB floor, no override -> reap ran (killed 1 orphan), POST 1.10 GB, `GATE:BLOCK ... Do NOT launch the nested fleet`, **exit 2**.
- **OVERRIDE path:** `-Override` -> `GATE:OVERRIDE ... proceeding per OWNER DIRECTIVE recorded in GRILL-DECISIONS_workflow-delegation_2026-09-22.md (G-12)`, **exit 0**.
- **Culture parsing proven:** the audit's culture-formatted `free RAM GB:` line parsed to 1.10-1.40 GB across four runs (comma-decimal-safe normalization).
- **UNTESTED:** the exit-1 `GATE:FAILED-TO-RUN` branches (dependency missing / unparseable audit output). Simple guard branches, but NOT proven by the runs above - settling experiment: point `$AuditScript` at a nonexistent file (or a script emitting no `free RAM GB:` line) and require exit 1.

## 10. Concurrency dial - CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS (B4, 2026-09-22)

The G-7a depth probe (C:/Users/Prekzursil/.agents/docs/PROBE-depth-dial.md, status
COMPLETE) proved a second native dial exists on Claude Code 2.1.277:
**CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS** - present in the binary with its OWN refusal
text (probe section 2.4). It caps how many subagents run at once. This section adopts
it as the native WIDTH control alongside the depth (HEIGHT) dial.

- **Dial:** env var only - the probe help scan found no CLI flag for either dial.
- **Refusal text:** captured in fragment only - "Do not retry... increase ..." (binary,
  probe section 2.4). The full verbatim string is UNVERIFIED - pull it from the binary
  before quoting it any longer. Live firing of the refusal is UNVERIFIED.
- **Recommended default on this RAM-pressed box: 4-6**, set per-wave AFTER the section 5
  RAM pre-flight returns exit 0. The G-12 gate decides IF a wave launches; this dial
  bounds its WIDTH when it does. Never raise the dial to buy throughput below the 8 GB
  fleet floor - reap orphans or split the wave instead (G-26/G-99,
  rules/common/mcp-process-hygiene.md).
- **Composition with depth:** `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=5` is NOW SET in the
  settings env block (disk-verified 2026-09-22). The probe proved unset yields
  GrowthBook-or-fallback 3, NOT 5 (binary: `var o=3,_="tengu_hazel_trellis"`), so the
  env set is what actually buys depth 5. Depth = tree HEIGHT (refusal when current
  depth >= cap: "Subagent nesting limit reached (depth X of Y). Complete this task
  directly using your tools instead of spawning another agent. If the user explicitly
  requested deeper nesting, ask them to raise CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH.");
  concurrency = tree WIDTH. Depth is enforced by tool-catalog omission - a capped
  context never receives the spawn tool, so no attempt and no PreToolUse fire; the
  concurrency enforcement path is binary-evidenced only (live behavior UNVERIFIED).
  For big fan-outs prefer wide-and-shallow (depth 1-2, concurrency <= 6) over deep
  chains.
- **Nested-leaf completions route to ROOT (probe Test A, section 3.1):** an L3
  completion surfaced in the MAIN session, not back in its L2 spawner (meta
  `requestShape:"background"`). delegate() therefore AGGREGATES AT ROOT: the
  orchestrator (L0) collects leaf results and re-issues them downstream
  (SendMessage/resume); do not write L1 turns that block awaiting a leaf they spawned.
  Confidence: likely - single run, model-reported routing plus one consistent meta
  field; settling experiment: repeat Test A once and watch notification addressing
  (probe section 8.4).