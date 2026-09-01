// /design-gate — saved, schema-typed Design Review Gate Workflow (gem G.6).
//
// Codifies the metaswarm Design Review Gate (run AFTER brainstorming, BEFORE
// planning) as a SAVED Workflow: five FRESH reviewer instances — PM, Architect,
// Designer, Security, CTO — spawned by the script in parallel, each returning a
// typed { verdict, blocking } schema. The metaswarm gate "iterates until all
// approve"; here that convergence loop is the HUMAN's to run (re-invoke after
// edits) because this build ships the gate in SHADOW mode.
//
// SHADOW MODE (council C5): ADVISORY. Emits a structured verdict + appends it to
// a bounded shadow sink; NEVER blocks or nags. Promotion to ENFORCE (block until
// all five approve) is a separate, deferred step.
//
// Reviewers are READ-ONLY. Authored per the workflow-authoring skill: self-
// contained (no args-as-string), no Date.now() in workflow JS (the sink
// timestamp is produced inside an agent's shell), one-level nesting, a null-
// tolerant fan-in barrier (.filter(Boolean)), and a schema on every fan-in.
//
// Evidence: MASTER-DECISION-QUEUE G.6 (workflow-improve #1); project CLAUDE.md
// "Design Review Gate (5 agents: PM, Architect, Designer, Security, CTO)";
// COUNCIL-VERDICT C5.

export const meta = {
  name: 'design-gate',
  description: 'Schema-typed Design Review Gate: 5 fresh reviewers (PM, Architect, Designer, Security, CTO) in parallel, each returns {verdict, blocking}. SHADOW/advisory — verdicts only, never blocks.',
  phases: [
    { title: 'Review', detail: '5 fresh design reviewers in parallel, each returns {verdict, blocking}' },
    { title: 'Verdict', detail: 'aggregate + append to the shadow sink; advisory only' },
  ],
}

// ---------------------------------------------------------------------------
// H6 — per-agent timeout + stall heartbeat. Paste at the top of the workflow.
// Sandbox-safe: uses only injected globals (setTimeout/clearTimeout/log/parallel).
// No Date.now / Math.random / new Date() -> stays workflow_lint clean.
// SCOPE: unblocks the BARRIER. Does NOT kill the agent -- the dropped agent keeps
// running and keeps its concurrency slot until it dies on its own.
// ---------------------------------------------------------------------------
const H6_TIMEOUT_MS = 1800000; // 30 min; blueprint dispatch_timeout_seconds default
const H6_STALL_MS = 90000; // 90 s; B3 falsifier #22

// A typed drop-receipt (design item H3). NEVER return a bare null from a barrier:
// null is produced for at least three different causes -- user skipped the agent,
// the subagent died on a terminal error, and (here) our own timeout -- and
// .filter(Boolean) throws that distinction away, making "12 of 15 returned"
// unauditable.
function h6Receipt(endReason, label, ms, detail) {
  return {
    __h6: true,
    __endReason: endReason, // 'timeout' | 'threw' | 'null'
    label: label,
    ms: ms,
    detail: detail === undefined ? null : detail,
  };
}

function h6IsDrop(r) {
  return !!r && r.__h6 === true;
}
function h6Survivors(results) {
  return results.filter(function (r) {
    return !h6IsDrop(r);
  });
}
function h6Drops(results) {
  return results.filter(h6IsDrop);
}

// Emit one heartbeat line if the unit is still outstanding at H6_STALL_MS.
// Returns a canceller. This is an OBSERVATION ("still waiting"), not a verdict
// that the agent is hung -- the sandbox cannot see orchestrator state.
function h6Heartbeat(label, stallMs) {
  if (typeof setTimeout !== 'function') return function () {};
  const t = setTimeout(function () {
    if (typeof log === 'function') {
      log('H6 heartbeat: still waiting on ' + label + ' after ' + stallMs + 'ms');
    }
  }, stallMs);
  return function () {
    if (typeof clearTimeout === 'function') clearTimeout(t);
  };
}

// Bound ONE thunk. Always resolves -- never rejects, never returns undefined --
// so a barrier over wrapped thunks can no longer be poisoned by one unit.
async function withTimeout(thunk, ms, label, stallMs) {
  const lbl = label === undefined ? 'unit' : label;
  const budgetMs = ms === undefined ? H6_TIMEOUT_MS : ms;
  // Runtime-drift guard: if a future build stops injecting timers, degrade to a
  // plain await instead of dying with a ReferenceError at fan-out time.
  if (typeof setTimeout !== 'function') {
    try {
      return await thunk();
    } catch (err) {
      return h6Receipt('threw', lbl, budgetMs, String((err && err.message) || err));
    }
  }
  const stopBeat = h6Heartbeat(lbl, stallMs === undefined ? H6_STALL_MS : stallMs);
  let timer = null;
  const expiry = new Promise(function (resolve) {
    timer = setTimeout(function () {
      resolve(h6Receipt('timeout', lbl, budgetMs, null));
    }, budgetMs);
  });
  try {
    return await Promise.race([Promise.resolve().then(thunk), expiry]);
  } catch (err) {
    return h6Receipt('threw', lbl, budgetMs, String((err && err.message) || err));
  } finally {
    // ALWAYS clear on the winning path too: an un-cleared timer stays in the
    // runtime's abort set and can hold the workflow open past its last agent.
    if (timer !== null && typeof clearTimeout === 'function') clearTimeout(timer);
    stopBeat();
  }
}

// A SETTLED barrier: same shape as parallel(), but one hung unit costs you that
// unit instead of the phase. Output is index-aligned with `thunks` and every
// slot is either a real result or a typed drop-receipt -- no nulls, no holes.
async function settle(thunks, ms, labels) {
  const nameOf = function (i) {
    return labels && labels[i] !== undefined ? labels[i] : 'unit-' + i;
  };
  const raw = await parallel(
    thunks.map(function (t, i) {
      return function () {
        return withTimeout(t, ms, nameOf(i));
      };
    }),
  );
  return raw.map(function (r, i) {
    // The runtime still yields null for a cause we never saw (a user skip).
    // Type it rather than filtering it away.
    return r === null || r === undefined ? h6Receipt('null', nameOf(i), ms, null) : r;
  });
}

const HOME = 'C:/Users/Prekzursil'
const SHADOW_SINK = `${HOME}/.claude/harness-meta/logs/gate_shadow.jsonl`
const DESIGN_HINT = `The design/brainstorm document under review. Locate it in this order: (1) an explicitly named design doc in the current task, (2) the most recently written design/brainstorm markdown in the repo (Glob docs/design/**, **/*design*.md, **/brainstorm*.md, **/*-design.md), (3) if none exists, return verdict FAIL with blocking=true and a blocking_issue "no design artifact found". Read the FULL document before judging.`

// ---- Phase 1: five fresh reviewers, in parallel ----
phase('Review')
const REVIEW_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['role', 'verdict', 'blocking', 'blocking_issues', 'notes'],
  properties: {
    role: { type: 'string' },
    verdict: { type: 'string', enum: ['APPROVE', 'REJECT'], description: 'APPROVE = this design is sound from your seat' },
    blocking: { type: 'boolean', description: 'true if issues MUST be resolved before the design can proceed to planning' },
    blocking_issues: { type: 'array', items: { type: 'string' } },
    non_blocking_notes: { type: 'array', items: { type: 'string' } },
    key_assumptions: { type: 'array', items: { type: 'string' }, description: 'load-bearing assumptions this design rests on' },
    notes: { type: 'string' },
  },
}
const REVIEWERS = [
  { role: 'PM', angle: `Product fit. Does the design solve the actual user problem and Definition of Done? Hunt for: unclear user value, missing/ambiguous requirements, success not measurable, wrong problem being solved, scope not matching the ask.` },
  { role: 'Architect', angle: `Technical soundness. Hunt for: brittle or over-complex structure, wrong abstractions, unproven integration assumptions, ignored existing components that should be reused, scalability/data-flow flaws, missing failure modes, a rejected/over-engineered component reintroduced.` },
  { role: 'Designer', angle: `UX / interaction / information design (and, for UI work, visual quality). Hunt for: unclear flows, missing states (loading/empty/error), poor affordances, accessibility gaps, inconsistency with existing patterns, template-default look where intentional design is required.` },
  { role: 'Security', angle: `Security & privacy. Hunt for: secrets handling, authn/authz gaps, unvalidated input at boundaries, data egress/consent issues, injection/XSS surface, insecure defaults, missing rate-limiting, PII exposure. Apply the always-on security floor (no secrets in code, validate inputs).` },
  { role: 'CTO', angle: `Strategic + cost + maintainability + risk. Hunt for: does this fit the broader system and the owner's anti-overfit/leanness creed, is the ongoing cost justified, are there cheaper native/existing paths, is the blast radius acceptable, what is the reversibility/rollback story.` },
]
const reviews = h6Survivors(await settle(REVIEWERS.map(r => () =>
  agent(
    `You are a FRESH, independent DESIGN reviewer occupying the **${r.role}** seat of a 5-person design review board. This gate runs AFTER brainstorming and BEFORE planning.\n\n${DESIGN_HINT}\n\n` +
    `${r.angle}\n\n` +
    `You are READ-ONLY — read the design and reason; modify nothing. Be specific: cite the exact section for every issue. APPROVE only if the design is genuinely sound from your seat; set blocking=true only for issues that MUST be resolved before this proceeds to a plan (real defects, not preferences). List the load-bearing assumptions. Return the schema.`,
    { label: `review:${r.role}`, phase: 'Review', schema: REVIEW_SCHEMA, effort: 'high' }
  )
), H6_TIMEOUT_MS)) // null-tolerant barrier: a throwing reviewer resolves to null, not batch-reject

// ---- Phase 2: aggregate + shadow-log (advisory verdict) ----
phase('Verdict')
const anyBlocking = reviews.some(r => r && r.blocking === true)
const anyReject = reviews.some(r => r && r.verdict === 'REJECT')
const allApprove = reviews.length === REVIEWERS.length && reviews.every(r => r && r.verdict === 'APPROVE')
const overall = reviews.length === 0 ? 'INCONCLUSIVE'
  : (anyBlocking ? 'REJECT' : (anyReject ? 'CONCERNS' : (allApprove ? 'APPROVE' : 'CONCERNS')))

const VERDICT_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['gate', 'mode', 'overall', 'blocking', 'reviewers', 'shadow_logged', 'summary'],
  properties: {
    gate: { type: 'string' },
    mode: { type: 'string' },
    overall: { type: 'string', enum: ['APPROVE', 'CONCERNS', 'REJECT', 'INCONCLUSIVE'] },
    blocking: { type: 'boolean' },
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
  `You are the design-gate AGGREGATOR. Combine the five seat reviews into ONE advisory verdict, then RECORD it (do not block anything).\n\n` +
  `Reviews:\n${digest || '(no reviews returned)'}\n\n` +
  `Computed overall = ${overall}; blocking = ${anyBlocking}; all-five-approve = ${allApprove}.\n\n` +
  `NOW: append EXACTLY ONE JSON line to the shadow sink "${SHADOW_SINK}" (create the parent dir if needed; generate the timestamp with your shell, e.g. PowerShell Get-Date -Format o — do NOT ask the workflow for it). The line = {"ts":<iso>,"gate":"design-gate","mode":"SHADOW","overall":"${overall}","blocking":${anyBlocking},"reviewers":[...role/verdict/blocking...]}. This sink is bounded+advisory; append-only.\n\n` +
  `Then return the verdict schema. State clearly in "summary" that this gate is SHADOW/ADVISORY — it surfaces concerns for the human, it does NOT block the design. The metaswarm "iterate until all five approve" convergence loop is the human's to run by re-invoking /design-gate after edits. Set shadow_logged=true only if the append succeeded.`,
  { label: 'aggregate', phase: 'Verdict', schema: VERDICT_SCHEMA, effort: 'high' }
)

return {
  gate: 'design-gate',
  mode: 'SHADOW/advisory (never blocks — council C5)',
  reviews,
  verdict,
}
