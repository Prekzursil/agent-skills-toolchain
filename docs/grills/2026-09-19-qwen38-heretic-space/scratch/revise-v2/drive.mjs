// Adversarial fake-harness drive of design-v2 §13 — the critic's 21 scenarios (critic-v1/drive.mjs) adapted to v2 + new scenarios N1-N12.
// Nothing here calls a real agent. Assertions that encoded a v1 DEFECT (inverted assertions) are flipped to the intended behaviour and marked [flipped].
import { makeScript } from './assembled.mjs'

const SHA = n => (String(n).padStart(2, '0')).repeat(20)          // 40-hex deterministic shas
const HEX = n => (String(n).padStart(2, '0')).repeat(32)          // 64-hex digests
const GATE_SHA = HEX(7), BASE_SHA = HEX(8), BASE = SHA(1)
const R = '/workspaces/space-build', WT = R + '-wt'
const COMMON = { repo_toplevel: WT + '/x', git_common_dir: R + '/.git', outward_actions_taken: [], installed_packages: [], notes: 'ok' }
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
const OA_HAPPY = { github_repo_url: null, staging_space_ids: [], fixture1_path: '/owner/fixture1.json', persona_boundary_fixture_path: '/owner/pb.json', persona_boundary_fixture_sha256: HEX(11), worker_checkpoint_decision: { candidate: 'x', needs_export: false } }
const DEC5 = ['G-1', 'G-3', 'G-2', 'M-5', 'G-15+G-24'].map(id => ({ id, decided_value: 'x', against_recommendation: true, consequences: [], dq_line: 85 }))   // checkPlan (C-19/F-9) requires these five rows — a valid plan carries them
function baseArgs(extra) {
  return Object.assign({
    stage: 'build', run_nonce: 'r1a', launched_at: '2026-09-19T00:00:00Z', cap: 2, wave_size: 2,
    build_repo: R, snapshot_dir: '/workspaces/snap', venv: '/workspaces/space-build-venv', wheels_dir: '/workspaces/wheels', libsrc: '/workspaces/space-build-libsrc', tools_dir: '/workspaces/space-build-tools',
    gate_sh: '/workspaces/space-build-tools/gate.sh', gate_sha256: GATE_SHA, baseline_path: '/workspaces/space-build-tools/baseline.json', baseline_sha256: BASE_SHA,
    base_sha: BASE, toolchain_status_sha256: HEX(9), resume_mode: 'git', max_agents_this_run: 400,
    plan_sha: SHA(2), owner_approvals: Object.assign({}, OA_HAPPY),
    decision_queue_path: '/g/DQ.md', lens4_path: '/g/l4.md', findings_path: '/g/f.md', redteam_path: '/g/rt.md', unverified_finding_ids: ['critic-1', 'critic-4'], against_recommendation_ids: ['G-1', 'G-3', 'G-2', 'M-5', 'G-15+G-24'], catalog_candidates: ['a/b'],
  }, extra || {})
}
function card(id, deps, files, extra) {
  const pre = id === 'platform-04-streamparser' ? 'fixture1_path' : id === 'product-13b-personas-readme' ? 'persona_boundary_fixture_path' : id === 'platform-08c-worker-checkpoint' ? 'worker_checkpoint_decision' : ''
  return Object.assign({ id, path: 'plan/cards/' + id + '.json', step: 1, depends_on: deps, files_allowed: files, tests_allowed: [], new_modules: [], required_files: MANIFEST_MIN[id] || [], deps_allowed: [], xfail_allowed: [], expected_green_tests: [], tests_removed_expected: 0, est_lines: 100, est_minutes: 20,
    dod: [{ id: 'D1', command: 'pytest tests/unit/test_' + id + '.py', expect: 'exit0', verification_level: 'local-stub' }], size: 'S', risk: 'none', protected_touch: id === 'platform-01-gate', bootstrap: false, decision_ids: [], finding_ids: [], apis_expected: [], owner_precondition: pre }, extra || {})
}
// the drive's plan: the 11 manifest cards + 02-pins (a valid plan under checkPlan); 02 and 03a both depend on 01 so wave 2 = [02, 03a] as in the critic's S1
function fullPlan() {
  return [card('platform-01-gate', [], ['tools/gate.sh']), card('platform-02-pins', ['platform-01-gate'], ['core/prompting.py']), card('platform-03a-types-fake', ['platform-01-gate'], ['core/types.py']),
    card('platform-03b-thin-slice', ['platform-03a-types-fake'], ['api/app.py']), card('platform-04-streamparser', ['platform-03b-thin-slice'], ['core/parsing.py']), card('platform-05a-registry', ['platform-04-streamparser'], ['core/tools/registry.py']),
    card('platform-05b-agent-session', ['platform-05a-registry'], ['core/agent.py']), card('platform-08a-worker-pure', ['platform-03a-types-fake'], ['worker/encode.py']), card('platform-08b-worker-backend', ['platform-08a-worker-pure', 'platform-04-streamparser'], ['worker/app.py']),
    card('product-13a-catalog', ['platform-03b-thin-slice'], ['core/catalog.py']), card('product-13b-personas-readme', ['platform-05b-agent-session', 'product-13a-catalog'], ['core/personas.py']), card('platform-14-promotion-ci', ['platform-08b-worker-backend'], ['tools/promote.py'])]
}
const N_CARDS = 12

// ---- the fake harness ------------------------------------------------------------------------
function makeHarness(scn, args) {
  const calls = [], logs = [], batches = []
  let counter = 0
  const H = {
    args, log: m => logs.push(String(m)), phase: () => {},
    budget: scn.budget || { total: null, spent: () => 0, remaining: () => Infinity },
    parallel: async thunks => Promise.all(thunks.map(async t => { try { return await t() } catch (e) { return null } })),
    pipeline: async (items, ...stages) => { if (items.length) batches.push(items.map(i => i && i.id)); return Promise.all(items.map(async (it, i) => { let prev = it; try { for (const s of stages) prev = await s(prev, it, i) } catch (e) { return null } return prev })) },
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
  if (role === 'integrator' && mode === 'setup') return Object.assign({ status: 'SUCCESS', venv_python: '3.12.3', nproc: 4, base_sha_ok: true, gate_sha256: GATE_SHA, baseline_sha256: BASE_SHA, baseline_collected: 73, baseline_skipped: 0, red_proof: { broken_red: true, false_claim_red: 'fixture-not-yet-delivered', digest: HEX(1) }, integration_head_live: st.head, plan_merged: true, branch_heads: [], merged_on_integration: st.mergedOnGit || [], remotes: [], prior_rows: st.priorRows || [], seen_keys: st.seenKeys || [], toolchain_status_sha256: HEX(9), worktrees_pruned: 0 }, st.setupOverride || {})
  if (role === 'verifier' && mode === 'index') return { status: 'SUCCESS', plan_sha: SHA(2), decisions_path: 'plan/decisions.json', api_ledger_path: 'plan/api-ledger.json', preverified_path: 'plan/preverified.json', decisions: DEC5, preverified: st.preverified || [], cards: st.cards, unmapped_finding_ids: [] }
  if (role === 'author' && mode === 'tests') return { status: 'SUCCESS', card_id: cid, branch: 'tests/' + cid + '-r1a', base_sha: st.head, tests_head: SHA(10 + st.seq(cid, 'tests')), test_paths: ['tests/unit/test_' + cid + '.py'], commits_made: 1, red_command: 'gate.sh --only-tests', red_exit_code: 1, red_excerpt: 'FAILED', gate_exit_code: 0, gate_digest: HEX(2), known_bads_xfail: [], mutants_suggested: [] }
  if (role === 'author' && mode === 'journeys') return { status: 'SUCCESS', card_id: 'journeys', branch: 'task/journeys', base_sha: st.head, tests_head: SHA(70 + (st.j = (st.j || 0) + 1)), test_paths: ['tests/journeys/test_h.py'], commits_made: 1, red_command: 'x', red_exit_code: 0, red_excerpt: '', gate_exit_code: 0, gate_digest: HEX(2) }   // v2.1 V-11: the acceptance now requires gate_exit_code 0 + digest
  if (role === 'verifier' && mode === 'red') { const th = /at ([0-9a-f]{40})\./.exec(ctx.prompt); return verdict('red', cid, th ? th[1] : SHA(0), 'pass', { gate_digest: HEX(2) }) }
  if (role === 'builder') { const h = SHA(30 + st.seq(cid, 'build')); st.lastBuild[cid] = h; return { status: 'done', card_id: cid, branch: 'task/' + cid + '-r1a', base_sha: st.head, head_sha: h, commits_made: 2, changed_files: ['x.py', 'tests/unit/test_extra.py'], dod: [{ id: 'D1', command: 'pytest', exit_code: 0, output_tail: 'ok' }], apis_used: [], gate_exit_code: 0, gate_digest: HEX(40 + st.seq(cid, 'build')), gate_profile: 'full', gate_steps: [{ name: 'ruff', exit_code: 0 }, { name: 'pytest-x2', exit_code: 0 }], remaining_dod_ids: [] } }
  if (role === 'verifier' && mode === 'verify') { const h = st.lastBuild[cid]; return verdict('verify', cid, h, 'pass', { ledger_head_sha: h, gate_digest: HEX(40 + st.seqPeek(cid, 'build')), gate_profile: 'full', hunks_cited: ['x.py:1@' + h], checks: [{ name: 'gate', command: 'bash gate.sh --card', exit_code: 0, output_tail: 'LEDGER_DIGEST' }, { name: 'apicheck-extended', command: 'bash gate.sh --apicheck', exit_code: 0, output_tail: 'ok' }], dod_reruns: [{ id: 'D1', exit_code: 0 }], mutants: { written: 3, killed: 3 }, revert_proof: { observed: 'red', command: 'gate.sh --revert-proof' }, diff_stats: { files: 1, insertions: 10, deletions: 2 }, gate_steps: [{ name: 'ruff', exit_code: 0 }, { name: 'pytest-x2', exit_code: 0 }] }) }
  if (role === 'integrator' && (mode === 'merge' || mode === 'ff')) { st.head = SHA(50 + (st.m = (st.m || 0) + 1)); const ms = SHA(80 + st.m); st.lastMerge = ms; return merge('merge', cid, 'merged', st.head, { merge_sha: ms }) }
  if (role === 'integrator' && mode === 'revert') { st.head = SHA(90 + (st.r = (st.r || 0) + 1)); return merge('revert', cid, 'merged', st.head) }
  if (role === 'integrator' && mode === 'clean') return merge('clean-gate', 'w', 'ok', st.head, { journeys: { collected: 1, failed: 0, skipped_needs: st.skippedNeeds || [] }, self_test: { broken_red: true, false_claim_red: 'true' }, toolchain_status_sha256: HEX(9), branch_count: 3 })
  if (role === 'integrator' && mode === 'fixcards') { st.head = SHA(60 + (st.fx = (st.fx || 0) + 1)); return merge('fixcards', 'fix', 'written', st.head, { files_written: [...new Set([...ctx.prompt.matchAll(/plan\/fixes\/[a-z0-9-]+\.json/g)].map(m => m[0]))] }) }
  if (role === 'verifier' && mode === 'review') return verdict('review', 'tree', st.head, 'pass', { findings: [], probes_used: ['grep'] })
  if (role === 'verifier' && mode === 'refute') return verdict('refute', id, st.head, 'refuted', {})
  if (role === 'verifier' && mode === 'veto') return verdict('veto', 'tree', st.head, 'no-veto', { findings: [] })
  if (role === 'verifier' && mode === 'evidence') return verdict('evidence', 'stage', st.head, 'pass', { findings: st.evidenceFindings || [] })
  if (role === 'synthesizer') return { status: 'SUCCESS', report_path: '/g/RUN-REPORT.md', report_bytes: 10, status_json_path: '/g/status.json', rows: ctx.__rows || [], owner_actions: [], what_would_most_improve_confidence: 'x' }
  if (role === 'verifier' && mode === 'preverify') return verdict('preverify', id, BASE, 'refuted', { findings: [{ id, title: 't', file: 'f', severity: 'low', kind: 'correctness', reproduction: { command: 'c', exit_code: 1, output_tail: '' }, corrected_claim: 'nope', verification_level: 'local-mechanical' }] })
  if (role === 'planner' && mode === 'apiledger') return verdict('plan', 'ledger', SHA(2), 'pass', {})
  if (role === 'verifier' && mode === 'catalog') return verdict('catalog', 'cat', 'none', 'pass', { findings: [] })
  if (role === 'planner' && mode === 'plan') return { status: 'SUCCESS', plan_sha: SHA(2), decisions_path: 'p', api_ledger_path: 'p', preverified_path: 'p', decisions: DEC5, preverified: [], cards: st.cards, unmapped_finding_ids: [] }
  if (role === 'verifier' && mode === 'plan') return verdict('plan', 'index', SHA(2), 'pass', {})
  return null
}
function verdict(mode, target, sha, v, o) { return Object.assign({ status: 'SUCCESS', mode, target_id: target, sha, verdict: v, ledger_sha256: HEX(5), ledger_head_sha: sha, gate_exit_code: 0, gate_digest: HEX(3), gate_profile: 'full', gate_sha256_observed: GATE_SHA, gate_steps: [], checks: [], dod_reruns: [], failures: [], hunks_cited: [], idiom_hits: 0, warnings_cleared: [], mutants: { written: 0, killed: 0 }, revert_proof: { observed: 'not-run', command: '' }, apicheck_unresolvable: [], findings: [], probes_used: [], strongest_disagreement: 'none', judge_rail: 'claude-fresh' }, o) }
function merge(mode, cid, status, head, o) { return Object.assign({ status, mode, card_id: cid, branch: 'task/' + cid, before_sha: SHA(0), head_sha: head, merge_sha: '', ledger_sha256: HEX(5), gate_digest: HEX(6), gate_exit_code: 0, gate_sha256_observed: GATE_SHA, cherry_unmerged: [], patch_ids_missing: [], conflicts: [], journeys: { collected: 0, failed: 0, skipped_needs: [] }, self_test: { broken_red: false, false_claim_red: 'not-run' }, files_written: [], remotes: [] }, o) }
function state(cards, o) { const seqs = {}; return Object.assign({ cards, head: SHA(3), lastBuild: {}, seq: (c, k) => (seqs[c + k] = (seqs[c + k] || 0) + 1), seqPeek: (c, k) => seqs[c + k] || 0 }, o || {}) }

// ---- assertions ------------------------------------------------------------------------------
const results = []
let current = ''
function assert(name, cond, detail) { results.push({ scenario: current, name, ok: !!cond, detail }); console.log((cond ? 'PASS ' : 'FAIL ') + name + (cond ? '' : (detail ? '  -- ' + String(detail).slice(0, 300) : ''))) }
async function runScenario(title, args, scn) {
  current = title.split(' ')[0]; console.log('\n=== ' + title)
  const { H, calls, logs, batches } = makeHarness(scn, args)
  let out, err = null
  try { out = await makeScript(H) } catch (e) { err = e }
  return { out, err, calls, logs, batches }
}
const rowsOf = r => (r.out ? r.out.rows.map(x => [x.task_id, x.state, x.reason]) : null)
const mergedCount = r => (r.out ? r.out.rows.filter(x => x.state === 'merged+gate-green').length : -1)
const row = (r, id) => r.out && r.out.rows.find(x => x.task_id === id)

// S1 happy path, full plan, wave rule --------------------------------------------------------------
{
  const st = state(fullPlan())
  const r = await runScenario('S1 happy build, 12 cards', baseArgs(), { reply: ctx => happy(ctx, st) })
  assert('S1 no throw', !r.err, r.err && r.err.message)
  assert('S1 all cards merged', mergedCount(r) === N_CARDS, JSON.stringify(rowsOf(r)))
  assert('S1 checkpoint status ready [flipped: the critic marked its own "blocked" expectation as a mistake; C1 actions are actions, not blockers]', r.out && r.out.status === 'ready', r.out && r.out.status)
  assert('S1 stop_reason satisfied', r.out && r.out.stop_reason === 'satisfied', r.out && r.out.stop_reason)
  assert('S1 wave 1 = [01] alone, wave 2 = [03a, 02] by rank desc (C-24: 03a carries the deeper dependents) [corrected, not a flip: my first draft wrote the critic\'s id order, which is not the rank order]', JSON.stringify(r.batches.slice(0, 2)) === JSON.stringify([['platform-01-gate'], ['platform-03a-types-fake', 'platform-02-pins']]), JSON.stringify(r.batches.slice(0, 3)))
  const labels = r.calls.map(c => c.label); assert('S1 labels unique', new Set(labels).size === labels.length)
  assert('S1 every agent call has phase+schema', r.calls.every(c => c.opts && c.opts.phase && c.opts.schema))
  const vp = r.calls.find(c => c.label.startsWith('verifier:verify:')).prompt
  assert('S1 verify prompt never carries the builder digest', !vp.includes(HEX(41)) && !vp.includes(HEX(40)))
  assert('S1 every row carries reason + next [flipped: v1 rows had none — C-22]', r.out && r.out.rows.every(x => typeof x.reason === 'string' && x.reason.length && typeof x.next === 'string'), JSON.stringify(Object.keys((r.out && r.out.rows[0]) || {})))
  assert('S1 next_args.stage = stage (satisfied + complete)', r.out && r.out.next_args.stage === 'stage', r.out && r.out.next_args.stage)
  assert('S1 every merge gate command carries --journeys', r.calls.filter(c => c.label.startsWith('integrator:merge:')).every(c => /--journeys/.test(c.prompt)))
  assert('S1 the review pre-check did not spend an extra clean gate (last clean gate already passing at head)', !r.calls.some(c => c.label === 'integrator:clean:review-pre'), r.calls.filter(c => c.label.startsWith('integrator:clean')).map(c => c.label).join(','))
}

// S2 schema-valid-but-empty verifier --------------------------------------------------------------
{
  const st = state(fullPlan())
  const r = await runScenario('S2 empty-but-valid verifier on card 01', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'verify' && ctx.id.startsWith('platform-01-gate')) Object.assign(h, { hunks_cited: [], mutants: { written: 0, killed: 0 }, dod_reruns: [], checks: [] }); return h } })
  assert('S2 card not merged', row(r, 'platform-01-gate') && row(r, 'platform-01-gate').state !== 'merged+gate-green', row(r, 'platform-01-gate') && row(r, 'platform-01-gate').state)
  assert('S2 parked with no-progress: the empty verify yields the SAME never-empty fingerprint twice → two-strikes (C-18) [corrected, not a flip: v1 burned all 3 builds only because its fingerprint could be empty, disabling two-strikes]', row(r, 'platform-01-gate') && row(r, 'platform-01-gate').state === 'parked' && /no-progress/.test(row(r, 'platform-01-gate').reason), JSON.stringify(row(r, 'platform-01-gate')))
  assert('S2 exactly 2 build calls (two-strikes bounds the loop before MAX_BUILD)', r.calls.filter(c => c.label.startsWith('builder:')).length === 2, String(r.calls.filter(c => c.label.startsWith('builder:')).length))
}

// S3 verifier agrees but its own gate digest differs -----------------------------------------------------
{
  const st = state(fullPlan())
  const r = await runScenario('S3 verifier pass with a different digest', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'verify') { h.gate_digest = HEX(99); h.gate_steps = [{ name: 'ruff', exit_code: 0 }, { name: 'pytest-x2', exit_code: 0 }, { name: 'tree-dirty', exit_code: 1 }] } return h } })
  assert('S3 digest mismatch blocks the card', row(r, 'platform-01-gate') && row(r, 'platform-01-gate').state === 'parked', row(r, 'platform-01-gate') && row(r, 'platform-01-gate').state)
  const fixer = r.calls.find(c => c.label.startsWith('builder:fix:'))
  assert('S3 the fixer receives a typed digest-mismatch failure with both ledgers\' steps [flipped: v1 passed failures: []]', fixer && /"kind": "digest-mismatch"/.test(fixer.prompt) && /steps_only_in_verifier/.test(fixer.prompt) && /tree-dirty=1/.test(fixer.prompt), fixer && fixer.prompt.slice(fixer.prompt.indexOf('FAILING EVIDENCE'), fixer.prompt.indexOf('FAILING EVIDENCE') + 400))
  assert('S3 two-strikes fires on the repeated mismatch → 2 builds, reason no-progress [flipped: v1 burned 3]', r.calls.filter(c => c.label.startsWith('builder:')).length === 2 && /no-progress/.test(row(r, 'platform-01-gate').reason), String(r.calls.filter(c => c.label.startsWith('builder:')).length) + ' ' + (row(r, 'platform-01-gate') || {}).reason)
}

// S4 implementer reports [] outward actions but the merge shows a new remote -----------------------------
{
  const st = state(fullPlan())
  const r = await runScenario('S4 hidden remote surfaces at merge', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'merge') h.remotes = ['origin\tgit@github.com:x/y (push)']; return h } })
  assert('S4 HALT remote-added', r.out && /remote-added/.test(r.out.halt || ''), r.out && r.out.halt)
  assert('S4 checkpoint failed', r.out && r.out.status === 'failed', r.out && r.out.status)
  const mergeN = r.calls.find(c => c.label.startsWith('integrator:merge')).n
  assert('S4 no agent launched after HALT except the synthesizer (which DID run)', r.calls.filter(c => c.n > mergeN).every(c => c.label.startsWith('synthesizer')) && r.calls.some(c => c.label.startsWith('synthesizer')), r.calls.map(c => c.label).join(','))
  assert('S4 card row says merged+gate-green (true to git) and the rest are not_attempted:halt', row(r, 'platform-01-gate').state === 'merged+gate-green' && r.out.rows.filter(x => x.task_id !== 'platform-01-gate').every(x => x.state === 'not_attempted' && /halt/.test(x.reason)), JSON.stringify(rowsOf(r)))
}

// S5 two cards with overlapping write sets ---------------------------------------------------------------
{
  const cards = fullPlan(); cards[1].files_allowed = ['core/x.py']; cards[2].files_allowed = ['core/x.py']
  const st = state(cards)
  const r = await runScenario('S5 overlapping write sets (02, 03a)', baseArgs(), { reply: ctx => happy(ctx, st) })
  assert('S5 overlapping cards never share a pipeline batch', !r.batches.some(b => b.includes('platform-02-pins') && b.includes('platform-03a-types-fake')), JSON.stringify(r.batches.slice(0, 4)))
  assert('S5 wait logged', r.logs.some(l => /wait \(size or write-set overlap\)/.test(l)))
  assert('S5 all cards still merge', mergedCount(r) === N_CARDS, JSON.stringify(rowsOf(r)))
}

// S6 clean gate returns exit 0 with no ledger / without self_test ---------------------------------------------
{
  const st = state(fullPlan())
  const r = await runScenario('S6 clean gate exit 0 but empty digest', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'clean') h.gate_digest = ''; return h } })
  assert('S6 malformed clean gate does NOT revert a good merge (typed gate-unavailable)', !r.calls.some(c => c.label.startsWith('integrator:revert')) && r.logs.some(l => /clean-gate MALFORMED/.test(l)), 'revert calls: ' + r.calls.filter(c => c.label.startsWith('integrator:revert')).length)
  const st2 = state(fullPlan())
  const r2 = await runScenario('S6b clean gate with a self_test that contradicts exit 0', baseArgs(), { reply: ctx => { const h = happy(ctx, st2); if (ctx.mode === 'clean') h.self_test = { broken_red: false, false_claim_red: 'not-run' }; return h } })
  assert('S6b contradictory self_test does NOT revert a good merge', !r2.calls.some(c => c.label.startsWith('integrator:revert')) && r2.logs.some(l => /self-test contradicts/.test(l)), 'revert calls: ' + r2.calls.filter(c => c.label.startsWith('integrator:revert')).length)
  assert('S6b no lenses spent on a tree without a passing clean gate; stop clean-gate-unavailable', !r2.calls.some(c => c.label.startsWith('verifier:review')) && r2.out.stop_reason === 'clean-gate-unavailable', r2.out.stop_reason)
}

// S7 clean-gate null on every wave, then resume ---------------------------------------------------------------
{
  const st = state(fullPlan())
  const r = await runScenario('S7 null clean gate', baseArgs(), { reply: ctx => (ctx.mode === 'clean' ? null : happy(ctx, st)) })
  assert('S7 no revert on a dropped clean gate', !r.calls.some(c => c.label.startsWith('integrator:revert')))
  assert('S7 stop is not satisfied', r.out && r.out.stop_reason !== 'satisfied', r.out && r.out.stop_reason)
  assert('S7 review lenses NOT spent on a never-clean-gated tree [flipped: v1 spent 6 agents]', !r.calls.some(c => c.label.startsWith('verifier:review')), String(r.calls.filter(c => c.label.startsWith('verifier:review')).length))
  assert('S7 next_args.stage stays build (C-9)', r.out && r.out.next_args.stage === 'build', r.out && r.out.next_args.stage)
  const na = r.out.next_args
  const st2 = state(fullPlan(), { head: na.integration_sha_at_launch, mergedOnGit: r.out.rows.filter(x => x.state === 'merged+gate-green').map(x => x.task_id), priorRows: r.out.rows })
  const r2 = await runScenario('S7b resume after the null clean gate', baseArgs({ stage: na.stage, integration_sha_at_launch: na.integration_sha_at_launch, last_clean_gate: na.last_clean_gate, prior_status_path: '/g/status.json' }), { reply: ctx => happy(ctx, st2) })
  assert('S7b resume re-runs a clean gate at the current head before reviewing', r2.calls.some(c => c.label === 'integrator:clean:review-pre'), 'clean calls: ' + r2.calls.filter(c => c.label.startsWith('integrator:clean')).map(c => c.label).join(',') + ' stop=' + (r2.out && r2.out.stop_reason))
  assert('S7b resume reaches satisfied', r2.out && r2.out.stop_reason === 'satisfied', r2.out && r2.out.stop_reason)
}

// S8 budget exhaustion mid-wave ---------------------------------------------------------------------------------
{
  const st = state(fullPlan())
  let spent = 0
  const budget = { total: 1000000, spent: () => spent, remaining: () => 1000000 - spent }
  const r = await runScenario('S8 budget crosses RESERVE mid-wave', baseArgs(), { budget, reply: ctx => { spent += ctx.n >= 8 ? 200000 : 1000; return happy(ctx, st) } })
  const parked = r.out ? r.out.rows.filter(x => /parked/.test(x.state)) : []
  const na = r.out ? r.out.rows.filter(x => x.state === 'not_attempted') : []
  assert('S8 budget-starved cards are not_attempted (retryable), never parked', parked.length === 0 && na.length > 0 && na.every(x => /budget|agent-slice|dependency-blocked/.test(x.reason)), JSON.stringify(rowsOf(r)))
  assert('S8 next_args.stage repeats build', r.out && r.out.next_args.stage === 'build', r.out && r.out.next_args.stage)
  assert('S8 the synthesizer still ran under the budget guard', r.calls.some(c => c.label.startsWith('synthesizer')))
  if (r.out) {
    const st2 = state(fullPlan(), { head: r.out.next_args.integration_sha_at_launch, mergedOnGit: r.out.rows.filter(x => x.state === 'merged+gate-green').map(x => x.task_id), priorRows: r.out.rows })
    const r2 = await runScenario('S8b resume after budget exhaustion', baseArgs({ integration_sha_at_launch: r.out.next_args.integration_sha_at_launch, prior_status_path: '/g/s.json' }), { reply: ctx => happy(ctx, st2) })
    assert('S8b the starved cards get built on resume without retry_parked', mergedCount(r2) === N_CARDS, JSON.stringify(rowsOf(r2)))
  }
}

// S8c budget-ceiling throw ----------------------------------------------------------------------------------
{
  const st = state(fullPlan())
  const r = await runScenario('S8c agent() throws budget ceiling', baseArgs(), { reply: ctx => { if (ctx.n === 6) throw new Error('budget ceiling reached: spent >= total'); return happy(ctx, st) } })
  assert('S8c HALT budget-exhausted', r.out && r.out.halt === 'budget-exhausted', r.out && r.out.halt)
  assert('S8c synthesizer still ran [flipped from FAIL: C-7]', r.calls.some(c => c.label.startsWith('synthesizer')), r.calls.map(c => c.label).join(','))
  assert('S8c no retry after the throw: every call after call 6 is a synthesizer call', r.calls.filter(c => c.n > 6).every(c => c.label.startsWith('synthesizer')), r.calls.map(c => c.label).join(','))
  assert('S8c starved chains are not_attempted with a halt reason (retryable on resume)', r.out && r.out.rows.some(x => x.state === 'not_attempted' && /halt/.test(x.reason)), JSON.stringify(rowsOf(r)))
}

// S9 resume where the launch sha changed ----------------------------------------------------------------------
{
  const st = state(fullPlan(), { head: SHA(77) })
  const r = await runScenario('S9 stale launch sha', baseArgs({ integration_sha_at_launch: SHA(3) }), { reply: ctx => happy(ctx, st) })
  assert('S9 throws stale-launch-args → FAILED stop', r.out && /stale-launch-args/.test(r.out.stop_reason), r.out && r.out.stop_reason)
  assert('S9 no card agent launched', !r.calls.some(c => /^author|^builder/.test(c.label)))
  assert('S9 checkpoint failed and synth ran', r.out && r.out.status === 'failed' && r.calls.some(c => c.label.startsWith('synthesizer')))
}

// S10 secret-shaped string in output_tail -----------------------------------------------------------------------
{
  const st = state(fullPlan()); const SECRET = 'hf_' + 'A'.repeat(30)
  const r = await runScenario('S10 secret in builder output_tail', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.role === 'builder') h.dod[0].output_tail = 'token=' + SECRET; return h } })
  const leaked = r.calls.some(c => c.prompt.includes(SECRET)) || r.logs.some(l => l.includes(SECRET)) || JSON.stringify(r.out).includes(SECRET)
  assert('S10 secret never reaches any prompt/log/checkpoint', !leaked)
  assert('S10 card blocked secret-shaped-output', r.logs.some(l => /SECRET-SHAPED/.test(l)) && row(r, 'platform-01-gate').state === 'parked' && /secret-shaped-output/.test(row(r, 'platform-01-gate').reason), JSON.stringify(row(r, 'platform-01-gate')))
  assert('S10 no fixer launched after the secret', !r.calls.some(c => c.label.startsWith('builder:fix')))
}

// S11 null from the veto judge ------------------------------------------------------------------------------------
{
  const st = state(fullPlan())
  const r = await runScenario('S11 veto judge null', baseArgs(), { reply: ctx => (ctx.mode === 'veto' ? null : happy(ctx, st)) })
  assert('S11 stop veto-unavailable', r.out && r.out.stop_reason === 'veto-unavailable', r.out && r.out.stop_reason)
  assert('S11 status not ready', r.out && r.out.status !== 'ready')
  assert('S11 veto retried once then parked (2 calls)', r.calls.filter(c => c.label.startsWith('verifier:veto')).length === 2, String(r.calls.filter(c => c.label.startsWith('verifier:veto')).length))
}

// S12 review finding → fix card: buildable? ----------------------------------------------------------------------
{
  const st = state(fullPlan()); let reviewed = 0
  const F = { id: 'RV-1', title: 'stop normaliser duplicated', file: 'core/x.py', severity: 'high', kind: 'correctness', reproduction: { command: '! grep -c normalize_stop core/x.py | grep -qx 1', exit_code: 1, output_tail: '2 defs' }, corrected_claim: 'one normaliser only', fix_hint: 'dedupe', files_allowed: ['core/x.py'], verification_level: 'local-mechanical' }
  const r = await runScenario('S12 fix card from a confirmed review finding', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'review' && ctx.id.includes('correctness') && reviewed++ === 0) h.findings = [F]; if (ctx.mode === 'refute') { h.verdict = 'holds'; h.findings = [F] } return h } })
  const fw = r.calls.find(c => c.label.startsWith('integrator:fixcards')), fa = r.calls.find(c => c.label.startsWith('author:tests:platform-00-rf'))
  assert('S12 the integrator wrote the fix card to plan/fixes/ BEFORE the author ran [flipped: v1 named a file nobody wrote]', fw && fa && fw.n < fa.n && /plan\/fixes\/platform-00-rf1-01-[a-z0-9-]+\.json/.test(fw.prompt), fw ? 'fixcards n=' + fw.n + ' author n=' + (fa && fa.n) : 'no fixcards call')
  assert('S12 fix-card prompt carries the finding text AND the DoD command [flipped from FAIL: C-3]', fa && fa.prompt.includes('normalize_stop') && fa.prompt.includes('one normaliser only'), 'absent')
  assert('S12 fix-card gate command passes --card plan/fixes/<fixid>.json', fa && /--card plan\/fixes\/platform-00-rf1-01/.test(fa.prompt))
  assert('S12 the fix card merged and the loop ended satisfied', row(r, 'platform-00-rf1-01-rv-1') && row(r, 'platform-00-rf1-01-rv-1').state === 'merged+gate-green' && r.out.stop_reason === 'satisfied', JSON.stringify(rowsOf(r)) + ' stop=' + r.out.stop_reason)
}

// S13 parked root card + not_attempted dependents → satisfied()? -------------------------------------------------
{
  const st = state(fullPlan())
  const r = await runScenario('S13 root card parked (verify fails ×3)', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'verify' && ctx.id.startsWith('platform-01-gate')) { h.verdict = 'fail'; h.failures = [{ test: 't' + ctx.n, first_error_line: 'AssertionError ' + ctx.n }] } return h } })
  assert('S13 review loop must NOT report satisfied on a tree with unbuilt cards [flipped from FAIL: C-5]', r.out && r.out.stop_reason === 'tree-incomplete', r.out && r.out.stop_reason)
  assert('S13 no review lenses spent', !r.calls.some(c => c.label.startsWith('verifier:review')), String(r.calls.filter(c => c.label.startsWith('verifier:review')).length) + ' lenses')
  assert('S13 checkpoint not ready', r.out && r.out.status !== 'ready')
  assert('S13 dependents are not_attempted:dependency-blocked and were never built', row(r, 'platform-02-pins').state === 'not_attempted' && /dependency-blocked:platform-01-gate\(parked\)/.test(row(r, 'platform-02-pins').reason) && !r.calls.some(c => /platform-02-pins|platform-03a/.test(c.label)), JSON.stringify(rowsOf(r)))
}

// S14 already-merged with a bogus head ---------------------------------------------------------------------------
{
  const st = state(fullPlan())
  const r = await runScenario('S14 integrator claims already-merged with a foreign head', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'merge') { h.status = 'already-merged'; h.head_sha = SHA(66); h.gate_exit_code = 1; h.gate_digest = ''; h.cherry_unmerged = ['deadbeef'] } return h } })
  assert('S14 already-merged without gate/cherry evidence must not count as merged', row(r, 'platform-01-gate').state !== 'merged+gate-green' && /already-merged-unproven/.test(row(r, 'platform-01-gate').reason), JSON.stringify(row(r, 'platform-01-gate')))
  assert('S14 head must not jump to an unverified sha (for the right reason: no clean gate reverted it)', r.out.head_sha === SHA(3) && !r.calls.some(c => c.label.startsWith('integrator:revert')), r.out.head_sha)
}

// S15 stage run: confirmed staging-evidence finding (canary failed) → promote-production? ----------------------------
{
  const F = { id: 'EV-1', title: 'canary failed: healthz git_sha mismatch ×3', file: 'evidence/staging/x/canary.json', severity: 'critical', kind: 'staging-evidence', reproduction: { command: 'jq -e .pass canary.json', exit_code: 1, output_tail: 'false' }, corrected_claim: 'canary did not pass', verification_level: 'staging-required' }
  const plan = fullPlan()
  const st = state(plan, { head: SHA(3), mergedOnGit: plan.map(c => c.id), evidenceFindings: [F] })
  const r = await runScenario('S15 stage with a failed canary in the evidence', baseArgs({ stage: 'stage', integration_sha_at_launch: SHA(3), last_clean_gate: { head_sha: SHA(3), digest: HEX(6) }, owner_approvals: Object.assign({}, OA_HAPPY, { github_repo_url: 'u', staging_space_ids: ['a', 'b'], staging_evidence_dir: '/ev', production_space_head: BASE }) }), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'refute') { h.verdict = 'holds'; h.findings = [F] } return h } })
  assert('S15 promote-production must NOT be emitted while a confirmed staging finding is blocked_on_owner [flipped from FAIL: C-6]', !(r.out && r.out.actions.some(a => a.kind === 'promote-production')), r.out && r.out.actions.map(a => a.kind).join(','))
  assert('S15 status blocked, stop blocked-on-owner:staging-evidence, the finding row carries severity + next', r.out && r.out.status === 'blocked' && r.out.stop_reason === 'blocked-on-owner:staging-evidence' && r.out.blocked_on_owner.some(b => b.task_id === 'finding:EV-1' && b.severity === 'critical' && b.next), r.out && (r.out.status + ' ' + r.out.stop_reason + ' ' + JSON.stringify(r.out.blocked_on_owner)))
  assert('S15 next_args.stage stays stage', r.out && r.out.next_args.stage === 'stage', r.out && r.out.next_args.stage)
}

// S16 journeys merge prompt: does the merge gate run the journeys? ------------------------------------------------------
{
  const st = state(fullPlan())
  const r = await runScenario('S16 seam card merges → journeys author → merge', baseArgs(), { reply: ctx => happy(ctx, st) })
  const jm = r.calls.find(c => /^integrator:merge:journeys-plan-w/.test(c.label))
  assert('S16 journeys author launched after a seam wave', r.calls.some(c => c.label.startsWith('author:journeys')))
  assert('S16 journeys merge gate command includes --journeys [flipped from FAIL: C-4]', jm && /--journeys/.test(jm.prompt), jm ? jm.prompt.match(/bash [^\n]*gate\.sh[^\n]*/)[0].slice(0, 200) : 'no merge call')
  const ja = r.calls.find(c => c.label.startsWith('author:journeys'))
  assert('S16 journeys author is told about the journey marker and the needs= rule', ja && /journey`/.test(ja.prompt) && /needs=<card-id>/.test(ja.prompt))
}

// S17 plan stage: REFUTED finding cited + manifest cards missing → checkpoint --------------------------------------------
{
  const cards = [card('platform-01-gate', [], ['tools/gate.sh'], { finding_ids: [{ id: 'critic-4', corrected_text: 'x'.repeat(30) }] })]
  const st = state(cards)
  const r = await runScenario('S17 plan cites a REFUTED finding (3-card plan)', baseArgs({ stage: 'plan', plan_sha: undefined }), { reply: ctx => happy(ctx, st) })
  assert('S17 plan-needs-repair recorded (REFUTED cite + missing manifest cards)', r.out && r.out.plan_defects && r.out.plan_defects.some(d => /REFUTED/.test(d)) && r.out.plan_defects.some(d => /plan lacks/.test(d)), r.out && JSON.stringify(r.out.plan_defects))
  assert('S17 approve-plan NOT emitted; repair-plan emitted instead [flipped from FAIL: C-19]', r.out && !r.out.actions.some(a => a.kind === 'approve-plan') && r.out.actions.some(a => a.kind === 'repair-plan'), r.out && r.out.actions.map(a => a.kind).join(','))
  assert('S17 next_args.stage = plan with plan_defects carried [flipped from FAIL: C-19/C-22]', r.out && r.out.next_args.stage === 'plan' && r.out.next_args.plan_defects.length > 0, r.out && r.out.next_args.stage)
  const st2 = state(cards, { preverified: [{ id: 'critic-4', verdict: 'refuted', corrected_claim: 'x', level: 'local-mechanical' }] })
  const r2 = await runScenario('S17b build stage with the defective plan', baseArgs(), { reply: ctx => happy(ctx, st2) })
  assert('S17b R1 refuses a plan whose card cites a REFUTED id / lacks manifest cards [flipped from FAIL: C-19]', r2.out && /FAILED:plan-needs-repair/.test(r2.out.stop_reason) && /REFUTED/.test(r2.out.stop_reason) && !r2.calls.some(c => /^author|^builder/.test(c.label)), r2.out && r2.out.stop_reason)
  // S17c: the repair path — the planner is re-run with args.plan_defects and the prompt carries them
  const st3 = state(fullPlan())
  const r3 = await runScenario('S17c plan repair relaunch with args.plan_defects', baseArgs({ stage: 'plan', plan_sha: undefined, plan_defects: ['decision G-3 must be marked against_recommendation (F-9)'] }), { reply: ctx => { const h = happy(ctx, st3); if (ctx.role === 'planner' && ctx.mode === 'plan') h.decisions = ['G-1', 'G-3', 'G-2', 'M-5', 'G-15+G-24'].map(id => ({ id, decided_value: 'x', against_recommendation: true, consequences: [], dq_line: 85 })); return h } })
  const pp = r3.calls.find(c => c.label.startsWith('planner:plan'))
  assert('S17c planner runs in REPAIR MODE with the defects, plan verified, approve-plan emitted', pp && /REPAIR MODE/.test(pp.prompt) && r3.out.stop_reason === 'plan-verified' && r3.out.actions.some(a => a.kind === 'approve-plan') && r3.out.next_args.stage === 'build', r3.out && (r3.out.stop_reason + ' ' + JSON.stringify(r3.out.plan_defects)))
}

// ======================= NEW SCENARIOS (v2) =======================
// N1 journeys still skipped after their card merged → synthetic blocking finding → refuter → fix card (C-4)
{
  const st = state(fullPlan()); let seenFix = false
  const r = await runScenario('N1 journey skipped after its card merged → synthetic finding', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'clean' && st.cards && (st.m || 0) >= 4) h.journeys = { collected: 3, failed: 0, skipped_needs: ['platform-03b-thin-slice'] }; if (ctx.mode === 'refute' && /journey-needs/.test(ctx.id)) { seenFix = true; h.verdict = 'holds'; h.findings = [{ id: 'journey-needs-platform-03b-thin-slice', title: 'journey skipped after its card merged', file: 'tests/journeys', severity: 'high', kind: 'interaction', reproduction: { command: 'gate --journeys', exit_code: 1, output_tail: 'skipped' }, verification_level: 'local-stub', files_allowed: ['tests/journeys'] }] } return h } })
  assert('N1 the synthetic finding reached the refuter', r.calls.some(c => /^verifier:refute:journey-needs-platform-03b-thin-slice/.test(c.label)), r.calls.filter(c => c.label.startsWith('verifier:refute')).map(c => c.label).join(','))
  assert('N1 a fix card for it was written to plan/fixes and built', r.calls.some(c => c.label.startsWith('integrator:fixcards')) && r.out.rows.some(x => /^platform-00-rf1-01-journey-needs/.test(x.task_id)), JSON.stringify(rowsOf(r)))
}

// N2 malformed clean gate on wave 1 only, healthy later → typed unavailable, no revert, satisfied in the end (C-11 + C-10)
{
  const st = state(fullPlan()); let n = 0
  const r = await runScenario('N2 one malformed clean gate, healthy afterwards', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'clean' && n++ === 0) h.gate_digest = 'not-a-digest'; return h } })
  assert('N2 no revert; the malformed return is logged as unavailable', !r.calls.some(c => c.label.startsWith('integrator:revert')) && r.logs.some(l => /MALFORMED/.test(l)))
  assert('N2 the run still ends satisfied and ready', r.out.stop_reason === 'satisfied' && r.out.status === 'ready', r.out.stop_reason + ' ' + r.out.status)
}

// N3 clean gate RED after a journeys merge → the revert targets the JOURNEYS merge sha, not the card's (C-12)
{
  const st = state(fullPlan()); let redOnce = false
  const r = await runScenario('N3 clean gate red right after a journeys merge', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'clean' && st.lastJourneyMerge && !redOnce) { redOnce = true; h.gate_exit_code = 1 } if (ctx.mode === 'merge' && /journeys/.test(ctx.id) && !redOnce) st.lastJourneyMerge = h.merge_sha; return h } })   // frozen at the first journeys merge: wave 4's journeys merge must not move the sha the assertion compares against
  const rv = r.calls.find(c => c.label.startsWith('integrator:revert'))
  assert('N3 exactly one revert, of the journeys merge, by its merge sha', rv && /journeys-plan-w/.test(rv.label) && rv.prompt.includes('git revert -m 1 ' + st.lastJourneyMerge), rv ? rv.label + ' ' + (rv.prompt.match(/git revert -m 1 [0-9a-f]{40}/) || [])[0] : 'no revert')
  assert('N3 no card row was marked reverted (the reverted merge was the journeys branch)', !r.out.rows.some(x => x.state === 'reverted'), JSON.stringify(rowsOf(r)))
  const firstCleanAfterRevert = rv ? r.calls.find(c => c.label.startsWith('integrator:clean') && c.n > rv.n) : null
  const firstLens = r.calls.find(c => c.label.startsWith('verifier:review'))
  assert('N3 a passing clean gate ran after the revert and before any lens; the run ended satisfied [corrected, not a flip: the re-gate is wave 4\'s clean gate, which is why the literal review-pre label never appears — the invariant is a clean pass at head before the first lens (C-10)]', !!firstCleanAfterRevert && (!firstLens || firstLens.n > firstCleanAfterRevert.n) && r.out.stop_reason === 'satisfied', r.out.stop_reason)
}

// N4 merge returns merged + gate red → checked revert by merge sha; state reverted (C-20)
{
  const st = state(fullPlan()); let once = false
  const r = await runScenario('N4 integrator returns merged with a red gate', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'merge' && !once) { once = true; h.gate_exit_code = 1 } return h } })
  const rv = r.calls.find(c => c.label.startsWith('integrator:revert'))
  assert('N4 a checked revert of that merge sha ran', rv && rv.prompt.includes('git revert -m 1 ' + SHA(81)), rv && (rv.prompt.match(/git revert -m 1 [0-9a-f]{40}/) || [])[0])
  assert('N4 card 01 is reverted (not merged), its dependents are dependency-blocked', row(r, 'platform-01-gate').state === 'reverted' && row(r, 'platform-02-pins').state === 'not_attempted', JSON.stringify(rowsOf(r)))
}

// N5 resume: prior parked rows with agent-null reasons are auto-retried; a real park stays parked unless retry_parked names it (C-8/C-22)
{
  const plan = fullPlan()
  const prior = [{ task_id: 'platform-01-gate', state: 'merged+gate-green', head_sha: SHA(51), reason: 'merged' }, { task_id: 'platform-02-pins', state: 'parked', head_sha: 'none', reason: 'agent-null:verifier' }, { task_id: 'platform-03a-types-fake', state: 'parked', head_sha: SHA(33), reason: 'fix-exhausted' }, { task_id: 'platform-03b-thin-slice', state: 'not_attempted', head_sha: 'none', reason: 'not_attempted:agent-slice-or-budget' }]
  const st = state(plan, { head: SHA(51), mergedOnGit: ['platform-01-gate'], priorRows: prior })
  const r = await runScenario('N5 resume with prior parked rows', baseArgs({ integration_sha_at_launch: SHA(51), prior_status_path: '/g/s.json', last_clean_gate: { head_sha: SHA(51), digest: HEX(6) } }), { reply: ctx => happy(ctx, st) })
  assert('N5 the agent-null park was re-driven automatically and merged', row(r, 'platform-02-pins').state === 'merged+gate-green' && r.logs.some(l => /platform-02-pins was parked for a retryable reason/.test(l)), JSON.stringify(row(r, 'platform-02-pins')))
  assert('N5 the fix-exhausted park stays parked with its reason; its dependents are dependency-blocked', row(r, 'platform-03a-types-fake').state === 'parked' && /prior:fix-exhausted/.test(row(r, 'platform-03a-types-fake').reason) && row(r, 'platform-03b-thin-slice').state === 'not_attempted', JSON.stringify(rowsOf(r)))
  assert('N5 stop tree-incomplete, no lenses, next_args.stage build', r.out.stop_reason === 'tree-incomplete' && !r.calls.some(c => c.label.startsWith('verifier:review')) && r.out.next_args.stage === 'build', r.out.stop_reason)
  const st2 = state(plan, { head: SHA(51), mergedOnGit: ['platform-01-gate'], priorRows: prior })
  const r2 = await runScenario('N5b same resume with retry_parked naming the fix-exhausted card', baseArgs({ integration_sha_at_launch: SHA(51), prior_status_path: '/g/s.json', last_clean_gate: { head_sha: SHA(51), digest: HEX(6) }, retry_parked: ['platform-03a-types-fake'] }), { reply: ctx => happy(ctx, st2) })
  assert('N5b retry_parked re-drives it; the whole tree completes', mergedCount(r2) === N_CARDS && r2.out.stop_reason === 'satisfied', JSON.stringify(rowsOf(r2)))
}

// N6 checkpoint: parked rows carry reason + next; retry_parked_suggested lists only retryable parks (C-22)
{
  const st = state(fullPlan()); let nulls = 0
  const r = await runScenario('N6 verifier drops twice on card 01 → agent-null park', baseArgs(), { reply: ctx => (ctx.mode === 'verify' && nulls++ < 2 ? null : happy(ctx, st)) })
  assert('N6 card 01 parked agent-null:verifier with next=retry_parked', row(r, 'platform-01-gate').state === 'parked' && row(r, 'platform-01-gate').reason === 'agent-null:verifier' && row(r, 'platform-01-gate').next === 'retry_parked', JSON.stringify(row(r, 'platform-01-gate')))
  assert('N6 parked[] entries carry reason + next; retry_parked_suggested = [platform-01-gate]', r.out.parked.every(p => p.reason && p.next) && JSON.stringify(r.out.next_args.retry_parked_suggested) === JSON.stringify(['platform-01-gate']), JSON.stringify(r.out.parked) + ' ' + JSON.stringify(r.out.next_args.retry_parked_suggested))
}

// N7 next_args.stage never advances after max-rounds (C-9): each round a fresh low-severity owner-level finding
{
  const st = state(fullPlan()); let k = 0
  const r = await runScenario('N7 review loop ends max-rounds', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'review' && ctx.id.includes('security')) { k++; h.findings = [{ id: 'OW-' + k, title: 'quota row ' + k, file: 'worker/lease.py', severity: 'high', kind: 'omitted-obligation', reproduction: { command: 'test -f x', exit_code: 1, output_tail: '' }, verification_level: 'staging-required' }] } if (ctx.mode === 'refute') { h.verdict = 'holds'; h.findings = [{ id: ctx.id.replace(/:.*/, ''), title: 'quota row', file: 'worker/lease.py', severity: 'high', kind: 'omitted-obligation', reproduction: { command: 'test -f x', exit_code: 1, output_tail: '' }, verification_level: 'staging-required' }] } return h } })   // severity high, not low: low-severity owner findings do not block satisfied() by design, so they can never drive the loop to max-rounds
  assert('N7 stop max-rounds(3) [corrected fixture, assertion unchanged: the drive originally fed low-severity findings, which satisfied() correctly tolerates — critical/high are what keep it false]', r.out.stop_reason === 'max-rounds(3)', r.out.stop_reason)
  assert('N7 status blocked (owner-level findings), next_args.stage stays build', r.out.status === 'blocked' && r.out.next_args.stage === 'build' && r.out.blocked_on_owner.length === 3, r.out.status + ' ' + r.out.next_args.stage + ' ' + r.out.blocked_on_owner.length)
}

// N8 promote stage with a confirmed critical finding → rollback action, no ready (C-6)
{
  const F = { id: 'PR-1', title: 'production healthz sha unknown', file: 'evidence/prod/healthz.json', severity: 'critical', kind: 'staging-evidence', reproduction: { command: 'jq -e ".git_sha != \\"unknown\\"" healthz.json', exit_code: 1, output_tail: 'false' }, verification_level: 'staging-required' }
  const plan = fullPlan(); const st = state(plan, { head: SHA(3), mergedOnGit: plan.map(c => c.id), evidenceFindings: [F] })
  const r = await runScenario('N8 promote stage with a confirmed critical finding', baseArgs({ stage: 'promote', integration_sha_at_launch: SHA(3), last_clean_gate: { head_sha: SHA(3), digest: HEX(6) }, owner_approvals: Object.assign({}, OA_HAPPY, { github_repo_url: 'u', staging_space_ids: ['a', 'b'], production_evidence_dir: '/pev', production_space_head: BASE }) }), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'refute') { h.verdict = 'holds'; h.findings = [F] } return h } })
  assert('N8 rollback action emitted with the finding id; status blocked; next stage stays promote [strengthened: C-9 pins the stage at promote, not merely not-done]', r.out.actions.some(a => a.kind === 'rollback' && /PR-1/.test(a.why)) && r.out.status === 'blocked' && r.out.next_args.stage === 'promote', r.out.actions.map(a => a.kind).join(',') + ' ' + r.out.status + ' ' + r.out.next_args.stage)
  const st2 = state(plan, { head: SHA(3), mergedOnGit: plan.map(c => c.id), evidenceFindings: [] })
  const r2 = await runScenario('N8b promote stage with clean evidence', baseArgs({ stage: 'promote', integration_sha_at_launch: SHA(3), last_clean_gate: { head_sha: SHA(3), digest: HEX(6) }, owner_approvals: Object.assign({}, OA_HAPPY, { github_repo_url: 'u', staging_space_ids: ['a', 'b'], production_evidence_dir: '/pev', production_space_head: BASE }) }), { reply: ctx => happy(ctx, st2) })
  assert('N8b clean evidence → satisfied, ready, no rollback', r2.out.stop_reason === 'satisfied' && r2.out.status === 'ready' && !r2.out.actions.some(a => a.kind === 'rollback'), r2.out.stop_reason + ' ' + r2.out.status)
}

// N9 already-merged WITH evidence (head unchanged, gate green, cherry empty) counts as merged (C-20, idempotent resume)
{
  const st = state(fullPlan())
  const r = await runScenario('N9 proven already-merged', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'merge' && ctx.id === 'platform-01-gate') { h.status = 'already-merged'; h.head_sha = SHA(3); h.merge_sha = '' } return h } })
  assert('N9 card 01 counted merged (already-merged(proven)); head unchanged; the run completes', row(r, 'platform-01-gate').state === 'merged+gate-green' && /already-merged\(proven\)/.test(row(r, 'platform-01-gate').reason) && mergedCount(r) === N_CARDS, JSON.stringify(row(r, 'platform-01-gate')))
}

// N10 "holds" with a reproduction that exits 0 is ignored (C-27); notes mentioning the digest are not receipt-shaped (C-23)
{
  const st = state(fullPlan()); let reviewed = 0
  const F = { id: 'RV-0', title: 'weak repro', file: 'core/y.py', severity: 'high', kind: 'correctness', reproduction: { command: 'grep -n foo core/y.py', exit_code: 0, output_tail: 'hit' }, files_allowed: ['core/y.py'], verification_level: 'local-mechanical' }
  const r = await runScenario('N10 holds with exit-0 reproduction; digest wording in notes', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'verify') h.notes = 'pass based on the digest equality'; if (ctx.mode === 'review' && ctx.id.includes('correctness') && reviewed++ === 0) h.findings = [F]; if (ctx.mode === 'refute') { h.verdict = 'holds'; h.findings = [F] } return h } })
  assert('N10 no fix card for a holds whose reproduction exits 0; logged', !r.calls.some(c => c.label.startsWith('integrator:fixcards')) && r.logs.some(l => /without a non-zero-exit reproduction ignored/.test(l)))
  assert('N10 verifier notes "based on the digest" are NOT nulled; all cards merged', mergedCount(r) === N_CARDS && !r.logs.some(l => /receipt-shaped/.test(l)), JSON.stringify(rowsOf(r)))
}

// N11 second author attempt receives the red verdict (C-26); confirm-RED requires digest equality (C-29)
{
  const st = state(fullPlan()); let reds = 0
  const r = await runScenario('N11 confirm-RED fails once (digest differs), author re-driven with the verdict', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'red' && ctx.id.startsWith('platform-01-gate') && reds++ === 0) { h.gate_digest = HEX(77); h.failures = [{ test: 'tests/unit/t.py::test_x', first_error_line: 'passed unexpectedly' }] } return h } })
  const a2 = r.calls.find(c => c.label === 'author:tests:platform-01-gate:2')
  assert('N11 author attempt 2 carries the red verdict (digest_equal false, failures)', a2 && /PREVIOUS ATTEMPT REJECTED/.test(a2.prompt) && /"digest_equal": false/.test(a2.prompt) && /passed unexpectedly/.test(a2.prompt), a2 ? a2.prompt.slice(-400) : 'no second author call')
  assert('N11 the card then builds and merges', row(r, 'platform-01-gate').state === 'merged+gate-green')
}

// N12 owner precondition: fixture #1 missing → 04 blocked_on_owner, downstream not_attempted, no lenses, status blocked, actions carry record-fixture-1
{
  const st = state(fullPlan())
  const r = await runScenario('N12 fixture #1 not recorded', baseArgs({ owner_approvals: Object.assign({}, OA_HAPPY, { fixture1_path: null }) }), { reply: ctx => happy(ctx, st) })
  assert('N12 04 blocked_on_owner with next; 05a not_attempted:dependency-blocked; 08a (independent) merged', row(r, 'platform-04-streamparser').state === 'blocked_on_owner' && /owner records/.test(row(r, 'platform-04-streamparser').next) && row(r, 'platform-05a-registry').state === 'not_attempted' && row(r, 'platform-08a-worker-pure').state === 'merged+gate-green', JSON.stringify(rowsOf(r)))
  assert('N12 status blocked, record-fixture-1 action, no lenses, next stage build', r.out.status === 'blocked' && r.out.actions.some(a => a.kind === 'record-fixture-1') && !r.calls.some(c => c.label.startsWith('verifier:review')) && r.out.next_args.stage === 'build', r.out.status + ' ' + r.out.stop_reason)
}

// ---- v2.1 scenarios (post critic-v2): V-1 receipt log-only · V-2 conftest pin · V-3 R1 repair next_args · V-11 journeys gate refused

// S38 (V-1) a verifier writes a REMAINING receipt phrase → the return stands, the fragment is logged, the card still merges (was: parked agent-null)
{
  const st = state(fullPlan())
  const r = await runScenario('S38 (V-1) verifier notes carry a remaining receipt phrase', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.role === 'verifier' && ctx.mode === 'verify' && ctx.id === 'platform-02-pins:1') h.strongest_disagreement = 'will report back when the run ends'; return h } })
  assert('S38 the receipt fragment is logged (matched "will report back when") and nothing is BLOCKED as receipt-shaped', r.logs.some(l => /receipt-shaped fragment \(matched "will report back when"\)/.test(l)) && !r.logs.some(l => /BLOCK .*receipt-shaped/.test(l)), JSON.stringify(r.logs.filter(l => /receipt/i.test(l))))
  assert('S38 the card PROCEEDS and merges — assertCommon no longer nulls on a receipt phrase', row(r, 'platform-02-pins').state === 'merged+gate-green', JSON.stringify(row(r, 'platform-02-pins')))
  assert('S38 the whole run still ends satisfied (log-only cost, no behaviour change)', r.out.stop_reason === 'satisfied', r.out.stop_reason)
}

// S39 (V-2) the stage=plan planner prompt pins the exact path-scoped journeys conftest, the pytest.ini marker registration and the both-collections DoD demand
{
  const st = state(fullPlan())
  const r = await runScenario('S39 (V-2) planner prompt pins the journeys conftest byte-for-byte', baseArgs({ stage: 'plan' }), { reply: ctx => happy(ctx, st) })
  const pp = r.calls.find(c => c.label === 'planner:plan:r1a')
  assert('S39 the prompt carries the exact path-scoped hook (not pytestmark-in-conftest, not unscoped)', !!pp && pp.prompt.includes('def pytest_collection_modifyitems(items):') && pp.prompt.includes('it.path.is_relative_to(pathlib.Path(__file__).parent)') && pp.prompt.includes('it.add_marker(pytest.mark.journey)') && pp.prompt.includes('BYTE-FOR-BYTE'), pp ? pp.prompt.slice(Math.max(0, pp.prompt.indexOf('pytest_collection_modifyitems') - 80), pp.prompt.indexOf('pytest_collection_modifyitems') + 320) : 'no planner call')
  assert('S39 the prompt demands the pytest.ini marker registration and BOTH collections on card 01', !!pp && /pytest\.ini registering `journey:` under markers/.test(pp.prompt) && /BOTH-collections line/.test(pp.prompt), pp ? 'registration/both-collections text missing' : 'no planner call')
}

// S40 (V-3) R1 plan-needs-repair → next_args loops back to stage=plan WITH the defects (was: stage=build, defects dropped)
{
  const stBad = state(fullPlan(), { preverified: [{ id: 'inf-9', verdict: 'refuted', corrected_claim: 'refuted by the executed pre-verification probe', level: 'local-mechanical' }] })
  stBad.cards = fullPlan(); stBad.cards[1] = Object.assign({}, stBad.cards[1], { finding_ids: [{ id: 'inf-9', corrected_text: 'cites inf-9 whose pre-verification REFUTED it' }] })
  const r = await runScenario('S40 (V-3) R1 throws plan-needs-repair on a REFUTED citation', baseArgs(), { reply: ctx => happy(ctx, stBad) })
  assert('S40 stop FAILED:plan-needs-repair before any author/builder runs', /^FAILED:plan-needs-repair/.test(r.out.stop_reason) && !r.calls.some(c => /^author|^builder/.test(c.label)), r.out.stop_reason)
  assert('S40 next_args.stage === \'plan\' WITH plan_defects populated [v2.1 V-3: previously stage=build with an empty list]', r.out.next_args.stage === 'plan' && Array.isArray(r.out.next_args.plan_defects) && r.out.next_args.plan_defects.some(d => /REFUTED/.test(d)), 'stage=' + (r.out.next_args || {}).stage + ' defects=' + JSON.stringify((r.out.next_args || {}).plan_defects))
}

// S41 (V-11) a journeys author reporting SUCCESS over a red journeys-only gate is refused — never integrated
{
  const st = state(fullPlan())
  const r = await runScenario('S41 (V-11) journeys authors report SUCCESS over red gates', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.role === 'author' && ctx.mode === 'journeys') h.gate_exit_code = 1; return h } })
  assert('S41 the refused journeys branch is never integrated (no merge/ff for it)', !r.calls.some(c => /^integrator:(merge|ff):journeys/.test(c.label)), r.calls.filter(c => /journeys/.test(c.label)).map(c => c.label).join(','))
  assert('S41 the refusal is logged with the required-evidence note and the run still ends satisfied', r.logs.some(l => /journeys author .*refused/.test(l)) && r.out.stop_reason === 'satisfied', r.out.stop_reason + ' ' + JSON.stringify(r.logs.filter(l => /journeys author/.test(l)).slice(0, 2)))
}

console.log('\n==== SUMMARY: ' + results.filter(r => r.ok).length + ' passed, ' + results.filter(r => !r.ok).length + ' failed, scenarios: ' + new Set(results.map(r => r.scenario)).size)
for (const r of results.filter(r => !r.ok)) console.log('FAILED: ' + r.name)
