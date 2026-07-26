// /plan-gate — saved, schema-typed Plan Review Gate Workflow (gem G.6).
//
// Codifies the metaswarm Plan Review Gate as a SAVED Workflow so the three
// adversarial reviewers are spawned as FRESH instances by the script (not by
// honor-system prompting), each returning a typed { verdict, blocking } schema,
// after a cheap MECHANICAL stage-0 lint runs FIRST (so a structurally broken
// plan is caught by ~1 ms of Python before N Opus reviewers burn tokens).
//
// SHADOW MODE (council C5): this gate is ADVISORY. It emits a structured
// verdict and appends it to a bounded shadow sink; it NEVER blocks a merge or
// nags. Promotion to an ENFORCE gate (block the plan on a blocking FAIL) is a
// separate, deferred step. The verdict lives in the return value + the sink.
//
// Reviewers are READ-ONLY (they read the plan and reason; they mutate nothing),
// so no worktree isolation is needed. Authored per the workflow-authoring skill:
// args-as-string-free (self-contained), no Date.now() in workflow JS (the sink
// timestamp is produced inside an agent's shell), one-level nesting, a null-
// tolerant fan-in barrier (a throwing reviewer resolves to null, filtered out),
// and a schema on every fan-in.
//
// Evidence: MASTER-DECISION-QUEUE G.6 (workflow-improve #1/#7/#10); project
// CLAUDE.md "Plan Review Gate (3 adversarial reviewers)"; COUNCIL-VERDICT C5.

export const meta = {
  name: 'plan-gate',
  description: 'Schema-typed Plan Review Gate: mechanical stage-0 lint then 3 fresh adversarial reviewers (Feasibility, Completeness, Scope & Alignment). SHADOW/advisory — verdicts only, never blocks.',
  phases: [
    { title: 'Stage-0', detail: 'mechanical plan-lint (WU<=5 files / no overlapping scopes / DAG) — cheap gate before the reviewers' },
    { title: 'Review', detail: '3 fresh adversarial reviewers in parallel, each returns {verdict, blocking}' },
    { title: 'Verdict', detail: 'aggregate + append to the shadow sink; advisory only' },
  ],
}

const HOME = 'C:/Users/Prekzursil'
const LINTER = `${HOME}/.claude/harness-meta/plan_lint_stage0.py`
const SHADOW_SINK = `${HOME}/.claude/harness-meta/logs/gate_shadow.jsonl`
// Where a plan typically lives; reviewers auto-discover if this is absent.
const PLAN_HINT = `The plan under review. Locate it in this order: (1) .beads/plans/active-plan.md, (2) the most recently written plan/spec markdown in the repo (Glob **/plan*.md, **/*-plan.md, docs/plans/**), (3) if none exists, return verdict FAIL with blocking=true and a blocking_issue "no plan artifact found". Read the FULL plan before judging.`

// ---- Phase 0: mechanical stage-0 lint (runs BEFORE the Opus reviewers) ----
phase('Stage-0')
const LINT_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['marker', 'verdict', 'wu_count', 'violations', 'plan_path'],
  properties: {
    marker: { type: 'string', description: 'PLAN_LINT:clean|dirty|na' },
    verdict: { type: 'string', enum: ['clean', 'dirty', 'na'] },
    wu_count: { type: 'number' },
    plan_path: { type: 'string' },
    violations: { type: 'array', items: { type: 'object', additionalProperties: false,
      properties: { kind: { type: 'string' }, wu: { type: 'string' }, detail: { type: 'string' } },
      required: ['kind', 'wu', 'detail'] } },
    notes: { type: 'string' },
  },
}
const lint = await agent(
  `You run the MECHANICAL stage-0 of the plan-gate. Do NOT judge quality — only run the deterministic linter and report.\n\n${PLAN_HINT}\n\n` +
  `STEPS:\n` +
  `1. Locate + Read the plan. Extract its work-unit decomposition into a JSON object {"work_units":[{"id","files":[...],"deps":[...]}]} — one entry per work unit, "files" = that WU's declared file scope, "deps" = the WU ids it depends on. Write it to a temp file plan.wu.json (use your shell; PowerShell — Bash is broken in this workspace).\n` +
  `2. Run: python "${LINTER}" --plan <plan.wu.json OR the plan .md directly> --json  (the linter also reads a fenced json block inside markdown). Capture the JSON.\n` +
  `3. Return the parsed marker/verdict/wu_count/violations verbatim from the linter output, plus plan_path = the plan you found. If you could not build a work-unit list, set verdict "na" and explain in notes.\n\n` +
  `This is SHADOW/advisory: a "dirty" result is a signal for the reviewers, it does NOT block.`,
  { label: 'stage0-lint', phase: 'Stage-0', schema: LINT_SCHEMA, effort: 'medium' }
)

// ---- Phase 1: three fresh adversarial reviewers, in parallel ----
phase('Review')
const REVIEW_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['role', 'verdict', 'blocking', 'blocking_issues', 'notes'],
  properties: {
    role: { type: 'string' },
    verdict: { type: 'string', enum: ['PASS', 'FAIL'], description: 'PASS = this dimension is satisfied' },
    blocking: { type: 'boolean', description: 'true if the issues MUST be fixed before the plan proceeds' },
    blocking_issues: { type: 'array', items: { type: 'string' } },
    non_blocking_notes: { type: 'array', items: { type: 'string' } },
    key_assumptions: { type: 'array', items: { type: 'string' }, description: 'load-bearing assumptions the plan rests on (Key Assumptions Check)' },
    notes: { type: 'string' },
  },
}
const LINT_CONTEXT = `\n\nMECHANICAL STAGE-0 RESULT (advisory input): ${lint ? `${lint.marker} — ${(lint.violations || []).map(v => `${v.kind}:${v.wu}`).join(', ') || 'no structural violations'}` : 'stage-0 unavailable'}.`
const REVIEWERS = [
  { role: 'Feasibility', angle: `Can this plan actually be built as written? Hunt for: missing prerequisites, hand-waved hard parts, unproven library/API assumptions, steps that assume a capability the workspace lacks, ordering that can't work, WUs whose "done" is undefined. Rate the load-bearing assumptions.` },
  { role: 'Completeness', angle: `Does the plan cover the WHOLE goal? Hunt for: unhandled edge cases, missing error/rollback paths, absent tests/coverage, no acceptance criteria, gaps between WUs where work falls through, "and then it works" leaps, missing non-functional needs (security, perf, migration).` },
  { role: 'Scope & Alignment', angle: `Does the plan match the stated goal — no more, no less? Hunt for: scope creep (building unrequested things), scope gaps (dropping a required outcome), drift from the Definition of Done, gold-plating, or a rejected/over-engineered component sneaking back in.` },
]
const reviews = (await parallel(REVIEWERS.map(r => () =>
  agent(
    `You are a FRESH, independent adversarial PLAN reviewer. Your single dimension: **${r.role}**.\n\n${PLAN_HINT}${LINT_CONTEXT}\n\n` +
    `${r.angle}\n\n` +
    `You are READ-ONLY — read the plan and reason; do not modify any file. Be adversarial and specific: cite the exact WU/section for every issue. Set verdict PASS only if your dimension is genuinely satisfied; set blocking=true only for issues that MUST be fixed before the plan proceeds (real defects, not nitpicks). List the plan's load-bearing assumptions. Return the schema.`,
    { label: `review:${r.role}`, phase: 'Review', schema: REVIEW_SCHEMA, effort: 'high' }
  )
))).filter(Boolean) // null-tolerant barrier: a throwing reviewer resolves to null, not batch-reject

// ---- Phase 2: aggregate + shadow-log (advisory verdict) ----
phase('Verdict')
const anyBlocking = reviews.some(r => r && r.blocking === true)
const anyFail = reviews.some(r => r && r.verdict === 'FAIL')
const overall = reviews.length === 0 ? 'INCONCLUSIVE' : (anyBlocking ? 'FAIL' : (anyFail ? 'CONCERNS' : 'PASS'))

const VERDICT_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['gate', 'mode', 'overall', 'blocking', 'stage0', 'reviewers', 'shadow_logged', 'summary'],
  properties: {
    gate: { type: 'string' },
    mode: { type: 'string', description: 'always SHADOW/advisory in this build' },
    overall: { type: 'string', enum: ['PASS', 'CONCERNS', 'FAIL', 'INCONCLUSIVE'] },
    blocking: { type: 'boolean' },
    stage0: { type: 'string', description: 'the PLAN_LINT marker' },
    reviewers: { type: 'array', items: { type: 'object', additionalProperties: false,
      properties: { role: { type: 'string' }, verdict: { type: 'string' }, blocking: { type: 'boolean' } },
      required: ['role', 'verdict', 'blocking'] } },
    top_blocking_issues: { type: 'array', items: { type: 'string' } },
    shadow_logged: { type: 'boolean' },
    summary: { type: 'string' },
  },
}
const digest = reviews.map(r => `### ${r.role}: ${r.verdict}${r.blocking ? ' (BLOCKING)' : ''}\n` +
  `blocking: ${(r.blocking_issues || []).join('; ') || 'none'}\nnotes: ${r.notes || ''}`).join('\n\n')
const verdict = await agent(
  `You are the plan-gate AGGREGATOR. Combine the mechanical stage-0 lint and the three adversarial reviews into ONE advisory verdict, then RECORD it (do not block anything).\n\n` +
  `Stage-0: ${lint ? lint.marker : 'unavailable'} (${lint ? (lint.violations || []).length : 0} structural violations).\n` +
  `Reviews:\n${digest || '(no reviews returned)'}\n\n` +
  `Computed overall = ${overall}; blocking = ${anyBlocking}.\n\n` +
  `NOW: append EXACTLY ONE JSON line to the shadow sink "${SHADOW_SINK}" (create the parent dir if needed; generate the timestamp with your shell, e.g. PowerShell Get-Date -Format o — do NOT ask the workflow for it). The line = {"ts":<iso>,"gate":"plan-gate","mode":"SHADOW","overall":"${overall}","blocking":${anyBlocking},"stage0":"${lint ? lint.marker : 'na'}","reviewers":[...role/verdict/blocking...]}. This sink is bounded+advisory; append-only.\n\n` +
  `Then return the verdict schema. State clearly in "summary" that this gate is SHADOW/ADVISORY — it surfaces concerns for the human, it does NOT block the plan. Set shadow_logged=true only if the append succeeded.`,
  { label: 'aggregate', phase: 'Verdict', schema: VERDICT_SCHEMA, effort: 'high' }
)

return {
  gate: 'plan-gate',
  mode: 'SHADOW/advisory (never blocks — council C5)',
  stage0: lint,
  reviews,
  verdict,
}
