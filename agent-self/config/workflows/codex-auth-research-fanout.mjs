// /codex-auth-research-fanout — schema-typed, artifact-first multi-wave research fan-out
//
// Authored with workflow-authoring skill (checklist at bottom of that skill):
//   - export const meta + phases
//   - schema on every fan-in; required[] = FLOOR only (no conditional fields)
//   - .filter(Boolean) after every parallel()
//   - small homogeneous barriers (default batch=4)
//   - no Date.now() / Math.random() / new Date() in workflow JS
//   - agents auto-discover catalog + ground truth from live files (args = one string)
//   - pure-JS batch chunking (no extra plan agent — deterministic + resume-cache friendly)
//   - write-first disk contract; C1 Gate re-validates status_fanout vs disk
//   - research agents Write only their own artifact path (no shared git mutation)
//
// Invoke (Claude Code workflows runtime):
//   /codex-auth-research-fanout
//   /codex-auth-research-fanout wave=source batch=4
//   /codex-auth-research-fanout wave=all batch=3
//
// Optional args string (one string — parse yourself):
//   wave=all|source|physics|supply-chain|threat-intel|control-plane|consistency|deep-search
//   batch=2..6 (default 4)
//
// Disk root (auto-discovered by agents):
//   C:/Users/Prekzursil/scratch/codex-auth-research-fanout/
//
// Truth table:
//   DONE  = artifact >=1024B AND ends with UNIT-COMPLETE: <id>
//   IGNORE = CODEX THREADS idle / rollout mtime / process exit alone
// Companion C1: python status_fanout.py

export const meta = {
  name: 'codex-auth-research-fanout',
  description:
    'Artifact-first Codex auth.json research fan-out: batched parallel lenses, UNIT-COMPLETE AND-gate, C1 status (not CODEX THREADS idle). Resume-safe.',
  phases: [
    { title: 'Ground', detail: 'load catalog + count disk AND-gate DONE; never trust CODEX THREADS' },
    { title: 'Fan-out', detail: 'homogeneous batches of N research agents; write-first disk contract' },
    { title: 'Gate', detail: 're-count artifacts; classify DONE vs missing; exercise monitor robustness' },
    { title: 'Synthesize', detail: 'owner playbook from delivered digests + open gaps' },
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

const ROOT = 'C:/Users/Prekzursil/scratch/codex-auth-research-fanout'
const CATALOG = `${ROOT}/units_catalog.json`
const ARTIFACTS = `${ROOT}/artifacts`
const STATUS_PY = `${ROOT}/status_fanout.py`
const STATE_DIR = `${ROOT}/state`

// Stable shared prefix (cache-cliff-aware) — no volatile timestamps / random ids
const GROUND_TRUTH = `
[REQUIRED] VERIFIED GROUND TRUTH — established by direct inspection before this workflow.
Treat as high-confidence. Each claim is tagged [probe: …]. To confirm OR refute you MUST use a
mechanically DIFFERENT probe. Re-running the tagged probe does NOT count as CONFIRMED.
1. auth_mode=chatgpt; local CODEX_HOME auth.json is the OAuth cache  [probe: redacted JWT + openai/codex login storage]
2. id_token ~1h; access_token ~10d aud=https://api.openai.com/v1; client_id app_EMoamEEZ73f0CkXaXp7hrann  [probe: JWT exp-iat]
3. refresh POST https://auth.openai.com/oauth/token; refresh_token_reused => Exhausted  [probe: manager.rs public source]
4. TOKEN_REFRESH_INTERVAL ~8 days; access refresh window ~5 minutes  [probe: manager.rs constants]
5. Dual-writer / dual CODEX_HOME refresh races kill fleets  [probe: openai/codex issues + openclaw #62247 class]
6. CODEX_ACCESS_TOKEN / ChatgptAuthTokens = AT-only path without RT  [probe: manager.rs]
7. 2026 npm codexui-class packages harvested auth.json  [probe: CSA/THN public writeups]
8. Browser next-auth cookies != CLI OAuth grant  [probe: cookie policy + token aud]
9. Owner-ops only: never print tokens/JWTs/emails; never modify live auth.json
10. CODEX THREADS IDLE is NOT done — only disk UNIT-COMPLETE is done  [probe: status_fanout C1]

[REQUIRED] ANTI-OVERFIT ANCHOR — proposals only if they (a) ride EXISTING owner control plane
(CODEX_HOME pin, lease, AT-only workers, allowlist), and (b) do not reintroduce browser-cookie
login from CLI tokens or dual-writer refresh. Prefer enable/native over new daemon.
`

const HARD = `
ENVIRONMENT: Windows 11, PowerShell 7 primary. Prefer raw.githubusercontent.com/openai/codex/main/...
for source lenses if local clone path fails. Full public web for threat-intel / supply-chain.

[REQUIRED] HONESTY CONTRACT (global contract does NOT inherit into fan-out — these apply here):
- Attach UNVERIFIED INLINE to the sentence it qualifies. End-of-doc limitations do NOT satisfy this.
- Every UNVERIFIED names the experiment that would settle it.
- "Absent / not found / broken" is a claim — verify detector finds a known-present item first.
- Do not report CONFIRMED on a probe that is the same mechanism as the one being checked.
- If a tool is denied, you are in a subagent — no user will answer. Record gap, use alternative.

NO: account takeover, buying sessions, stealer construction, C2 recipes, printing live secrets.
`

// Schema floor only — conditional fields optional (workflow-authoring rule 7)
const DIGEST = {
  type: 'object',
  additionalProperties: false,
  required: ['unit_id', 'delivered', 'bytes', 'digest', 'evidence'],
  properties: {
    unit_id: { type: 'string' },
    delivered: {
      type: 'boolean',
      description: 'true only if you verified the artifact exists on disk with UNIT-COMPLETE',
    },
    bytes: { type: 'number', description: 'artifact byte size after write; 0 if missing' },
    artifact: { type: 'string', description: 'absolute path written' },
    digest: {
      type: 'string',
      description: '<=400 words structured digest; lead with corrections to ground truth',
    },
    evidence: {
      type: 'array',
      items: { type: 'string' },
      description: '3-5 file:line or URL anchors; exempt from word cap',
    },
    blocker: { type: 'string', description: 'optional; why incomplete' },
  },
}

const GATE = {
  type: 'object',
  additionalProperties: false,
  required: ['done', 'total', 'missing', 'banner', 'monitor_ok'],
  properties: {
    done: { type: 'number' },
    total: { type: 'number' },
    missing: { type: 'array', items: { type: 'string' } },
    banner: { type: 'string' },
    monitor_ok: {
      type: 'boolean',
      description:
        'true if status_fanout disk_done matches AND-gate and never claims all-done early',
    },
    notes: { type: 'string' },
  },
}

const SYNTH = {
  type: 'object',
  additionalProperties: false,
  required: ['playbook_path', 'done', 'total', 'top_findings', 'open_gaps'],
  properties: {
    playbook_path: { type: 'string' },
    done: { type: 'number' },
    total: { type: 'number' },
    top_findings: { type: 'array', items: { type: 'string' } },
    open_gaps: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
}

// ---- args: one string; default wave=all batch=4 ----
const ARGS = typeof args === 'string' ? args : ''
const WAVE = (ARGS.match(/wave=([a-z-]+)/i) || [, 'all'])[1]
const BATCH = Math.min(6, Math.max(2, parseInt((ARGS.match(/batch=(\d+)/i) || [, '4'])[1], 10) || 4))

function chunkIds(ids, size) {
  const out = []
  for (let i = 0; i < ids.length; i += size) {
    out.push(ids.slice(i, i + size))
  }
  return out
}

// ---- Phase: Ground ----
phase('Ground')
const ground = await agent(
  `You are the GROUND agent for the codex-auth research fan-out.
${HARD}
${GROUND_TRUTH}

TASK (counts only — do not re-research units):
1) Read the live catalog at ${CATALOG} (JSON). Count units (expect unit_count or units.length).
2) For each unit, check whether its artifact path under ${ROOT} exists, is >=1024 bytes, and the
   last ~600 bytes contain the exact line UNIT-COMPLETE: <id>.
3) Run: python "${STATUS_PY}" and capture the first-line banner.
4) List missing unit ids (AND-gate fail), filtered by wave="${WAVE}" if wave is not "all"
   (match unit.phase). Skip units already DONE (e.g. A01, A02 if present).
5) Write resume manifest with the Write tool to ${STATE_DIR}/workflow-ground.json:
   {done,total,missing,wave,batch:${BATCH},banner}
6) monitor_ok: true if status_fanout DONE count equals your independent AND-gate count AND
   status never claims done==total while disk is less.

Return GATE schema: done, total, missing, banner, monitor_ok, notes.`,
  {
    label: 'ground-c1',
    phase: 'Ground',
    schema: GATE,
    effort: 'medium',
  },
)

// ---- Phase: Fan-out (batched parallel; pure-JS chunking; small homogeneous barriers) ----
phase('Fan-out')

// Prefer ground.missing; if ground failed/null, a fallback ground re-read is allowed once.
let missingIds = Array.isArray(ground?.missing) ? ground.missing.filter(Boolean) : []

if (!Array.isArray(ground?.missing)) {
  const fallback = await agent(
    `GROUND FALLBACK: ground agent returned null/invalid.
Read ${CATALOG}. For each unit check AND-gate on ${ROOT}/<artifact>.
Wave filter: ${WAVE}. Return GATE schema with missing = ids still needed.
Do not invent ids. Prefer running python "${STATUS_PY}".`,
    { label: 'ground-fallback', phase: 'Fan-out', schema: GATE, effort: 'medium' },
  )
  missingIds = Array.isArray(fallback?.missing) ? fallback.missing.filter(Boolean) : []
}

const batches = chunkIds(missingIds, BATCH)
const allDigests = []

for (let bi = 0; bi < batches.length; bi++) {
  const ids = batches[bi]
  // one-level parallel; null-tolerant barrier (workflow-authoring rules 5–7)
  const waveResults = h6Survivors(await settle(
      ids.map(
        (uid) => () =>
          agent(
            `You are a FRESH research lens for unit ${uid}.
${HARD}
${GROUND_TRUTH}

AUTO-DISCOVER (args are unreliable — read live files):
1) Read ${CATALOG} and find the unit object whose id is exactly "${uid}".
2) Use its title, task, phase, and artifact path (relative to ${ROOT}).
3) Prefer primary sources: raw.githubusercontent.com/openai/codex/main/… for source-phase units.

=== YOUR TASK (${uid}) ===
Execute the unit.task from the catalog. Be concrete about THIS axis, not generic OAuth advice.

[REQUIRED] PER-FINDING RUBRIC — for every RECOMMENDATION (skip pure audit facts):
  name / what / why THIS owner specifically / how (file, command, policy) / source file:line or URL /
  value (H|M|L) x effort (H|M|L) /
  disposition: NATIVE | ADOPT | BUILD | PRUNE /
  confidence: almost-certain 90-99% | likely 55-80% | roughly-even 45-55% | unlikely 20-45% + evidence.

[REQUIRED] OUTPUT CONTRACT
1) Write the FULL analysis with the Write tool to:
   ${ROOT}/<unit.artifact>
   Create parent directories if needed. If one Write is too large, chunk with PowerShell Add-Content —
   never build a multi-KB literal inside a shell command string (Windows 32k CreateProcess limit).
2) End the file with a line that is exactly:
   UNIT-COMPLETE: ${uid}
3) Immediately stop after a successful write. Prefer finishing the file over more searches.
4) If blocked, still write a partial file + UNIT-COMPLETE + BLOCKER section.
5) Flush a partial artifact early if long-running so a cohort interrupt does not zero the unit.

Then return the DIGEST schema (NOT the full doc):
- unit_id, delivered (true only if you verified Test-Path + size>=1024 + UNIT-COMPLETE line),
- bytes, artifact absolute path, digest (<=400 words; lead with ground-truth corrections),
- evidence[3-5] (exempt from word cap), optional blocker.

Final line of your digest text should conceptually match: DELIVERED: <abs path> (<n> bytes)
Session IDLE in a dashboard is NOT success. Disk is success.`,
            {
              label: `unit:${uid}`,
              phase: 'Fan-out',
              schema: DIGEST,
              effort: 'high',
              // Single-file artifact write; no shared git mutation → no worktree required
            },
          ),
      ),
    H6_TIMEOUT_MS))

  for (const d of waveResults) allDigests.push(d)
}

// ---- Phase: Gate (C1 monitor robustness) ----
phase('Gate')
const gate = await agent(
  `You are the C1 GATE / monitor robustness checker for the fan-out.

1) Run: python "${STATUS_PY}"
2) Independently re-count AND-gate passes by scanning ${ARTIFACTS} for *.md whose tail contains UNIT-COMPLETE.
3) Compare status_fanout DONE count to your independent count.
4) never_claims_all_done_early: if status says done==total but disk is less, monitor_ok=false.
5) List missing unit ids still without AND-gate pass (from ${CATALOG}).
6) Append ONE JSON line to ${STATE_DIR}/monitor_robustness.jsonl using PowerShell Add-Content.
   Get the timestamp INSIDE the shell with Get-Date -Format o — do NOT invent clocks in pure thought.
   Fields: ts, checks{status_exit_0,parsed_banner,disk_done_matches_status,never_claims_all_done_early,disk_done,status_done,status_running,status_abandoned,total}, banner

Return GATE schema accurately. Trust disk + status_fanout, never CODEX THREADS.`,
  { label: 'c1-gate', phase: 'Gate', schema: GATE, effort: 'medium' },
)

// ---- Phase: Synthesize ----
phase('Synthesize')
const digestPack = allDigests
  .map(
    (d) =>
      `### ${d.unit_id} delivered=${d.delivered} bytes=${d.bytes}\n${(d.digest || '').slice(0, 600)}\nEVIDENCE: ${(d.evidence || []).join(' | ')}`,
  )
  .join('\n\n')

const synth = await agent(
  `You synthesize the owner multi-agent Codex auth playbook.
${HARD}
${GROUND_TRUTH}

GATE RESULT: done=${gate?.done} total=${gate?.total} monitor_ok=${gate?.monitor_ok}
MISSING: ${(gate?.missing || []).slice(0, 40).join(', ')}

DIGESTS FROM THIS RUN (may be partial vs full catalog):
${digestPack.slice(0, 120000)}

Also Glob/Read any completed artifacts under ${ARTIFACTS}/**/*.md that end with UNIT-COMPLETE.

Write playbook to:
  ${ROOT}/artifacts/SYNTHESIS-owner-playbook.md
End with UNIT-COMPLETE: SYNTHESIS

Playbook must cover: single-writer rule, AT-only workers, supply-chain allowlist, re-login runbook,
what NOT to trust (CODEX THREADS idle), how to run status_fanout, dual-CODEX_HOME races.

Return SYNTH schema with top_findings and open_gaps.`,
  { label: 'synthesize', phase: 'Synthesize', schema: SYNTH, effort: 'high' },
)

return {
  wave: WAVE,
  batch: BATCH,
  ground,
  digests_returned: allDigests.length,
  digests: allDigests,
  gate,
  synth,
  tip: 'Trust status_fanout / UNIT-COMPLETE on disk — never CODEX THREADS idle/done counters.',
  invoke: '/codex-auth-research-fanout wave=all batch=4',
}
