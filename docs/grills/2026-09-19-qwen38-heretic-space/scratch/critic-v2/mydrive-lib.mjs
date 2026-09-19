// critic-v2 adversarial drive — INDEPENDENT fakes and assertions (not the reviser's drive).
// Targets the v2 mechanisms specifically + the mandated adversarial cases.
import { makeScript } from './assembled-factory-doc.mjs'

const SHA = n => String(n).padStart(2, '0').repeat(20)
const HEX = n => String(n).padStart(2, '0').repeat(32)
const GATE_SHA = HEX(7), BASE_SHA = HEX(8), BASE = SHA(1)
const R = '/workspaces/space-build', WT = R + '-wt'
const COMMON = { repo_toplevel: WT + '/x', git_common_dir: R + '/.git', outward_actions_taken: [], installed_packages: [], notes: 'ok' }

const MANIFEST_MIN = {
  'platform-01-gate': ['tools/gate.sh', 'tools/gate.pin', 'tools/baseline.json', 'tests/protected.txt', 'tests/test_constants_pin.py', 'config.py', 'tests/journeys/conftest.py', 'tools/make_boundary_fixture.py'],
  'platform-03a-types-fake': ['core/types.py', 'core/engine.py', 'backends/fake.py'],
  'platform-03b-thin-slice': ['api/app.py', 'app.py', 'build_info.json'],
  'platform-04-streamparser': ['core/parsing.py'],
  'product-13b-personas-readme': ['core/personas.py', 'tests/test_personas.py', 'tests/fixtures/persona_boundary.json'],
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
// 6-card plan: 01 -> {02, 03a} -> 03b -> 04 ; 13b depends on 04
function fullPlan() {
  return [card('platform-01-gate', [], ['tools/gate.sh']),
    card('platform-02-pins', ['platform-01-gate'], ['core/prompting.py']),
    card('platform-03a-types-fake', ['platform-01-gate'], ['core/types.py']),
    card('platform-03b-thin-slice', ['platform-03a-types-fake'], ['api/app.py']),
    card('platform-04-streamparser', ['platform-03b-thin-slice'], ['core/parsing.py']),
    card('product-13b-personas-readme', ['platform-04-streamparser'], ['core/personas.py'])]
}

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


export { SHA, HEX, GATE_SHA, BASE, R, WT, COMMON, MANIFEST_MIN, DEC5, baseArgs, card, fullPlan, makeHarness, verdict, merge, state, happy, results, assert }
