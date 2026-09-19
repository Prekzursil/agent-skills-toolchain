// critic-v2 adversarial drive — INDEPENDENT fakes and assertions (not the reviser's drive).
// Targets the v2 mechanisms specifically + the mandated adversarial cases.
import { makeScript } from './assembled-factory-doc.mjs'

const SHA = n => String(n).padStart(2, '0').repeat(20)
const HEX = n => String(n).padStart(2, '0').repeat(32)
const GATE_SHA = HEX(7), BASE_SHA = HEX(8), BASE = SHA(1)
const R = '/workspaces/space-build', WT = R + '-wt'
const COMMON = { repo_toplevel: WT + '/x', git_common_dir: R + '/.git', outward_actions_taken: [], installed_packages: [], notes: 'ok' }

// the SCRIPT's own MANIFEST_MIN (§13) — the plan must cover it exactly (C-14)
const MANIFEST_MIN = {
  'platform-01-gate': ['tools/gate.sh', 'tools/gate.pin', 'tools/baseline.json', 'tools/baseline.pin', 'tests/protected.txt', 'tests/test_constants_pin.py', 'tests/test_import_contract.py', 'tests/fixtures/gate/false-claim.patch', 'tests/fixtures/gate/false-claim-target.txt', 'tests/journeys/conftest.py', 'tools/make_boundary_fixture.py', 'tools/stubs/torch/__init__.py', 'tools/stubs/transformers/__init__.py', 'tools/stubs/spaces/__init__.py', 'config.py', 'ruff.toml', 'pytest.ini', '.gitattributes', '.editorconfig', '.gitignore'],
  'platform-03a-types-fake': ['core/types.py', 'core/engine.py', 'backends/base.py', 'backends/fake.py', 'tools/record_fixture.py', 'tests/conformance/conftest.py'],
  'platform-03b-thin-slice': ['app.py', 'api/app.py', 'backends/hosted.py', 'models.yaml', 'build_info.json'],
  'platform-04-streamparser': ['core/parsing.py', 'core/events.py'],
  'platform-05a-registry': ['core/tools/registry.py', 'tests/test_python_eval_surfaces.py'],
  'platform-05b-agent-session': ['core/agent.py', 'core/session.py'],
  'platform-08a-worker-pure': ['worker/encode.py', 'worker/lease.py'],
  'platform-08b-worker-backend': ['worker/app.py', 'backends/worker.py'],
  'product-13a-catalog': ['tools/render_readme.py', 'core/catalog.py', 'tests/test_catalog_policy.py', 'evidence/catalog/README.md'],
  'product-13b-personas-readme': ['core/personas.py', 'tests/test_personas.py', 'tests/fixtures/persona_boundary.json'],
  'platform-14-promotion-ci': ['.github/workflows/gate.yml', '.github/workflows/deploy-staging.yml', '.github/workflows/promote.yml', '.github/workflows/health.yml', 'tools/promote.py', 'tools/expected.py'],
}
const DEC5 = ['G-1', 'G-3', 'G-2', 'M-5', 'G-15+G-24'].map(id => ({ id, decided_value: 'x', against_recommendation: true, consequences: [], dq_line: 85 }))

function baseArgs(extra) {
  return Object.assign({
    stage: 'build', run_nonce: 'r1a', launched_at: '2026-09-19T00:00:00Z', cap: 2, wave_size: 2,
    build_repo: R, snapshot_dir: '/workspaces/snap', venv: '/workspaces/space-build-venv', wheels_dir: '/workspaces/wheels', libsrc: '/workspaces/space-build-libsrc', tools_dir: '/workspaces/space-build-tools',
    gate_sh: '/workspaces/space-build-tools/gate.sh', gate_sha256: GATE_SHA, baseline_path: '/workspaces/space-build-tools/baseline.json', baseline_sha256: BASE_SHA,
    base_sha: BASE, toolchain_status_sha256: HEX(9), resume_mode: 'git', max_agents_this_run: 400,
    plan_sha: SHA(2), owner_approvals: { github_repo_url: null, fixture1_path: '/owner/f1.json', persona_boundary_fixture_path: '/owner/pb.json', persona_boundary_fixture_sha256: HEX(11), worker_checkpoint_decision: { needs_export: false } },
    decision_queue_path: '/g/DQ.md', lens4_path: '/g/l4.md', findings_path: '/g/f.md', redteam_path: '/g/rt.md',
    unverified_finding_ids: ['critic-1'], against_recommendation_ids: ['G-1', 'G-3', 'G-2', 'M-5', 'G-15+G-24'], catalog_candidates: ['a/b'],
  }, extra || {})
}
function card(id, deps, files, extra) {
  const pre = id === 'platform-04-streamparser' ? 'fixture1_path' : id === 'product-13b-personas-readme' ? 'persona_boundary_fixture_path' : ''
  return Object.assign({ id, path: 'plan/cards/' + id + '.json', step: 1, depends_on: deps, files_allowed: files, tests_allowed: [], new_modules: [], required_files: MANIFEST_MIN[id] || [], deps_allowed: [], xfail_allowed: [], expected_green_tests: [], tests_removed_expected: 0, est_lines: 100, est_minutes: 20,
    dod: [{ id: 'D1', command: 'pytest tests/unit/t.py', expect: 'exit0', verification_level: 'local-stub' }], size: 'S', risk: 'none', protected_touch: id === 'platform-01-gate', bootstrap: false, decision_ids: [], finding_ids: [], apis_expected: [], owner_precondition: pre }, extra || {})
}
// 11-card plan covering the script's MANIFEST_MIN (02-pins is the extra non-manifest card)
function fullPlan() {
  return [card('platform-01-gate', [], ['tools/gate.sh']),
    card('platform-02-pins', ['platform-01-gate'], ['core/prompting.py']),
    card('platform-03a-types-fake', ['platform-01-gate'], ['core/types.py']),
    card('platform-03b-thin-slice', ['platform-03a-types-fake'], ['api/app.py']),
    card('platform-04-streamparser', ['platform-03b-thin-slice'], ['core/parsing.py']),
    card('platform-05a-registry', ['platform-04-streamparser'], ['core/tools/registry.py']),
    card('platform-05b-agent-session', ['platform-05a-registry'], ['core/agent.py']),
    card('platform-08a-worker-pure', ['platform-03a-types-fake'], ['worker/encode.py']),
    card('platform-08b-worker-backend', ['platform-08a-worker-pure', 'platform-04-streamparser'], ['worker/app.py']),
    card('product-13a-catalog', ['platform-03b-thin-slice'], ['core/catalog.py']),
    card('product-13b-personas-readme', ['platform-05b-agent-session', 'product-13a-catalog'], ['core/personas.py']),
    card('platform-14-promotion-ci', ['platform-08b-worker-backend'], ['tools/promote.py'])]
}
const N_CARDS = 12

function makeHarness(scn, args) {
  const calls = [], logs = [], batches = []
  let counter = 0, spent = 0
  const H = {
    log: m => logs.push(String(m)), phase: () => {},
    budget: scn.budgetTotal != null ? { total: scn.budgetTotal, spent: () => spent, remaining: () => scn.budgetTotal - spent } : { total: null, spent: () => 0, remaining: () => Infinity },
    parallel: async thunks => Promise.all(thunks.map(async t => { try { return await t() } catch (e) { return null } })),
    pipeline: async (items, ...stages) => { if (items.length && typeof items[0] === 'object' && items[0].id) batches.push(items.map(i => i.id)); return Promise.all(items.map(async (it, i) => { let prev = it; try { for (const s of stages) prev = await s(prev, it, i) } catch (e) { return null } return prev })) },
    agent: async (prompt, opts) => {
      const n = ++counter, label = (opts && opts.label) || ''
      calls.push({ n, label, prompt, opts })
      const [role, mode, ...rest] = label.split(':'); const id = rest.join(':')
      if (scn.throwOn && scn.throwOn(label)) { const e = new Error(scn.throwMsg || 'budget ceiling exceeded'); throw e }
      const r = scn.reply({ n, role, mode, id, label, prompt, opts, calls })
      if (scn.budgetTotal != null) spent += 60000 // each fake agent costs 60k tokens
      if (r && typeof r === 'object' && !r.__raw) return Object.assign({}, COMMON, r)
      return r === undefined ? null : r
    },
  }
  H.args = args
  return { agent: H.agent, parallel: H.parallel, pipeline: H.pipeline, budget: H.budget, log: H.log, phase: H.phase, calls, logs, batches }
}

function verdict(mode, target, sha, v, o) { return Object.assign({ status: 'SUCCESS', mode, target_id: target, sha, verdict: v, ledger_sha256: HEX(5), ledger_head_sha: sha, gate_exit_code: 0, gate_digest: HEX(3), gate_profile: 'full', gate_sha256_observed: GATE_SHA, gate_steps: [], checks: [], dod_reruns: [], failures: [], hunks_cited: [], idiom_hits: 0, warnings_cleared: [], mutants: { written: 0, killed: 0 }, revert_proof: { observed: 'not-run', command: '' }, apicheck_unresolvable: [], findings: [], probes_used: [], strongest_disagreement: 'none', judge_rail: 'claude-fresh' }, o) }
function merge(mode, cid, status, head, o) { return Object.assign({ status, mode, card_id: cid, branch: 'task/' + cid, before_sha: SHA(0), head_sha: head, merge_sha: '', ledger_sha256: HEX(5), gate_digest: HEX(6), gate_exit_code: 0, gate_sha256_observed: GATE_SHA, cherry_unmerged: [], patch_ids_missing: [], conflicts: [], journeys: { collected: 0, failed: 0, skipped_needs: [] }, self_test: { broken_red: false, false_claim_red: 'not-run' }, files_written: [], remotes: [] }, o) }
function state(cards, o) { const seqs = {}; return Object.assign({ cards, head: SHA(3), lastBuild: {}, seq: (c, k) => (seqs[c + k] = (seqs[c + k] || 0) + 1), seqPeek: (c, k) => seqs[c + k] || 0 }, o || {}) }

// happy replies (deterministic digests: verifier reproduces builder's by construction)
function happy(ctx, st) {
  const { role, mode, id } = ctx, cid = id.replace(/:.*$/, '')
  if (role === 'integrator' && mode === 'setup') return Object.assign({ status: 'SUCCESS', venv_python: '3.12.3', nproc: 4, base_sha_ok: true, gate_sha256: GATE_SHA, baseline_sha256: BASE_SHA, baseline_collected: 73, baseline_skipped: 0, red_proof: { broken_red: true, false_claim_red: 'fixture-not-yet-delivered', digest: HEX(1) }, integration_head_live: st.head, plan_merged: true, branch_heads: [], merged_on_integration: st.mergedOnGit || [], remotes: [], prior_rows: st.priorRows || [], seen_keys: st.seenKeys || [], toolchain_status_sha256: HEX(9), worktrees_pruned: 0 }, st.setupOverride || {})
  if (role === 'verifier' && mode === 'index') return { status: 'SUCCESS', plan_sha: SHA(2), decisions_path: 'p', api_ledger_path: 'p', preverified_path: 'p', decisions: DEC5, preverified: st.preverified || [], cards: st.cards, unmapped_finding_ids: [] }
  if (role === 'author' && mode === 'tests') return { status: 'SUCCESS', card_id: cid, branch: 'tests/' + cid, base_sha: st.head, tests_head: SHA(10 + st.seq(cid, 'tests')), test_paths: ['tests/unit/t_' + cid + '.py'], commits_made: 1, red_command: 'g', red_exit_code: 1, red_excerpt: 'FAILED', gate_digest: HEX(2), known_bads_xfail: [], mutants_suggested: [] }
  if (role === 'author' && mode === 'journeys') return { status: 'SUCCESS', card_id: 'j', branch: 'task/j', base_sha: st.head, tests_head: SHA(70 + (st.j = (st.j || 0) + 1)), test_paths: ['tests/journeys/test_h.py'], commits_made: 1, red_command: 'x', red_exit_code: 0, red_excerpt: '', gate_digest: HEX(2) }
  if (role === 'verifier' && mode === 'red') { const th = /at ([0-9a-f]{40})\./.exec(ctx.prompt); return verdict('red', cid, th ? th[1] : SHA(0), 'pass', { gate_digest: HEX(2) }) }
  if (role === 'builder') { const h = SHA(30 + st.seq(cid, 'build')); st.lastBuild[cid] = h; return { status: 'done', card_id: cid, branch: 'task/' + cid, base_sha: st.head, head_sha: h, commits_made: 2, changed_files: ['x.py'], dod: [{ id: 'D1', command: 'pytest', exit_code: 0, output_tail: 'ok' }], apis_used: [], gate_exit_code: 0, gate_digest: HEX(40 + st.seq(cid, 'build')), gate_profile: 'full', gate_steps: [{ name: 'ruff', exit_code: 0 }], remaining_dod_ids: [] } }
  if (role === 'verifier' && mode === 'verify') { const h = st.lastBuild[cid]; return verdict('verify', cid, h, 'pass', { ledger_head_sha: h, gate_digest: HEX(40 + st.seqPeek(cid, 'build')), gate_profile: 'full', hunks_cited: ['x.py:1@' + h], checks: [{ name: 'gate', command: 'bash gate.sh --card', exit_code: 0, output_tail: 'LEDGER_DIGEST' }, { name: 'apicheck-extended', command: 'bash gate.sh --apicheck', exit_code: 0, output_tail: 'ok' }], dod_reruns: [{ id: 'D1', exit_code: 0 }], mutants: { written: 3, killed: 3 }, revert_proof: { observed: 'red', command: 'gate.sh --revert-proof' }, diff_stats: { files: 1, insertions: 10, deletions: 2 }, gate_steps: [{ name: 'ruff', exit_code: 0 }] }) }
  if (role === 'integrator' && (mode === 'merge' || mode === 'ff')) { st.head = SHA(50 + (st.m = (st.m || 0) + 1)); const ms = SHA(80 + st.m); return merge(mode, cid, 'merged', st.head, { merge_sha: ms }) }
  if (role === 'integrator' && mode === 'revert') { st.head = SHA(90 + (st.r = (st.r || 0) + 1)); return merge('revert', cid, 'merged', st.head) }
  if (role === 'integrator' && mode === 'clean') return merge('clean-gate', 'w', 'ok', st.head, { journeys: { collected: 1, failed: 0, skipped_needs: st.skippedNeeds || [] }, self_test: { broken_red: true, false_claim_red: 'true' }, toolchain_status_sha256: HEX(9), branch_count: 3 })
  if (role === 'integrator' && mode === 'fixcards') { st.head = SHA(60 + (st.fx = (st.fx || 0) + 1)); return merge('fixcards', 'fix', 'written', st.head, { files_written: [...new Set([...ctx.prompt.matchAll(/plan\/fixes\/[a-z0-9-]+\.json/g)].map(m => m[0]))] }) }
  if (role === 'verifier' && mode === 'review') return verdict('review', 'tree', st.head, 'pass', { findings: st.reviewFindings ? st.reviewFindings() : [], probes_used: ['grep'] })
  if (role === 'verifier' && mode === 'refute') { if (st.refuteOverride) return st.refuteOverride(ctx, st); return verdict('refute', id, st.head, 'refuted', {}) }
  if (role === 'verifier' && mode === 'veto') { if (st.vetoOverride) return st.vetoOverride(ctx, st); return verdict('veto', 'tree', st.head, 'no-veto', { findings: [] }) }
  if (role === 'verifier' && mode === 'evidence') return verdict('evidence', 'stage', st.head, 'pass', { findings: st.evidenceFindings ? st.evidenceFindings() : [] })
  if (role === 'synthesizer') {
    // echo the ROWS the script computed (parse from the prompt) so rows_consistent is meaningful
    let rows = []
    const i = ctx.prompt.indexOf('; ROWS='), j = ctx.prompt.indexOf('; CHECKPOINT=')
    if (i >= 0 && j > i) { try { rows = JSON.parse(ctx.prompt.slice(i + 7, j)).map(r => ({ task_id: r.task_id, state: r.state, reason: r.reason, next: r.next, head_sha: r.head_sha, dod_done: r.dod_done, dod_total: r.dod_total, dod_deferred: r.dod_deferred })) } catch (e) {} }
    return { status: 'SUCCESS', report_path: '/g/RUN-REPORT.md', report_bytes: 10, status_json_path: '/g/status.json', rows, owner_actions: [], what_would_most_improve_confidence: 'x' }
  }
  if (role === 'verifier' && mode === 'preverify') return verdict('preverify', id, BASE, 'refuted', { findings: [{ id, title: 't', file: 'f', severity: 'low', kind: 'correctness', reproduction: { command: 'c', exit_code: 1, output_tail: '' }, corrected_claim: 'nope', verification_level: 'local-mechanical' }] })
  if (role === 'planner' && mode === 'apiledger') return verdict('plan', 'ledger', SHA(2), 'pass', {})
  if (role === 'verifier' && mode === 'catalog') return verdict('catalog', 'cat', 'none', 'pass', { findings: [] })
  if (role === 'planner' && mode === 'plan') return { status: 'SUCCESS', plan_sha: SHA(2), decisions_path: 'p', api_ledger_path: 'p', preverified_path: 'p', decisions: DEC5, preverified: [], cards: st.cards, unmapped_finding_ids: [] }
  if (role === 'verifier' && mode === 'plan') return verdict('plan', 'index', SHA(2), 'pass', {})
  return null
}

const results = []
let current = ''
function assert(name, cond, detail) { results.push({ scenario: current, name, ok: !!cond, detail }); console.log((cond ? 'PASS ' : 'FAIL ') + name + (cond ? '' : (detail ? '  -- ' + String(detail).slice(0, 400) : ''))) }
async function runScenario(title, args, scn) {
  current = title.split(' ')[0]; console.log('\n=== ' + title)
  const H = makeHarness(scn, args)
  let out = null, err = null
  try { out = await makeScript(args, H.agent, H.parallel, H.pipeline, H.budget, H.log, H.phase) } catch (e) { err = e }
  return { out, err, calls: H.calls, logs: H.logs, batches: H.batches }
}
const rowsOf = r => r.out ? r.out.rows.map(x => [x.task_id, x.state]) : null
const row = (r, id) => r.out && r.out.rows.find(x => x.task_id === id)
const labels = r => r.calls.map(c => c.label)
const findCall = (r, re) => r.calls.find(c => re.test(c.label))

// M1 happy build — sanity + journeys on every merge gate + boundary sha in gate commands + verify prompt never carries builder digest
{
  const st = state(fullPlan())
  const r = await runScenario('M1 happy build 6 cards', baseArgs(), { reply: ctx => happy(ctx, st) })
  assert('M1 no throw, all merged, satisfied, ready', !r.err && r.out.rows.length === N_CARDS && r.out.rows.every(x => x.state === 'merged+gate-green') && r.out.stop_reason === 'satisfied' && r.out.status === 'ready', r.err || JSON.stringify(rowsOf(r)))
  const mergeGates = r.calls.filter(c => /^integrator:(merge|ff):/.test(c.label)).map(c => c.prompt)
  assert('M1 every merge gate carries --journeys (C-4)', mergeGates.length >= N_CARDS && mergeGates.every(p => p.includes('--journeys')), mergeGates.length)
  assert('M1 merge gates carry --boundary-sha256 (C-21 pin)', mergeGates.every(p => p.includes('--boundary-sha256 ' + HEX(11))))
  const vp = findCall(r, /^verifier:verify:/)
  assert('M1 verify prompt never contains the builder digest (F-30)', !vp.prompt.includes(HEX(40 + 1)), 'leaked')
  assert('M1 rows_consistent (synth echoed rows)', r.out.rows_consistent === true)
}

// M2 RECEIPT_RE probe — verifier notes "will report back when done" (a remaining RECEIPT_RE alternative)
{
  const st = state(fullPlan())
  const r = await runScenario('M2 receipt-shaped notes', baseArgs(), { reply: ctx => { const x = happy(ctx, st); if (ctx.role === 'verifier' && ctx.mode === 'verify' && x) { x.strongest_disagreement = 'will report back when the run ends'; } return x } })
  // CODE behaviour: the return is nulled (receipt-shaped) -> card parks agent-null:verifier
  assert('M2 CODE: receipt-shaped verifier notes NULL the return -> parked agent-null:verifier', row(r, 'platform-01-gate') && /agent-null:verifier/.test(row(r, 'platform-01-gate').reason), JSON.stringify(rowsOf(r)))
  // PROSE (§9/§12.2/§12.7) says: "a receipt-shaped fragment is now only logged". Contradiction recorded as V-gap.
  assert('M2 the card is NOT merged (the null had teeth)', !row(r, 'platform-01-gate') || row(r, 'platform-01-gate').state !== 'merged+gate-green')
}

// M3 rubber-stamp verifier (schema-valid-but-empty): no hunks, no mutants, revert-proof green, dod rerun fails
{
  const st = state(fullPlan())
  const r = await runScenario('M3 rubber-stamp verifier', baseArgs(), { reply: ctx => { const x = happy(ctx, st); if (ctx.role === 'verifier' && ctx.mode === 'verify') { Object.assign(x, { hunks_cited: [], mutants: { written: 0, killed: 0 }, revert_proof: { observed: 'green', command: 'x' }, dod_reruns: [{ id: 'D1', exit_code: 1 }], checks: [] }) } return x } })
  assert('M3 card NOT merged; parked after 2 builds with no-progress (C-18 never-empty fingerprint)', row(r, 'platform-01-gate') && row(r, 'platform-01-gate').state === 'parked' && /no-progress/.test(row(r, 'platform-01-gate').reason) && r.calls.filter(c => /^builder:(build|fix):platform-01-gate/.test(c.label)).length === 2, JSON.stringify([rowsOf(r), labels(r).filter(l => l.includes('platform-01-gate'))]))
  assert('M3 tree-incomplete: dependents never launched, no review lenses', !findCall(r, /^verifier:review:/) && row(r, 'platform-02-pins') && /dependency-blocked/.test(row(r, 'platform-02-pins').reason), JSON.stringify(rowsOf(r)))
  assert('M3 stop is tree-incomplete, status blocked, next stage build (C-5/C-9)', r.out.stop_reason === 'tree-incomplete' && r.out.status === 'blocked' && r.out.next_args.stage === 'build')
}

// M4 implementer adds a remote at merge -> HALT; synthesizer still runs (C-7); checkpoint failed
{
  const st = state(fullPlan())
  const r = await runScenario('M4 remote added at merge', baseArgs(), { reply: ctx => { const x = happy(ctx, st); if (ctx.role === 'integrator' && ctx.mode === 'merge' && /platform-02-pins/.test(ctx.label)) x.remotes = ['origin https://github.com/x/y']; return x } })
  assert('M4 HALT remote-added', /HALT .*remote-added/.test(r.logs.join('\n')) || /remote-added/.test(String(r.out.halt)), JSON.stringify(r.out.halt))
  assert('M4 checkpoint failed, not ready', r.out.status === 'failed' && r.out.status !== 'ready')
  const synthCalls = r.calls.filter(c => /^synthesizer:synth:/.test(c.label))
  assert('M4 synthesizer RAN after the HALT (C-7)', synthCalls.length >= 1, labels(r).slice(-4))
  assert('M4 no review lenses after HALT', !findCall(r, /^verifier:review:/))
}

// M5 overlapping write sets never share a pipeline batch
{
  const st = state(fullPlan())
  const p = fullPlan(); p[1].files_allowed = ['core/shared.py']; p[2].files_allowed = ['core/shared.py']; st.cards = p
  const r = await runScenario('M5 overlapping write sets', baseArgs(), { reply: ctx => happy(ctx, st) })
  const clash = r.batches.filter(b => b.includes('platform-02-pins') && b.includes('platform-03a-types-fake'))
  assert('M5 overlapping cards never in one batch; all merge', clash.length === 0 && r.out.rows.every(x => x.state === 'merged+gate-green'), JSON.stringify(r.batches))
}

// M6 budget exhaustion mid-wave -> starved not_attempted; resume rebuilds without retry_parked (C-8)
{
  const st = state(fullPlan())
  const args6 = baseArgs()
  const r = await runScenario('M6 budget exhausted mid-wave', args6, { budgetTotal: 500000, reply: ctx => happy(ctx, st) })
  assert('M6 starved cards are not_attempted with a retryable reason (C-8)', row(r, 'platform-03a-types-fake') && row(r, 'platform-03a-types-fake').state === 'not_attempted' && /starved|budget/.test(row(r, 'platform-03a-types-fake').reason), JSON.stringify(rowsOf(r)))
  assert('M6 next stage stays build (C-9); synthesizer ran', r.out.next_args.stage === 'build' && findCall(r, /^synthesizer:synth:/))
  // resume: prior rows carry the starved parks; setup reports the SAME live head and no merged-on-git for them
  const st2 = state(fullPlan(), { priorRows: r.out.rows.map(x => ({ task_id: x.task_id, state: x.state.includes('merged') ? 'merged+gate-green' : 'not_attempted', head_sha: 'none', reason: x.reason })), mergedOnGit: r.out.rows.filter(x => x.state === 'merged+gate-green').map(x => x.task_id) })
  st2.head = st.head
  const args6b = baseArgs({ integration_sha_at_launch: st.head })
  const r2 = await runScenario('M6b resume after starvation', args6b, { reply: ctx => happy(ctx, st2) })
  assert('M6b starved cards rebuilt on resume without retry_parked (C-8 auto-retry)', r2.out.rows.every(x => x.state === 'merged+gate-green') && r2.out.stop_reason === 'satisfied', JSON.stringify(rowsOf(r2)))
}

// M7 resume with a changed launch sha -> stale-launch-args
{
  const st = state(fullPlan())
  const r = await runScenario('M7 stale launch sha', baseArgs({ integration_sha_at_launch: SHA(99) }), { reply: ctx => happy(ctx, st) })
  assert('M7 throws stale-launch-args; no card agent; synth ran; checkpoint failed', /stale-launch-args/.test(String(r.out && r.out.stop_reason)) && !findCall(r, /^author:tests:/) && findCall(r, /^synthesizer:synth:/), JSON.stringify(r.out && r.out.stop_reason))
}

// M8 secret in builder output_tail -> redacted everywhere, card blocked secret-shaped-output, no fixer
{
  const st = state(fullPlan())
  const SECRET = 'hf_' + 'a1b2c3d4e5f6a1b2c3d4e5f6a1b2'
  const r = await runScenario('M8 secret in builder return', baseArgs(), { reply: ctx => { const x = happy(ctx, st); if (ctx.role === 'builder' && /platform-02-pins/.test(ctx.label)) { x.dod = [{ id: 'D1', command: 'pytest', exit_code: 0, output_tail: 'token ' + SECRET + ' ok' }] } return x } })
  assert('M8 secret in no prompt, log or checkpoint', !r.calls.some(c => c.prompt.includes(SECRET)) && !r.logs.some(l => l.includes(SECRET)) && !JSON.stringify(r.out).includes(SECRET))
  assert('M8 card blocked secret-shaped-output; no fixer launched', row(r, 'platform-02-pins') && /secret-shaped-output/.test(row(r, 'platform-02-pins').reason) && !findCall(r, /^builder:fix:platform-02-pins/), JSON.stringify(rowsOf(r)))
}

// M9 null from the final judge -> veto-unavailable, not ready
{
  const st = state(fullPlan())
  const r = await runScenario('M9 veto judge null', baseArgs(), { reply: ctx => { if (ctx.role === 'verifier' && ctx.mode === 'veto') return null; return happy(ctx, st) } })
  assert('M9 stop veto-unavailable; not ready; exactly 2 veto calls (retry once)', r.out.stop_reason === 'veto-unavailable' && r.out.status !== 'ready' && r.calls.filter(c => /^verifier:veto:/.test(c.label)).length === 2, r.out.stop_reason)
}

// M10 review finding -> fix card on plan/fixes with full content in prompts; fixcards BEFORE author
{
  let round = 0
  const st = state(fullPlan(), { reviewFindings: () => round === 0 ? [{ id: 'F-1', title: 'broken invariant', file: 'core/x.py', severity: 'high', kind: 'correctness', reproduction: { command: 'pytest -q core_x', exit_code: 1, output_tail: 'AssertionError' }, corrected_claim: 'the invariant is broken', fix_hint: 'guard the branch', files_allowed: ['core/x.py'], verification_level: 'local-stub' }] : [], refuteOverride: (ctx, s) => verdict('refute', ctx.id, s.head, 'holds', { findings: [{ id: 'F-1', title: 'broken invariant', file: 'core/x.py', severity: 'high', kind: 'correctness', reproduction: { command: 'pytest -q core_x', exit_code: 1, output_tail: 'AssertionError' }, corrected_claim: 'the invariant is broken', verification_level: 'local-stub' }] }) })
  const r = await runScenario('M10 review fix-card chain', baseArgs(), { reply: ctx => happy(ctx, st) })
  const fx = findCall(r, /^integrator:fixcards:/)
  const fixAuthor = r.calls.find(c => /^author:tests:platform-00-rf1/.test(c.label))
  assert('M10 fixcards ran and wrote plan/fixes/<id>.json (C-3)', fx && fx.prompt.includes('plan/fixes/platform-00-rf1-01-f-1.json'), fx && fx.label)
  assert('M10 fix-card author prompt carries the FINDING text and the DoD command (C-3)', fixAuthor && fixAuthor.prompt.includes('broken invariant') && fixAuthor.prompt.includes('pytest -q core_x') && fixAuthor.prompt.includes('plan/fixes/platform-00-rf1-01-f-1.json'), fixAuthor && fixAuthor.label)
  assert('M10 fix-card gate uses --card plan/fixes/... (C-3)', fixAuthor && fixAuthor.prompt.includes('--card plan/fixes/platform-00-rf1-01-f-1.json'))
  const fi = r.calls.findIndex(c => c.label.startsWith('integrator:fixcards')), fa = r.calls.findIndex(c => /^author:tests:platform-00-rf1/.test(c.label))
  assert('M10 fixcards BEFORE the fix author (C-3)', fi >= 0 && fa >= 0 && fi < fa)
  assert('M10 fix card merged; final stop satisfied', r.out.rows.some(x => x.task_id.startsWith('platform-00-rf1') && x.state === 'merged+gate-green') && r.out.stop_reason === 'satisfied', JSON.stringify(rowsOf(r)))
}

// M11 parked root -> dependents dependency-blocked; no lenses; tree-incomplete (C-5)
{
  const st = state(fullPlan())
  const r = await runScenario('M11 parked root', baseArgs(), { reply: ctx => { const x = happy(ctx, st); if (ctx.role === 'verifier' && ctx.mode === 'verify' && /platform-01-gate/.test(ctx.label)) Object.assign(x, { verdict: 'fail', mutants: { written: 3, killed: 1 } }); return x } })
  assert('M11 root parked; dependents not_attempted:dependency-blocked; no lenses; stop tree-incomplete', row(r, 'platform-01-gate').state === 'parked' && /dependency-blocked/.test(row(r, 'platform-02-pins').reason) && !findCall(r, /^verifier:review:/) && r.out.stop_reason === 'tree-incomplete', JSON.stringify([rowsOf(r), r.out.stop_reason]))
  assert('M11 status blocked, next stage build (C-9)', r.out.status === 'blocked' && r.out.next_args.stage === 'build')
}

// M12 stage run with confirmed critical staging finding -> no promote-production; promote run -> rollback; stage pinned
{
  const finding = { id: 'EV-1', title: 'canary failed 3/3', file: 'canary.json', severity: 'critical', kind: 'staging-evidence', reproduction: { command: 'jq .pass canary.json', exit_code: 1, output_tail: 'false' }, corrected_claim: 'canary fails', verification_level: 'staging-required' }
  const stS = state(fullPlan(), { mergedOnGit: fullPlan().map(c => c.id), evidenceFindings: () => [finding], refuteOverride: (ctx, s) => verdict('refute', ctx.id, s.head, 'holds', { findings: [Object.assign({}, finding)] }) })
  const rS = await runScenario('M12 stage with failed canary', baseArgs({ stage: 'stage', integration_sha_at_launch: stS.head, last_clean_gate: { head_sha: stS.head, digest: HEX(4) }, owner_approvals: Object.assign({}, baseArgs().owner_approvals, { staging_evidence_dir: '/g/ev', production_space_head: BASE }) }), { reply: ctx => happy(ctx, stS) })
  assert('M12 NO promote-production; stop blocked-on-owner:staging-evidence; not ready (C-6)', !rS.out.actions.some(a => a.kind === 'promote-production') && rS.out.stop_reason === 'blocked-on-owner:staging-evidence' && rS.out.status !== 'ready', JSON.stringify([rS.out.actions.map(a => a.kind), rS.out.stop_reason, rS.out.status]))
  assert('M12 stage stays stage (C-9)', rS.out.next_args.stage === 'stage')
  const stP = state(fullPlan(), { mergedOnGit: fullPlan().map(c => c.id), evidenceFindings: () => [finding], refuteOverride: (ctx, s) => verdict('refute', ctx.id, s.head, 'holds', { findings: [Object.assign({}, finding)] }) })
  const rP = await runScenario('M12b promote with critical finding', baseArgs({ stage: 'promote', integration_sha_at_launch: stP.head, last_clean_gate: { head_sha: stP.head, digest: HEX(4) }, owner_approvals: Object.assign({}, baseArgs().owner_approvals, { production_evidence_dir: '/g/ev' }) }), { reply: ctx => happy(ctx, stP) })
  assert('M12b rollback emitted with the finding id; stage pinned at promote (C-6/C-9)', rP.out.actions.some(a => a.kind === 'rollback' && JSON.stringify(a).includes('EV-1')) && rP.out.next_args.stage === 'promote' && rP.out.status !== 'ready', JSON.stringify([rP.out.actions.map(a => a.kind), rP.out.next_args.stage]))
  // medium/low accepted carve (Q10): accepted medium -> deferred, ready reachable
  const medFind = Object.assign({}, finding, { id: 'EV-2', severity: 'medium' })
  const stM = state(fullPlan(), { mergedOnGit: fullPlan().map(c => c.id), evidenceFindings: () => [medFind], refuteOverride: (ctx, s) => verdict('refute', ctx.id, s.head, 'holds', { findings: [Object.assign({}, medFind)] }) })
  const rM = await runScenario('M12c accepted medium finding', baseArgs({ stage: 'stage', integration_sha_at_launch: stM.head, last_clean_gate: { head_sha: stM.head, digest: HEX(4) }, owner_approvals: Object.assign({}, baseArgs().owner_approvals, { staging_evidence_dir: '/g/ev', production_space_head: BASE, accepted_findings: ['EV-2'] }) }), { reply: ctx => happy(ctx, stM) })
  assert('M12c accepted medium/low finding deferred, NOT blocking; ready reachable (Q10/C-6)', rM.out.actions.some(a => a.kind === 'promote-production') && rM.out.status === 'ready', JSON.stringify([rM.out.actions.map(a => a.kind), rM.out.status, rM.out.stop_reason]))
}

// M13 already-merged evidence rule (C-20)
{
  const st = state(fullPlan())
  const r = await runScenario('M13 bogus already-merged', baseArgs({ integration_sha_at_launch: SHA(3) }), { reply: ctx => { const x = happy(ctx, st); if (ctx.role === 'integrator' && ctx.mode === 'merge' && /platform-02-pins/.test(ctx.label)) { Object.assign(x, { status: 'already-merged', head_sha: SHA(77), gate_exit_code: 1, cherry_unmerged: ['x'] }) } return x } })
  assert('M13 unevidenced already-merged -> blocked already-merged-unproven; head never jumps (C-20)', row(r, 'platform-02-pins') && /already-merged-unproven/.test(row(r, 'platform-02-pins').reason), JSON.stringify(rowsOf(r)))
  const st2 = state(fullPlan())
  const r2 = await runScenario('M13b proven already-merged', baseArgs(), { reply: ctx => { const preHead = /is at ([0-9a-f]{40})/.exec(ctx.prompt); const x = happy(ctx, st2); if (ctx.role === 'integrator' && ctx.mode === 'merge' && /platform-02-pins/.test(ctx.label) && preHead) { Object.assign(x, { status: 'already-merged', head_sha: preHead[1], gate_digest: HEX(12), cherry_unmerged: [], patch_ids_missing: [] }) } return x } })
  assert('M13b evidenced already-merged counts as merged (C-20)', row(r2, 'platform-02-pins').state === 'merged+gate-green' && /already-merged\(proven\)/.test(row(r2, 'platform-02-pins').reason), JSON.stringify(rowsOf(r2)))
}

// M14 digest mismatch -> fixer receives digest_mismatch with BOTH ledgers' steps (C-18)
{
  const st = state(fullPlan())
  const r = await runScenario('M14 digest mismatch', baseArgs(), { reply: ctx => { const x = happy(ctx, st); if (ctx.role === 'verifier' && ctx.mode === 'verify' && /platform-01-gate/.test(ctx.label)) x.gate_digest = HEX(99); return x } })
  const fixer = r.calls.find(c => /^builder:fix:platform-01-gate/.test(c.label))
  assert('M14 fixer prompt carries digest_mismatch with builder_steps and verifier_steps (C-18)', fixer && /digest_mismatch/.test(fixer.prompt) && /builder_steps/.test(fixer.prompt) && /verifier_steps/.test(fixer.prompt) && /steps_only_in_/.test(fixer.prompt), fixer && fixer.label)
  assert('M14 two-strikes at 2 builds (never-empty fingerprint)', r.calls.filter(c => /^builder:(build|fix):platform-01-gate/.test(c.label)).length === 2 && /no-progress/.test(row(r, 'platform-01-gate').reason))
}

// M15 journey skipped after its card merged -> synthetic blocking finding -> fix card (C-4)
{
  let round = 0
  const st = state(fullPlan(), { skippedNeeds: ['platform-03b-thin-slice'], reviewFindings: () => [] })
  const r = await runScenario('M15 journey skipped after merge', baseArgs(), { reply: ctx => { const x = happy(ctx, st); if (ctx.role === 'verifier' && ctx.mode === 'refute' && /journey-needs/.test(ctx.label)) { return verdict('refute', ctx.id, st.head, 'holds', { findings: [{ id: 'journey-needs-platform-03b-thin-slice', title: 'journey skipped after its card merged', file: 'tests/journeys', severity: 'high', kind: 'interaction', reproduction: { command: 'gate --journeys', exit_code: 1, output_tail: 'skipped' }, verification_level: 'local-stub' }] }) } return x } })
  const synth = findCall(r, /^synthesizer:synth:/)
  assert('M15 synthetic journey finding raised (logged) and queued through refute', r.logs.some(l => l.includes('journeys still skipped although their card merged')), r.logs.filter(l => l.includes('journey')).join(' | '))
  assert('M15 fix card for the journey finding exists on plan/fixes', r.calls.some(c => c.label.startsWith('integrator:fixcards') && c.prompt.includes('journey-needs')), labels(r).join(','))
}

// M16 plan repair paths (C-19): R0 defective -> repair-plan; R1 defective -> refusal (and the next_args question)
{
  const badPlan = fullPlan(); badPlan[1].finding_ids = [{ id: 'critic-1', corrected_text: 'x'.repeat(30) }] // critic-1 is REFUTED by the fake preverifier
  const st = state(badPlan)
  const r0 = await runScenario('M16 R0 plan cites a REFUTED id', baseArgs({ stage: 'plan' }), { reply: ctx => happy(ctx, st) })
  assert('M16 R0 repair-plan (never approve-plan); plan_defects carried; next stage plan (C-19)', r0.out.actions.some(a => a.kind === 'repair-plan') && !r0.out.actions.some(a => a.kind === 'approve-plan') && r0.out.plan_defects.length > 0 && r0.out.next_args.stage === 'plan', JSON.stringify([r0.out.actions.map(a => a.kind), r0.out.next_args]))
  const st1 = state(badPlan, { preverified: [{ id: 'critic-1', verdict: 'refuted', corrected_claim: '', level: 'local-mechanical' }] })
  const r1 = await runScenario('M16b R1 refuses the defective plan', baseArgs(), { reply: ctx => happy(ctx, st1) })
  assert('M16b R1 throws plan-needs-repair BEFORE any author/builder (C-19)', /plan-needs-repair/.test(String(r1.out.stop_reason)) && !findCall(r1, /^author:tests:/) && !findCall(r1, /^builder:/), r1.out.stop_reason)
  // The next_args question: does the checkpoint tell the owner to relaunch plan?
  console.log('M16b OBSERVED next_args.stage=' + r1.out.next_args.stage + ' plan_defects=' + JSON.stringify(r1.out.next_args.plan_defects) + ' stop_reason=' + String(r1.out.stop_reason).slice(0, 120))
  assert('M16b next_args.stage points at plan (or plan_defects carried) for the repair relaunch', r1.out.next_args.stage === 'plan' || (r1.out.next_args.plan_defects || []).length > 0, 'next_args says ' + r1.out.next_args.stage + ' with plan_defects [] — the repair instruction lives only in stop_reason')
}

// M17 ownership rule (C-21): plan-time validation both ways
{
  const badPlan = fullPlan(); badPlan[1].files_allowed = ['core/prompting.py', 'tests/test_constants_pin.py'] // protected, not in 02's manifest
  const st = state(badPlan)
  const r = await runScenario('M17 non-owner writes a protected path', baseArgs({ stage: 'plan' }), { reply: ctx => happy(ctx, st) })
  assert('M17 plan refused (repair-plan) — ownership rule at plan time (C-21)', r.out.actions.some(a => a.kind === 'repair-plan') && r.out.plan_defects.some(d => /protected/.test(d)), JSON.stringify(r.out.plan_defects))
  const goodPlan = fullPlan() // 13b declares tests/fixtures/persona_boundary.json via its manifest
  const st2 = state(goodPlan)
  const r2 = await runScenario('M17b owner-manifest protected write passes', baseArgs({ stage: 'plan' }), { reply: ctx => happy(ctx, st2) })
  assert('M17b a card whose MANIFEST_MIN declares the protected path passes (C-21)', r2.out.actions.some(a => a.kind === 'approve-plan'), JSON.stringify(r2.out.plan_defects))
}

// M18 synthesizer after budget-ceiling HALT (C-7/CG-20)
{
  const st = state(fullPlan())
  const st18 = state(fullPlan())
  const r = await runScenario('M18 agent throws budget ceiling', baseArgs(), { reply: ctx => happy(ctx, st18), throwOn: l => l.startsWith('builder:build:platform-02-pins'), throwMsg: 'budget ceiling exceeded' })
  assert('M18 HALT budget-exhausted, synthesizer still ran, no retry fan-out', /budget-exhausted/.test(String(r.out.halt)) && findCall(r, /^synthesizer:synth:/) && r.calls.filter(c => c.label.includes('retry')).length === 0, JSON.stringify([r.out.halt, labels(r).slice(-3)]))
}

// M19 smoke mode: review loop skipped, single card (C-33)
{
  const st = state(fullPlan())
  const r = await runScenario('M19 smoke run', baseArgs({ smoke: true }), { reply: ctx => happy(ctx, st) })
  assert('M19 one card only; review skipped; not ready (C-33)', r.out.rows.length === 1 && r.out.stop_reason === 'smoke-skip-review' && !findCall(r, /^verifier:review:/) && r.out.status !== 'ready', JSON.stringify([rowsOf(r), r.out.stop_reason]))
}

// M20 integration-dirty: clean gate red + revert fails -> typed row; RETRYABLE_RE probe
{
  const st = state(fullPlan())
  const r = await runScenario('M20 revert fails after clean-gate red', baseArgs(), { reply: ctx => { const x = happy(ctx, st); if (ctx.role === 'integrator' && ctx.mode === 'clean') { Object.assign(x, { gate_exit_code: 1, status: 'ok' }) } if (ctx.role === 'integrator' && ctx.mode === 'revert') { Object.assign(x, { status: 'failed', head_sha: '' }) } return x } })
  assert('M20 revert-failed typed; integration dirty; status failed', row(r, 'platform-01-gate') && /revert-failed|clean-gate-red/.test(row(r, 'platform-01-gate').reason) && r.out.status === 'failed', JSON.stringify(rowsOf(r)))
  const dirtRow = r.out.rows.find(x => /integration-dirty/.test(x.reason || ''))
  console.log('M20 OBSERVED integration-dirty rows: ' + JSON.stringify(dirtRow || null))
  // the regex probe: does 'not_attempted:integration-dirty' match RETRYABLE_RE (auto-retried on resume)?
  const RETRYABLE_RE = /^(not_attempted|starved):|agent-null|threw|timeout-or-dialog|integration:not-merged:null|fixcards-unavailable/
  assert('M20 [finding probe] not_attempted:integration-dirty matches RETRYABLE_RE although next says owner-inspect', RETRYABLE_RE.test('not_attempted:integration-dirty'))
}

// M21 no venv (C-31): setup reports FAILED -> run fails loudly, no agent told to create it
{
  const st = state(fullPlan(), { setupOverride: { status: 'FAILED', venv_python: '' } })
  const r = await runScenario('M21 venv missing', baseArgs(), { reply: ctx => happy(ctx, st) })
  assert('M21 run fails; no author launched; synthesizer ran', /FAILED/.test(String(r.out.stop_reason)) && !findCall(r, /^author:tests:/) && findCall(r, /^synthesizer:synth:/), r.out.stop_reason)
  const setupPrompt = findCall(r, /^integrator:setup:/)
  assert('M21 setup prompt never says create the venv (C-31)', setupPrompt && !/create it or install/i.test(setupPrompt.prompt.split('venv')[1] || '') && setupPrompt.prompt.includes('NEVER create it'))
}

// M22 timeout receipt label (C-37): a timeout maps to timeout-or-dialog and REPLAY_RISK
{
  const st = state(fullPlan())
  const r = await runScenario('M22 timeout receipt', baseArgs(), { reply: ctx => { if (ctx.label.startsWith('verifier:verify:platform-02-pins:1')) return { __raw: true, __h6: true, __endReason: 'timeout', label: 'x', ms: 1, detail: null }; return happy(ctx, st) } })
  assert('M22 timeout typed timeout-or-dialog; retry once; REPLAY_RISK forces git resume (C-37/CG-13)', r.out.next_args.resume_mode === 'git' && r.logs.some(l => l.includes('timeout-or-dialog')), JSON.stringify(r.out.next_args))
}

// summary
const pass = results.filter(x => x.ok).length, fail = results.filter(x => !x.ok).length
console.log(`\n==== MY-DRIVE SUMMARY: ${pass} passed, ${fail} failed, assertions: ${results.length}`)
if (fail) { console.log('FAILED:'); results.filter(x => !x.ok).forEach(x => console.log('  [' + x.scenario + '] ' + x.name + ' :: ' + String(x.detail).slice(0, 300))) }
process.exit(fail ? 1 : 0)
