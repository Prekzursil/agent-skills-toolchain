const meta = {
  name: 'space-rebuild-v2',
  description: 'Implementation workflow for the qwen38 heretic Space (design-v2 = A3 base + judge grafts + critic fixes): plan (pre-verify findings → api ledger → catalog provenance → planner → JS checkPlan → plan verifier; repair path) → per card (author → confirm-RED with expected_green exceptions → build → verify with digest equality, mutants, revert-proof → bounded fix with typed digest-mismatch) in runtime DAG waves → serial integrate by merge sha + clean gate typed pass|fail|unavailable with self-test + journeys → review/refute/fix cards on plan/fixes → veto loop → synthesizer always; outward actions only as owner checkpoints between runs',
  phases: [
    { title: 'Setup', detail: 'idempotent + the one live state probe per invocation: durable clone at base_sha, pinned venv/gate/baseline verified (never created here), red-proof, plan merged into integration, live heads, remotes, prior rows with reasons' },
    { title: 'Plan', detail: 'pre-verify UNVERIFIED findings (executed reproduction) ‖ api-ledger with known_bad ‖ catalog provenance saved raw → planner writes decisions.json (against_recommendation, dq_line) + cards + index → checkPlan (JS, every stage) → verifier mode:plan refutes; a defective plan yields repair-plan, never approve-plan' },
    { title: 'Build', detail: 'per card: author → red (expected_green_tests exempt) → builder → verifier (gate digest must equal the builder\'s on a clean tree; mutants all killed; revert-proof red; every local DoD id exit 0 on both sides) → bounded fix with typed failures; waves computed one at a time from the live status map (dependents of a parked card are never built)' },
    { title: 'Integrate', detail: 'serial single-writer merges in rank order, gate on the merged tree with --journeys, conflict call, revert by merge sha (checked), bundle, clean-gate --self-test --journeys per wave typed pass|fail|gate-unavailable, journeys author when a seam card merged' },
    { title: 'Review', detail: 'tree-complete + passing clean gate at head required before any lens; 3 lenses → dedup vs persisted seen → refute with a non-zero-exit reproduction → fix cards written to plan/fixes by the integrator → satisfied() predicate → veto-only judge (fail closed on drop; probesUsed to the inversion mandate); MAX_ROUNDS/dry/budget/agent caps; evidence stages stop on a confirmed critical/high staging finding' },
    { title: 'Synthesize', detail: 'script-computed row table (with reason + next per row) rendered; rows re-written on disk by a probe when they differ; checkpoint object returned by the script; runs after every HALT' },
  ],
  whenToUse: 'One run per args.stage (plan | build | stage | promote); launch only from the orchestrator turn that holds the owner\'s approval words; never with a secret in args or the trigger message',
}

// ---------------------------------------------------------------------------------------------
// args contract — every value computed by the orchestrator with git rev-parse / sha256sum right
// before invocation; NEED lists every arg a prompt interpolates for that stage (J2: complete NEED)
// ---------------------------------------------------------------------------------------------
const A = args || {}
const NEED_ALL = ['stage', 'run_nonce', 'launched_at', 'cap', 'wave_size', 'build_repo', 'snapshot_dir', 'venv', 'wheels_dir', 'libsrc', 'tools_dir', 'gate_sh', 'gate_sha256', 'baseline_path', 'baseline_sha256', 'base_sha', 'toolchain_status_sha256', 'resume_mode', 'max_agents_this_run']
const NEED_BY_STAGE = {
  plan: ['decision_queue_path', 'lens4_path', 'findings_path', 'redteam_path', 'unverified_finding_ids', 'against_recommendation_ids', 'catalog_candidates'],
  build: ['plan_sha', 'owner_approvals'],
  stage: ['plan_sha', 'owner_approvals', 'integration_sha_at_launch', 'last_clean_gate'],
  promote: ['plan_sha', 'owner_approvals', 'integration_sha_at_launch', 'last_clean_gate'],
}
if (!NEED_BY_STAGE[A.stage]) throw new Error('args.stage must be plan|build|stage|promote')
for (const k of NEED_ALL.concat(NEED_BY_STAGE[A.stage])) if (A[k] === undefined || A[k] === null || A[k] === '') throw new Error('args.' + k + ' is required for stage ' + A.stage)
const isSha = s => typeof s === 'string' && /^[0-9a-f]{40}$/.test(s)
const isHex64 = s => typeof s === 'string' && /^[0-9a-f]{64}$/.test(s)
if (!isSha(A.base_sha)) throw new Error('args.base_sha must be a full 40-hex sha')
if (!isHex64(A.gate_sha256) || !isHex64(A.baseline_sha256)) throw new Error('args.gate_sha256 / baseline_sha256 must be 64-hex (the orchestrator pins both at P0)')
if (A.plan_sha && !isSha(A.plan_sha)) throw new Error('args.plan_sha must be a full 40-hex sha')
if (A.integration_sha_at_launch && !isSha(A.integration_sha_at_launch)) throw new Error('args.integration_sha_at_launch must be a full 40-hex sha')
const TOOLCHAIN = '/workspaces/agent-skills-toolchain'
for (const k of ['build_repo', 'tools_dir', 'libsrc', 'venv']) if (String(A[k]).startsWith('/tmp/') || String(A[k]).startsWith(TOOLCHAIN)) throw new Error('args.' + k + ' must be durable and outside the toolchain repo (F-1, F-2)')
if (!['git', 'cache'].includes(A.resume_mode)) throw new Error('args.resume_mode must be git|cache (cache only after the smoke-run settling experiment, §10.1)')
if (!(A.wave_size >= 1 && A.wave_size <= A.cap)) throw new Error('args.wave_size must be 1..cap so a wave never enqueues more agents than the cap (CG: queue wait vs timers)')
const OA = A.owner_approvals || {}                                           // F-6: approvals are DATA
const R = A.build_repo, WT = R + '-wt', TOOLS = A.tools_dir, GRILL = A.grill_dir || '/home/codespace/grills/2026-09-19-qwen38-heretic-space'
const BUNDLES = (A.bundles_dir || '/workspaces/space-build-bundles') + '/' + A.run_nonce      // C-17: bundles live OUTSIDE the rsynced grill tree; the grill gets the manifest
const STATUS_JSON = GRILL + '/build-bundles/' + A.run_nonce + '/status.json', BUNDLE_MANIFEST = GRILL + '/build-bundles/' + A.run_nonce + '/bundles-manifest.json'
const CAP = A.cap, WAVE = A.wave_size, MAX_ROUNDS = A.max_rounds || 3, MAX_BUILD = A.max_build || 3, MAX_AUTHOR = 2
const RESERVE = A.reserve_tokens || 120000, AGENT_SOFT_CAP = 800, MAX_AGENTS_RUN = A.max_agents_this_run, RESERVE_PER_CHAIN = 7
const INTEG = 'integration/' + A.run_nonce, PLAN_BRANCH = 'plan/' + A.run_nonce
const TIMEOUT = { author: 1500000, red: 600000, build: 3000000, fix: 2400000, verify: 1800000, merge: 1200000, conflict: 1800000, ff: 900000, revert: 900000, clean: 1500000, journeys: 1500000, review: 1800000, refute: 900000, veto: 1500000, plan: 2400000, setup: 1800000, synth: 900000, synthfix: 600000, preverify: 1200000, apiledger: 1500000, catalog: 900000, evidence: 900000, index: 600000, fixcards: 600000 }
const tmo = (mode, enqueued) => (TIMEOUT[mode] || 1800000) * Math.max(1, Math.ceil((enqueued || 1) / CAP))   // CG: queue wait counts against the timer → size it by queue depth
const AGAINST = A.against_recommendation_ids                                 // ['G-1', 'G-3', 'G-2', 'M-5', 'G-15+G-24'] — the five decisions taken against the recommendation
const STAGING_RE = /\b(lease|quota|ZeroGPU|worker fork|Triton|fla|x-ip-token|MCP transport|Space rebuild|cold[- ]start|tok\/s|FP8|GPTQ|provider|requirements resolution|canary|rollback|OIDC|secret)\b/i
const RECEIPT_RE = /started in the background|Check \/codex:status|as a follow-up task|will report back when/i      // C-23: "based on the digest" dropped — it is the design's central phrase
const SECRET_RE = /ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----/
const RETRYABLE_RE = /^(not_attempted|starved):|agent-null|threw|timeout-or-dialog|integration:not-merged:null|fixcards-unavailable/   // C-8: reasons that mean "nobody judged the work" — retried on resume without retry_parked
const TOOLCHAIN_STATUS_CMD = 'git -C ' + TOOLCHAIN + ' status --porcelain -- . ":!docs/grills"'   // C-17: the grill sync loop writes docs/grills every 5 min; that is not a mutation of the toolchain
// C-21 / C-14: protected paths (only platform-01-gate may create or modify them) and the design's minimum required-files manifest per card.
// The persona-boundary fixture is NOT protected by name — it is pinned by owner_approvals.persona_boundary_fixture_sha256 (gate step boundary-fixture).
const PROTECTED = ['tests/test_personas.py', 'tests/test_constants_pin.py', 'tests/test_import_contract.py', 'tests/test_python_eval_surfaces.py', 'tests/test_catalog_policy.py', 'tests/fixtures/gate/false-claim.patch', 'tests/fixtures/gate/false-claim-target.txt', 'tests/journeys/conftest.py', 'tests/protected.txt', 'tools/gate.sh', 'tools/gate.pin', 'tools/baseline.json', 'tools/baseline.pin', 'tools/make_boundary_fixture.py', 'ruff.toml', 'pytest.ini', '.gitattributes', '.editorconfig', '.gitignore', 'conftest.py']
const MANIFEST_MIN = {
  'platform-01-gate': ['tools/gate.sh', 'tools/gate.pin', 'tools/baseline.json', 'tools/baseline.pin', 'tests/protected.txt', 'tests/test_constants_pin.py', 'tests/test_import_contract.py', 'tests/fixtures/gate/false-claim.patch', 'tests/fixtures/gate/false-claim-target.txt', 'tests/journeys/conftest.py', 'tools/make_boundary_fixture.py', 'tools/stubs/torch/__init__.py', 'tools/stubs/transformers/__init__.py', 'tools/stubs/spaces/__init__.py', 'config.py', 'ruff.toml', 'pytest.ini', '.gitattributes', '.editorconfig', '.gitignore'],
  'platform-03a-types-fake': ['core/types.py', 'core/engine.py', 'backends/base.py', 'backends/fake.py', 'tools/record_fixture.py', 'tests/conformance/conftest.py'],
  'platform-03b-thin-slice': ['app.py', 'api/app.py', 'backends/hosted.py', 'models.yaml', 'build_info.json'],
  'platform-04-streamparser': ['core/parsing.py', 'core/events.py'],
  'platform-05a-registry': ['core/tools/registry.py', 'tests/test_python_eval_surfaces.py'],
  'platform-05b-agent-session': ['core/agent.py', 'core/session.py'],
  'platform-08a-worker-pure': ['worker/encode.py', 'worker/lease.py'].concat(A.torch_in_venv ? ['worker/penalty.py'] : []),   // C-14: Q2 default removes the placebo; penalty.py only when torch is in the venv
  'platform-08b-worker-backend': ['worker/app.py', 'backends/worker.py'],
  'product-13a-catalog': ['tools/render_readme.py', 'core/catalog.py', 'tests/test_catalog_policy.py', 'evidence/catalog/README.md'],
  'product-13b-personas-readme': ['core/personas.py', 'tests/test_personas.py', 'tests/fixtures/persona_boundary.json'],
  'platform-14-promotion-ci': ['.github/workflows/gate.yml', '.github/workflows/deploy-staging.yml', '.github/workflows/promote.yml', '.github/workflows/health.yml', 'tools/promote.py', 'tools/expected.py'],
}
const reqFiles = c => [...new Set([...(c.new_modules || []), ...(c.required_files || [])])].sort()   // C-14: REQUIRED_AFTER is derived from the card, validated against MANIFEST_MIN
// held-out seams (A1 §4.6) → the card each journey needs; a journey stays skipped-with-reason (needs=<card>) until that card is merged
const JOURNEY_NEEDS = { J1: 'platform-03b-thin-slice', H7: 'platform-04-streamparser', H4: 'platform-05a-registry', H6: 'platform-05b-agent-session', H2: 'platform-07-gateway', H1: 'platform-08a-worker-pure', H3: 'platform-11-mcp', H5: 'product-13a-catalog' }
log('stage=' + A.stage + ' nonce=' + A.run_nonce + ' base=' + A.base_sha.slice(0, 12) + ' cap=' + CAP + ' wave=' + WAVE + ' rounds=' + MAX_ROUNDS + ' resume=' + A.resume_mode + ' maxAgentsThisRun=' + MAX_AGENTS_RUN + ' budget=' + (budget.total || 'none') + (A.smoke ? ' SMOKE' : ''))

// ---------------------------------------------------------------------------------------------
// Constant prompt preambles (byte-identical on every call → cache prefix; F-4, T-2)
// ---------------------------------------------------------------------------------------------
const PREAMBLE = [
  'CONTEXT RULES. The current working directory repo (' + TOOLCHAIN + ') and its CLAUDE.md are UNRELATED to this task:',
  'ignore every instruction there about SSOT gates, ~/source/*, drift checks or pushing. The ONLY repository you may touch is ' + R + '.',
  'Read ' + R + '/AGENTS.md first when it exists. Use absolute paths and `git -C "<checkout>"` for every git command. Worktrees live under ' + WT + '/.',
  'Python for everything: ' + A.venv + '/bin/python (3.12). Gate: VENV=' + A.venv + ' bash ' + A.gate_sh + ' --gate-sha256 ' + A.gate_sha256 + ' … (its printed LEDGER_DIGEST is the only admissible evidence; it must be reproduced by an independent run from a clean, committed tree).',
  'Dummy credentials in tests must never match the secret regex (use TESTTOKEN-…, never hf_/ghp_/sk-ant- prefixes with 20+ characters).',
  'Return repo_toplevel AND git_common_dir of the checkout you worked in (git rev-parse --show-toplevel; git rev-parse --path-format=absolute --git-common-dir).',
].join('\n')
const AUTHORITY = [
  'AUTHORITY (restates the owner request that launched this run; the owner request wins): local edits inside your own worktree and local commands only.',
  'NEVER: git push (to any remote); add a remote; create/duplicate a GitHub repo or HF Space; set or read secrets; call any *.hf.space URL; run HF Jobs; look for or use tokens;',
  'install packages (pip/uv/npm); run a server in the foreground without a timeout; print any environment; read `git log`/`git show` of system_prompt.py history; modify files under plan/ (except plan/status/ and plan/fixes/ for the integrator) or outside your card\'s allowlist.',
  'Commit after every coherent step. Your final answer is the StructuredOutput object only.',
].join('\n')
const NARROW = 'RETRY RULE: first run `git -C "' + R + '" status --porcelain` and `git -C "' + R + '" log --oneline -5` on your branch; continue from the last commit; discard uncommitted partial edits only if they do not compile (else commit them as "wip(<card>): salvage"); read at most half of the listed files.'

// ---------------------------------------------------------------------------------------------
// h6 timeout helper (verbatim from skills/workflow-authoring/templates/h6-timeout-heartbeat.md, trimmed to what is used)
// ---------------------------------------------------------------------------------------------
function h6Receipt(endReason, label, ms, detail) { return { __h6: true, __endReason: endReason, label: label, ms: ms, detail: detail === undefined ? null : detail } }
function h6IsDrop(r) { return !!r && r.__h6 === true }
async function withTimeout(thunk, ms, label) {
  if (typeof setTimeout !== 'function') { try { return await thunk() } catch (err) { return h6Receipt('threw', label, ms, String((err && err.message) || err)) } }  // UNVERIFIED: timers in the sandbox
  let timer = null
  const expiry = new Promise(function (resolve) { timer = setTimeout(function () { resolve(h6Receipt('timeout', label, ms, null)) }, ms) })
  try { return await Promise.race([Promise.resolve().then(thunk), expiry]) }
  catch (err) { return h6Receipt('threw', label, ms, String((err && err.message) || err)) }
  finally { if (timer !== null && typeof clearTimeout === 'function') clearTimeout(timer) }
}

// ---------------------------------------------------------------------------------------------
// Pure helpers (D-19: algorithms, not agents)
// ---------------------------------------------------------------------------------------------
const byId = (a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
const J = o => JSON.stringify(o, null, 1)
const cap = (s, n) => String(s === undefined || s === null ? '' : s).slice(0, n)      // string caps enforced in JS, not by maxLength
const fkey = f => (f.file || '') + '::' + String(f.title || '').toLowerCase().replace(/[^a-z0-9 ]/g, '').replace(/\s+/g, ' ').trim()
const fingerprint = fails => (fails || []).map(f => f.test + '|' + String(f.first_error_line || '').replace(/[0-9a-f]{7,40}/g, 'SHA').replace(/\d+/g, 'N').replace(/\/\S+/g, 'P').trim()).sort().join(';')
const ledgerKey = l => [l.role, l.mode, l.id, String(l.attempt)].join('|')
function redact(r, label) {                            // CG3: secret-shaped strings never enter a prompt, a ledger row or a report
  let hit = false
  const walk = (o, depth) => {
    if (depth > 6 || !o || typeof o !== 'object') return o
    for (const k of Object.keys(o)) {
      const v = o[k]
      if (typeof v === 'string') { if (SECRET_RE.test(v)) { hit = true; o[k] = v.replace(new RegExp(SECRET_RE.source, 'g'), '[REDACTED]') } }
      else if (typeof v === 'object') walk(v, depth + 1)
    }
    return o
  }
  walk(r, 0)
  if (hit) { log('SECRET-SHAPED STRING redacted in return of ' + label + ' (value never logged)'); r.__secret_redacted = true }
  return r
}
function topoOrder(cards) {
  const byKey = new Map(cards.map(c => [c.id, c])), out = [], state = new Map()
  const visit = id => {
    if (state.get(id) === 2) return
    if (state.get(id) === 1) throw new Error('dependency cycle at ' + id)
    const c = byKey.get(id); if (!c) throw new Error('unknown dependency ' + id)
    state.set(id, 1); for (const d of [...c.depends_on].sort()) visit(d); state.set(id, 2); out.push(c)
  }
  for (const c of [...cards].sort(byId)) visit(c.id)
  return out
}
function rankCards(cards) {                            // A2 §4d: rank = longest path to a sink in estimated minutes; deps strictly outrank dependents
  const by = new Map(cards.map(c => [c.id, c])), children = new Map(cards.map(c => [c.id, []]))
  for (const c of cards) for (const d of c.depends_on) if (children.has(d)) children.get(d).push(c.id)
  const memo = new Map()
  const rank = id => { if (memo.has(id)) return memo.get(id); const c = by.get(id); const own = (c.est_minutes || (c.size === 'M' ? 35 : 20)) + 14
    const r = own + Math.max(0, ...children.get(id).map(rank)); memo.set(id, r); return r }
  cards.forEach(c => rank(c.id)); return memo
}
const writeSet = c => new Set([...(c.files_allowed || []), ...(c.tests_allowed || []), ...(c.new_modules || []), ...(c.required_files || [])])
const byRank = rank => (a, b) => (rank.get(b.id) - rank.get(a.id)) || byId(a, b)         // C-24: (−rank, id) for scheduling AND integration order
function raiseLevels(items, textOf) {                  // A2/A1 (F-37): keyword-forced verification level, in code, at return time
  let raised = 0
  for (const it of items || []) if (STAGING_RE.test(textOf(it)) && String(it.verification_level || '').startsWith('local')) { it.verification_level = 'staging-required'; raised++ }
  return raised
}
function validateCards(cards) {                        // throws on a plan that cannot be built (A1 §13.1; D-1); called through checkPlan in EVERY stage (C-19)
  const ids = new Set(cards.map(c => c.id)); if (ids.size !== cards.length) throw new Error('duplicate card ids')
  for (const c of cards) {
    if (!/^(platform|product)-[0-9]{2}[a-d]?-[a-z0-9-]+$/.test(c.id)) throw new Error(c.id + ': bad id')
    if (!(c.step >= 1 && c.step <= 14)) throw new Error(c.id + ': step out of range')
    if (!c.dod.length || c.dod.length > 8 || c.dod.some(d => !d.command || d.command.length < 3)) throw new Error(c.id + ': dod must have 1..8 runnable lines')
    if (c.dod.some(d => /(^|\s)(-k|-x|--deselect|--ignore|--lf)(\s|=)|\|\|\s*true/.test(d.command))) throw new Error(c.id + ': a dod command narrows or masks pytest')
    if (c.size === 'L') throw new Error(c.id + ': size L is not a card')
    if ((c.size === 'S' && c.est_lines > 120) || (c.size === 'M' && c.est_lines > 300)) throw new Error(c.id + ': est_lines exceeds its size class (S ≤ 120, M ≤ 300)')
    if (c.protected_touch && c.id !== 'platform-01-gate') throw new Error(c.id + ': only platform-01-gate may touch protected paths')
    if (c.bootstrap) throw new Error(c.id + ': bootstrap must be false on every card (the profile exists only for the setup red-proof at base_sha)')
    const protHit = (c.tests_allowed || []).concat(c.files_allowed || [], c.new_modules || [], c.required_files || []).filter(p => PROTECTED.includes(p))
    if (protHit.length && !c.protected_touch) throw new Error(c.id + ': write set intersects the protected list (' + protHit.join(',') + ') without protected_touch (C-21)')
    if ((c.expected_green_tests || []).some(t => !/^[A-Za-z0-9_.\/-]+::[A-Za-z0-9_\[\]-]+$/.test(t))) throw new Error(c.id + ': expected_green_tests must be module::name ids')
    if (c.finding_ids.some(f => !f.corrected_text || f.corrected_text.length < 20)) throw new Error(c.id + ': every cited finding must carry its CORRECTED text (F-10)')
    if (c.risk === 'security' && !c.dod.some(d => /surface|operator|flag|unreachable/i.test(d.expect + ' ' + d.command))) throw new Error(c.id + ': a security card needs a surface/operator-flag DoD line (G-15 point 5)')
    if (MANIFEST_MIN[c.id]) { const miss = MANIFEST_MIN[c.id].filter(p => !reqFiles(c).includes(p) && !(c.files_allowed || []).includes(p)); if (miss.length) throw new Error(c.id + ': required-files manifest not declared by the card (' + miss.join(',') + ') — new_modules/required_files must cover MANIFEST_MIN (C-14)') }
    for (const pre of ['platform-04-streamparser:fixture1_path', 'product-13b-personas-readme:persona_boundary_fixture_path', 'platform-08c-worker-checkpoint:worker_checkpoint_decision']) { const [id, field] = pre.split(':'); if (c.id === id && c.owner_precondition !== field) throw new Error(c.id + ': owner_precondition must be ' + field) }
    raiseLevels(c.dod, d => d.command + ' ' + d.expect)
  }
  topoOrder(cards)
}
function checkPlan(idx, preverified) {                 // C-19: the plan-level checks, run in EVERY stage; returns defects[] (R0 records them, R1+ throws)
  const defects = []
  try { validateCards(idx.cards) } catch (e) { defects.push(String(e.message)) }
  for (const id of AGAINST) { const row = (idx.decisions || []).find(d => d.id === id); if (!row || row.against_recommendation !== true) defects.push('decision ' + id + ' must be marked against_recommendation (F-9)') }
  const refuted = new Set((preverified || []).filter(p => p.verdict === 'refuted').map(p => p.id))
  idx.cards.forEach(c => c.finding_ids.forEach(f => { if (refuted.has(f.id)) defects.push(c.id + ' cites REFUTED finding ' + f.id) }))
  for (const cid of Object.keys(MANIFEST_MIN)) if (!idx.cards.some(c => c.id === cid)) defects.push('required-files manifest names card ' + cid + ' which the plan lacks')
  if ((idx.unmapped_finding_ids || []).length) defects.push('unmapped findings: ' + idx.unmapped_finding_ids.join(','))
  return defects
}
function assertCommon(r, what) {                       // F-1, F-5, F-35: script-level invariants on every return
  if (!r || h6IsDrop(r) || r.status === 'null') return r
  const top = r.repo_toplevel || '', cdir = r.git_common_dir || ''
  if (top && !(top === R || top.startsWith(WT + '/'))) { log('BLOCK ' + what + ': worked in ' + top); return { status: 'null', reason: 'wrong-repo' } }          // D1: prefix test — sibling worktrees pass
  if (cdir && cdir !== R + '/.git') { log('BLOCK ' + what + ': common dir ' + cdir); return { status: 'null', reason: 'wrong-store' } }
  if ((r.outward_actions_taken || []).length) { HALT = 'outward-action:' + what; log('HALT ' + HALT + ': ' + r.outward_actions_taken.join(',') + ' — no further agents; synthesizer still runs'); return { status: 'null', reason: 'outward-action' } }
  if ((r.installed_packages || []).length) { log('BLOCK ' + what + ': installed ' + r.installed_packages.join(',')); return { status: 'null', reason: 'installed-packages' } }
  const rc = RECEIPT_RE.exec(r.notes || '') || RECEIPT_RE.exec(r.strongest_disagreement || '')
  if (rc) { log('BLOCK ' + what + ': receipt-shaped return (matched "' + rc[0] + '")'); return { status: 'null', reason: 'receipt-shaped' } }   // C-23: the fragment is logged
  return r
}

// ---------------------------------------------------------------------------------------------
// The single agent wrapper: ledger for every call, one narrower retry on null, typed results (F-41, F-42),
// early halt on budget exhaustion or an outward action (CG), secret redaction (CG3), sorted ledger keys
// ---------------------------------------------------------------------------------------------
const ledger = []; let agentCount = 0, HALT = null
function budgetOk(label, exemptFromHalt) {
  if (HALT && !exemptFromHalt) { log('HALTED (' + HALT + ') before ' + label); return false }       // C-7: the synthesizer is exempt from the HALT branch only
  if (agentCount >= Math.min(AGENT_SOFT_CAP, MAX_AGENTS_RUN)) { log('AGENT CAP: ' + agentCount + ' >= ' + Math.min(AGENT_SOFT_CAP, MAX_AGENTS_RUN) + ' before ' + label); return false }
  if (!budget.total) return true
  const ok = budget.remaining() > RESERVE; if (!ok) log('BUDGET GUARD before ' + label + ': remaining ' + budget.remaining() + ' < reserve ' + RESERVE)
  return ok
}
function agentsOk(label, need) {                       // A2 §13: per-chain reservation so a wave never starts a chain it cannot finish inside this invocation
  const ok = agentCount + need <= Math.min(AGENT_SOFT_CAP, MAX_AGENTS_RUN)
  if (!ok) log('AGENT SLICE: ' + label + ' needs ' + need + ' agents; ' + agentCount + ' used of ' + Math.min(AGENT_SOFT_CAP, MAX_AGENTS_RUN) + ' — deferred to the next invocation')
  return ok
}
async function run(role, mode, id, prompt, opts, enqueued) {
  const label = role + ':' + mode + ':' + id, ms = tmo(mode, enqueued)
  for (let attempt = 1; attempt <= 2; attempt++) {
    if (!budgetOk(label, role === 'synthesizer')) { const why = HALT && role !== 'synthesizer' ? 'halt' : (agentCount >= Math.min(AGENT_SOFT_CAP, MAX_AGENTS_RUN) ? 'agent-slice' : 'budget'); ledger.push({ role, mode, id, attempt, status: why }); return { status: 'null', reason: why } }
    agentCount++
    const p = attempt === 1 ? prompt : prompt + '\n' + NARROW + '\nattempt: 2'     // attempt suffix → cache miss by construction (F-43)
    const r = await withTimeout(() => agent(p, Object.assign({ label: label + (attempt === 2 ? ':retry' : '') }, opts)), ms, label)
    if (r && !h6IsDrop(r)) {
      redact(r, label)
      ledger.push({ role, mode, id, attempt, status: r.status || r.verdict || 'ok', sha: r.head_sha || r.sha || r.tests_head || null })
      return assertCommon(r, label)
    }
    const why = r ? (r.__endReason === 'timeout' ? 'timeout-or-dialog' : r.__endReason) : 'null', detail = r ? cap(r.detail, 200) : null   // C-37: the promised label
    ledger.push({ role, mode, id, attempt, status: why, detail })
    if (why === 'threw' && /budget|ceiling|spent/i.test(String(detail))) { HALT = 'budget-exhausted'; log('HALT budget-exhausted at ' + label + ' — no retries, loops wind down, synthesizer runs'); return { status: 'null', reason: 'halt' } }
    if (why === 'timeout-or-dialog') REPLAY_RISK = true   // CG: a timed-out call may still journal a result; cache resume would diverge → next_args.resume_mode = 'git'
    log('DROP ' + label + ' attempt ' + attempt + ': ' + why + (attempt === 1 ? ' — retrying narrower' : ' — parking'))
  }
  return { status: 'null', reason: 'agent-null' }
}
let REPLAY_RISK = false

// design-v2 §9 — schemas. Keyword set deliberately limited to what the observed run exercised
// (type / enum / required / properties / items / minItems / description). No pattern, maxLength,
// minLength, minimum or maximum: their support in the StructuredOutput validator is UNVERIFIED
// (J2 gap 5), so every such constraint is enforced in JS instead (isSha, cap(), okSemantics).
const LEVELS = ['local-mechanical', 'local-stub', 'staging-required', 'owner-required', 'unverified']
const COMMON = {
  repo_toplevel: { type: 'string', description: 'output of git rev-parse --show-toplevel in the checkout you worked in ("" if you touched no checkout)' },
  git_common_dir: { type: 'string', description: 'output of git rev-parse --path-format=absolute --git-common-dir in that checkout ("" if none); must be <build_repo>/.git' },
  outward_actions_taken: { type: 'array', items: { type: 'string' }, description: 'MUST be empty: any push/repo/Space/secret/HF-job/*.hf.space action' },
  installed_packages: { type: 'array', items: { type: 'string' }, description: 'MUST be empty: pip/uv/npm installs are forbidden' },
  notes: { type: 'string', description: '<= 120 words; never a summary of another agent' },
}
const COMMON_REQ = ['repo_toplevel', 'git_common_dir', 'outward_actions_taken', 'installed_packages']
const CMD = { type: 'object', properties: { command: { type: 'string' }, exit_code: { type: 'integer' }, output_tail: { type: 'string', description: '<= 40 lines verbatim; secret-shaped strings are redacted in JS' } }, required: ['command', 'exit_code', 'output_tail'] }
const GATE_STEP = { type: 'object', properties: { name: { type: 'string' }, exit_code: { type: 'integer' } }, required: ['name', 'exit_code'] }
const ROW_STATE = ['merged+gate-green', 'merged+gate-red', 'parked', 'reverted', 'revert-failed', 'blocked_on_owner', 'dropped_null', 'not_attempted', 'deferred']

// ---- 9.0 SETUP (integrator mode:setup; also the ONE live state probe per invocation) ----
const SETUP = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['SUCCESS', 'FAILED'] },
  venv_python: { type: 'string' }, nproc: { type: 'integer' },
  base_sha_ok: { type: 'boolean' }, gate_sha256: { type: 'string' }, baseline_sha256: { type: 'string' },
  baseline_collected: { type: 'integer' }, baseline_skipped: { type: 'integer' },
  red_proof: { type: 'object', properties: { broken_red: { type: 'boolean' }, false_claim_red: { type: 'string', enum: ['true', 'false', 'fixture-missing', 'fixture-not-yet-delivered', 'worktree-failed', 'inner-ledger-unreadable', 'no-claim-lint-step', 'not-run'] }, digest: { type: 'string' } }, required: ['broken_red', 'false_claim_red', 'digest'] },
  integration_head_live: { type: 'string', description: '40-hex of integration/<nonce> right now, or "none"' },
  plan_merged: { type: 'boolean', description: 'plan/<nonce> at plan_sha is an ancestor of integration/<nonce>' },
  branch_heads: { type: 'array', items: { type: 'object', properties: { branch: { type: 'string' }, sha: { type: 'string' } }, required: ['branch', 'sha'] }, description: 'every tests/*-<nonce> and task/*-<nonce> branch and its head (live)' },
  merged_on_integration: { type: 'array', items: { type: 'string' }, description: 'card ids whose plan/status/<id>.json on integration/<nonce> says merged (live git ls-tree)' },
  remotes: { type: 'array', items: { type: 'string' }, description: 'git remote -v lines; MUST be empty unless owner_approvals.github_repo_url is set' },
  prior_rows: { type: 'array', items: { type: 'object', properties: { task_id: { type: 'string' }, state: { type: 'string', enum: ROW_STATE }, head_sha: { type: 'string' }, reason: { type: 'string' } }, required: ['task_id', 'state', 'head_sha', 'reason'] }, description: 'rows of args.prior_status_path (previous invocation), [] if none' },
  seen_keys: { type: 'array', items: { type: 'string' }, description: 'review dedup keys from args.prior_status_path, [] if none' },
  toolchain_status_sha256: { type: 'string', description: 'sha256 of `git -C /workspaces/agent-skills-toolchain status --porcelain -- . ":!docs/grills"` (the grill sync loop writes docs/grills legitimately)' },
  worktrees_pruned: { type: 'integer' },
}, required: ['status', 'venv_python', 'nproc', 'base_sha_ok', 'gate_sha256', 'baseline_sha256', 'baseline_collected', 'baseline_skipped', 'red_proof', 'integration_head_live', 'plan_merged', 'branch_heads', 'merged_on_integration', 'remotes', 'prior_rows', 'seen_keys', 'toolchain_status_sha256', ...COMMON_REQ] }

// ---- 9.1 CARD_INDEX (planner → script; the cards themselves are files on plan/<nonce>; the index agent returns the same shape in R1+) ----
const CARD = { type: 'object', properties: {
  id: { type: 'string' }, path: { type: 'string', description: 'plan/cards/<id>.json (review fix cards: plan/fixes/<id>.json)' }, step: { type: 'integer' },
  depends_on: { type: 'array', items: { type: 'string' } },
  files_allowed: { type: 'array', items: { type: 'string' } }, tests_allowed: { type: 'array', items: { type: 'string' } },
  new_modules: { type: 'array', items: { type: 'string' } }, deps_allowed: { type: 'array', items: { type: 'string' } },
  required_files: { type: 'array', items: { type: 'string' }, description: 'non-module files this card must deliver; new_modules ∪ required_files = the required-files manifest after this card merges (C-14)' },
  xfail_allowed: { type: 'array', items: { type: 'string' }, description: 'test ids (file::name) that may be xfail/skip; the known-bads of lens-4 §F only' },
  expected_green_tests: { type: 'array', items: { type: 'string' }, description: 'test ids (module::name) that are green on the OLD tree by design (characterisation pins, contract tests); confirm-RED exempts exactly these (C-13)' },
  tests_removed_expected: { type: 'integer' }, est_lines: { type: 'integer' }, est_minutes: { type: 'integer' },
  dod: { type: 'array', minItems: 1, items: { type: 'object', properties: {
    id: { type: 'string' }, command: { type: 'string' }, expect: { type: 'string' },
    verification_level: { type: 'string', enum: ['local-mechanical', 'local-stub', 'staging-required', 'owner-required'] } },
    required: ['id', 'command', 'expect', 'verification_level'] } },
  size: { type: 'string', enum: ['S', 'M'] }, risk: { type: 'string', enum: ['none', 'security', 'persona', 'catalog'] },
  protected_touch: { type: 'boolean' }, bootstrap: { type: 'boolean', description: 'must be false on every card in v2 (the bootstrap profile exists only for the setup red-proof at base_sha)' },
  decision_ids: { type: 'array', items: { type: 'string' } },
  finding_ids: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, corrected_text: { type: 'string' } }, required: ['id', 'corrected_text'] } },
  apis_expected: { type: 'array', items: { type: 'object', properties: { module: { type: 'string' }, symbol: { type: 'string' }, kwargs: { type: 'array', items: { type: 'string' } } }, required: ['module', 'symbol', 'kwargs'] } },
  owner_precondition: { type: 'string', description: 'owner_approvals field that must be non-null before this card may build ("" if none)' } },
  required: ['id', 'path', 'step', 'depends_on', 'files_allowed', 'tests_allowed', 'new_modules', 'deps_allowed', 'required_files', 'xfail_allowed', 'expected_green_tests', 'tests_removed_expected', 'est_lines', 'est_minutes', 'dod', 'size', 'risk', 'protected_touch', 'bootstrap', 'decision_ids', 'finding_ids', 'apis_expected', 'owner_precondition'] }
const CARD_INDEX = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['SUCCESS', 'FAILED'] },
  plan_sha: { type: 'string', description: '40-hex commit on plan/<nonce> holding plan/**' },
  decisions_path: { type: 'string' }, api_ledger_path: { type: 'string' }, preverified_path: { type: 'string' },
  decisions: { type: 'array', minItems: 1, items: { type: 'object', properties: {
    id: { type: 'string' }, decided_value: { type: 'string' }, against_recommendation: { type: 'boolean' }, consequences: { type: 'array', items: { type: 'string' } }, dq_line: { type: 'integer' } },
    required: ['id', 'decided_value', 'against_recommendation', 'consequences', 'dq_line'] } },
  preverified: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, verdict: { type: 'string', enum: ['confirmed', 'refuted', 'unverified'] }, corrected_claim: { type: 'string' }, level: { type: 'string', enum: LEVELS } }, required: ['id', 'verdict', 'corrected_claim', 'level'] }, description: 'plan/preverified.json rows (R1+ reads them back through the index agent so checkPlan runs in every stage, C-19)' },
  cards: { type: 'array', minItems: 1, items: CARD },
  unmapped_finding_ids: { type: 'array', items: { type: 'string' }, description: 'confirmed/partially-confirmed finding ids no card cites (must be empty or explained)' },
}, required: ['status', 'plan_sha', 'decisions_path', 'api_ledger_path', 'preverified_path', 'decisions', 'preverified', 'cards', 'unmapped_finding_ids', ...COMMON_REQ] }

// ---- 9.2 TESTS (author, modes tests and journeys) ----
const TESTS = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['SUCCESS', 'FAILED', 'reused'] },
  card_id: { type: 'string' }, branch: { type: 'string' },
  base_sha: { type: 'string' }, tests_head: { type: 'string' },
  test_paths: { type: 'array', minItems: 1, items: { type: 'string' } },
  commits_made: { type: 'integer' },
  red_command: { type: 'string' }, red_exit_code: { type: 'integer' }, red_excerpt: { type: 'string' },
  gate_digest: { type: 'string', description: 'LEDGER_DIGEST printed by gate.sh --only-tests, or ""' },
  known_bads_xfail: { type: 'array', items: { type: 'string' } },
  mutants_suggested: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, find: { type: 'string' }, replace: { type: 'string' } }, required: ['file', 'find', 'replace'] } },
}, required: ['status', 'card_id', 'branch', 'base_sha', 'tests_head', 'test_paths', 'commits_made', 'red_command', 'red_exit_code', 'red_excerpt', 'gate_digest', ...COMMON_REQ] }

// ---- 9.3 BUILD (builder, modes implement and fix) ----
const BUILD = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['done', 'partial', 'failed', 'reused'] },
  card_id: { type: 'string' }, branch: { type: 'string' },
  base_sha: { type: 'string' }, head_sha: { type: 'string' },
  commits_made: { type: 'integer' },
  changed_files: { type: 'array', items: { type: 'string' } },
  dod: { type: 'array', minItems: 1, items: { type: 'object', properties: {
    id: { type: 'string' }, command: { type: 'string' }, exit_code: { type: 'integer' }, output_tail: { type: 'string' } },
    required: ['id', 'command', 'exit_code', 'output_tail'] } },
  apis_used: { type: 'array', items: { type: 'object', properties: { module: { type: 'string' }, symbol: { type: 'string' }, kwargs: { type: 'array', items: { type: 'string' } }, ledger_ref: { type: 'string', description: 'plan/api-ledger.json entry id or libsrc path:line' } }, required: ['module', 'symbol', 'kwargs', 'ledger_ref'] } },
  gate_exit_code: { type: 'integer', description: 'advisory: your own gate.sh run at head_sha on a clean tree; the verifier re-runs it' },
  gate_digest: { type: 'string', description: 'LEDGER_DIGEST of your own full gate run at head_sha ("" if not run); the verifier must reproduce it' },
  gate_profile: { type: 'string', enum: ['full', 'bootstrap'] },
  gate_steps: { type: 'array', items: GATE_STEP, description: 'the steps[] {name, exit_code} of your gate ledger (.gate/last_run.json) — compared to the verifier\'s on a digest mismatch (C-18)' },
  remaining_dod_ids: { type: 'array', items: { type: 'string' } },
}, required: ['status', 'card_id', 'branch', 'base_sha', 'head_sha', 'commits_made', 'changed_files', 'dod', 'apis_used', 'gate_exit_code', 'gate_digest', 'gate_profile', 'gate_steps', 'remaining_dod_ids', ...COMMON_REQ] }

// ---- 9.4 VERDICT (verifier; every mode; the only schema with a verdict) ----
const FINDING = { type: 'object', properties: {
  id: { type: 'string' }, title: { type: 'string' }, file: { type: 'string' },
  severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
  kind: { type: 'string', enum: ['decision-fidelity', 'scope', 'correctness', 'tests-integrity', 'security', 'secrets', 'interaction', 'omitted-obligation', 'staging-evidence'] },
  reproduction: CMD,
  corrected_claim: { type: 'string' }, fix_hint: { type: 'string' },
  files_allowed: { type: 'array', items: { type: 'string' } },
  verification_level: { type: 'string', enum: LEVELS } },
  required: ['id', 'title', 'file', 'severity', 'kind', 'reproduction', 'verification_level'] }
const VERDICT = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['SUCCESS', 'FAILED'] },
  mode: { type: 'string', enum: ['plan', 'red', 'verify', 'refute', 'review', 'veto', 'evidence', 'preverify', 'catalog'] },
  target_id: { type: 'string', description: 'card id, finding id, wave id, "tree" or "index"' },
  sha: { type: 'string', description: 'the exact revision you read/ran (40-hex), or "none"' },
  verdict: { type: 'string', enum: ['pass', 'fail', 'unverified', 'refuted', 'holds', 'veto', 'no-veto'] },
  ledger_sha256: { type: 'string' }, ledger_head_sha: { type: 'string' }, gate_exit_code: { type: 'integer' },
  gate_digest: { type: 'string', description: 'LEDGER_DIGEST of the full gate run YOU executed with the SAME pinned command ("" if none)' },
  gate_profile: { type: 'string', enum: ['full', 'bootstrap', 'none'] },
  gate_sha256_observed: { type: 'string', description: 'sha256sum of the gate.sh you executed ("" if none)' },
  gate_steps: { type: 'array', items: GATE_STEP, description: 'steps[] {name, exit_code} of YOUR gate ledger' },
  checks: { type: 'array', items: { type: 'object', properties: { name: { type: 'string' }, command: { type: 'string' }, exit_code: { type: 'integer' }, output_tail: { type: 'string' } }, required: ['name', 'command', 'exit_code', 'output_tail'] } },
  dod_reruns: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, exit_code: { type: 'integer' } }, required: ['id', 'exit_code'] } },
  failures: { type: 'array', items: { type: 'object', properties: { test: { type: 'string' }, first_error_line: { type: 'string' }, dod_id: { type: 'string' } }, required: ['test', 'first_error_line'] } },
  hunks_cited: { type: 'array', items: { type: 'string', description: 'path:line@sha' } },
  idiom_hits: { type: 'integer', description: 'IDIOM_HITS from the ledger of your gate run' },
  warnings_cleared: { type: 'array', items: { type: 'object', properties: { idiom: { type: 'string' }, reason: { type: 'string' } }, required: ['idiom', 'reason'] } },
  mutants: { type: 'object', properties: { written: { type: 'integer' }, killed: { type: 'integer' }, path: { type: 'string' } }, required: ['written', 'killed'] },
  revert_proof: { type: 'object', properties: { observed: { type: 'string', enum: ['red', 'green', 'unrunnable', 'not-run'] }, command: { type: 'string' } }, required: ['observed', 'command'] },
  diff_stats: { type: 'object', properties: { files: { type: 'integer' }, insertions: { type: 'integer' }, deletions: { type: 'integer' }, moves_only: { type: 'boolean' } }, required: ['files', 'insertions', 'deletions'], description: 'verify: copy the LEDGER_DIFF_STATS line of your gate run (required; the script fails closed without it, C-25)' },
  apicheck_unresolvable: { type: 'array', items: { type: 'string' }, description: 'verify: apicheck_unresolvable[] of your ledgers (symbols needing torch with no wheel source; recorded, never a failure — C-16)' },
  findings: { type: 'array', items: FINDING },
  probes_used: { type: 'array', items: { type: 'string' }, description: 'review/veto: the commands or angles you used (fed to the inversion mandate)' },
  remotes: { type: 'array', items: { type: 'string' }, description: 'clean-gate/evidence: git remote -v lines of the build repo' },
  strongest_disagreement: { type: 'string', description: 'required even when the verdict is pass/holds' },
  judge_rail: { type: 'string', enum: ['claude-fresh'] },
}, required: ['status', 'mode', 'target_id', 'sha', 'verdict', 'ledger_sha256', 'ledger_head_sha', 'gate_exit_code', 'gate_digest', 'gate_profile', 'gate_sha256_observed', 'gate_steps', 'checks', 'dod_reruns', 'failures', 'hunks_cited', 'idiom_hits', 'warnings_cleared', 'mutants', 'revert_proof', 'findings', 'probes_used', 'strongest_disagreement', ...COMMON_REQ] }

// ---- 9.5 MERGE (integrator; modes merge, conflict, ff, revert, clean-gate, fixcards) ----
const MERGE = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['merged', 'conflict', 'gate-red', 'reverted', 'missing-ref', 'already-merged', 'written', 'ok', 'failed'] },
  mode: { type: 'string', enum: ['merge', 'conflict', 'ff', 'revert', 'clean-gate', 'fixcards'] },
  card_id: { type: 'string' }, branch: { type: 'string' },
  before_sha: { type: 'string' }, head_sha: { type: 'string' },
  merge_sha: { type: 'string', description: 'merge/ff/conflict: the merge commit itself (before the status commit) — the revert target (C-12); "" otherwise' },
  ledger_sha256: { type: 'string' }, gate_digest: { type: 'string' }, gate_exit_code: { type: 'integer' },
  gate_sha256_observed: { type: 'string' },
  cherry_unmerged: { type: 'array', items: { type: 'string' } }, patch_ids_missing: { type: 'array', items: { type: 'string' } },
  conflicts: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, ours: { type: 'string' }, theirs: { type: 'string' } }, required: ['file', 'ours', 'theirs'] } },
  bundle_path: { type: 'string' }, bundle_bytes: { type: 'integer' },
  journeys: { type: 'object', properties: { collected: { type: 'integer' }, failed: { type: 'integer' }, skipped_needs: { type: 'array', items: { type: 'string' } } }, required: ['collected', 'failed', 'skipped_needs'], description: 'from the ledger; {0,0,[]} when the gate ran without --journeys' },
  self_test: { type: 'object', properties: { broken_red: { type: 'boolean' }, false_claim_red: { type: 'string', enum: ['true', 'false', 'fixture-missing', 'fixture-not-yet-delivered', 'worktree-failed', 'inner-ledger-unreadable', 'no-claim-lint-step', 'not-run'] } }, required: ['broken_red', 'false_claim_red'], description: 'from the ledger; {false, "not-run"} when the gate ran without --self-test' },
  files_written: { type: 'array', items: { type: 'string' }, description: 'fixcards: the plan/fixes/<id>.json paths committed' },
  remotes: { type: 'array', items: { type: 'string' } },
  branch_count: { type: 'integer' },
  toolchain_status_sha256: { type: 'string' },
}, required: ['status', 'mode', 'head_sha', 'merge_sha', 'ledger_sha256', 'gate_digest', 'gate_exit_code', 'gate_sha256_observed', 'cherry_unmerged', 'patch_ids_missing', 'conflicts', 'journeys', 'self_test', 'files_written', 'remotes', ...COMMON_REQ] }

// ---- 9.6 REPORT (synthesizer; rows are checked against the script's ledger) ----
const REPORT = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['SUCCESS', 'FAILED'] },
  report_path: { type: 'string' }, report_bytes: { type: 'integer' }, status_json_path: { type: 'string' },
  rows: { type: 'array', items: { type: 'object', properties: {
    task_id: { type: 'string' },
    state: { type: 'string', enum: ROW_STATE },
    reason: { type: 'string' }, next: { type: 'string' },
    head_sha: { type: 'string' }, dod_done: { type: 'integer' }, dod_total: { type: 'integer' }, dod_deferred: { type: 'integer' } },
    required: ['task_id', 'state', 'reason', 'next', 'head_sha', 'dod_done', 'dod_total', 'dod_deferred'] } },
  owner_actions: { type: 'array', items: { type: 'string' } },
  what_would_most_improve_confidence: { type: 'string' },
}, required: ['status', 'report_path', 'report_bytes', 'status_json_path', 'rows', 'owner_actions', 'what_would_most_improve_confidence', ...COMMON_REQ] }


// ---------------------------------------------------------------------------------------------
// Prompt builders (pure functions of args + sorted results; the sha pins the cache)
// ---------------------------------------------------------------------------------------------
const testsBranch = id => 'tests/' + id + '-' + A.run_nonce
const taskBranch = id => 'task/' + id + '-' + A.run_nonce          // ONE helper for every merged branch — journeys use it too (J2 A3-1)
const cardPath = c => c.path || 'plan/cards/' + c.id + '.json'
const cardRef = c => 'CARD: ' + R + '/' + cardPath(c) + ' (plan sha ' + A.plan_sha + '; plan/ is merged into ' + INTEG + ' so the file is in every worktree' + (c.finding ? '; this is a REVIEW FIX CARD written by the integrator to plan/fixes/' : '') + '). CARD CONTENT (verbatim from that file): ' + J({ id: c.id, files_allowed: [...(c.files_allowed || [])].sort(), new_modules: [...(c.new_modules || [])].sort(), required_files: [...(c.required_files || [])].sort(), tests_allowed: [...(c.tests_allowed || [])].sort(), expected_green_tests: [...(c.expected_green_tests || [])].sort(), xfail_allowed: [...(c.xfail_allowed || [])].sort(), dod: c.dod, finding_ids: c.finding_ids, risk: c.risk, owner_precondition: c.owner_precondition }) + (c.finding ? '\nFINDING (confirmed by an independent refuter): ' + J({ id: c.finding.id, title: c.finding.title, file: c.finding.file, severity: c.finding.severity, kind: c.finding.kind, corrected_claim: cap(c.finding.corrected_claim, 600), fix_hint: cap(c.finding.fix_hint, 400), reproduction: c.finding.reproduction }) : '') + '\nDECISIONS: plan/decisions.json. API LEDGER: plan/api-ledger.json. PRE-VERIFIED FINDINGS: plan/preverified.json.'
const PINS = ' --gate-sha256 ' + A.gate_sha256 + ' --baseline ' + A.baseline_path + ' --baseline-sha256 ' + A.baseline_sha256 + ' --libsrc ' + A.libsrc
const gateCmd = extra => 'VENV=' + A.venv + ' bash ' + A.gate_sh + PINS + ' ' + extra
const redriveLine = k => (k ? '\nredrive: ' + k : '')                 // D4: a stale re-drive is a different prompt → cache miss by construction
const boundaryArg = () => (OA.persona_boundary_fixture_sha256 && isHex64(OA.persona_boundary_fixture_sha256) ? ' --boundary-sha256 ' + OA.persona_boundary_fixture_sha256 : '')
function mergedArgs(mergedIds) {                                     // --require / --xfail-allow / --tests-removed for gates on trees that contain merged cards (C-14: from the cards)
  const ids = [...mergedIds].sort()
  const cards = ids.map(id => CARD_BY_ID.get(id)).filter(Boolean)
  const req = [...new Set(cards.flatMap(reqFiles))].sort()
  const xf = [...new Set(cards.flatMap(c => c.xfail_allowed || []))].sort(), removed = cards.reduce((n, c) => n + (c.tests_removed_expected || 0), 0)
  return (req.length ? ' --require ' + req.join(',') : '') + (xf.length ? ' --xfail-allow ' + xf.join(',') : '') + (removed ? ' --tests-removed ' + removed : '') + boundaryArg()
}
const CARD_BY_ID = new Map()
const P = {
  setup: () => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:setup (idempotent) + the live state probe of this invocation (launched_at ' + (A.resume_mode === 'git' ? A.launched_at : 'n/a') + '). Ensure and report:',
    '(1) ' + R + ' is a clone of the read-only snapshot ' + A.snapshot_dir + ' whose first commit is ' + A.base_sha + ' (create it if missing; never modify the snapshot; `chmod -R a-w` the snapshot and ' + A.libsrc + ');',
    '(2) the venv ' + A.venv + ' EXISTS (P0 created it; `python -V` must be 3.12.*; NEVER create it or install anything — report status FAILED if absent); report nproc;',
    '(3) sha256sum of ' + A.gate_sh + ' and of ' + A.baseline_path + ' (both created at P0; report both — the script compares them to args; never create or rewrite either);',
    '(4) BROKEN_SHA=' + A.base_sha + ' run ' + gateCmd('--self-test --profile bootstrap --base ' + A.base_sha) + ' in a detached worktree at ' + A.base_sha + ' and report red_proof {broken_red, false_claim_red, digest};',
    A.stage === 'plan' ? '(5) branch ' + PLAN_BRANCH + ' exists or is created at ' + A.base_sha + ';' : '(5) branch ' + INTEG + ' exists (create at ' + A.base_sha + ' if missing) and ' + PLAN_BRANCH + ' at ' + A.plan_sha + ' is merged into it (`git merge --no-ff ' + A.plan_sha + '` as its first commit if not yet; plan/** only); report plan_merged and integration_head_live (40-hex);',
    '(6) report branch_heads for every tests/*-' + A.run_nonce + ' and task/*-' + A.run_nonce + ' branch, merged_on_integration from `git ls-tree ' + INTEG + ' plan/status/` (ids whose json says merged), and `git remote -v` lines (expected: none);',
    '(7) if ' + (A.prior_status_path || 'no prior status file') + ' exists, return its rows (task_id, state, head_sha, reason) as prior_rows and its seen_keys; else [] and [];',
    '(8) `git -C ' + R + ' worktree prune`; remove worktrees under ' + WT + ' whose branch is already merged into ' + INTEG + '; mkdir -p ' + BUNDLES + ' ' + GRILL + '/build-bundles/' + A.run_nonce + ';',
    '(9) report toolchain_status_sha256 = sha256 of `' + TOOLCHAIN_STATUS_CMD + '` (must equal ' + A.toolchain_status_sha256 + '; docs/grills is excluded because the owner\'s sync loop writes there) — report base_sha_ok=false if any assertion fails. Never install into any interpreter.'].join('\n'),
  preverify: fid => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:preverify (refute-first). Finding ' + fid + ' in ' + A.findings_path + ' is UNVERIFIED. Reproduce or refute it at ' + A.base_sha + ' in a detached worktree of ' + R + ' with a probe mechanically different from the finder\'s (the finder read source; you execute: render the chat template with jinja2, run the code path with a fake, diff the checkpoint index — whatever applies). Never print environment variables; never call any URL. Return verdict holds|refuted|unverified with the executed reproduction, corrected_claim, and verification_level; findings[0] carries the result.'].join('\n'),
  apiLedger: () => [PREAMBLE, AUTHORITY, 'ROLE: planner mode:api-ledger. In a worktree of ' + R + ' on branch ' + PLAN_BRANCH + ' (create ' + WT + '/apiledger-' + A.run_nonce + ' with `git -C ' + R + ' worktree add`), from ' + A.libsrc + ' ONLY (gradio 6.26.0, spaces 0.51.3, transformers 5.16.1, huggingface_hub 1.32.0, gradio_client 2.6.1) write plan/api-ledger.json: every symbol the design §4.2 cards need with module, symbol, kwargs, libsrc path:line (≥ 30 entries: gr.Blocks/ChatInterface/Chatbot/mount_gradio_app/api, spaces.GPU(size=,duration=), GenerationConfig fields incl. max_time and the ABSENCE of presence_penalty, continue_final_message bool|str, HfApi.restart_space/duplicate_repo/fetch_space_logs/wait_for_space, gradio_client.Client) plus known_bad[] as regexes with why and libsrc anchor: gr.Chatbot(type=…), gr.ChatInterface(type=…), @spaces.GPU(gpu_size=…), presence_penalty to generate, restart_space(revision=…), from gradio.client import, Path.read_text(newline=…), preexec_fn=, trust_remote_code=True, prefill_chunk_size with the VLM class, continue_final_message for thinking resumes. Commit on ' + PLAN_BRANCH + ', remove the worktree, and return VERDICT (mode plan, verdict pass, sha = that commit, checks[] listing the files written, hunks_cited = the ledger path@sha).'].join('\n'),
  catalog: () => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:catalog (read-only Hub reads via ToolSearch: hub_repo_details / hf_fs cat of model.safetensors.index.json and config.json). For each candidate in ' + J(A.catalog_candidates) + ' save the RAW response under ' + GRILL + '/evidence/catalog/<owner>__<name>.json with fetched_at, record revision (40-hex), inferenceProviderMapping, has_visual_tensors (any weight key starting with model.visual.), quant format; on any fetch failure after 3 tries record status unresolved for that entry — never a remembered value. (Card product-13a-catalog later copies these files into the repo at evidence/catalog/ so the gate and CI can read saved_path.) Return VERDICT with findings[] one per candidate (kind omitted-obligation, verification_level local-mechanical, reproduction = the tool call you made and the saved path).'].join('\n'),
  plan: (pre, defects) => [PREAMBLE, AUTHORITY, 'ROLE: planner mode:plan. Inputs: ' + A.decision_queue_path + ' (Resolved decisions ONLY — decided values, never recommendations; record the DQ line number of each), ' + A.lens4_path + ' (§B layout, §C duplication list, §D 14 steps, §E ship-but-flag, §F pins), ' + A.findings_path + ' (use ONLY the CORRECTED CLAIM / CORRECTED RECOMMENDATION lines), ' + A.redteam_path + ' §1-§3, plan/api-ledger.json, and these pre-verified findings (a REFUTED id must not become a card; an UNVERIFIED one may only be cited at verification_level unverified):', J(pre),
    defects && defects.length ? 'REPAIR MODE: the previous plan on ' + PLAN_BRANCH + ' was rejected by the script for these defects — fix every one, keep everything else, commit on the same branch:\n' + J(defects) : '',
    'On branch ' + PLAN_BRANCH + ' write: plan/decisions.json (one row per G-/M- id and per clarification the design §4.0 lists: id, decided_value, against_recommendation, consequences[], dq_line; the ids ' + J(AGAINST) + ' are against_recommendation=true); plan/preverified.json (the list above); plan/cards/<id>.json for the design §4.2 split (22 cards, S/M only, path, files_allowed/tests_allowed/new_modules/required_files (together they must cover the design\'s MANIFEST_MIN for that card)/deps_allowed/xfail_allowed (lens-4 §F known-bads only)/expected_green_tests (characterisation pins and contract tests that are green on the old tree BY DESIGN — nothing else)/tests_removed_expected/est_lines (S ≤ 120, M ≤ 300)/est_minutes, dod[] ≤ 8 runnable CPU commands with expect and verification_level, risk, protected_touch only on platform-01-gate, bootstrap false everywhere, decision_ids, finding_ids with corrected_text, apis_expected, owner_precondition: fixture1_path on platform-04-streamparser, persona_boundary_fixture_path on product-13b-personas-readme, worker_checkpoint_decision on platform-08c-worker-checkpoint); plan/index.json (cards + decisions + preverified); AGENTS.md (this preamble + gate usage). Locate code by symbol (`git grep -n "def <name>"`), never by line. Card platform-01-gate (size M) delivers the config.py skeleton with every §4.6 default, tools/stubs, tools/make_boundary_fixture.py, the false-claim fixture pair and the journeys conftest. Card platform-05a-registry quotes G-15 point (5) verbatim. Cards 08a/08b quote the token-level continuation (gpu-lease-3 CORRECTED + critic-4), the VLM-class precondition (inference-perf-2/-5/-7 CORRECTED), the find_spec probe (inference-perf-4 CORRECTED) and the presence_penalty decision (' + (A.torch_in_venv ? 'torch IS in the venv: worker/penalty.py with a CPU test' : 'torch is NOT in the venv: remove the placebo; API 400 unless 0') + '). The persona card lists only the G-19 role names and forbids reading system_prompt.py history. Commit and return CARD_INDEX (decisions[] echoes the sheet rows; preverified[] echoes plan/preverified.json).'].join('\n'),
  planCheck: idx => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:plan (refute-first). Read every card under ' + R + '/plan/cards at ' + idx.plan_sha + ', plan/decisions.json and plan/preverified.json. REFUTE: (a) any DoD command that is not runnable on CPU under the venv (run it — it may fail, it must not be unrunnable); (b) any card whose text contradicts a decided value or quotes an original recommendation instead of the CORRECTED line; (c) any decision row whose decided_value or dq_line does not match ' + A.decision_queue_path + '; (d) any confirmed finding id no card cites, any REFUTED id a card cites; (e) any staging/quota/lease claim at a local verification_level; (f) any xfail_allowed id that is not a lens-4 §F known-bad; (g) any lens-4 §C duplication item without a DoD line on some card; (h) any expected_green_tests id that is not a characterisation pin (lens-4 §F) or a contract test green on the old tree by construction; (i) any card whose est_lines exceeds its size class. Return findings with reproduction (the command you ran) and verdict pass|fail.'].join('\n'),
  index: () => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:evidence. Read ' + R + '/plan/index.json, plan/decisions.json and plan/preverified.json at ' + A.plan_sha + ' and return them as the `cards`, `decisions` and `preverified` arrays of CARD_INDEX (no changes); status FAILED if the sha or a file is missing.'].join('\n'),
  author: (c, base, k, rd, redInfo) => [PREAMBLE, AUTHORITY, 'ROLE: author mode:tests for ' + c.id + ' (attempt ' + k + '). ' + cardRef(c), 'Base: ' + base + '. Create worktree ' + WT + '/tests-' + c.id + '-' + A.run_nonce + ' on NEW branch ' + testsBranch(c.id) + ' from the base (if the branch exists and its tests already exist, verify them and return status reused).',
    c.risk === 'persona' ? 'PERSONA BOUNDARY: create the worktree as a history-free clone instead: `git clone --depth 1 --single-branch --branch ' + INTEG + ' file://' + R + ' ' + WT + '/tests-' + c.id + '-' + A.run_nonce + '` at ' + base + ', commit there, then `git -C "' + R + '" fetch "' + WT + '/tests-' + c.id + '-' + A.run_nonce + '" HEAD:refs/heads/' + testsBranch(c.id) + '`. FIXTURE COPY STEP: copy the owner-generated file ' + (OA.persona_boundary_fixture_path || '<owner_approvals.persona_boundary_fixture_path>') + ' verbatim to tests/fixtures/persona_boundary.json (its sha256 must equal ' + (OA.persona_boundary_fixture_sha256 || '<owner_approvals.persona_boundary_fixture_sha256>') + '; the gate pins it) and commit it with the tests. The absence test reads ONLY that fixture (hashed 6-word shingles) and asserts no persona text shingle matches; it never contains or reads the excluded clause.' : '',
    'Write ONLY the tests that prove the card\'s DoD lines (files listed in tests_allowed, or new files under tests/); no implementation code; never modify protected files unless the card is platform-01-gate; xfail/skip markers only for ids in the card\'s xfail_allowed. Every new test must be RED on the base for the expected reason (assertion / NotImplemented, or ImportError only for modules in new_modules) EXCEPT the ids listed in expected_green_tests, which must be green (they characterise the old tree). Commit "tests(' + c.id + '): …" with trailer "Card: ' + c.id + '". Run ' + gateCmd('--only-tests <your test paths> --card ' + cardPath(c) + ' --base ' + base) + ' on the committed, clean tree and quote its confirm-red line and LEDGER_DIGEST; suggest up to 3 one-line mutants (file, find, replace) in files_allowed that your tests should catch. Remove your worktree (branch survives).',
    redInfo ? 'PREVIOUS ATTEMPT REJECTED by the independent red verifier — do not return the same tests: ' + J(redInfo) : '', redriveLine(rd)].join('\n'),
  red: (c, t, base, rd) => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:red for ' + c.id + '. ' + cardRef(c), 'Detached worktree ' + WT + '/red-' + c.id + '-' + A.run_nonce + ' at ' + t.tests_head + '. Run ' + gateCmd('--only-tests ' + t.test_paths.join(' ') + ' --card ' + cardPath(c) + ' --base ' + base) + ' yourself (return its LEDGER_DIGEST as gate_digest — it must equal the author\'s) and `pytest --collect-only -q` on the rest of the suite. verdict pass ONLY if the gate\'s confirm-red step is green: every new test fails for the expected reason (rc 1 or 2; not SyntaxError; ImportError only for new_modules; not rc 5) except the expected_green_tests, which are green, and the author-tamper step is green. Remove the worktree.' + redriveLine(rd)].join('\n'),
  build: (c, t, base, k, fails, mergedIds, rd) => [PREAMBLE, AUTHORITY, 'ROLE: builder mode:' + (fails ? 'fix' : 'implement') + ' for ' + c.id + ' (build call ' + k + '/' + MAX_BUILD + '). ' + cardRef(c),
    'Branch ' + taskBranch(c.id) + (fails ? ' already exists: worktree ' + WT + '/task-' + c.id + '-' + A.run_nonce + '-fix' + k + ' on it' : ': create worktree ' + WT + '/task-' + c.id + '-' + A.run_nonce + ' on that NEW branch from ' + testsBranch(c.id) + ' (head ' + t.tests_head + '); if the branch already exists and is green on the card\'s DoD, report status reused') + '.',
    c.risk === 'persona' ? 'PERSONA BOUNDARY: use a history-free clone (`git clone --depth 1 --single-branch --branch ' + testsBranch(c.id) + ' file://' + R + ' <worktree>`) and `git -C "' + R + '" fetch <worktree> HEAD:refs/heads/' + taskBranch(c.id) + '` when done.' : '',
    'Make the card\'s tests pass by implementing exactly the card (files_allowed/new_modules/required_files only; you may ADD tests under tests/unit/ but never modify or delete an existing test; never touch plan/). Every gradio/spaces/transformers/huggingface_hub call must cite plan/api-ledger.json (apis_used[].ledger_ref) — never memory. Commit per coherent step; each message has a "Claims:" block naming symbols/files that ARE in that diff, and trailer "Card: ' + c.id + '". Run every DoD command, then run the gate LAST, at your final commit, on a clean tree (`git status --porcelain` empty — the gate refuses a dirty tree): ' + gateCmd('--card ' + cardPath(c) + ' --base ' + t.tests_head + ' --oracle ' + t.tests_head + mergedArgs(mergedIds)) + ' (advisory; return its LEDGER_DIGEST as gate_digest, its profile, and its steps[] {name, exit_code} as gate_steps). Return head_sha, dod[] with one row per card DoD id and exit codes, apis_used[], changed_files. Remove your worktree at the end.',
    fails ? 'FAILING EVIDENCE (typed, from an independent verifier; fix the cause, never the test):\n' + J(fails) : '', redriveLine(rd)].join('\n'),
  verify: (c, t, b, k, mergedIds, rd) => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:verify for ' + c.id + ' (verify ' + k + '). ' + cardRef(c), 'Detached worktree ' + WT + '/verify-' + c.id + '-' + A.run_nonce + '-' + k + ' at ' + b.head_sha + '. Do NOT trust the builder: (1) run EXACTLY ' + gateCmd('--card ' + cardPath(c) + ' --base ' + t.tests_head + ' --oracle ' + t.tests_head + mergedArgs(mergedIds)) + ' yourself and return its LEDGER_DIGEST as gate_digest, its LEDGER_SHA256, the head_sha in the ledger, the profile, IDIOM_HITS as idiom_hits, its steps[] as gate_steps, its LEDGER_DIFF_STATS as diff_stats (required), its apicheck_unresolvable[] and `sha256sum ' + A.gate_sh + '` as gate_sha256_observed;',
    '(1b) SEPARATELY: write .gate/card-' + c.id + '.json = the card with apis_expected extended by the builder-reported APIS_USED below and run ' + gateCmd('--apicheck .gate/card-' + c.id + '.json --base ' + t.tests_head + ' --out .gate/apicheck-' + c.id + '.json') + ' — record it in checks[] as name "apicheck-extended" (this run has its own ledger and never changes the digest of (1)); APIS_USED: ' + J([...(b.apis_used || [])].sort((x, y) => (x.module + x.symbol < y.module + y.symbol ? -1 : 1))) + '; (2) re-run every DoD command (dod_reruns[] one per card DoD id); (3) read `git diff ' + t.tests_head + '..' + b.head_sha + '` and cite hunks; (4) write .gate/mutants/' + c.id + '.json ({"tests":[the author\'s test paths],"mutants":[3 one-line breaks inside files_allowed that the card\'s tests must catch; start from the author\'s suggestions if any]}) and run ' + gateCmd('--mutants .gate/mutants/' + c.id + '.json --tests ' + t.test_paths.join(',') + ' --out .gate/mutants-' + c.id + '.json') + ' (written ≥ 1, ALL killed); (5) run ' + gateCmd('--revert-proof ' + t.tests_head + ' --tests ' + [...new Set(t.test_paths.concat((b.changed_files || []).filter(f => /^tests\/unit\/.*\.py$/.test(f))))].sort().join(',') + ' --out .gate/revert-' + c.id + '.json') + ' (the author\'s tests plus the builder-added tests/unit files) and report revert_proof.observed;',
    '(6) clear every idiom-lint warning by idiom with a reason, or fail; (7) verdict fail on ANY failure, on a bootstrap profile, on collected 0, on a missing DoD row. Default to fail when uncertain; state your strongest disagreement even on pass. Remove the worktree.' + redriveLine(rd)].join('\n'),
  merge: (c, b, head, mergedIds) => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:merge (single writer of ' + INTEG + '). In ' + R + ': ensure ' + INTEG + ' is at ' + head + '; if ' + b.head_sha + ' is already an ancestor (`git merge-base --is-ancestor`; exit 128 = unknown → status missing-ref) run ' + gateCmd('--base ' + head + '~1 --journeys' + mergedArgs([...mergedIds, c.id])) + ' at the CURRENT head and return status already-merged with head_sha = ' + head + ' (the head never moves on already-merged), its LEDGER_DIGEST, exit code, and the cherry/patch-id assertions; else `git merge --no-ff ' + taskBranch(c.id) + '` (head ' + b.head_sha + '). If the ref is missing → status missing-ref. On ANY conflict: `git merge --abort`, return status conflict with the hunks (ours/theirs) — do not resolve.',
    'On a clean merge: record the merge commit as merge_sha; run ' + gateCmd('--base ' + head + ' --journeys' + mergedArgs([...mergedIds, c.id])) + ' (the journeys, when present, run at every merge); if red → `git revert -m 1 <merge_sha>` immediately and return status reverted with merge_sha and the ledger; if green → assert `git cherry ' + INTEG + ' ' + taskBranch(c.id) + '` is empty and every `git patch-id` of the task commits appears in ' + head + '..HEAD; write plan/status/' + c.id + '.json {state:"merged", head_sha, merge_sha, gate_digest} and commit "status(' + c.id + '): merged"; `git bundle create ' + BUNDLES + '/' + c.id + '.bundle ' + head + '..' + INTEG + '` (incremental) and append {id, path, sha256, bytes} to ' + BUNDLE_MANIFEST + '; remove worktrees of ' + taskBranch(c.id) + ' and ' + testsBranch(c.id) + '; return status merged + head_sha (after the status commit) + merge_sha + LEDGER_DIGEST as gate_digest + gate_sha256_observed + journeys {collected, failed, skipped_needs[]} from the ledger + `git remote -v` lines.'].join('\n'),
  conflict: (c, b, head, hunks) => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:conflict (fresh). `git -C ' + R + ' worktree add --detach ' + WT + '/conflict-' + c.id + '-' + A.run_nonce + ' ' + head + '` (detached: ' + INTEG + ' is checked out in ' + R + '). Merge ' + taskBranch(c.id) + ' (' + b.head_sha + ') resolving ONLY these hunks so that this card\'s DoD AND the already-merged cards still hold; run ' + gateCmd('--base ' + head + ' --journeys') + '; commit the merge; return head_sha = merge_sha = that commit + LEDGER_DIGEST (status merged) or gate-red. ' + cardRef(c), 'HUNKS:', J(hunks)].join('\n'),
  ff: (c, sha, mergedIds) => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:ff. Fast-forward ' + INTEG + ' in ' + R + ' to ' + sha + ' (a merge commit made in a worktree; merge_sha = ' + sha + '); run ' + gateCmd('--base ' + sha + '~1 --journeys' + mergedArgs([...mergedIds, c.id])) + '; cherry/patch-id assertions for ' + taskBranch(c.id) + '; write plan/status/' + c.id + '.json and commit; bundle to ' + BUNDLES + '/' + c.id + '.bundle and append to ' + BUNDLE_MANIFEST + '; return status merged + head_sha + merge_sha + LEDGER_DIGEST + journeys from the ledger.'].join('\n'),
  revert: (id, head, mergeSha, mergedIds) => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:revert (single writer of ' + INTEG + '). In ' + R + ' on ' + INTEG + ' at ' + head + ': `git revert -m 1 ' + mergeSha + '` (the merge commit of ' + id + '; also remove plan/status/' + id + '.json in the same commit if it exists); run ' + gateCmd('--base ' + head + ' --journeys' + mergedArgs(mergedIds)) + ' on the result; return status merged with the new head_sha (merge_sha = "") and LEDGER_DIGEST when the gate is green, else status gate-red with the ledger. Do nothing else.'].join('\n'),
  fixcards: (cards, head, round) => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:fixcards (single writer of ' + INTEG + '). In ' + R + ' on ' + INTEG + ' at ' + head + ': write each of these review fix cards VERBATIM to its path (plan/fixes/ is the mutable area for review fix cards; plan/cards/ stays immutable), commit them together as "plan(fixes): review round ' + round + '" and return status written, head_sha (the new head) and files_written[] (every path). CARDS: ' + J(cards.map(c => ({ path: cardPath(c), content: Object.assign({}, c, { finding: undefined }) })))].join('\n'),
  clean: (w, head, mergedIds, lintBase) => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:clean-gate for wave ' + w + '. `git -C ' + R + ' worktree add --detach ' + WT + '/clean-w' + w + '-' + A.run_nonce + ' ' + head + '`; inside it run BROKEN_SHA=' + A.base_sha + ' ' + gateCmd('--clean --self-test --journeys --base ' + A.base_sha + ' --lint-base ' + lintBase + mergedArgs(mergedIds)) + ' (full suite twice, conformance on the fake backend, journeys with needs= skips counted, README check, red-proofs, gate integrity); return LEDGER_DIGEST as gate_digest, head_sha, journeys {collected, failed, skipped_needs[]}, self_test {broken_red, false_claim_red} from the ledger, gate_exit_code, gate_sha256_observed, `git -C ' + R + ' remote -v` lines and `git -C ' + R + ' branch --list | wc -l` as branch_count; remove the worktree. Also report toolchain_status_sha256 = sha256 of `' + TOOLCHAIN_STATUS_CMD + '` (must equal ' + A.toolchain_status_sha256 + ').'].join('\n'),
  journeys: (tag, head, seams) => [PREAMBLE, AUTHORITY, 'ROLE: author mode:journeys (' + tag + ') at ' + head + '. Seams whose card merged this wave: ' + seams.join(', ') + '. On NEW branch ' + taskBranch('journeys-' + tag) + ' from ' + head + ' write composition tests under tests/journeys/ (tests/journeys/conftest.py from card 01 marks them `journey`; they are deselected from every default pytest run and selected only by gate.sh --journeys) for those seams (H1 tool loop × streaming × Continue at TOKEN level: turn 2 contains turn 1\'s tool results, finish_reason length → Continue resumes from prefix_ids; H2 /v1 × identity: x-ip-token bound inside the generator body, 429 on the non-blocking semaphore; H3 MCP ask→poll→status→preflight with chat hidden; H4 python_eval × operator flag × every surface: UI checkbox alone cannot enable it, unreachable over /v1 and MCP; H5 catalog admission × models.yaml schema × harness zero-call × pending entries hidden; H6 session isolation × TTL sweep × no rmtree on unload; H7 error taxonomy quota/illegal-duration/abort → titled notice in UI, {"error":…} event on /v1, partial text kept; J1 QWEN_STUB=1 boot serves UI + /healthz{git_sha from build_info.json} in < 10 s on a free port). Each journey that needs an unmerged card is marked `pytest.mark.skip(reason="needs=<card-id>")` — no other skip reason is allowed. Commit, run ' + gateCmd('--only-tests tests/journeys --base ' + head) + ' (composition tests are allowed to be green; the step journeys-only-tests reports them), return tests_head and test_paths.'].join('\n'),
  review: (lens, head, seenKeys, round) => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:review, lens ' + lens + ', round ' + round + '. Branch ' + INTEG + ' at ' + head + ' in a detached worktree ' + WT + '/review-' + lens + '-r' + round + '-' + A.run_nonce + '. Read plan/decisions.json, plan/index.json and `git diff ' + A.base_sha + '..' + head + '` (use --color-moved to skip pure moves).',
    'Report ONLY problems that affect correctness, a decided value, scope, test integrity, security or secrets — each with a reproduction at ' + head + ' whose command EXITS NON-ZERO while the defect exists and 0 once it is fixed (e.g. `! grep -q …`, a pytest invocation, a python -c assertion; never a bare `grep` that exits 0 on a hit), plus a files_allowed[] for its fix; no style findings. List probes_used[] (the commands/angles you used). Known finding keys to skip: ' + J(seenKeys) + '. Remove the worktree.'].join('\n'),
  refute: (f, head) => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:refute. Try to REFUTE this finding at ' + head + ' in a detached worktree; default to refuted if uncertain; holds ONLY with a reproduction you executed whose command exits NON-ZERO on the defect (and would exit 0 once fixed) — rewrite the command if the reviewer\'s does not have that shape. Return the finding back as findings[0] with your corrected_claim.', J(f)].join('\n'),
  veto: (head, rows, last, probes) => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:veto (you may only VETO with a reproduction; you can never approve). ' + INTEG + ' at ' + head + '. Inputs: plan/decisions.json, plan/index.json, the clean-gate ledger, and this status table: ' + J(rows), last ? 'LAST ROUND MANDATE (DoD inversion): start from the decided values and the cards; independently try to falsify every claimed end-state or find an omitted obligation; you may NOT reuse these probes: ' + J(probes) : 'Cite hunks; each veto is a finding with a reproduction (non-zero exit on the defect); otherwise return verdict no-veto with your strongest disagreement.'].join('\n'),
  evidence: (dir, head) => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:evidence for stage ' + A.stage + '. Read ONLY files under ' + dir + ' (space-runtime.json, healthz.json, canary.json, build-log.txt, rollback-drill.json, hardening-selftest.json) and ' + R + '/evidence/staging/' + head + '/EXPECTED.json (written by CI with tools/expected.py). For every expected number report a finding (kind staging-evidence, verification_level staging-required, severity critical for a failed canary / wrong sha / visibility not private, high for a missing file) with reproduction (the jq/python command you ran on the file, exiting non-zero on the defect) when the evidence is missing or contradicts EXPECTED; healthz.git_sha must equal the pushed sha and must not be "unknown"; the python version in space-runtime.json and the resolved requirements in build-log.txt must match requirements.lock (a difference is a finding at verification_level local-mechanical). Never call any URL.'].join('\n'),
  synth: (rows, checkpoint, stop, seenKeys, ledgerSummary) => [PREAMBLE, AUTHORITY, 'ROLE: synthesizer (never edits code). Write ' + GRILL + '/RUN-REPORT-' + A.run_nonce + '.md and ' + STATUS_JSON + ' ({rows (with reason and next), seen_keys, head_sha, last_clean_gate, halt, stop}) from ONLY these mechanical inputs: STOP=' + stop + '; ROWS=' + J(rows) + '; CHECKPOINT=' + J(checkpoint) + '; SEEN_KEYS=' + J(seenKeys) + '; LEDGER (sorted by role,mode,id,attempt)=' + J(ledgerSummary) + '; ledgers under ' + R + '/.gate and ' + R + '/plan/status; the bundle manifest ' + BUNDLE_MANIFEST + '. Rows in your return must equal the ROWS given (they will be overwritten otherwise). Include the persona absence-test result, deferred DoD lines by verification_level, blocked_on_owner first, the suggested retry_parked list, unresolvable API symbols per card, the owner\'s Hub post-checks (`gh repo list`, namespace listing unchanged), and "what would most improve confidence". Return report_path, report_bytes, status_json_path.'].join('\n'),
  synthFix: (path, rows) => [PREAMBLE, AUTHORITY, 'ROLE: synthesizer mode:fix (bash). The rows table in ' + path + ' differs from the script\'s ledger. Rewrite ONLY the rows table (and the matching rows in ' + STATUS_JSON + ') from these rows, nothing else: ' + J(rows) + '. Return report_path, report_bytes, status_json_path and the same rows.'].join('\n'),
}

// ---------------------------------------------------------------------------------------------
// Inner loop per card (§5) — returns a typed result, never throws; rd = re-drive counter (prompt suffix)
// ---------------------------------------------------------------------------------------------
const localLevel = lvl => !/staging|owner|unverified/.test(String(lvl))
const starved = r => r && r.status === 'null' && /^(budget|halt|agent-slice)$/.test(String(r.reason))   // C-8: nobody judged the work → retryable, never parked
function okSemantics(c, t, b, v) {                     // taskDone(): every condition a judge asked for, in code; returns the failed condition ids
  const ok = []
  ok[1] = v.verdict === 'pass' && v.gate_exit_code === 0 && v.status !== 'null'
  ok[2] = v.ledger_head_sha === b.head_sha && isSha(b.head_sha) && v.sha === b.head_sha
  ok[3] = isHex64(v.gate_digest) && v.gate_digest === b.gate_digest                                   // A1 G1: two independent executions agree (F-12)
  ok[4] = v.gate_sha256_observed === A.gate_sha256 && v.gate_profile === 'full' && b.gate_profile === 'full'   // pinned gate; the bootstrap profile is never a card profile (CG1, A2 G9)
  ok[5] = (v.hunks_cited || []).length >= 1 && (v.checks || []).some(x => /gate\.sh/.test(x.command || ''))
  ok[6] = !!v.mutants && v.mutants.written >= 1 && v.mutants.killed === v.mutants.written               // mutants mandatory, all killed (F-20)
  ok[7] = !!v.revert_proof && v.revert_proof.observed === 'red'                                          // negative control (A1 ok[7]/ok[8])
  ok[8] = (b.dod || []).length === c.dod.length && c.dod.every(d => !localLevel(d.verification_level) || ((b.dod || []).some(x => x.id === d.id && x.exit_code === 0) && (v.dod_reruns || []).some(x => x.id === d.id && x.exit_code === 0)))   // every local DoD id exit 0 on BOTH sides (A1 ok[6])
  ok[9] = (v.warnings_cleared || []).length >= (v.idiom_hits || 0)                                     // F-10 in code (A2 G14)
  ok[10] = !!v.diff_stats && Number.isInteger(v.diff_stats.insertions) && Number.isInteger(v.diff_stats.deletions) && (v.diff_stats.insertions + v.diff_stats.deletions) <= 2 * (c.est_lines || 300)   // scope expansion, fail closed without stats (A2 G8, C-25)
  ok[11] = !b.__secret_redacted && !v.__secret_redacted                                               // CG3: a secret-shaped output blocks the card
  ok[12] = (b.commits_made >= 1 || b.status === 'reused') && b.status !== 'partial' && (b.apis_used || []).every(a => !!a.ledger_ref)   // F-8: every API the builder used is anchored in the ledger
  const failed = [1,2,3,4,5,6,7,8,9,10,11,12].filter(k => !ok[k])
  log(c.id + ' taskDone: ' + [1,2,3,4,5,6,7,8,9,10,11,12].map(k => k + (ok[k] ? '✓' : '✗')).join(' '))
  return failed
}
function typedFailures(c, b, v, failedConds) {         // C-18: the fixer always receives an actionable, typed object; a digest mismatch carries both ledgers' steps
  const f = { conditions_failed: failedConds, failures: v.failures || [], checks_failed: (v.checks || []).filter(x => x.exit_code !== 0), dod_reruns_failed: (v.dod_reruns || []).filter(x => x.exit_code !== 0), strongest_disagreement: cap(v.strongest_disagreement, 600) }
  if (failedConds.includes(3)) {
    const bs = (b.gate_steps || []).map(s => s.name + '=' + s.exit_code), vs = (v.gate_steps || []).map(s => s.name + '=' + s.exit_code)
    f.digest_mismatch = { kind: 'digest-mismatch', builder_head: b.head_sha, verifier_head: v.ledger_head_sha, builder_steps: bs, verifier_steps: vs, steps_only_in_builder: bs.filter(x => !vs.includes(x)), steps_only_in_verifier: vs.filter(x => !bs.includes(x)), hint: 'the builder\'s advisory gate did not run at the final commit on a clean tree, or a step differs (see steps_only_in_*); re-run the gate LAST on the committed tree and return its digest' }
  }
  if (failedConds.includes(6)) f.mutants = v.mutants
  if (failedConds.includes(7)) f.revert_proof = v.revert_proof
  if (failedConds.includes(10)) f.scope = { diff_stats: v.diff_stats || null, est_lines: c.est_lines, hint: 'insertions + deletions must be ≤ 2 × est_lines (LEDGER_DIFF_STATS excludes tools/gate.sh and tests/fixtures/)' }
  return f
}
const failFingerprint = (v, failedConds, tf) => (fingerprint(v.failures) + '|cond:' + failedConds.join(',') + (tf.digest_mismatch ? '|dm:' + tf.digest_mismatch.steps_only_in_builder.concat(tf.digest_mismatch.steps_only_in_verifier).sort().join(',') : '')).replace(/[0-9a-f]{7,40}/g, 'SHA')
async function buildTask(c, base, mergedIds, rd) {
  const trail = []; let t = null, redInfo = null
  try {
    for (let k = 1; k <= MAX_AUTHOR; k++) {
      const a = await run('author', 'tests', c.id + ':' + k, P.author(c, base, k, rd, redInfo), { phase: 'Build', schema: TESTS, effort: 'medium' })
      if (starved(a)) return { card: c, state: 'starved', reason: 'starved:' + a.reason + ':author', trail }
      if (a.status === 'null') return { card: c, state: 'blocked', reason: 'agent-null:author:' + a.reason, trail }
      if (!isSha(a.tests_head) || !(a.commits_made >= 1 || a.status === 'reused')) return { card: c, state: 'blocked', reason: 'author-no-commit', trail }
      const red = await run('verifier', 'red', c.id + ':' + k, P.red(c, a, base, rd), { phase: 'Build', schema: VERDICT, effort: 'low' })
      trail.push({ author: k, red: red.verdict || red.status })
      if (starved(red)) return { card: c, state: 'starved', reason: 'starved:' + red.reason + ':red', trail }
      if (red.status === 'null') return { card: c, state: 'blocked', reason: 'agent-null:red', trail }
      if (red.verdict === 'pass' && red.gate_exit_code === 0 && red.sha === a.tests_head && isHex64(red.gate_digest) && red.gate_digest === a.gate_digest) { t = a; break }   // C-29: confirm-RED is a two-execution equality too
      if (k === MAX_AUTHOR) return { card: c, state: 'blocked', reason: 'tests-not-red', trail }
      redInfo = { verdict: red.verdict, digest_equal: red.gate_digest === a.gate_digest, failures: (red.failures || []).slice(0, 8), checks_failed: (red.checks || []).filter(x => x.exit_code !== 0).slice(0, 5), strongest_disagreement: cap(red.strongest_disagreement, 400) }   // C-26
      log(c.id + ': confirm-RED failed (' + k + '/' + MAX_AUTHOR + ') — re-driving the author with the red verdict')
    }
    let b = null, v = null, fails = null, prevFp = null, fps = []
    for (let k = 1; k <= MAX_BUILD; k++) {
      b = await run('builder', k === 1 ? 'build' : 'fix', c.id + ':' + k, P.build(c, t, base, k, fails, mergedIds, rd), { phase: 'Build', schema: BUILD, effort: 'high' })
      if (starved(b)) return { card: c, state: 'starved', reason: 'starved:' + b.reason + ':builder', trail, tests: t }
      if (b.status === 'null' || b.status === 'failed') return { card: c, state: 'blocked', reason: 'agent-null:builder:' + (b.reason || b.status), trail, tests: t }
      if (!(b.commits_made >= 1) && b.status !== 'reused') return { card: c, state: 'blocked', reason: 'no-commits', trail, tests: t }
      v = await run('verifier', 'verify', c.id + ':' + k, P.verify(c, t, b, k, mergedIds, rd), { phase: 'Build', schema: VERDICT, effort: c.risk === 'security' ? 'xhigh' : 'medium' })
      if (starved(v)) return { card: c, state: 'starved', reason: 'starved:' + v.reason + ':verifier', trail, tests: t, build: b }
      if (v.status === 'null') return { card: c, state: 'blocked', reason: 'agent-null:verifier', trail, tests: t, build: b }
      raiseLevels(v.findings, f => f.title + ' ' + (f.reproduction || {}).command)
      const failedConds = okSemantics(c, t, b, v)
      trail.push({ build: k, verdict: v.verdict || v.status, digestOk: v.gate_digest === b.gate_digest, failed: failedConds })
      if (!failedConds.length) break
      if (b.__secret_redacted || v.__secret_redacted) return { card: c, state: 'blocked', reason: 'secret-shaped-output', trail, tests: t, build: b, verify: v }
      const tf = typedFailures(c, b, v, failedConds), fp = failFingerprint(v, failedConds, tf); fps.push(fp)
      if (fp === prevFp) return { card: c, state: 'blocked', reason: 'no-progress', trail, tests: t, build: b, verify: v }          // two strikes (D-8) — never empty now (C-18)
      if (fps.length >= 3 && fps[fps.length - 1] === fps[fps.length - 3]) return { card: c, state: 'blocked', reason: 'oscillation', trail, tests: t, build: b, verify: v }
      if (k === MAX_BUILD) return { card: c, state: 'blocked', reason: 'fix-exhausted', trail, tests: t, build: b, verify: v }
      prevFp = fp; fails = tf
      log(c.id + ': verify FAILED (' + k + '/' + MAX_BUILD + ') conditions ' + failedConds.join(',') + ' fp=' + fp.slice(0, 60) + ' — fixing')
    }
    const deferred = c.dod.filter(d => !localLevel(d.verification_level)).map(d => d.id)
    return { card: c, state: 'built', tests: t, build: b, verify: v, deferred, apiUnresolvable: (v.apicheck_unresolvable || []).slice().sort(), trail }        // taskDone() true
  } catch (e) { log(c.id + ': stage threw ' + String(e && e.message)); return { card: c, state: 'blocked', reason: 'threw', trail } }
}

// ---------------------------------------------------------------------------------------------
// Serial integration of one built card (§4.5) — mutates `head` via the returned value only; every merge is logged with its merge sha (C-12)
// ---------------------------------------------------------------------------------------------
const mergeOk = m => m.status === 'merged' && isSha(m.head_sha) && isSha(m.merge_sha) && m.gate_exit_code === 0 && isHex64(m.gate_digest) && m.gate_sha256_observed === A.gate_sha256 && !(m.cherry_unmerged || []).length && !(m.patch_ids_missing || []).length
const alreadyOk = (m, head) => m.status === 'already-merged' && m.head_sha === head && m.gate_exit_code === 0 && isHex64(m.gate_digest) && m.gate_sha256_observed === A.gate_sha256 && !(m.cherry_unmerged || []).length && !(m.patch_ids_missing || []).length   // C-20: an ancestor never moves the head; gate + cherry evidence required
const mergeLog = []                          // [{id, merge_sha, head_after}] in order — the revert target is always the LAST entry (journeys included)
const journeyChecks = []                     // journeys skipped after their card merged → synthetic findings (collected at merge and clean gates)
function noteJourneys(cg, where) {
  const stillSkipped = ((cg.journeys || {}).skipped_needs || []).filter(n => mergedSet().has(n)).sort()
  if (stillSkipped.length) { log(where + ': journeys still skipped although their card merged: ' + stillSkipped.join(',') + ' → synthetic finding'); journeyChecks.push({ id: 'journey-needs-' + stillSkipped.join('+'), title: 'journey skipped after its card merged', file: 'tests/journeys', severity: 'high', kind: 'interaction', reproduction: { command: gateCmd('--clean --journeys'), exit_code: 1, output_tail: 'skipped_needs=' + stillSkipped.join(',') }, verification_level: 'local-stub', files_allowed: ['tests/journeys'] }) }
}
async function checkedRevert(id, head, mergeSha, why) {   // CG-24 + C-12/C-20: revert by merge sha; the result is checked; failure dirties the branch
  const rv = await run('integrator', 'revert', id + ':revert', P.revert(id, head, mergeSha, [...mergedSet()].filter(x => x !== id)), { phase: 'Integrate', schema: MERGE, effort: 'low' })
  if (rv.status === 'merged' && isSha(rv.head_sha) && rv.gate_exit_code === 0 && isHex64(rv.gate_digest) && rv.gate_sha256_observed === A.gate_sha256) { log(id + ': reverted (' + why + ') → ' + rv.head_sha.slice(0, 12)); return { ok: true, head: rv.head_sha } }
  INTEG_DIRTY = true; log('REVERT FAILED for ' + id + ' (' + why + ', ' + (rv.status || rv.reason) + ') — integration branch marked dirty; no further merges (CG-24)'); return { ok: false, head }
}
async function integrate(r, head, mergedIds) {
  let m = await run('integrator', 'merge', r.card.id, P.merge(r.card, r.build, head, mergedIds), { phase: 'Integrate', schema: MERGE, effort: 'low' })
  if (m.status === 'conflict') {
    log(r.card.id + ': conflict in ' + m.conflicts.map(x => x.file).join(',') + ' — fresh conflict call')
    const res = await run('integrator', 'conflict', r.card.id, P.conflict(r.card, r.build, head, m.conflicts), { phase: 'Integrate', schema: MERGE, effort: 'high' })
    m = res.status === 'merged' ? await run('integrator', 'ff', r.card.id + ':ff', P.ff(r.card, res.head_sha, mergedIds), { phase: 'Integrate', schema: MERGE, effort: 'low' }) : res
  }
  if (starved(m)) return { head, state: 'starved', reason: 'starved:' + m.reason + ':integrator' }
  if (m.status === 'missing-ref') { log(r.card.id + ': ref missing (stale sha) — will re-drive live'); return { head, state: 'stale' } }
  if (m.status === 'already-merged') { if (alreadyOk(m, head)) return { head, state: 'merged', digest: m.gate_digest, already: true }; log(r.card.id + ': already-merged WITHOUT evidence (head ' + String(m.head_sha).slice(0, 12) + ' vs ' + head.slice(0, 12) + ', exit ' + m.gate_exit_code + ', cherry ' + (m.cherry_unmerged || []).length + ') — not counted (C-20)'); return { head, state: 'blocked', reason: 'integration:already-merged-unproven' } }
  if (m.status === 'reverted') return { head: isSha(m.head_sha) ? m.head_sha : head, state: 'reverted', reason: 'integration:gate-red-after-merge(reverted)' }
  if (m.status === 'merged' && m.gate_exit_code !== 0 && isSha(m.merge_sha)) {            // C-20: "merged + red" is a revert-now case, checked
    const rv = await checkedRevert(r.card.id, isSha(m.head_sha) ? m.head_sha : head, m.merge_sha, 'merge gate red')
    return rv.ok ? { head: rv.head, state: 'reverted', reason: 'integration:gate-red-after-merge(reverted)' } : { head: rv.head, state: 'revert-failed', reason: 'integration:gate-red-after-merge(revert-failed)' }
  }
  if (!mergeOk(m)) { log(r.card.id + ': NOT integrated (' + m.status + (m.reason ? ':' + m.reason : '') + ')'); return { head, state: 'blocked', reason: 'integration:not-merged:' + (m.status === 'null' ? String(m.reason || 'null') : m.status) } }
  if ((m.remotes || []).length && !OA.github_repo_url) { HALT = 'remote-added:' + r.card.id; log('HALT ' + HALT) }   // CG5: mechanical post-check, not self-report
  mergeLog.push({ id: r.card.id, merge_sha: m.merge_sha, head_after: m.head_sha })
  noteJourneys(m, 'merge ' + r.card.id)
  return { head: m.head_sha, state: 'merged', digest: m.gate_digest, merge_sha: m.merge_sha }
}
// clean gate, typed three ways (C-11): pass | fail | gate-unavailable(reason) — a malformed return never reverts anything
async function cleanGate(tag, head, mergedIds) {
  const lintBase = lastClean.verdict === 'pass' && isSha(lastClean.head_sha) ? lastClean.head_sha : A.base_sha        // C-15: lint only what this wave added
  const cg = await run('integrator', 'clean', tag, P.clean(tag, head, mergedIds, lintBase), { phase: 'Integrate', schema: MERGE, effort: 'low' })
  if (cg.status === 'null') { lastClean = { verdict: 'gate-unavailable', head_sha: head, digest: null, wave: tag, why: cg.reason }; log(tag + ': clean-gate UNAVAILABLE (' + cg.reason + ') — no revert; satisfied() stays false'); return lastClean }
  const st = cg.self_test || {}, shaped = isSha(cg.head_sha) && isHex64(cg.gate_digest) && cg.gate_sha256_observed === A.gate_sha256 && typeof st.broken_red === 'boolean' && typeof st.false_claim_red === 'string' && !!cg.journeys && Number.isInteger(cg.gate_exit_code)
  if (!shaped || cg.head_sha !== head) { lastClean = { verdict: 'gate-unavailable', head_sha: head, digest: null, wave: tag, why: !shaped ? 'malformed' : 'wrong-head:' + String(cg.head_sha).slice(0, 12) }; log(tag + ': clean-gate MALFORMED (' + lastClean.why + ') — treated as unavailable, no revert (C-11)'); return lastClean }
  if (cg.toolchain_status_sha256 && cg.toolchain_status_sha256 !== A.toolchain_status_sha256) { HALT = 'toolchain-mutated'; log('HALT ' + HALT + ' (F-1; docs/grills excluded from the comparison)') }
  if ((cg.remotes || []).length && !OA.github_repo_url) { HALT = 'remote-added:clean-gate'; log('HALT ' + HALT) }
  noteJourneys(cg, tag)
  const pass = cg.gate_exit_code === 0 && st.broken_red === true && st.false_claim_red === 'true'
  if (cg.gate_exit_code === 0 && !pass) { lastClean = { verdict: 'gate-unavailable', head_sha: head, digest: cg.gate_digest, wave: tag, why: 'exit0-but-self-test-not-red:' + st.broken_red + '/' + st.false_claim_red }; log(tag + ': clean-gate exit 0 but self-test contradicts it — treated as unavailable (C-11)'); return lastClean }
  lastClean = { verdict: pass ? 'pass' : 'fail', head_sha: head, digest: cg.gate_digest, wave: tag }
  return lastClean
}

// ---------------------------------------------------------------------------------------------
// Build + integrate a list of cards — waves computed ONE AT A TIME from the live status map (C-5); used for the plan and for review fix tasks
// ---------------------------------------------------------------------------------------------
const status = new Map()                    // card id → typed state (the script's own row table; F-40); every entry carries a reason (C-22)
let lastClean = { verdict: 'gate-unavailable', head_sha: null, digest: null, why: 'never-run' }, INTEG_DIRTY = false
const mergedSet = () => new Set([...status.entries()].filter(([, s]) => s.state === 'merged').map(([id]) => id))
const stateOf = id => (status.get(id) || {}).state || null
const PARKED_RE = /^(parked|reverted|revert-failed|dropped_null)$/
function readyWave(cards, rank) {           // cards with no status whose deps are all merged, by (−rank, id), disjoint write sets, ≤ WAVE; the waiters are logged
  const ready = cards.filter(c => !status.has(c.id) && c.depends_on.every(d => mergedSet().has(d))).sort(byRank(rank))
  const wave = [], used = new Set(), waited = []
  for (const c of ready) { const ws = writeSet(c), clash = [...ws].some(f => used.has(f)); if (!clash && wave.length < WAVE) { wave.push(c); ws.forEach(f => used.add(f)) } else waited.push(c.id) }
  if (waited.length) log('wave: ' + waited.join(',') + ' wait (size or write-set overlap)')   // T-AP-11: never silent
  return wave
}
function markDependencyBlocked(cards) {     // after the loop: every card still without a status has a dependency that is not merged
  for (const c of cards) if (!status.has(c.id)) { const unmet = c.depends_on.filter(d => !mergedSet().has(d)); if (unmet.length) { status.set(c.id, { state: 'not_attempted', reason: 'dependency-blocked:' + unmet.map(d => d + '(' + (stateOf(d) || 'unscheduled') + ')').join('/'), next: 'resolve the dependency; relaunch stage=' + A.stage }); log(c.id + ': not attempted (deps ' + unmet.join('/') + ')') } }
}
async function buildAndIntegrate(cards, head, tag) {
  cards.forEach(c => CARD_BY_ID.set(c.id, c))
  for (const c of cards) { const pre = c.owner_precondition; if (pre && !OA[pre] && !status.has(c.id)) { status.set(c.id, { state: 'blocked_on_owner', field: pre, reason: 'owner-precondition:' + pre, next: 'owner records owner_approvals.' + pre + '; relaunch stage=' + A.stage }); log(c.id + ': blocked on owner_approvals.' + pre) } }
  const rank = rankCards(cards)
  let w = 0
  while (true) {
    const wave = readyWave(cards, rank)
    if (!wave.length) break
    w++
    if (INTEG_DIRTY || !budgetOk(tag + ' wave ' + w) || !agentsOk(tag + ' wave ' + w, RESERVE_PER_CHAIN * wave.length + 4)) {   // C-8: starvation is not_attempted (retryable), never parked
      const why = INTEG_DIRTY ? 'integration-dirty' : (HALT ? 'halt:' + HALT : 'agent-slice-or-budget')
      cards.filter(c => !status.has(c.id)).forEach(c => status.set(c.id, { state: 'not_attempted', reason: 'not_attempted:' + why, next: why === 'integration-dirty' ? 'owner inspects ' + INTEG + ' (revert failed); relaunch after repair' : 'relaunch stage=' + A.stage + ' with next_args' }))
      log(tag + ': wave ' + w + ' and the rest NOT attempted (' + why + ')'); break
    }
    log(tag + ' wave ' + w + ': ' + wave.map(c => c.id).join(', ') + ' on ' + head.slice(0, 12))
    const mergedBefore = [...mergedSet()]
    const results = await pipeline(wave, c => buildTask(c, head, mergedBefore, 0))
    let dropped = 0; results.forEach((r, i) => { if (!r) { dropped++; status.set(wave[i].id, { state: 'dropped_null', reason: 'chain-null', next: 'retry_parked' }) } })
    if (dropped) log(tag + ' wave ' + w + ': ' + dropped + ' chain(s) resolved null (typed dropped_null)')
    phase('Integrate')
    const merged = []
    for (const r of results.filter(Boolean).sort((x, y) => byRank(rank)(x.card, y.card))) {      // C-24: serial, rank order, ties by id
      if (r.state === 'starved') { status.set(r.card.id, { state: 'not_attempted', reason: r.reason, next: 'relaunch stage=' + A.stage + ' with next_args (branches survive; author/builder return reused)', trail: r.trail }); continue }
      if (r.state !== 'built') { status.set(r.card.id, { state: 'parked', reason: r.reason, next: RETRYABLE_RE.test(r.reason) ? 'retry_parked' : 'inspect the trail; a review fix card or a plan repair', head_sha: r.build ? r.build.head_sha : null, dod: r.build ? r.build.dod : [], trail: r.trail }); continue }
      let it = await integrate(r, head, [...mergedSet()])
      if (it.state === 'stale') { const again = await buildTask(r.card, head, [...mergedSet()], 1); it = again.state === 'built' ? await integrate(again, head, [...mergedSet()]) : { state: again.state === 'starved' ? 'starved' : 'blocked', reason: again.reason, head } }
      if (it.state === 'merged') { head = it.head; merged.push(r.card.id); status.set(r.card.id, { state: 'merged', reason: it.already ? 'already-merged(proven)' : 'merged', next: 'none', head_sha: head, merge_sha: it.merge_sha || null, dod: r.build.dod, deferred: r.deferred, digest: it.digest, api_unresolvable: r.apiUnresolvable }); log(r.card.id + ' merged → ' + head.slice(0, 12)) }
      else if (it.state === 'starved') status.set(r.card.id, { state: 'not_attempted', reason: it.reason, next: 'relaunch stage=' + A.stage + ' (built branch survives)', head_sha: r.build.head_sha, dod: r.build.dod })
      else { if (isSha(it.head)) head = it.head; status.set(r.card.id, { state: it.state === 'reverted' ? 'reverted' : it.state === 'revert-failed' ? 'revert-failed' : 'parked', reason: it.reason, next: RETRYABLE_RE.test(it.reason) ? 'retry_parked' : 'review fix card', head_sha: r.build.head_sha, dod: r.build.dod }) }
    }
    const seams = Object.keys(JOURNEY_NEEDS).filter(s => merged.includes(JOURNEY_NEEDS[s])).sort()
    let journeysMerged = false
    if (seams.length && !A.smoke) {
      const jw = await run('author', 'journeys', tag + ':w' + w, P.journeys(tag + '-w' + w, head, seams), { phase: 'Integrate', schema: TESTS, effort: 'medium' })
      if (jw.status === 'SUCCESS' && isSha(jw.tests_head)) { const jm = await integrate({ card: { id: 'journeys-' + tag + '-w' + w }, build: { head_sha: jw.tests_head } }, head, [...mergedSet()]); if (jm.state === 'merged') { head = jm.head; journeysMerged = true } else log('journeys ' + tag + '-w' + w + ' NOT merged: ' + jm.reason) }
      else log('journeys author ' + tag + '-w' + w + ' dropped/failed: ' + (jw.reason || jw.status))
    }
    if (!merged.length && !journeysMerged && lastClean.verdict === 'pass' && lastClean.head_sha === head) { log(tag + ' wave ' + w + ': nothing merged, clean gate already passing at ' + head.slice(0, 12) + ' — skipped (C-38)'); phase('Build'); continue }
    const cg = await cleanGate(tag + ':w' + w, head, [...mergedSet()])
    if (cg.verdict === 'fail') {
      const last = mergeLog[mergeLog.length - 1]; log(tag + ' wave ' + w + ': clean-gate RED at ' + head.slice(0, 12) + (last ? ' — reverting the last merge ' + last.id + ' (' + String(last.merge_sha).slice(0, 12) + ')' : ' — nothing to revert'))
      if (last) {
        const rv = await checkedRevert(last.id, head, last.merge_sha, 'clean-gate red')
        mergeLog.pop()
        if (rv.ok) { head = rv.head; if (status.has(last.id)) status.set(last.id, { state: 'reverted', reason: 'clean-gate-red', next: 'review fix card', head_sha: head }); lastClean = { verdict: 'fail-reverted', head_sha: head, digest: null, wave: tag + ':w' + w } }   // C-10: not a pass — the review pre-check re-runs a clean gate
        else if (status.has(last.id)) status.set(last.id, { state: 'revert-failed', reason: 'revert:clean-gate-red', next: 'owner inspects ' + INTEG, head_sha: head })
      }
    }
    phase('Build')
  }
  markDependencyBlocked(cards)
  return head
}

// ---------------------------------------------------------------------------------------------
// satisfied() — the ONLY way the run says the tree is done (D-24, C-D); evidence stages use the same predicate
// ---------------------------------------------------------------------------------------------
const openBlocking = [], seen = new Set(), probesUsed = new Set(), ownerFindings = []
function treeIncomplete(allCards) {         // C-5: any card not merged and not a parked LEAF makes the tree incomplete; dependents of a parked card count
  const parked = allCards.filter(c => PARKED_RE.test(stateOf(c.id) || ''))
  const parkedCritical = parked.filter(p => allCards.some(c => c.depends_on.includes(p.id) && stateOf(c.id) !== 'merged')).map(p => p.id)
  const pending = allCards.filter(c => !status.has(c.id) || /^(not_attempted|blocked_on_owner)$/.test(stateOf(c.id))).map(c => c.id)
  return { parkedCritical, pending, reasons: parkedCritical.map(id => 'parked-with-dependents:' + id).concat(pending.map(id => stateOf(id) ? stateOf(id) + ':' + id : 'unscheduled:' + id)) }
}
function satisfied(head, allCards) {
  const inc = treeIncomplete(allCards)
  const ownerCritical = ownerFindings.filter(f => /^(critical|high)$/.test(f.severity)).length
  const ok = !HALT && !INTEG_DIRTY && lastClean.verdict === 'pass' && lastClean.head_sha === head && openBlocking.length === 0 && inc.reasons.length === 0 && ownerCritical === 0
  log('satisfied()=' + ok + ' clean=' + lastClean.verdict + '@' + String(lastClean.head_sha).slice(0, 12) + ' openBlocking=' + openBlocking.length + ' incomplete=' + inc.reasons.length + ' ownerCritical=' + ownerCritical + (HALT ? ' HALT=' + HALT : ''))
  return ok
}
const toFixCard = (f, round, i) => { const id = 'platform-00-rf' + round + '-' + String(i + 1).padStart(2, '0') + '-' + f.id.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 24); return { id, path: 'plan/fixes/' + id + '.json', step: 1, depends_on: [], files_allowed: f.files_allowed || [f.file], tests_allowed: [], new_modules: [], required_files: [], deps_allowed: [], xfail_allowed: [], expected_green_tests: [], tests_removed_expected: 0, est_lines: 120, est_minutes: 20,
  dod: [{ id: 'D1', command: f.reproduction.command, expect: 'exit 0 once fixed (the reproduction exits non-zero on the defect)', verification_level: localLevel(f.verification_level) ? f.verification_level : 'local-stub' }], size: 'S', risk: f.kind === 'security' || f.kind === 'secrets' ? 'security' : 'none', protected_touch: false, bootstrap: false, decision_ids: [], finding_ids: [{ id: f.id, corrected_text: cap(f.corrected_claim || f.title, 600) }], apis_expected: [], owner_precondition: '', finding: f } }

// ---------------------------------------------------------------------------------------------
// Whole-tree review loop (§6.2)
// ---------------------------------------------------------------------------------------------
async function reviewLoop(head, allCards) {
  phase('Review')
  const LENSES = ['decision-fidelity+scope', 'correctness+tests-integrity', 'security+secrets']
  let round = 0, dry = 0, stop = null, vetoes = []
  if (A.smoke) { log('SMOKE: review loop skipped (C-33)'); return { head, stop: 'smoke-skip-review', round } }
  const inc = treeIncomplete(allCards)
  if (inc.reasons.length) { log('review loop NOT started: tree incomplete (' + inc.reasons.slice(0, 6).join(', ') + ') — no lenses spent (C-5)'); return { head, stop: 'tree-incomplete', round } }
  if (!HALT && !INTEG_DIRTY && !(lastClean.verdict === 'pass' && lastClean.head_sha === head)) {   // C-10: never review a tree without a passing clean gate at its head
    log('review pre-check: last clean gate is ' + lastClean.verdict + '@' + String(lastClean.head_sha).slice(0, 12) + ' vs head ' + head.slice(0, 12) + ' — re-running one clean gate before any lens')
    if (!budgetOk('review pre-check clean gate')) return { head, stop: HALT ? 'halt:' + HALT : 'budget-or-agent-cap', round }
    const cg = await cleanGate('review-pre', head, [...mergedSet()])
    if (cg.verdict !== 'pass') { log('review loop NOT started: clean gate ' + cg.verdict + (cg.why ? ' (' + cg.why + ')' : '')); return { head, stop: 'clean-gate-' + (cg.verdict === 'fail' ? 'red' : 'unavailable'), round } }
  }
  while (true) {
    if (satisfied(head, allCards) && vetoes.length === 0 && round > 0) { stop = 'satisfied'; break }
    if (HALT) { stop = 'halt:' + HALT; break }
    if (INTEG_DIRTY) { stop = 'integration-dirty'; break }
    if (round >= MAX_ROUNDS) { stop = 'max-rounds(' + MAX_ROUNDS + ')'; break }
    if (dry >= 2) { stop = 'dry(2)'; break }
    if (!budgetOk('review round ' + (round + 1)) || !agentsOk('review round ' + (round + 1), 3 + 4)) { stop = 'budget-or-agent-cap'; break }
    round++
    const seenKeys = [...seen].sort()
    const reviews = await parallel(LENSES.map(lens => () => run('verifier', 'review', lens + ':r' + round, P.review(lens, head, seenKeys, round), { phase: 'Review', schema: VERDICT, effort: 'high' }, LENSES.length)))   // barrier: dedup needs all
    const lensDrops = reviews.filter(r => !r || r.status === 'null').length
    reviews.filter(r => r && r.status !== 'null').forEach(r => (r.probes_used || []).forEach(p => probesUsed.add(cap(p, 200))))
    const found = reviews.filter(r => r && r.status !== 'null').flatMap(r => r.findings || []).concat(journeyChecks.splice(0), syntheticFindings.splice(0)).filter(f => f.reproduction && f.verification_level !== 'unverified').sort(byId)
    raiseLevels(found, f => f.title + ' ' + (f.reproduction || {}).command)
    const fresh = found.filter(f => !seen.has(fkey(f))); fresh.forEach(f => seen.add(fkey(f)))
    log('review r' + round + ': ' + found.length + ' found, ' + fresh.length + ' fresh, ' + lensDrops + ' lens(es) dropped')
    const judged = fresh.length ? await pipeline(fresh, f => run('verifier', 'refute', f.id + ':r' + round, P.refute(f, head), { phase: 'Review', schema: VERDICT, effort: 'medium' }, fresh.length).then(v => ({ f, v }))) : []
    const judgeDrops = judged.filter(j => !j).length; if (judgeDrops) log('review r' + round + ': ' + judgeDrops + ' refute chain(s) resolved null (counted, not queued)')   // J1 D5
    const confirmed = judged.filter(Boolean).filter(({ v }) => v.status !== 'null' && v.verdict === 'holds' && v.findings && v.findings[0] && v.findings[0].reproduction && v.findings[0].reproduction.exit_code !== 0).map(({ f, v }) => Object.assign({}, f, v.findings[0]))   // C-27: a reproduction that exits 0 proves nothing
    const shapeless = judged.filter(Boolean).filter(({ v }) => v.status !== 'null' && v.verdict === 'holds' && !(v.findings && v.findings[0] && v.findings[0].reproduction && v.findings[0].reproduction.exit_code !== 0)).length; if (shapeless) log('review r' + round + ': ' + shapeless + ' "holds" verdict(s) without a non-zero-exit reproduction ignored (C-27)')
    log('review r' + round + ': ' + confirmed.length + '/' + fresh.length + ' hold after refutation')
    const accepted = new Set(OA.accepted_findings || [])                                   // owner data: medium/low evidence findings the owner explicitly accepts (never critical/high)
    const ownerOnly = confirmed.filter(f => !localLevel(f.verification_level) && !(accepted.has(f.id) && /^(medium|low)$/.test(f.severity)))
    confirmed.filter(f => !localLevel(f.verification_level) && accepted.has(f.id) && /^(medium|low)$/.test(f.severity)).forEach(f => { log('finding ' + f.id + ' (' + f.severity + ') accepted by owner_approvals.accepted_findings — recorded, not blocking'); if (!status.has('finding:' + f.id)) status.set('finding:' + f.id, { state: 'deferred', reason: 'accepted-by-owner:' + f.id, next: 'none' }) })
    ownerOnly.forEach(f => { if (!status.has('finding:' + f.id)) { status.set('finding:' + f.id, { state: 'blocked_on_owner', field: A.stage === 'promote' ? 'production_evidence_dir' : 'staging_evidence_dir', reason: 'finding ' + f.id + ' (' + f.severity + ', ' + f.kind + ') is ' + f.verification_level, next: A.stage === 'promote' ? 'rollback, then fix on staging' : 'fix on staging; re-run the CI evidence job; relaunch stage=' + A.stage, severity: f.severity }); ownerFindings.push({ id: f.id, severity: f.severity, kind: f.kind, title: f.title }) } })
    if ((A.stage === 'stage' || A.stage === 'promote') && ownerOnly.some(f => /^(critical|high)$/.test(f.severity))) { stop = 'blocked-on-owner:staging-evidence'; log('review r' + round + ': confirmed critical/high staging finding(s) ' + ownerOnly.filter(f => /^(critical|high)$/.test(f.severity)).map(f => f.id).join(',') + ' → stop; no promotion can be emitted (C-6)'); break }
    const fixable = confirmed.filter(f => localLevel(f.verification_level))
    const blocking = fixable.filter(f => f.severity === 'critical' || f.severity === 'high'); openBlocking.push(...blocking.map(f => f.id))
    const fixCards = [...fixable, ...vetoes].map((f, i) => toFixCard(f, round, i))
    if (fixCards.length) {
      const fw = await run('integrator', 'fixcards', 'r' + round, P.fixcards(fixCards, head, round), { phase: 'Review', schema: MERGE, effort: 'low' })   // C-3: first-class cards on plan/fixes, committed by the single writer
      const written = fw.status === 'written' && isSha(fw.head_sha) && fixCards.every(c => (fw.files_written || []).includes(cardPath(c)))
      if (!written) { log('review r' + round + ': fix cards NOT written (' + (fw.status || fw.reason) + ') — ' + fixCards.length + ' fix card(s) not attempted this round'); fixCards.forEach(c => status.set(c.id, { state: 'not_attempted', reason: 'fixcards-unavailable', next: 'relaunch stage=' + A.stage })) }
      else { head = fw.head_sha; head = await buildAndIntegrate(fixCards, head, 'fix-r' + round); fixCards.forEach(c => { if (stateOf(c.id) === 'merged') { const k = openBlocking.indexOf(c.finding_ids[0].id); if (k >= 0) openBlocking.splice(k, 1) } }) }
    }
    vetoes = []
    if (satisfied(head, allCards)) {
      const rows = [...status.entries()].sort().map(([id, s]) => ({ id, state: s.state, reason: s.reason || null }))
      const vj = await run('verifier', 'veto', 'r' + round, P.veto(head, rows, round === MAX_ROUNDS || dry === 1, [...probesUsed].sort()), { phase: 'Review', schema: VERDICT, effort: 'xhigh' })
      if (vj.status === 'null') { stop = 'veto-unavailable'; log('veto r' + round + ': judge dropped → NOT satisfied (fail closed)'); break }   // A1 §13.7 fail-closed judging
      vetoes = (vj.findings || []).filter(f => f.reproduction && f.reproduction.exit_code !== 0 && f.verification_level !== 'unverified'); const notes = (vj.findings || []).length - vetoes.length
      ;(vj.probes_used || []).forEach(p => probesUsed.add(cap(p, 200)))
      log('veto r' + round + ': ' + vetoes.length + ' veto(es) with a non-zero-exit reproduction, ' + notes + ' note(s) without')
    }
    dry = (fresh.length === 0 && vetoes.length === 0) ? dry + 1 : 0
  }
  log('review loop ended: ' + stop + ' after ' + round + ' round(s); seen=' + seen.size + ' openBlocking=' + openBlocking.length)
  return { head, stop, round }
}
const syntheticFindings = []

// ---------------------------------------------------------------------------------------------
// Checkpoint object (computed by the script; the synthesizer only renders it) — §2.2; every row carries reason + next (C-22)
// ---------------------------------------------------------------------------------------------
function checkpoint(stage, head, stop, planDefects) {
  const rows = [...status.entries()].filter(([id]) => !id.startsWith('finding:') && id !== 'evidence').sort().map(([task_id, s]) => ({ task_id, state: s.state === 'merged' ? 'merged+gate-green' : s.state, reason: s.reason || s.state, next: s.next || 'none', head_sha: s.head_sha || 'none', dod_done: (s.dod || []).filter(d => d.exit_code === 0).length, dod_total: (s.dod || []).length, dod_deferred: (s.deferred || []).length }))
  const actions = [], blocked_on_owner = [], deferred = []
  const act = (id, kind, why, steps, blast, rollback, cost) => actions.push({ id, kind, why, exact_steps: steps, blast_radius: blast, rollback, cost_estimate: cost, evidence_paths: [R + '/.gate/last_run.json', STATUS_JSON] })
  for (const [id, s] of status) if (s.state === 'blocked_on_owner') blocked_on_owner.push({ task_id: id, field: s.field, why: s.reason, next: s.next || null, severity: s.severity || null })
  for (const [id, s] of status) if (s.state === 'merged' && (s.deferred || []).length) deferred.push({ task_id: id, dod_ids: s.deferred, why: 'staging/owner-required DoD lines; proven by the CI evidence job in R2' })   // informational, not a blocker of R1's ready
  const api_unresolvable = [...status.entries()].filter(([, s]) => (s.api_unresolvable || []).length).map(([id, s]) => ({ task_id: id, symbols: s.api_unresolvable }))
  const retry_parked_suggested = rows.filter(r => PARKED_RE.test(r.state) && RETRYABLE_RE.test(r.reason)).map(r => r.task_id)
  const complete = stage === 'plan' ? stop === 'plan-verified' : rows.length > 0 && rows.every(r => /^(merged\+gate-green|parked|reverted)$/.test(r.state))   // a card blocked on the owner, not attempted or revert-failed ⇒ the stage is not done
  const ownerCritical = ownerFindings.filter(f => /^(critical|high)$/.test(f.severity))
  let ready = !HALT && !INTEG_DIRTY && (stage === 'plan' ? stop === 'plan-verified' : stop === 'satisfied') && complete && blocked_on_owner.length === 0 && ownerCritical.length === 0   // C-6
  if (stage === 'plan') {
    if (stop === 'plan-verified') act('C0-1', 'approve-plan', 'F-9: the owner approves plan/decisions.json (incl. the five against-recommendation rows and the clarifications) and plan/index.json before any code is written', ['read ' + R + '/plan/decisions.json and plan/index.json at ' + (A.plan_sha || '<plan_sha from the CARD_INDEX>'), 'launch stage=build with plan_sha=<that sha>'], 'none', 'none', '0')
    else act('C0-0', 'repair-plan', 'the plan was rejected by the script/plan verifier (' + (planDefects || []).length + ' defect(s) listed in plan_defects); it must not be approved or built', ['read plan_defects and plan_findings in this checkpoint', 'relaunch stage=plan with args.plan_defects = plan_defects (the planner runs in REPAIR MODE on the same branch)'], 'none', 'none', '0')   // C-19
    act('C0-2', 'record-fixture-1', 'lens-4 biggest risk: ONE metered streamed router call (tool + thinking on) decides where the parser lives; card platform-04-streamparser is blocked_on_owner until owner_approvals.fixture1_path is set (the thin slice 03b must exist first — expect this stop after R1\'s first invocation)', ['after cards 01-03b merge: python tools/record_fixture.py --i-accept-cost 0.10 --out tests/fixtures/recorded/hosted-1.json', 'pass owner_approvals.fixture1_path'], 'cents', 'none', '< $0.10')
    act('C0-3', 'record-boundary-fixture', 'G-19/F-17: the persona absence test needs owner-generated shingle hashes of the excluded clause (the workflow never sees the clause); card product-13b is blocked until owner_approvals.persona_boundary_fixture_path (+ _sha256) is set', ['after card 01 merges: python tools/make_boundary_fixture.py --clause-file <owner-only path> --out <owner-only path>/persona_boundary.json (off-workflow)', 'pass owner_approvals.persona_boundary_fixture_path and persona_boundary_fixture_sha256 (sha256sum of that file)'], 'none', 'none', '0')
    act('C0-4', 'decide-worker-checkpoint', 'M-2 + inference-perf-2/-5/-7 CORRECTED: the resident checkpoint must carry model.visual.* (VLM class kept for G-16); evidence/catalog records has_visual_tensors per candidate; if neither candidate has them a VLM-class export HF Job precedes staging', ['read ' + GRILL + '/evidence/catalog/*.json has_visual_tensors', 'set owner_approvals.worker_checkpoint_decision = {candidate, needs_export: true|false}'], 'none (decision only)', 'none', '0')
  }
  if (stage === 'build') {
    if (!OA.github_repo_url) act('C1-1', 'create-github-repo', 'G-1a: GitHub is the SSOT, CI the only production writer', ['gh repo create <owner>/<name> --private', 'git -C ' + R + ' remote add origin <url>', 'git -C ' + R + ' push -u origin ' + INTEG + ' ' + PLAN_BRANCH, 'post-check: gh repo list --json name shows exactly one new repo'], 'new private repo', 'delete the repo (irreversible) or leave it', '0')
    if (!(OA.staging_space_ids || []).length) act('C1-2', 'create-staging-spaces', 'G-27/M-2: CPU front + ZeroGPU worker staging Spaces (private)', ['hf repos duplicate <prod> <ns>/<name>-staging --type space --private --exist-ok', 'same for the worker Space (ZeroGPU large)', 'post-check: namespace listing shows exactly two new private Spaces'], 'two private Spaces', 'delete Spaces', 'PRO quota only')
    act('C1-3', 'set-staging-secrets', 'G-15/G-24 clarification (owner must approve): the UI/API Space holds ONE fine-grained token scoped to inference-provider calls + read access to the private worker Space; if HF cannot combine those scopes, a second read-only token for the worker is the only alternative — record owner_approvals.token_topology = one-token|two-tokens', ['create the fine-grained token in the Hub UI (never in chat)', 'set it as the staging secret', 'pass owner_approvals.token_topology'], 'staging only', 'revoke token', '0')
    if (!OA.fixture1_path) act('C1-4', 'record-fixture-1', 'card platform-04-streamparser and every card downstream of it stay blocked until fixture #1 exists', ['python tools/record_fixture.py --i-accept-cost 0.10 --out tests/fixtures/recorded/hosted-1.json', 'pass owner_approvals.fixture1_path'], 'cents', 'none', '< $0.10')
    if (!OA.persona_boundary_fixture_path || !OA.persona_boundary_fixture_sha256) act('C1-5', 'record-boundary-fixture', 'card product-13b-personas-readme stays blocked until the shingle-hash fixture and its sha256 exist', ['see C0-3'], 'none', 'none', '0')
    if (!OA.worker_checkpoint_decision) act('C1-6', 'decide-worker-checkpoint', 'card platform-08c-worker-checkpoint stays blocked until the resident checkpoint (with visual tensors) is decided', ['see C0-4'], 'none', 'none', '0')
  }
  if (stage === 'stage') {
    if (OA.worker_checkpoint_decision && OA.worker_checkpoint_decision.needs_export) act('C2-1', 'run-hf-job-quantize', 'inference-perf-2 CORRECTED: quantise/export offline with the VLM class (never inside a lease); keep the bf16 mount until one boot on the exported checkpoint is observed', ['hf jobs run … tools/export_checkpoint.py --class AutoModelForImageTextToText --budget <usd>'], 'paid HF Job', 'delete the exported repo', OA.hf_job_budget_usd ? '<= $' + OA.hf_job_budget_usd : 'owner sets hf_job_budget_usd')
    act('C2-2', 'run-harness', 'M-3: admission only after the 12-prompt harness; release 1 needs at least one entry with admission: passed (pending entries are hidden from the selector and /v1/models)', ['python tools/harness.py --backend hosted --i-accept-cost --budget ' + (OA.hosted_call_budget_usd || '<usd>') + ' on staging', 'config PR flips admission for the measured entries'], 'provider spend', 'none', OA.hosted_call_budget_usd ? '<= $' + OA.hosted_call_budget_usd : 'owner sets hosted_call_budget_usd')
    const headOk = OA.production_space_head === A.base_sha || !!OA.adopted_delta_sha
    if (!headOk) { ready = false; blocked_on_owner.push({ task_id: 'promotion', field: 'production_space_head', why: 'F-38: read the production Space HEAD (read-only Hub read) and record it; it must equal base ' + A.base_sha.slice(0, 12) + ' or the delta must be adopted explicitly (adopted_delta_sha)', next: 'record the field; relaunch stage=stage', severity: null }) }
    if (ready && headOk) act('C2-3', 'promote-production', 'G-2/M-5: the single production promotion from staging', ['trigger the production environment job (required reviewer = owner)', 'watch /healthz git_sha == pushed sha; canary ×3; keep the rollback command at hand'], 'production', 'tools/promote.py --to <last_good_sha>', '0')
  }
  if (stage === 'promote' && ownerCritical.length) act('C3-1', 'rollback', 'post-promotion evidence contradicts EXPECTED.json: confirmed critical/high finding(s) ' + ownerCritical.map(f => f.id).join(','), ['tools/promote.py --to <last_good_sha>', 'then fix on staging and relaunch stage=stage'], 'production', 'none', '0')   // C-6: rollback only on confirmed evidence, never on an unavailable gate
  const nextStage = stage === 'plan' ? (stop === 'plan-verified' ? 'build' : 'plan') : stage === 'build' ? (ready ? 'stage' : 'build') : stage === 'stage' ? (ready ? 'promote' : 'stage') : 'done'   // C-9: never advances after dry/halt/budget/incomplete
  return { stage, nonce: A.run_nonce, status: (HALT || INTEG_DIRTY || /^FAILED:/.test(String(stop))) ? 'failed' : ready ? 'ready' : 'blocked', halt: HALT, head_sha: head, integration_branch: INTEG, actions, blocked_on_owner, deferred, parked: rows.filter(r => PARKED_RE.test(r.state)).map(r => ({ task_id: r.task_id, state: r.state, reason: r.reason, next: r.next })), rows, api_unresolvable, stop_reason: stop, agents: agentCount, replay_risk: REPLAY_RISK, last_clean_gate: { verdict: lastClean.verdict, head_sha: lastClean.head_sha, digest: lastClean.digest, why: lastClean.why || null },
    next_args: { stage: nextStage, plan_sha: A.plan_sha || null, integration_sha_at_launch: head, resume_mode: REPLAY_RISK ? 'git' : A.resume_mode, prior_status_path: STATUS_JSON, last_clean_gate: { head_sha: lastClean.verdict === 'pass' ? lastClean.head_sha : null, digest: lastClean.verdict === 'pass' ? lastClean.digest : null }, retry_parked_suggested, plan_defects: stage === 'plan' && stop !== 'plan-verified' ? (planDefects || []) : [] } }
}

// ---------------------------------------------------------------------------------------------
// Main: one run per args.stage
// ---------------------------------------------------------------------------------------------
let head = A.integration_sha_at_launch || A.base_sha, stop = 'not-run', allCards = [], planDefects = []
try {
  phase('Setup')
  const setup = await run('integrator', 'setup', A.run_nonce, P.setup(), { phase: 'Setup', schema: SETUP, effort: 'medium' })
  if (setup.status === 'null' || setup.status === 'FAILED' || !setup.base_sha_ok) throw new Error('setup failed: ' + cap(J(setup), 600))
  if (setup.gate_sha256 !== A.gate_sha256 || setup.baseline_sha256 !== A.baseline_sha256) throw new Error('gate/baseline pin mismatch: the tools dir does not hold the bytes args pin (CG1)')
  if (Math.min(16, setup.nproc - 2) !== CAP) throw new Error('cap-mismatch: nproc ' + setup.nproc + ' → cap ' + Math.min(16, setup.nproc - 2) + ' but args.cap=' + CAP + ' (stale args after a resize?)')
  if (!setup.red_proof.broken_red) throw new Error('gate red-proof failed: the gate is not RED on the broken base (D-14)')
  if ((setup.remotes || []).length && !OA.github_repo_url) throw new Error('remote present without approval: ' + setup.remotes.join(' | ') + ' (F-35 post-check)')
  if (setup.toolchain_status_sha256 && setup.toolchain_status_sha256 !== A.toolchain_status_sha256) throw new Error('toolchain-mutated at setup (status excluding docs/grills differs from P0) — F-1')
  if (A.stage !== 'plan') {
    if (!setup.plan_merged) throw new Error('plan/' + A.run_nonce + '@' + A.plan_sha.slice(0, 12) + ' is not merged into ' + INTEG)
    if (!isSha(setup.integration_head_live)) throw new Error('integration head unreadable')
    if (A.integration_sha_at_launch && setup.integration_head_live !== A.integration_sha_at_launch) throw new Error('stale-launch-args: live ' + INTEG + ' is ' + setup.integration_head_live.slice(0, 12) + ' but args say ' + A.integration_sha_at_launch.slice(0, 12) + ' — recompute args and launch fresh (F-43 as a script invariant)')
    head = setup.integration_head_live
    const liveMerged = new Set(setup.merged_on_integration || [])
    liveMerged.forEach(id => status.set(id, { state: 'merged', reason: 'merged (git)', next: 'none', head_sha: 'on-' + INTEG, dod: [], deferred: [] }))   // git is the truth for "merged"
    const retryParked = new Set(A.retry_parked || []); let autoRetry = 0
    for (const row of setup.prior_rows || []) {      // CG7 + C-8: prior rows add detail only where git agrees; parks persist unless retryable or named in retry_parked
      if (row.state === 'merged+gate-green' && liveMerged.has(row.task_id)) status.set(row.task_id, { state: 'merged', reason: 'merged (git + prior)', next: 'none', head_sha: row.head_sha, dod: [], deferred: [] })
      else if (PARKED_RE.test(row.state) && !liveMerged.has(row.task_id)) {
        if (retryParked.has(row.task_id)) log('resume: ' + row.task_id + ' re-driven (args.retry_parked)')
        else if (RETRYABLE_RE.test(row.reason || '')) { autoRetry++; log('resume: ' + row.task_id + ' was ' + row.state + ' for a retryable reason (' + row.reason + ') — re-driven automatically') }
        else status.set(row.task_id, { state: 'parked', reason: 'prior:' + (row.reason || row.state), next: 'retry_parked or a review fix card', head_sha: row.head_sha })
      }   // not_attempted / blocked_on_owner / dropped_null prior rows are never adopted: they are re-evaluated live
    }
    ;(setup.seen_keys || []).forEach(k => seen.add(k))
    if (A.last_clean_gate && A.last_clean_gate.head_sha === head && isHex64(A.last_clean_gate.digest)) lastClean = { verdict: 'pass', head_sha: head, digest: A.last_clean_gate.digest, wave: 'prior' }
    else lastClean = { verdict: 'gate-unavailable', head_sha: null, digest: null, why: 'no prior pass at this head' }
    log('resume state: ' + status.size + ' prior rows adopted (' + liveMerged.size + ' merged per git, ' + autoRetry + ' auto-retried), seen=' + seen.size + ', lastClean=' + lastClean.verdict)
  }
  log('setup ok: venv=' + setup.venv_python + ' nproc=' + setup.nproc + ' baseline_collected=' + setup.baseline_collected + ' red_proof=' + J(setup.red_proof))

  if (A.stage === 'plan') {
    phase('Plan')
    const unverified = [...A.unverified_finding_ids].sort()
    const ground = await parallel([
      () => run('planner', 'apiledger', A.run_nonce, P.apiLedger(), { phase: 'Plan', schema: VERDICT, effort: 'medium' }, 2 + unverified.length),
      () => run('verifier', 'catalog', A.run_nonce, P.catalog(), { phase: 'Plan', schema: VERDICT, effort: 'low' }, 2 + unverified.length),
      () => pipeline(unverified, fid => run('verifier', 'preverify', fid, P.preverify(fid), { phase: 'Plan', schema: VERDICT, effort: 'medium' }, 2 + unverified.length).then(v => ({ fid, v }))),
    ])
    const [apiLedger, catalog, pre] = ground
    if (!apiLedger || apiLedger.status === 'null' || apiLedger.verdict !== 'pass') throw new Error('api-ledger not written (' + (apiLedger && apiLedger.reason) + ')')
    const preverified = (pre || []).filter(Boolean).map(({ fid, v }) => ({ id: fid, verdict: v.status === 'null' ? 'unverified' : (v.verdict === 'holds' ? 'confirmed' : v.verdict === 'refuted' ? 'refuted' : 'unverified'), corrected_claim: cap(((v.findings || [])[0] || {}).corrected_claim || '', 600), level: ((v.findings || [])[0] || {}).verification_level || 'unverified' })).sort(byId)
    log('grounding: api-ledger ' + apiLedger.verdict + '; catalog ' + (catalog ? catalog.verdict : 'null') + ' (' + ((catalog && catalog.findings) || []).filter(f => /unresolved/i.test(f.title)).length + ' unresolved); pre-verified ' + preverified.map(p => p.id + '=' + p.verdict).join(','))
    const idx = await run('planner', 'plan', A.run_nonce + (A.plan_defects && A.plan_defects.length ? ':repair' : ''), P.plan(preverified, A.plan_defects || []), { phase: 'Plan', schema: CARD_INDEX, effort: 'high' })
    if (idx.status !== 'SUCCESS' || !isSha(idx.plan_sha)) throw new Error('planner failed')
    planDefects = checkPlan(idx, preverified)
    const chk = await run('verifier', 'plan', idx.plan_sha, P.planCheck(idx), { phase: 'Plan', schema: VERDICT, effort: 'medium' })
    if (chk.status === 'null') planDefects.push('plan verifier unavailable (' + chk.reason + ') — a plan is never approved unverified')
    else if (chk.verdict !== 'pass') planDefects.push('plan verifier: ' + (chk.findings || []).length + ' finding(s)')
    stop = planDefects.length ? 'plan-needs-repair' : 'plan-verified'
    log('plan: ' + idx.cards.length + ' cards; ' + stop + '; defects: ' + (planDefects.join('; ') || 'none') + '; plan findings: ' + ((chk.findings || []).length))
    A.plan_sha = idx.plan_sha
    const cp = checkpoint('plan', A.base_sha, stop, planDefects); cp.plan_sha = idx.plan_sha; cp.plan_defects = planDefects; cp.plan_findings = chk.findings || []; cp.preverified = preverified
    phase('Synthesize'); await run('synthesizer', 'synth', A.run_nonce, P.synth([], cp, stop, [], []), { phase: 'Synthesize', schema: REPORT, effort: 'low' })
    return cp
  }

  phase('Plan')
  const idx = await run('verifier', 'index', 'index@' + A.plan_sha, P.index(), { phase: 'Plan', schema: CARD_INDEX, effort: 'low' })
  if (idx.status !== 'SUCCESS') throw new Error('plan index unreadable at ' + A.plan_sha)
  planDefects = checkPlan(idx, idx.preverified || [])
  if (planDefects.length) throw new Error('plan-needs-repair: ' + planDefects.join('; ') + ' — relaunch stage=plan with args.plan_defects (C-19)')
  allCards = A.smoke ? topoOrder(idx.cards).slice(0, 1) : idx.cards
  allCards.forEach(c => CARD_BY_ID.set(c.id, c))
  if (A.stage === 'build') {
    phase('Build'); head = await buildAndIntegrate(allCards, head, 'plan')
    const rl = await reviewLoop(head, allCards); head = rl.head; stop = rl.stop
  }
  if (A.stage === 'stage' || A.stage === 'promote') {
    const dir = A.stage === 'stage' ? OA.staging_evidence_dir : OA.production_evidence_dir
    if (!dir) { stop = 'blocked:evidence-dir-missing'; status.set('evidence', { state: 'blocked_on_owner', field: A.stage === 'stage' ? 'staging_evidence_dir' : 'production_evidence_dir', reason: 'no evidence directory', next: 'run the CI evidence job; pass the directory; relaunch' }) } else {
      phase('Review')
      const ev = await run('verifier', 'evidence', A.stage + ':' + A.run_nonce, P.evidence(dir, head), { phase: 'Review', schema: VERDICT, effort: 'medium' })
      if (ev.status === 'null') { stop = 'evidence-unavailable' } else {
        raiseLevels(ev.findings, f => f.title + ' ' + (f.reproduction || {}).command)
        syntheticFindings.push(...(ev.findings || []).filter(f => f.reproduction))
        const rl = await reviewLoop(head, allCards); head = rl.head; stop = rl.stop
      }
    }
  }
} catch (e) { stop = 'FAILED:' + String(e && e.message); log(stop) }

phase('Synthesize')                                                                 // always runs, also after every HALT (F-45, C-7)
const cp = checkpoint(A.stage, head, stop, planDefects)
try {
  const seenKeys = [...seen].sort(), ledgerSummary = ledger.map(l => ({ role: l.role, mode: l.mode, id: l.id, attempt: l.attempt, status: l.status })).sort((x, y) => (ledgerKey(x) < ledgerKey(y) ? -1 : 1))
  let s = await run('synthesizer', 'synth', A.run_nonce, P.synth(cp.rows, cp, stop, seenKeys, ledgerSummary), { phase: 'Synthesize', schema: REPORT, effort: 'low' })
  const same = r => r && r.status === 'SUCCESS' && J(r.rows.map(x => [x.task_id, x.state, x.reason]).sort()) === J(cp.rows.map(x => [x.task_id, x.state, x.reason]).sort())
  if (s.status === 'SUCCESS' && !same(s)) { log('SYNTH ROWS DIFFER from the ledger — rewriting the on-disk rows (J1 G13)'); s = await run('synthesizer', 'synthfix', A.run_nonce, P.synthFix(s.report_path, cp.rows), { phase: 'Synthesize', schema: REPORT, effort: 'low' }) }
  if (s.status === 'SUCCESS') { cp.report_path = s.report_path; cp.status_json_path = s.status_json_path; cp.owner_actions = s.owner_actions; cp.rows_consistent = same(s) }
  else { cp.rows_consistent = false; cp.synth_status = s.reason || s.status }
} catch (e) { log('synthesizer threw: ' + String(e && e.message)) }
log('RUN END stage=' + A.stage + ' stop=' + stop + ' head=' + String(head).slice(0, 12) + ' agents=' + agentCount + ' ledger=' + ledger.length + ' dropped=' + ledger.filter(l => /null|timeout|threw/.test(l.status)).length + (HALT ? ' HALT=' + HALT : ''))
return cp
