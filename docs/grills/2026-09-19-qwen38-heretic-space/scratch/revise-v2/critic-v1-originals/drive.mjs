// Independent adversarial fake-harness drive of design-v1 §13 (critic-v1). Nothing here calls a real agent.
import { makeScript } from './assembled.mjs'

const SHA = n => (String(n).padStart(2, '0')).repeat(20)          // 40-hex deterministic shas
const HEX = n => (String(n).padStart(2, '0')).repeat(32)          // 64-hex digests
const GATE_SHA = HEX(7), BASE_SHA = HEX(8), BASE = SHA(1)
const R = '/workspaces/space-build', WT = R + '-wt'
const COMMON = { repo_toplevel: WT + '/x', git_common_dir: R + '/.git', outward_actions_taken: [], installed_packages: [], notes: 'ok' }

function baseArgs(extra) {
  return Object.assign({
    stage: 'build', run_nonce: 'r1a', launched_at: '2026-09-19T00:00:00Z', cap: 2, wave_size: 2,
    build_repo: R, snapshot_dir: '/workspaces/snap', venv: '/workspaces/space-build-venv', wheels_dir: '/workspaces/wheels', libsrc: '/workspaces/space-build-libsrc', tools_dir: '/workspaces/space-build-tools',
    gate_sh: '/workspaces/space-build-tools/gate.sh', gate_sha256: GATE_SHA, baseline_path: '/workspaces/space-build-tools/baseline.json', baseline_sha256: BASE_SHA,
    base_sha: BASE, toolchain_status_sha256: HEX(9), resume_mode: 'git', max_agents_this_run: 110,
    plan_sha: SHA(2), owner_approvals: { github_repo_url: null, staging_space_ids: [], fixture1_path: null, persona_boundary_fixture_path: null, worker_checkpoint_decision: null },
    decision_queue_path: '/g/DQ.md', lens4_path: '/g/l4.md', findings_path: '/g/f.md', redteam_path: '/g/rt.md', unverified_finding_ids: ['critic-1', 'critic-4'], against_recommendation_ids: ['G-1', 'G-3', 'G-2', 'M-5', 'G-15+G-24'], catalog_candidates: ['a/b'],
  }, extra || {})
}

function card(id, deps, files, extra) {
  return Object.assign({ id, path: 'plan/cards/' + id + '.json', step: 1, depends_on: deps, files_allowed: files, tests_allowed: [], new_modules: [], deps_allowed: [], xfail_allowed: [], tests_removed_expected: 0, est_lines: 100, est_minutes: 20,
    dod: [{ id: 'D1', command: 'pytest tests/unit/test_' + id + '.py', expect: 'exit0', verification_level: 'local-stub' }], size: 'S', risk: 'none', protected_touch: id === 'platform-01-gate', bootstrap: id === 'platform-01-gate', decision_ids: [], finding_ids: [], apis_expected: [], owner_precondition: '' }, extra || {})
}
const PLAN3 = [card('platform-01-gate', [], ['tools/gate.sh']), card('platform-02-pins', ['platform-01-gate'], ['core/prompting.py']), card('platform-03a-types-fake', ['platform-01-gate'], ['core/types.py'])]

// ---- the fake harness ------------------------------------------------------------------------
function makeHarness(scn, args) {
  const calls = [], logs = [], batches = []
  let counter = 0
  const H = {
    args, log: m => logs.push(String(m)), phase: () => {},
    budget: scn.budget || { total: null, spent: () => 0, remaining: () => Infinity },
    parallel: async thunks => Promise.all(thunks.map(async t => { try { return await t() } catch (e) { return null } })),
    pipeline: async (items, ...stages) => { batches.push(items.map(i => i && i.id)); return Promise.all(items.map(async (it, i) => { let prev = it; try { for (const s of stages) prev = await s(prev, it, i) } catch (e) { return null } return prev })) },
    agent: async (prompt, opts) => {
      const n = ++counter, label = (opts && opts.label) || ''
      calls.push({ n, label, prompt, opts })
      const [role, mode, ...rest] = label.split(':'); const id = rest.join(':')
      const r = scn.reply({ n, role, mode, id, label, prompt, opts, calls })
      if (r && typeof r === 'object' && !r.__raw) return Object.assign({}, COMMON, r)
      return r === undefined ? null : r
    },
  }
  return { H, calls, logs, batches }
}
// default happy replies per role/mode; scenarios override
function happy(ctx, st) {
  const { role, mode, id } = ctx
  const cid = id.replace(/:.*$/, '')
  if (role === 'integrator' && mode === 'setup') return Object.assign({ status: 'SUCCESS', venv_python: '3.12.3', nproc: 4, base_sha_ok: true, gate_sha256: GATE_SHA, baseline_sha256: BASE_SHA, baseline_collected: 73, baseline_skipped: 0, red_proof: { broken_red: true, false_claim_red: 'fixture-not-yet-delivered', digest: HEX(1) }, integration_head_live: st.head, plan_merged: true, branch_heads: [], merged_on_integration: st.mergedOnGit || [], remotes: [], prior_rows: st.priorRows || [], seen_keys: st.seenKeys || [], worktrees_pruned: 0 }, st.setupOverride || {})
  if (role === 'verifier' && mode === 'index') return { status: 'SUCCESS', plan_sha: SHA(2), decisions_path: 'plan/decisions.json', api_ledger_path: 'plan/api-ledger.json', preverified_path: 'plan/preverified.json', decisions: [], cards: st.cards, unmapped_finding_ids: [] }
  if (role === 'author' && mode === 'tests') return { status: 'SUCCESS', card_id: cid, branch: 'tests/' + cid + '-r1a', base_sha: st.head, tests_head: SHA(10 + st.seq(cid, 'tests')), test_paths: ['tests/unit/test_' + cid + '.py'], commits_made: 1, red_command: 'gate.sh --only-tests', red_exit_code: 1, red_excerpt: 'FAILED', gate_digest: HEX(2), known_bads_xfail: [], mutants_suggested: [] }
  if (role === 'author' && mode === 'journeys') return { status: 'SUCCESS', card_id: 'journeys', branch: 'task/journeys', base_sha: st.head, tests_head: SHA(70 + (st.j = (st.j || 0) + 1)), test_paths: ['tests/journeys/test_h.py'], commits_made: 1, red_command: 'x', red_exit_code: 1, red_excerpt: '', gate_digest: HEX(2) }
  if (role === 'verifier' && mode === 'red') { const th = /at ([0-9a-f]{40})\./.exec(ctx.prompt); return verdict('red', cid, th ? th[1] : SHA(0), 'pass', { gate_digest: HEX(3) }) }
  if (role === 'builder') { const h = SHA(30 + st.seq(cid, 'build')); st.lastBuild[cid] = h; return { status: 'done', card_id: cid, branch: 'task/' + cid + '-r1a', base_sha: st.head, head_sha: h, commits_made: 2, changed_files: ['x.py'], dod: [{ id: 'D1', command: 'pytest', exit_code: 0, output_tail: 'ok' }], apis_used: [], gate_exit_code: 0, gate_digest: HEX(40 + st.seq(cid, 'build')), gate_profile: cid === 'platform-01-gate' ? 'bootstrap' : 'full', remaining_dod_ids: [] } }
  if (role === 'verifier' && mode === 'verify') { const h = st.lastBuild[cid]; return verdict('verify', cid, h, 'pass', { ledger_head_sha: h, gate_digest: HEX(40 + st.seqPeek(cid, 'build')), gate_profile: cid === 'platform-01-gate' ? 'bootstrap' : 'full', hunks_cited: ['x.py:1@' + h], checks: [{ name: 'gate', command: 'bash gate.sh --card', exit_code: 0, output_tail: 'LEDGER_DIGEST' }], dod_reruns: [{ id: 'D1', exit_code: 0 }], mutants: { written: 3, killed: 3 }, revert_proof: { observed: 'red', command: 'gate.sh --revert-proof' }, diff_stats: { files: 1, insertions: 10, deletions: 2 } }) }
  if (role === 'integrator' && (mode === 'merge' || mode === 'ff')) { st.head = SHA(50 + (st.m = (st.m || 0) + 1)); return merge('merge', cid, 'merged', st.head) }
  if (role === 'integrator' && mode === 'revert') { st.head = SHA(90); return merge('revert', cid, 'merged', st.head) }
  if (role === 'integrator' && mode === 'clean') return merge('clean-gate', 'w', 'ok', st.head, { journeys: { collected: 1, failed: 0, skipped_needs: [] }, self_test: { broken_red: true, false_claim_red: 'true' }, toolchain_status_sha256: HEX(9) })
  if (role === 'verifier' && mode === 'review') return verdict('review', 'tree', st.head, 'pass', { findings: [], probes_used: ['grep'] })
  if (role === 'verifier' && mode === 'refute') return verdict('refute', id, st.head, 'refuted', {})
  if (role === 'verifier' && mode === 'veto') return verdict('veto', 'tree', st.head, 'no-veto', { findings: [] })
  if (role === 'verifier' && mode === 'evidence') return verdict('evidence', 'stage', st.head, 'pass', { findings: st.evidenceFindings || [] })
  if (role === 'synthesizer') return { status: 'SUCCESS', report_path: '/g/RUN-REPORT.md', report_bytes: 10, status_json_path: '/g/status.json', rows: ctx.__rows || [], owner_actions: [], what_would_most_improve_confidence: 'x' }
  if (role === 'verifier' && mode === 'preverify') return verdict('preverify', id, BASE, 'refuted', { findings: [{ id, title: 't', file: 'f', severity: 'low', kind: 'correctness', reproduction: { command: 'c', exit_code: 0, output_tail: '' }, corrected_claim: 'nope', verification_level: 'local-mechanical' }] })
  if (role === 'planner' && mode === 'apiledger') return verdict('plan', 'ledger', SHA(2), 'pass', {})
  if (role === 'verifier' && mode === 'catalog') return verdict('catalog', 'cat', 'none', 'pass', { findings: [] })
  if (role === 'planner' && mode === 'plan') return { status: 'SUCCESS', plan_sha: SHA(2), decisions_path: 'p', api_ledger_path: 'p', preverified_path: 'p', decisions: [{ id: 'G-1', decided_value: 'x', against_recommendation: true, consequences: [], dq_line: 85 }], cards: st.cards, unmapped_finding_ids: [] }
  if (role === 'verifier' && mode === 'plan') return verdict('plan', 'index', SHA(2), 'pass', {})
  return null
}
function verdict(mode, target, sha, v, o) { return Object.assign({ status: 'SUCCESS', mode, target_id: target, sha, verdict: v, ledger_sha256: HEX(5), ledger_head_sha: sha, gate_exit_code: 0, gate_digest: HEX(3), gate_profile: 'full', gate_sha256_observed: GATE_SHA, checks: [], dod_reruns: [], failures: [], hunks_cited: [], idiom_hits: 0, warnings_cleared: [], mutants: { written: 0, killed: 0 }, revert_proof: { observed: 'not-run', command: '' }, findings: [], probes_used: [], strongest_disagreement: 'none', judge_rail: 'claude-fresh' }, o) }
function merge(mode, cid, status, head, o) { return Object.assign({ status, mode, card_id: cid, branch: 'task/' + cid, before_sha: SHA(0), head_sha: head, ledger_sha256: HEX(5), gate_digest: HEX(6), gate_exit_code: 0, gate_sha256_observed: GATE_SHA, cherry_unmerged: [], patch_ids_missing: [], conflicts: [], remotes: [] }, o) }
function state(cards, o) { const seqs = {}; return Object.assign({ cards, head: SHA(3), lastBuild: {}, seq: (c, k) => (seqs[c + k] = (seqs[c + k] || 0) + 1), seqPeek: (c, k) => seqs[c + k] || 0 }, o || {}) }

// ---- assertions ------------------------------------------------------------------------------
const results = []
function assert(name, cond, detail) { results.push({ name, ok: !!cond, detail }); console.log((cond ? 'PASS ' : 'FAIL ') + name + (detail ? '  -- ' + detail : '')) }
async function runScenario(title, args, scn) {
  console.log('\n=== ' + title)
  const { H, calls, logs, batches } = makeHarness(scn, args)
  let out, err = null
  try { out = await makeScript(H) } catch (e) { err = e }
  return { out, err, calls, logs, batches }
}

// S1 happy path, 3 cards, wave rule --------------------------------------------------------------
{
  const st = state(PLAN3)
  const r = await runScenario('S1 happy build, 3 cards', baseArgs(), { reply: ctx => happy(ctx, st) })
  assert('S1 no throw', !r.err, r.err && r.err.message)
  assert('S1 all three merged', r.out && r.out.rows.filter(x => x.state === 'merged+gate-green').length === 3, JSON.stringify(r.out && r.out.rows.map(x => [x.task_id, x.state])))
  assert('S1 checkpoint status blocked (C1 actions outstanding), not ready', r.out && r.out.status === 'blocked', r.out && r.out.status)
  assert('S1 stop_reason satisfied', r.out && r.out.stop_reason === 'satisfied', r.out && r.out.stop_reason)
  assert('S1 wave 1 = [01] alone, wave 2 = [02, 03a]', JSON.stringify(r.batches.slice(0, 2)) === JSON.stringify([['platform-01-gate'], ['platform-02-pins', 'platform-03a-types-fake']]), JSON.stringify(r.batches))
  const labels = r.calls.map(c => c.label); assert('S1 labels unique', new Set(labels).size === labels.length)
  assert('S1 every agent call has phase+schema', r.calls.every(c => c.opts && c.opts.phase && c.opts.schema))
  const vp = r.calls.find(c => c.label.startsWith('verifier:verify:')).prompt
  assert('S1 verify prompt never carries the builder digest', !vp.includes(HEX(41)) && !vp.includes(HEX(40)))
  assert('S1 parked rows carry NO reason field (owner cannot act)', r.out && Array.isArray(r.out.parked) && (r.out.rows.length === 0 || !('reason' in r.out.rows[0])), JSON.stringify(Object.keys((r.out && r.out.rows[0]) || {})))
  const fixPrompts = r.calls.filter(c => /journeys/.test(c.label)); assert('S1 journeys author ran after seam card 03a? (03a is not a seam card; expect none)', fixPrompts.length === 0)
}

// S2 schema-valid-but-empty verifier --------------------------------------------------------------
{
  const st = state(PLAN3.slice(0, 1))
  const r = await runScenario('S2 empty-but-valid verifier', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'verify') Object.assign(h, { hunks_cited: [], mutants: { written: 0, killed: 0 }, dod_reruns: [], checks: [] }); return h } })
  assert('S2 card not merged', r.out && r.out.rows[0].state !== 'merged+gate-green', r.out && r.out.rows[0].state)
  assert('S2 parked with fix-exhausted (bounded)', r.logs.some(l => /fix-exhausted|no-progress/.test(l)) || (r.out && r.out.rows[0].state === 'parked'), r.out && JSON.stringify(r.out.rows))
  assert('S2 exactly 3 build calls (MAX_BUILD)', r.calls.filter(c => c.label.startsWith('builder:')).length === 3, String(r.calls.filter(c => c.label.startsWith('builder:')).length))
}

// S3 verifier agrees but its own gate digest differs (builder ran the gate at an earlier commit / dirty tree) -------
{
  const st = state(PLAN3.slice(0, 1))
  const r = await runScenario('S3 verifier pass with a different digest', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'verify') h.gate_digest = HEX(99); return h } })
  assert('S3 digest mismatch blocks the card', r.out && r.out.rows[0].state === 'parked', r.out && r.out.rows[0].state)
  const fixer = r.calls.find(c => c.label.startsWith('builder:fix:'))
  assert('S3 the fixer receives NO actionable failure for a digest mismatch (failures empty)', fixer && /"failures": \[\]/.test(fixer.prompt), fixer && fixer.prompt.slice(fixer.prompt.indexOf('FAILING EVIDENCE'), fixer.prompt.indexOf('FAILING EVIDENCE') + 200))
  assert('S3 fingerprint empty → two-strikes never fires → all 3 builds spent', r.calls.filter(c => c.label.startsWith('builder:')).length === 3)
}

// S4 implementer reports [] outward actions but the merge shows a new remote -----------------------------
{
  const st = state(PLAN3.slice(0, 1))
  const r = await runScenario('S4 hidden remote surfaces at merge', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'merge') h.remotes = ['origin\tgit@github.com:x/y (push)']; return h } })
  assert('S4 HALT remote-added', r.out && /remote-added/.test(r.out.halt || ''), r.out && r.out.halt)
  assert('S4 checkpoint failed', r.out && r.out.status === 'failed', r.out && r.out.status)
  assert('S4 no agent launched after HALT except synthesizer', r.calls.filter(c => c.n > r.calls.find(c => c.label.startsWith('integrator:merge')).n).every(c => c.label.startsWith('synthesizer')), r.calls.map(c => c.label).join(','))
  assert('S4 card row still says merged+gate-green although the run halted on its merge', r.out && r.out.rows[0].state === 'merged+gate-green', r.out && r.out.rows[0].state)
}

// S5 two cards with overlapping write sets ---------------------------------------------------------------
{
  const cards = [card('platform-01-gate', [], ['tools/gate.sh']), card('platform-02-pins', ['platform-01-gate'], ['core/x.py']), card('platform-03a-types-fake', ['platform-01-gate'], ['core/x.py'])]
  const st = state(cards)
  const r = await runScenario('S5 overlapping write sets', baseArgs(), { reply: ctx => happy(ctx, st) })
  assert('S5 overlapping cards never share a pipeline batch', r.batches.every(b => b.length === 1), JSON.stringify(r.batches))
  assert('S5 wait logged', r.logs.some(l => /wait \(size or write-set overlap\)/.test(l)))
}

// S6 gate returns exit 0 with no ledger (clean gate) → what happens to the good merge? --------------------------
{
  const st = state(PLAN3.slice(0, 1))
  const r = await runScenario('S6 clean gate exit 0 but empty digest', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'clean') h.gate_digest = ''; return h } })
  assert('S6 malformed clean gate does NOT revert a good merge (expected gate-unavailable/malformed)', !r.calls.some(c => c.label.startsWith('integrator:revert')), 'revert calls: ' + r.calls.filter(c => c.label.startsWith('integrator:revert')).length)
  const st2 = state(PLAN3.slice(0, 1))
  const r2 = await runScenario('S6b clean gate without self_test field (schema-valid, optional)', baseArgs(), { reply: ctx => { const h = happy(ctx, st2); if (ctx.mode === 'clean') delete h.self_test; return h } })
  assert('S6b missing self_test does NOT revert a good merge', !r2.calls.some(c => c.label.startsWith('integrator:revert')), 'revert calls: ' + r2.calls.filter(c => c.label.startsWith('integrator:revert')).length)
}

// S7 clean-gate null in the last wave, then resume ---------------------------------------------------------------
{
  const st = state(PLAN3.slice(0, 1))
  const r = await runScenario('S7 null clean gate, last wave', baseArgs(), { reply: ctx => (ctx.mode === 'clean' ? null : happy(ctx, st)) })
  assert('S7 no revert on a dropped clean gate', !r.calls.some(c => c.label.startsWith('integrator:revert')))
  assert('S7 stop is dry(2) / not satisfied', r.out && r.out.stop_reason !== 'satisfied', r.out && r.out.stop_reason)
  assert('S7 review lenses ran although the tree was never clean-gated (wasted agents)', r.calls.filter(c => c.label.startsWith('verifier:review')).length >= 3, String(r.calls.filter(c => c.label.startsWith('verifier:review')).length))
  // resume with next_args
  const na = r.out.next_args
  const st2 = state(PLAN3.slice(0, 1), { head: na.integration_sha_at_launch, mergedOnGit: ['platform-01-gate'], priorRows: r.out.rows })
  const r2 = await runScenario('S7b resume after the null clean gate', baseArgs({ stage: na.stage, integration_sha_at_launch: na.integration_sha_at_launch, last_clean_gate: na.last_clean_gate, prior_status_path: '/g/status.json' }), { reply: ctx => happy(ctx, st2) })
  assert('S7b resume re-runs a clean gate at the current head before reviewing', r2.calls.some(c => c.label.startsWith('integrator:clean')), 'clean calls: ' + r2.calls.filter(c => c.label.startsWith('integrator:clean')).length + ' stop=' + (r2.out && r2.out.stop_reason))
  assert('S7b resume can reach satisfied', r2.out && r2.out.stop_reason === 'satisfied', r2.out && r2.out.stop_reason)
}

// S8 budget exhaustion mid-wave ---------------------------------------------------------------------------------
{
  const st = state(PLAN3)
  let spent = 0
  const budget = { total: 1000000, spent: () => spent, remaining: () => 1000000 - spent }
  const r = await runScenario('S8 budget crosses RESERVE mid-wave', baseArgs(), { budget, reply: ctx => { spent += ctx.n >= 8 ? 200000 : 1000; return happy(ctx, st) } })
  const parked = r.out ? r.out.rows.filter(x => /parked/.test(x.state)) : []
  console.log('   rows:', JSON.stringify(r.out && r.out.rows.map(x => [x.task_id, x.state])), 'log tail:', r.logs.filter(l => /BUDGET|parked|NOT integrated|blocked/.test(l)).slice(0, 6))
  assert('S8 budget-starved cards are not_attempted (retryable), not parked', parked.length === 0, JSON.stringify(parked))
  assert('S8 next_args.stage repeats build', r.out && r.out.next_args.stage === 'build', r.out && r.out.next_args.stage)
  // resume: prior rows adopted
  if (r.out) {
    const st2 = state(PLAN3, { head: r.out.next_args.integration_sha_at_launch, mergedOnGit: r.out.rows.filter(x => x.state === 'merged+gate-green').map(x => x.task_id), priorRows: r.out.rows })
    const r2 = await runScenario('S8b resume after budget exhaustion', baseArgs({ integration_sha_at_launch: r.out.next_args.integration_sha_at_launch, prior_status_path: '/g/s.json' }), { reply: ctx => happy(ctx, st2) })
    assert('S8b the starved cards get built on resume without retry_parked', r2.out && r2.out.rows.filter(x => x.state === 'merged+gate-green').length === 3, JSON.stringify(r2.out && r2.out.rows.map(x => [x.task_id, x.state])))
  }
}

// S8c budget-ceiling throw ----------------------------------------------------------------------------------
{
  const st = state(PLAN3)
  const r = await runScenario('S8c agent() throws budget ceiling', baseArgs(), { reply: ctx => { if (ctx.n === 6) throw new Error('budget ceiling reached: spent >= total'); return happy(ctx, st) } })
  assert('S8c HALT budget-exhausted', r.out && r.out.halt === 'budget-exhausted', r.out && r.out.halt)
  assert('S8c synthesizer still ran', r.calls.some(c => c.label.startsWith('synthesizer')))
  assert('S8c no retry after the throw (call 7 is the synthesizer)', r.calls.length === 7, String(r.calls.length) + ' ' + r.calls.map(c => c.label).join(','))
}

// S9 resume where the launch sha changed ----------------------------------------------------------------------
{
  const st = state(PLAN3, { head: SHA(77) })
  const r = await runScenario('S9 stale launch sha', baseArgs({ integration_sha_at_launch: SHA(3) }), { reply: ctx => happy(ctx, st) })
  assert('S9 throws stale-launch-args → FAILED stop', r.out && /stale-launch-args/.test(r.out.stop_reason), r.out && r.out.stop_reason)
  assert('S9 no card agent launched', !r.calls.some(c => /^author|^builder/.test(c.label)))
  assert('S9 checkpoint failed and synth ran', r.out && r.out.status === 'failed' && r.calls.some(c => c.label.startsWith('synthesizer')))
}

// S10 secret-shaped string in output_tail -----------------------------------------------------------------------
{
  const st = state(PLAN3.slice(0, 1)); const SECRET = 'hf_' + 'A'.repeat(30)
  const r = await runScenario('S10 secret in builder output_tail', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.role === 'builder') h.dod[0].output_tail = 'token=' + SECRET; return h } })
  const leaked = r.calls.some(c => c.prompt.includes(SECRET)) || r.logs.some(l => l.includes(SECRET)) || JSON.stringify(r.out).includes(SECRET)
  assert('S10 secret never reaches any prompt/log/checkpoint', !leaked)
  assert('S10 card blocked secret-shaped-output', r.logs.some(l => /secret-shaped|SECRET-SHAPED/.test(l)) && r.out && r.out.rows[0].state === 'parked', r.out && JSON.stringify(r.out.rows))
  assert('S10 no fixer launched after the secret', !r.calls.some(c => c.label.startsWith('builder:fix')))
}

// S11 null from the veto judge ------------------------------------------------------------------------------------
{
  const st = state(PLAN3.slice(0, 1))
  const r = await runScenario('S11 veto judge null', baseArgs(), { reply: ctx => (ctx.mode === 'veto' ? null : happy(ctx, st)) })
  assert('S11 stop veto-unavailable', r.out && r.out.stop_reason === 'veto-unavailable', r.out && r.out.stop_reason)
  assert('S11 status not ready', r.out && r.out.status !== 'ready')
  assert('S11 veto retried once then parked (2 calls)', r.calls.filter(c => c.label.startsWith('verifier:veto')).length === 2, String(r.calls.filter(c => c.label.startsWith('verifier:veto')).length))
}

// S12 review finding → fix card: is the fix card buildable? ----------------------------------------------------
{
  const st = state(PLAN3.slice(0, 1)); let reviewed = 0
  const F = { id: 'RV-1', title: 'stop normaliser duplicated', file: 'core/x.py', severity: 'high', kind: 'correctness', reproduction: { command: 'grep -n normalize_stop core/x.py', exit_code: 0, output_tail: '2 defs' }, corrected_claim: 'one normaliser only', fix_hint: 'dedupe', files_allowed: ['core/x.py'], verification_level: 'local-mechanical' }
  const r = await runScenario('S12 fix card from a confirmed review finding', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'review' && ctx.id.includes('correctness') && reviewed++ === 0) h.findings = [F]; if (ctx.mode === 'refute') { h.verdict = 'holds'; h.findings = [F] } return h } })
  const fa = r.calls.find(c => c.label.startsWith('author:tests:platform-00-rf'))
  assert('S12 a fix card author was launched', !!fa)
  assert('S12 fix-card prompt names a plan/cards/<fixid>.json path that no agent ever wrote', fa && /plan\/cards\/platform-00-rf1-01-[a-z0-9-]+\.json/.test(fa.prompt) && !r.calls.some(c => /write .*plan\/cards\/platform-00-rf/.test(c.prompt)))
  assert('S12 fix-card prompt carries the finding text or DoD command (needed to be buildable)', fa && (fa.prompt.includes('grep -n normalize_stop') || fa.prompt.includes('one normaliser only')), 'absent')
  assert('S12 fix-card gate command passes --card plan/cards/<fixid>.json (file missing → python crash → RED)', fa && /--card plan\/cards\/platform-00-rf1-01/.test(fa.prompt))
}

// S13 parked root card + not_attempted dependents → satisfied()? -------------------------------------------------
{
  const st = state(PLAN3)
  const r = await runScenario('S13 root card parked (fix-exhausted)', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'verify' && ctx.id.startsWith('platform-01-gate')) h.verdict = 'fail'; return h } })
  console.log('   rows:', JSON.stringify(r.out && r.out.rows.map(x => [x.task_id, x.state])), 'stop=', r.out && r.out.stop_reason)
  assert('S13 review loop must NOT report satisfied on a tree with unbuilt cards', r.out && r.out.stop_reason !== 'satisfied', r.out && r.out.stop_reason)
  assert('S13 no review lenses spent on a one-card tree with 2 cards not attempted', !r.calls.some(c => c.label.startsWith('verifier:review')), String(r.calls.filter(c => c.label.startsWith('verifier:review')).length) + ' lenses')
  assert('S13 checkpoint not ready', r.out && r.out.status !== 'ready')
}

// S14 already-merged with a bogus head bypasses every check --------------------------------------------------------
{
  const st = state(PLAN3.slice(0, 1))
  const r = await runScenario('S14 integrator claims already-merged with a foreign head', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'merge') { h.status = 'already-merged'; h.head_sha = SHA(66); h.gate_exit_code = 1; h.gate_digest = ''; h.cherry_unmerged = ['deadbeef'] } return h } })
  assert('S14 already-merged without gate/cherry evidence must not count as merged', !(r.out && r.out.rows[0].state === 'merged+gate-green'), r.out && r.out.rows[0].state)
  assert('S14 head must not jump to an unverified sha', !(r.out && r.out.head_sha === SHA(66)), r.out && r.out.head_sha)
}

// S15 stage run: confirmed staging-evidence finding (canary failed) → promote-production? ----------------------------
{
  const F = { id: 'EV-1', title: 'canary failed: healthz git_sha mismatch ×3', file: 'evidence/staging/x/canary.json', severity: 'critical', kind: 'staging-evidence', reproduction: { command: 'jq .pass canary.json', exit_code: 1, output_tail: 'false' }, corrected_claim: 'canary did not pass', verification_level: 'staging-required' }
  const st = state(PLAN3, { head: SHA(3), mergedOnGit: PLAN3.map(c => c.id), evidenceFindings: [F] })
  const r = await runScenario('S15 stage with a failed canary in the evidence', baseArgs({ stage: 'stage', integration_sha_at_launch: SHA(3), last_clean_gate: { head_sha: SHA(3), digest: HEX(6) }, owner_approvals: { github_repo_url: 'u', staging_space_ids: ['a', 'b'], staging_evidence_dir: '/ev', fixture1_path: '/f', persona_boundary_fixture_path: '/p', worker_checkpoint_decision: { candidate: 'x', needs_export: false }, production_space_head: BASE } }), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'refute') { h.verdict = 'holds'; h.findings = [F] } return h } })
  console.log('   status=', r.out && r.out.status, 'stop=', r.out && r.out.stop_reason, 'actions=', r.out && r.out.actions.map(a => a.kind), 'blocked_on_owner=', r.out && r.out.blocked_on_owner.map(b => b.task_id))
  assert('S15 promote-production must NOT be emitted while a confirmed staging finding is blocked_on_owner', !(r.out && r.out.actions.some(a => a.kind === 'promote-production')), r.out && r.out.actions.map(a => a.kind).join(','))
  assert('S15 status must not be ready', r.out && r.out.status !== 'ready', r.out && r.out.status)
}

// S16 journeys merge prompt: does the merge gate run the journeys? ------------------------------------------------------
{
  const cards = [card('platform-01-gate', [], ['tools/gate.sh']), card('platform-03b-thin-slice', ['platform-01-gate'], ['api/app.py'])]
  const st = state(cards)
  const r = await runScenario('S16 seam card merges → journeys author → merge', baseArgs(), { reply: ctx => happy(ctx, st) })
  const jm = r.calls.find(c => c.label === 'integrator:merge:journeys-plan-w2')
  assert('S16 journeys author launched after the seam wave', r.calls.some(c => c.label.startsWith('author:journeys')))
  assert('S16 journeys merge gate command includes --journeys (else journeys skips fail the skip SET rule / never run at merge)', jm && /--journeys/.test(jm.prompt), jm ? jm.prompt.match(/bash [^\n]*gate\.sh[^\n]*/)[0].slice(0, 200) : 'no merge call')
}

// S17 plan stage: REFUTED finding cited → checkpoint --------------------------------------------------------------
{
  const cards = [card('platform-01-gate', [], ['tools/gate.sh'], { finding_ids: [{ id: 'critic-4', corrected_text: 'x'.repeat(30) }] })]
  const st = state(cards)
  const r = await runScenario('S17 plan cites a REFUTED finding', baseArgs({ stage: 'plan', plan_sha: undefined }), { reply: ctx => happy(ctx, st) })
  console.log('   status=', r.out && r.out.status, 'stop=', r.out && r.out.stop_reason, 'defects=', r.out && r.out.plan_defects, 'next=', r.out && r.out.next_args.stage, 'actions=', r.out && r.out.actions.map(a => a.kind))
  assert('S17 plan-needs-repair recorded', r.out && r.out.plan_defects && r.out.plan_defects.length > 0)
  assert('S17 approve-plan action must not be emitted for a plan that needs repair', !(r.out && r.out.actions.some(a => a.kind === 'approve-plan')), r.out && r.out.actions.map(a => a.kind).join(','))
  assert('S17 next_args.stage must not be build for a plan that needs repair', !(r.out && r.out.next_args.stage === 'build'), r.out && r.out.next_args.stage)
  // and R1 with the same defective plan
  const st2 = state(cards)
  const r2 = await runScenario('S17b build stage with the defective plan (REFUTED cite, manifest cards missing)', baseArgs(), { reply: ctx => happy(ctx, st2) })
  assert('S17b R1 refuses a plan whose card cites a REFUTED id / lacks manifest cards', r2.out && /FAILED/.test(r2.out.stop_reason), r2.out && r2.out.stop_reason)
}

console.log('\n==== SUMMARY: ' + results.filter(r => r.ok).length + ' passed, ' + results.filter(r => !r.ok).length + ' failed')
for (const r of results.filter(r => !r.ok)) console.log('FAILED: ' + r.name)
