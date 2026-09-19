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


{
  const st = state(PLAN3)
  const r = await runScenario('S13x root card parked', baseArgs(), { reply: ctx => { const h = happy(ctx, st); if (ctx.mode === 'verify' && ctx.id.startsWith('platform-01-gate')) h.verdict = 'fail'; return h } })
  console.log('batches:', JSON.stringify(r.batches))
  console.log('calls:', r.calls.map(c=>c.label).join(' | '))
  console.log(r.logs.filter(l=>/wave|satisfied|parked|NOT attempted/.test(l)).join('\n'))
}
{
  const st = state(PLAN3)
  const r = await runScenario('S8cx budget throw', baseArgs(), { reply: ctx => { if (ctx.n === 6) throw new Error('budget ceiling reached'); return happy(ctx, st) } })
  console.log('calls:', r.calls.map(c=>c.label).join(' | '))
  console.log(r.logs.filter(l=>/HALT|synth|RUN END/.test(l)).join('\n'))
  console.log('report_path in checkpoint:', r.out && r.out.report_path, 'rows_consistent:', r.out && r.out.rows_consistent)
}
