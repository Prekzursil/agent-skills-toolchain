// Recursive Tournament Voting + Parallel-Distill-Refine (RTV+PDR)
// Test-time-compute scaling for hard coding work-units.
// Based on: arXiv:2604.16529 (RTV+PDR methodology).
//
// COST WARNING: N parallel Opus rollouts per invocation.
// Gate this workflow behind the ESE (Ensemble Semantic Entropy) escalation
// gate — fire only on hard/contentious work-units.
// CLAUDE_CODE_FORK_SUBAGENT fork-cache is automatically used for parallel
// Opus rollouts when enabled, cutting warmup overhead.
//
// Input (args global):
//   args.task          {string}  — the work-unit task description (required)
//   args.repo_context  {string}  — repo/codebase context (optional, recommended)
//   args.n             {number}  — number of parallel rollouts (default 4, keep 3-5)
//   args.pdr_mode      {boolean} — if true, run a PDR refine pass after tournament
//
// Output: FINAL_SCHEMA {winner, runner_up, rounds, rationale}

export const meta = {
  name: 'rtv-pdr',
  description: 'Recursive Tournament Voting + Parallel-Distill-Refine: spawn N independent Opus rollouts on a hard coding work-unit, distill each to a structured summary, run recursive pairwise judging by separate agents until one winner survives, then optionally refine via PDR (next rollout conditioned on losers failure_modes). Gate behind ESE — expensive.',
  phases: [
    { title: 'Rollout', detail: 'N independent parallel Opus rollouts, each returning a structured distillation' },
    { title: 'Tournament', detail: 'Recursive pairwise judging by fresh agents — contestants never judge themselves' },
    { title: 'Refine', detail: '(Optional — pdr_mode) One PDR refine rollout conditioned on winner + losers failure_modes' },
  ],
}

// ── Schemas ─────────────────────────────────────────────────────────────────

const ROLLOUT_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  required: ['approach'],
  properties: {
    approach: {
      type: 'string',
      description: 'The complete solution narrative: strategy, concrete changes, and patch or plan. This is the ONLY required field; put all substance here even if optional fields are omitted.',
    },
    key_changes: {
      type: 'array',
      items: { type: 'string' },
      description: 'Concrete file/function-level changes proposed or implemented',
    },
    hypotheses: {
      type: 'array',
      items: { type: 'string' },
      description: 'Key assumptions or hypotheses that underpin this approach',
    },
    failure_modes: {
      type: 'array',
      items: { type: 'string' },
      description: 'Ways this approach could fail or be wrong; honest self-assessment of risks',
    },
    candidate_patch_or_plan: {
      type: 'string',
      description: 'The actual code patch, diff, or concrete implementation plan',
    },
    self_reported_confidence: {
      type: 'number',
      description: 'Self-reported confidence 0.0-1.0 (used for logging only — judges, not this, determine the winner)',
    },
  },
}

const COMPARE_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  required: ['winner_id'],
  properties: {
    winner_id: {
      type: 'string',
      description: 'The ID of the winning rollout (e.g. "R0", "R2") — must be one of the two contestants',
    },
    reason: {
      type: 'string',
      description: 'Concise rationale for why the winner is superior for this specific task',
    },
  },
}

const FINAL_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  required: ['rationale'],
  properties: {
    winner: {
      type: 'object',
      additionalProperties: true,
      required: ['id'],
      properties: {
        id: { type: 'string', description: 'Rollout ID, e.g. "R0"' },
        summary: { type: 'object', additionalProperties: true, description: 'The winning rollout distillation (ROLLOUT_SCHEMA shape)' },
      },
    },
    runner_up: {
      type: ['object', 'null'],
      description: 'Finalist that lost the final match, or null if N < 2',
      additionalProperties: true,
    },
    rounds: {
      type: 'integer',
      description: 'Number of tournament rounds run',
    },
    rationale: {
      type: 'string',
      description: 'Summary rationale for the winner, drawn from the final judge verdict and PDR refine if applicable',
    },
  },
}

// ── Phase 1: Rollout ─────────────────────────────────────────────────────────

phase('Rollout')

const N = (typeof args.n === 'number' && args.n >= 2 && args.n <= 5) ? Math.round(args.n) : 4
const taskDesc = args.task || '(no task provided)'
const repoCtx = args.repo_context ? `\n\nREPO CONTEXT:\n${args.repo_context}` : ''

log(`RTV+PDR: launching ${N} parallel rollouts (model: opus)`)

const rolloutThunks = []
for (let i = 0; i < N; i++) {
  const idx = i
  rolloutThunks.push(() => agent(
    `You are an independent coding agent tasked with solving a hard work-unit.
Approach this from a FRESH, DIVERSE angle — rollout index ${idx} of ${N - 1}.
Avoid guessing what other rollouts might do; choose the strategy that YOU find most principled.

TASK:
${taskDesc}${repoCtx}

Produce a structured distillation of your solution attempt. Put the COMPLETE solution in approach:
strategy, concrete changes, and the actual patch/code or precise plan. It is the ONLY required field,
so it must preserve all substance even if you omit optional fields. Be honest about failure_modes and risks.
self_reported_confidence is for logging only — a separate judge will select the winner.`,
    {
      label: `rollout:R${idx}`,
      phase: 'Rollout',
      schema: ROLLOUT_SCHEMA,
      model: 'opus',
      isolation: 'worktree',
    }
  ))
}

const rawRollouts = await parallel(rolloutThunks)

// Build survivor list with stable IDs — filter nulls immediately
const survivors = rawRollouts
  .map((s, i) => s ? { id: `R${i}`, summary: s } : null)
  .filter(Boolean)

log(`Rollout complete: ${survivors.length}/${N} succeeded`)

if (survivors.length === 0) {
  return { winner: null, runner_up: null, rounds: 0, rationale: 'All rollouts failed — no survivors.' }
}
if (survivors.length === 1) {
  return { winner: survivors[0], runner_up: null, rounds: 0, rationale: `Single survivor (${survivors[0].id}) — no tournament needed.` }
}

// ── Phase 2: Tournament ──────────────────────────────────────────────────────

phase('Tournament')

// Recursive pairwise tournament.
// CRITICAL: judge agents are ALWAYS fresh — never the contestants.
// Odd contestant counts → the last entry gets a bye (advances automatically).
// On hallucinated winner_id → re-run judge once; if still bad → lower-index advances.

let current = survivors.slice()  // working set for this round
let roundNum = 0
let runnerUp = null              // tracked from the final match

while (current.length > 1) {
  roundNum++
  log(`Tournament round ${roundNum}: ${current.length} contestants`)

  const pairs = []
  const byes = []

  for (let i = 0; i + 1 < current.length; i += 2) {
    pairs.push([current[i], current[i + 1]])
  }
  // If odd count, the last entry gets a bye (advances without judging)
  if (current.length % 2 === 1) {
    byes.push(current[current.length - 1])
  }

  // Run all pair comparisons in parallel (each is a fresh judge)
  const judgeThunks = pairs.map(([a, b]) => {
    return () => agent(
      `You are a FRESH, INDEPENDENT judge evaluating two coding solution summaries for the same task.
You are NOT one of the contestants. Your only job is to pick the better solution for the stated task.

TASK BEING SOLVED:
${taskDesc}${repoCtx}

SOLUTION ${a.id}:
${JSON.stringify(a.summary, null, 2)}

SOLUTION ${b.id}:
${JSON.stringify(b.summary, null, 2)}

Judge ONLY on technical merit, correctness, and approach quality for this specific task.
Do NOT use self_reported_confidence as the deciding factor — it is self-assessed and unreliable.
Pick the solution more likely to actually solve the problem correctly.
Your winner_id MUST be exactly "${a.id}" or "${b.id}" — no other value is valid.`,
      {
        label: `judge:${a.id}vs${b.id}:r${roundNum}`,
        phase: 'Tournament',
        schema: COMPARE_SCHEMA,
        model: 'opus',
      }
    )
  })

  const judgeResults = (await parallel(judgeThunks)).filter(Boolean)

  // Resolve winners from judge results
  const roundWinners = []
  for (let p = 0; p < pairs.length; p++) {
    const [a, b] = pairs[p]
    let verdict = judgeResults[p]

    // Validate: winner_id must be one of the two contestants
    const isValid = (v) => v && (v.winner_id === a.id || v.winner_id === b.id)

    if (!isValid(verdict)) {
      log(`Judge hallucinated winner_id for ${a.id} vs ${b.id} — re-running once`)
      // One retry
      verdict = await agent(
        `You are a FRESH judge re-evaluating two coding solutions after a prior judge returned an invalid choice.
The valid winner IDs are "${a.id}" or "${b.id}" — you MUST pick one of these exactly.

TASK:
${taskDesc}

SOLUTION ${a.id} (approach): ${a.summary.approach}
SOLUTION ${b.id} (approach): ${b.summary.approach}

Pick the better solution. winner_id must be exactly "${a.id}" or "${b.id}".`,
        {
          label: `judge-retry:${a.id}vs${b.id}:r${roundNum}`,
          phase: 'Tournament',
          schema: COMPARE_SCHEMA,
          model: 'opus',
        }
      )
    }

    // Deterministic fallback: if still invalid, lower-index advances
    let winnerEntry, loserEntry
    if (isValid(verdict)) {
      winnerEntry = verdict.winner_id === a.id ? a : b
      loserEntry  = verdict.winner_id === a.id ? b : a
    } else {
      log(`Judge still invalid for ${a.id} vs ${b.id} — lower-index (${a.id}) advances by fallback`)
      winnerEntry = a
      loserEntry  = b
    }

    // Track runner_up from the FINAL match only (last pair in the final round)
    roundWinners.push(winnerEntry)

    // In the final round with exactly 2 contestants, capture the loser as runner_up
    if (current.length === 2) {
      runnerUp = loserEntry
    }
  }

  // New current set = pair winners + byes
  current = [...roundWinners, ...byes]
}

const winner = current[0]
log(`Tournament complete: winner is ${winner.id} after ${roundNum} round(s)`)

// ── Phase 3: Refine (optional PDR) ──────────────────────────────────────────

let finalRationale = `Winner ${winner.id} selected by tournament after ${roundNum} round(s). Approach: ${winner.summary.approach}`

if (args.pdr_mode) {
  phase('Refine')
  log('PDR mode enabled — running refine rollout conditioned on tournament context')

  // Collect all losers' failure_modes (distilled summaries only, not raw history)
  const loserContext = survivors
    .filter(s => s.id !== winner.id)
    .map(s => `${s.id}: failure_modes=${JSON.stringify(s.summary.failure_modes)}, approach="${s.summary.approach}"`)
    .join('\n')

  const refineResult = await agent(
    `You are a REFINE agent running a PDR (Parallel-Distill-Refine) pass.
A tournament has already selected a winner. Your job is to produce an improved solution
conditioned on what you know about the winner AND what went wrong with other approaches.

TASK:
${taskDesc}${repoCtx}

TOURNAMENT WINNER (${winner.id}) — distilled summary:
${JSON.stringify(winner.summary, null, 2)}

PRIOR LOSERS' FAILURE MODES (use these to avoid known pitfalls):
${loserContext}

Produce a refined solution that builds on the winner's strengths and avoids the identified failure modes.
Your solution may supersede the winner's if you find a clearly better path.`,
    {
      label: 'pdr-refine',
      phase: 'Refine',
      schema: ROLLOUT_SCHEMA,
      model: 'opus',
      isolation: 'worktree',
    }
  )

  if (refineResult) {
    // Run one final judge: tournament winner vs PDR refine
    const refineId = 'R-PDR'
    const refineEntry = { id: refineId, summary: refineResult }
    const finalVerdict = await agent(
      `You are a FRESH judge comparing the tournament winner against a PDR-refined solution.

TASK:
${taskDesc}

TOURNAMENT WINNER (${winner.id}):
${JSON.stringify(winner.summary, null, 2)}

PDR REFINED SOLUTION (${refineId}):
${JSON.stringify(refineResult, null, 2)}

Pick the better solution. winner_id must be exactly "${winner.id}" or "${refineId}".`,
      {
        label: 'judge:winner-vs-pdr',
        phase: 'Refine',
        schema: COMPARE_SCHEMA,
        model: 'opus',
      }
    )

    const validIds = [winner.id, refineId]
    if (finalVerdict && validIds.includes(finalVerdict.winner_id)) {
      if (finalVerdict.winner_id === refineId) {
        // PDR refine beats tournament winner — capture original winner id before reassigning
        const prevWinnerId = winner.id
        runnerUp = { id: winner.id, summary: winner.summary }
        // Reassign winner fields to refine entry (winner is const but mutable)
        winner.id = refineEntry.id
        winner.summary = refineEntry.summary
        finalRationale = `PDR refine (${refineId}) beat tournament winner (${prevWinnerId}). Reason: ${finalVerdict.reason}`
        log(`PDR refine superseded tournament winner`)
      } else {
        finalRationale = `Tournament winner (${winner.id}) held against PDR refine. Reason: ${finalVerdict.reason}`
        log(`Tournament winner held against PDR refine`)
      }
    } else {
      finalRationale = `PDR refine ran but judge returned invalid verdict — tournament winner (${winner.id}) retained.`
    }
  } else {
    finalRationale = `PDR refine agent failed — tournament winner (${winner.id}) retained. Approach: ${winner.summary.approach}`
  }
}

// ── Final Output ─────────────────────────────────────────────────────────────

return {
  winner: {
    id: winner.id,
    summary: winner.summary,
  },
  runner_up: runnerUp ? { id: runnerUp.id, summary: runnerUp.summary } : null,
  rounds: roundNum,
  rationale: finalRationale,
}
