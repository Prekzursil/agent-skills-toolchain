---
title: resume-wired-fanout
type: note
permalink: dqverify-repo-20261013/skills/workflow-authoring/templates/resume-wired-fanout
---

# TEMPLATE — resume-wired fan-out Workflow

Copy the fenced block below to `~/.claude/workflows/<name>.mjs`, replace `UNITS`,
`MANIFEST` and `meta.name`, and the fan-out becomes crash-resumable: a unit that
dies mid-flight is re-driven on the next run while its siblings keep their `done`
state.

Lint it before saving:

```bash
python skills/workflow-authoring/scripts/workflow_lint.py ~/.claude/workflows/<name>.mjs
```

The block is kept lint-CLEAN on purpose (pure-literal `meta`, no banned
non-determinism, a `schema:` on every `agent()`, a `.filter(Boolean)` barrier, an
`args` parse-if-string guard) and `scripts/test_workflow_lint.py` asserts that in
CI, so a future edit that breaks a rule fails the gate instead of shipping a
template that teaches the footgun.

```js
// TEMPLATE — a fan-out Workflow WIRED to the cross-session resume manifest.
//
// WHY THIS FILE EXISTS
// `~/.claude/harness-meta/plan_lint_stage0.py` has shipped a complete, fsync'd
// `ResumeManifest` (write-ahead `done.jsonl`, `mark_partial` / `mark_done` /
// `mark_failed`, `resume(all_wu_ids) -> {done, partial, failed, pending}`) since
// 2026-07-12 with ZERO callers. Every saved Workflow that dies mid-wave therefore
// redoes the whole wave. This template is the wiring.
//
// WHY AN `agent()` STEP AND NOT A JS SHIM
// A workflow file is NOT a plain ES module: the runner injects `agent`/`parallel`/
// `phase`, reads `export const meta`, and WRAPS THE BODY so top-level `await` is
// legal (SKILL.md rule 1). A wrapped body cannot carry a static top-level
// `import`, and measured across all 11 saved workflows in ~/.claude/workflows
// there is not ONE `import`, `require(`, `child_process` or `fs.` call — every
// disk read is delegated to an `agent()`. So the manifest is reached the same way
// the existing accumulator workflow reaches disk: through a shell inside an agent.
//
// THE CONTRACT — three touch-points, nothing else:
//   1. GROUND   `--ids <work-list> --next`  -> stdout is exactly the ids still to
//               run (crashed-partial + failed + never-seen-pending), one per line.
//   2. BEFORE   `--mark-partial <id>`       -> write-ahead, BEFORE the unit works.
//   3. AFTER    `--mark-done <id>` (or `--mark-failed <id>`) -> after it commits.
// The manifest is append-only and fsync'd per record, so a unit killed between (2)
// and (3) is reclassified `partial` on the next run and re-driven; its siblings
// keep their `done` state. MEASURED: process-kill durability is executable-proven
// (taskkill /F between mark-partial and resume -> the id lands in `partial`).
// UNVERIFIED, inline: machine-crash / power-loss durability is NOT proven — a
// process kill cannot distinguish fsync'd bytes from page-cache bytes. Settling
// experiment: run the same protocol in a VM and hard-cut power between the append
// and the read.
//
// SHADOW: the CLI always exits 0 and never blocks; a missing manifest simply means
// "nothing done yet", so wiring it can only ever ADD information.

export const meta = {
  name: 'resume-wired-fanout',
  description: 'TEMPLATE: fan-out whose work-list is filtered through the cross-session resume manifest, so a mid-wave crash re-drives only the dead units.',
  phases: [
    { title: 'Ground', detail: 'classify the declared work-list through plan_lint_stage0 --next' },
    { title: 'Fan-out', detail: 'run ONLY the to-run units; each write-aheads partial then marks done' },
    { title: 'Report', detail: 'final classification; a non-empty partial set means a unit died' },
  ],
}

const HOME = 'C:/Users/Prekzursil'
const LINTER = `${HOME}/.claude/harness-meta/plan_lint_stage0.py`
// One manifest dir per PROGRAM (not per session) — that is what makes it cross-session.
const MANIFEST = `${HOME}/.claude/harness-meta/resume/my-program`

// Declare the work-list HERE, as a literal. This is the whole reason `--ids` exists:
// a Workflow's unit list is a JS array, so `--plan` (which reads a plan file) can
// never name these units.
const UNITS = [
  { id: 'U01', body: 'the first unit of real work' },
  { id: 'U02', body: 'the second unit of real work' },
  { id: 'U03', body: 'the third unit of real work' },
]
const ALL_IDS = UNITS.map((u) => u.id).join(',')

// SKILL.md rule 2 — `args` can arrive JSON-encoded; never destructure it raw.
const RAW_ARGS = typeof args === 'string' ? args : ''
const FORCE_ALL = RAW_ARGS.includes('--force-all')

// ---------------------------------------------------------------- Ground ----
phase('Ground')

const GROUND_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['to_run', 'done', 'partial', 'failed', 'manifest_existed'],
  properties: {
    to_run: { type: 'array', items: { type: 'string' }, description: 'verbatim stdout lines of --next' },
    done: { type: 'array', items: { type: 'string' } },
    partial: { type: 'array', items: { type: 'string' }, description: 'units that crashed mid-flight' },
    failed: { type: 'array', items: { type: 'string' } },
    manifest_existed: { type: 'boolean', description: 'false on the very first run of this program' },
  },
}

const ground = await agent(
  `You are the RESUME GROUND step. Do NOT do any unit work. Run two commands and report verbatim.\n\n` +
    `1. python "${LINTER}" --manifest "${MANIFEST}" --ids "${ALL_IDS}" --next\n` +
    `   Every stdout line is one work-unit id still to run. An EMPTY stdout means everything is done.\n` +
    `2. python "${LINTER}" --manifest "${MANIFEST}" --ids "${ALL_IDS}" --resume --json\n` +
    `   Parse the JSON for done/partial/failed.\n\n` +
    `Set manifest_existed=false if "${MANIFEST}/done.jsonl" does not exist. Report exactly what the ` +
    `commands printed; do NOT infer, and do NOT invent ids that were not in the output. Both commands ` +
    `exit 0 by design (SHADOW mode) — a zero exit is NOT evidence the manifest was read, the stdout is.`,
  { label: 'resume-ground', phase: 'Ground', schema: GROUND_SCHEMA, effort: 'low' },
)

const toRun = FORCE_ALL ? UNITS.map((u) => u.id) : ground.to_run
const queue = UNITS.filter((u) => toRun.includes(u.id))

// A collapsed work-list must die loudly, never silently run 1 of N.
if (!FORCE_ALL && queue.length !== toRun.length) {
  throw new Error(
    `resume-ground returned ${toRun.length} id(s) but only ${queue.length} match the declared UNITS ` +
      `(${ALL_IDS}) — the manifest and the work-list have drifted; fix the ids before running.`,
  )
}

// --------------------------------------------------------------- Fan-out ----
phase('Fan-out')

const UNIT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['id', 'marked_partial', 'marked_terminal', 'outcome', 'evidence'],
  properties: {
    id: { type: 'string' },
    marked_partial: { type: 'boolean', description: 'true only if the --mark-partial command really ran' },
    marked_terminal: { type: 'string', enum: ['done', 'failed', 'none'] },
    outcome: { type: 'string' },
    evidence: { type: 'string', description: 'file:line or real command output for the work claim' },
  },
}

const WRITE_AHEAD = (id) =>
  `RESUME CONTRACT — obey both halves or the wave cannot recover from your death.\n` +
  `FIRST, before any other tool call:\n` +
  `  python "${LINTER}" --manifest "${MANIFEST}" --mark-partial ${id}\n` +
  `LAST, only after your work is committed/written:\n` +
  `  python "${LINTER}" --manifest "${MANIFEST}" --mark-done ${id}\n` +
  `If you cannot finish, run --mark-failed ${id} instead. Do NOT mark done on a partial result: a ` +
  `wrongly-done unit is silently skipped forever, which is worse than being re-driven.\n\n`

// REQUIRED PREAMBLE: paste the H6 block from templates/h6-timeout-heartbeat.md
// above this line. It defines withTimeout() and is what stops ONE hung unit from
// freezing this entire fan-out -- parallel() is a BARRIER, so without it the wave
// waits forever on its slowest dead agent (measured: a 13-hour deadlock). The
// wrapper unblocks the BARRIER only; the dropped agent keeps running and keeps
// its slot. Red-proof: tools/wf-timeout/test_h6_timeout.py.
const UNIT_TIMEOUT_MS = 1800000

const results = (
  await parallel(
    queue.map(
      (u) => () =>
        withTimeout(
          () =>
            agent(WRITE_AHEAD(u.id) + `WORK UNIT ${u.id}\n\n${u.body}`, {
              label: `unit:${u.id}`,
              phase: 'Fan-out',
              schema: UNIT_SCHEMA,
            }),
          UNIT_TIMEOUT_MS,
          u.id,
        ),
    ),
  )
).filter(Boolean)

// ---------------------------------------------------------------- Report ----
phase('Report')

const REPORT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['done', 'partial', 'failed', 'pending', 'clean'],
  properties: {
    done: { type: 'array', items: { type: 'string' } },
    partial: { type: 'array', items: { type: 'string' } },
    failed: { type: 'array', items: { type: 'string' } },
    pending: { type: 'array', items: { type: 'string' } },
    clean: { type: 'boolean', description: 'true only when partial and pending are both empty' },
  },
}

const final = await agent(
  `Run: python "${LINTER}" --manifest "${MANIFEST}" --ids "${ALL_IDS}" --resume --json\n` +
    `Report the four lists verbatim. clean=true ONLY when partial and pending are both empty. ` +
    `A non-empty partial set is the signal that a unit died between its write-ahead and its ` +
    `terminal mark — re-run this workflow and it will re-drive exactly those ids.`,
  { label: 'resume-report', phase: 'Report', schema: REPORT_SCHEMA, effort: 'low' },
)

return { ground, results, final }
```

## The three touch-points, restated

| when | command | effect |
|---|---|---|
| GROUND, once | `--manifest M --ids <all> --next` | stdout = exactly the ids still to run |
| BEFORE each unit | `--manifest M --mark-partial <id>` | write-ahead; an fsync'd `partial` record |
| AFTER each unit | `--manifest M --mark-done <id>` (or `--mark-failed`) | terminal state |

`--ids` exists because a Workflow's unit list is a **JS array**, not a plan file:
`--plan` reads a plan document and can never name these units. Without it an author
must synthesise a throwaway `plan.wu.json` just to name their own work — which is
why the manifest shipped with zero callers.

## Honest limits

* `--mark-done` is asserted by the unit agent, not verified by the orchestrator. A
  unit that lies is skipped forever. Pair the contract with an independent
  postcondition probe (artifact exists AND ends with your completion marker) before
  trusting a `done` — the accumulator workflow's AND-gate is the precedent.
* Process-kill durability is executable-proven. **UNVERIFIED, inline:**
  machine-crash / power-loss durability is not — a process kill cannot distinguish
  `fsync`'d bytes from page-cache bytes. Settling experiment: run the write-ahead /
  kill / resume protocol in a VM and hard-cut power between the append and the read.
* The manifest is append-only and never pruned. A long-lived program's `done.jsonl`
  grows without bound; `records()` reads the whole file each time. Fine at wave
  scale (hundreds of records), not a database.