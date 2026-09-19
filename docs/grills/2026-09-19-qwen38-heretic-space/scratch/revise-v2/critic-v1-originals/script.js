export const meta = {
  name: 'space-rebuild-v1',
  description: 'Implementation workflow for the qwen38 heretic Space (design-v1 = A3 base + judge grafts): plan (pre-verify findings → api ledger → catalog provenance → planner → plan verifier) → per card (author → confirm-RED → build → verify with digest equality, mutants, revert-proof → bounded fix) in barrier waves → serial integrate + clean gate with self-test + journeys → review/refute/veto loop → synthesize; outward actions only as owner checkpoints between runs',
  phases: [
    { title: 'Setup', detail: 'idempotent + the one live state probe per invocation: durable clone at base_sha, 3.12 venv from pinned wheels, pinned gate.sh + baseline, red-proof, plan merged into integration, live heads, remotes, prior rows' },
    { title: 'Plan', detail: 'pre-verify UNVERIFIED findings (executed reproduction) ‖ api-ledger with known_bad ‖ catalog provenance saved raw → planner writes decisions.json (against_recommendation, dq_line) + cards + index → JS checks → verifier mode:plan refutes' },
    { title: 'Build', detail: 'per card: author → red → builder → verifier (gate digest must equal the builder\'s; mutants all killed; revert-proof red; every local DoD id exit 0 on both sides) → bounded fix; barrier waves by rank with disjoint write sets, ≤ cap' },
    { title: 'Integrate', detail: 'serial single-writer merges in rank order, gate on the merged tree, conflict call, checked revert, bundle, clean-gate --self-test --journeys per wave, journeys author when a seam card merged' },
    { title: 'Review', detail: '3 lenses → dedup vs persisted seen → refute with reproduction → fix cards → satisfied() predicate → veto-only judge (fail closed on drop; probesUsed to the inversion mandate); MAX_ROUNDS/dry/budget/agent caps' },
    { title: 'Synthesize', detail: 'script-computed row table rendered; rows re-written on disk by a probe when they differ; checkpoint object returned by the script' },
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
for (const k of ['build_repo', 'tools_dir', 'libsrc', 'venv']) if (String(A[k]).startsWith('/tmp/') || String(A[k]).startsWith('/workspaces/agent-skills-toolchain')) throw new Error('args.' + k + ' must be durable and outside the toolchain repo (F-1, F-2)')
if (!['git', 'cache'].includes(A.resume_mode)) throw new Error('args.resume_mode must be git|cache (cache only after the smoke-run settling experiment, §10.1)')
if (!(A.wave_size >= 1 && A.wave_size <= A.cap)) throw new Error('args.wave_size must be 1..cap so a wave never enqueues more agents than the cap (CG: queue wait vs timers)')
const OA = A.owner_approvals || {}                                           // F-6: approvals are DATA
const R = A.build_repo, WT = R + '-wt', TOOLS = A.tools_dir, GRILL = A.grill_dir || '/home/codespace/grills/2026-09-19-qwen38-heretic-space'
const BUNDLES = GRILL + '/build-bundles/' + A.run_nonce, STATUS_JSON = BUNDLES + '/status.json'
const CAP = A.cap, WAVE = A.wave_size, MAX_ROUNDS = A.max_rounds || 3, MAX_BUILD = A.max_build || 3, MAX_AUTHOR = 2
const RESERVE = A.reserve_tokens || 120000, AGENT_SOFT_CAP = 800, MAX_AGENTS_RUN = A.max_agents_this_run, RESERVE_PER_CHAIN = 7
const INTEG = 'integration/' + A.run_nonce, PLAN_BRANCH = 'plan/' + A.run_nonce
const TIMEOUT = { author: 1500000, red: 600000, build: 3000000, fix: 2400000, verify: 1800000, merge: 1200000, conflict: 1800000, ff: 900000, revert: 900000, clean: 1500000, journeys: 1500000, review: 1800000, refute: 900000, veto: 1500000, plan: 2400000, setup: 1800000, synth: 900000, synthfix: 600000, preverify: 1200000, apiledger: 1500000, catalog: 900000, evidence: 900000, index: 600000 }
const tmo = (mode, enqueued) => (TIMEOUT[mode] || 1800000) * Math.max(1, Math.ceil((enqueued || 1) / CAP))   // CG: queue wait counts against the timer → size it by queue depth
const AGAINST = A.against_recommendation_ids                                 // ['G-1', 'G-3', 'G-2', 'M-5', 'G-15+G-24'] — the five decisions taken against the recommendation
const STAGING_RE = /\b(lease|quota|ZeroGPU|worker fork|Triton|fla|x-ip-token|MCP transport|Space rebuild|cold[- ]start|tok\/s|FP8|GPTQ|provider|requirements resolution|canary|rollback|OIDC|secret)\b/i
const RECEIPT_RE = /started in the background|Check \/codex:status|based on the digest|as a follow-up task/i
const SECRET_RE = /ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----/
// CG10: required-files manifest — once the named card is merged, every listed path must exist or the gate is RED (never silently skipped)
const REQUIRED_AFTER = {
  'platform-01-gate': ['tools/gate.sh', 'tests/protected.txt', 'tests/test_constants_pin.py', 'tests/test_import_contract.py', 'tests/fixtures/gate/false-claim.patch', 'ruff.toml', 'pytest.ini', '.gitattributes', '.editorconfig'],
  'platform-03a-types-fake': ['core/types.py', 'backends/base.py', 'backends/fake.py', 'tools/stubs/torch/__init__.py', 'tools/stubs/transformers/__init__.py', 'tools/stubs/spaces/__init__.py', 'tools/record_fixture.py', 'tests/conformance/conftest.py'],
  'platform-03b-thin-slice': ['api/app.py', 'backends/hosted.py', 'models.yaml', 'build_info.json'],
  'platform-04-streamparser': ['core/parsing.py', 'core/events.py'],
  'platform-05a-registry': ['core/tools/registry.py', 'tests/test_python_eval_surfaces.py'],
  'platform-05b-agent-session': ['core/agent.py', 'core/session.py'],
  'platform-08a-worker-pure': ['worker/encode.py', 'worker/lease.py', 'worker/penalty.py'],
  'platform-08b-worker-backend': ['worker/app.py', 'backends/worker.py'],
  'product-13a-catalog': ['tools/render_readme.py', 'core/catalog.py', 'tests/test_catalog_policy.py'],
  'product-13b-personas-readme': ['core/personas.py', 'tests/test_personas.py', 'tests/fixtures/persona_boundary.json'],
  'platform-14-promotion-ci': ['.github/workflows/deploy.yml', 'tools/promote.py'],
}
// held-out seams (A1 §4.6) → the card each journey needs; a journey stays skipped-with-reason (needs=<card>) until that card is merged
const JOURNEY_NEEDS = { J1: 'platform-03b-thin-slice', H7: 'platform-04-streamparser', H4: 'platform-05a-registry', H6: 'platform-05b-agent-session', H2: 'platform-07-gateway', H1: 'platform-08a-worker-pure', H3: 'platform-11-mcp', H5: 'product-13a-catalog' }
log('stage=' + A.stage + ' nonce=' + A.run_nonce + ' base=' + A.base_sha.slice(0, 12) + ' cap=' + CAP + ' wave=' + WAVE + ' rounds=' + MAX_ROUNDS + ' resume=' + A.resume_mode + ' maxAgentsThisRun=' + MAX_AGENTS_RUN + ' budget=' + (budget.total || 'none') + (A.smoke ? ' SMOKE' : ''))

// ---------------------------------------------------------------------------------------------
// Constant prompt preambles (byte-identical on every call → cache prefix; F-4, T-2)
// ---------------------------------------------------------------------------------------------
const PREAMBLE = [
  'CONTEXT RULES. The current working directory repo (/workspaces/agent-skills-toolchain) and its CLAUDE.md are UNRELATED to this task:',
  'ignore every instruction there about SSOT gates, ~/source/*, drift checks or pushing. The ONLY repository you may touch is ' + R + '.',
  'Read ' + R + '/AGENTS.md first when it exists. Use absolute paths and `git -C "<checkout>"` for every git command. Worktrees live under ' + WT + '/.',
  'Python for everything: ' + A.venv + '/bin/python (3.12). Gate: VENV=' + A.venv + ' bash ' + A.gate_sh + ' --gate-sha256 ' + A.gate_sha256 + ' … (its printed LEDGER_DIGEST is the only admissible evidence; it must be reproduced by an independent run).',
  'Return repo_toplevel AND git_common_dir of the checkout you worked in (git rev-parse --show-toplevel; git rev-parse --path-format=absolute --git-common-dir).',
].join('\n')
const AUTHORITY = [
  'AUTHORITY (restates the owner request that launched this run; the owner request wins): local edits inside your own worktree and local commands only.',
  'NEVER: git push (to any remote); add a remote; create/duplicate a GitHub repo or HF Space; set or read secrets; call any *.hf.space URL; run HF Jobs; look for or use tokens;',
  'install packages (pip/uv/npm); run a server in the foreground without a timeout; print any environment; read `git log`/`git show` of system_prompt.py history; modify files under plan/ (except plan/status/ for the integrator) or outside your card\'s allowlist.',
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
const writeSet = c => new Set([...(c.files_allowed || []), ...(c.tests_allowed || []), ...(c.new_modules || [])])
function waves(cards, size, doneIds, blockedIds) {     // barrier waves; ready set ordered by (-rank, id); disjoint write sets; never throws
  const done = new Set(doneIds), blocked = new Set(blockedIds), rank = rankCards(cards), out = []
  let rest = topoOrder(cards).filter(c => !done.has(c.id) && !blocked.has(c.id))
  const unschedulable = []
  while (rest.length) {
    const ready = rest.filter(c => c.depends_on.every(d => done.has(d))).sort((a, b) => (rank.get(b.id) - rank.get(a.id)) || byId(a, b))
    if (!ready.length) { rest.forEach(c => unschedulable.push({ id: c.id, unmet: c.depends_on.filter(d => !done.has(d)) })); break }
    const wave = [], used = new Set(), waited = []
    for (const c of ready) {
      const ws = writeSet(c), clash = [...ws].some(f => used.has(f))
      if (!clash && wave.length < size) { wave.push(c); ws.forEach(f => used.add(f)) } else waited.push(c.id)
    }
    if (waited.length) log('wave ' + (out.length + 1) + ': ' + waited.join(',') + ' wait (size or write-set overlap)')   // T-AP-11: never silent
    out.push(wave); wave.forEach(c => done.add(c.id)); rest = rest.filter(c => !done.has(c.id))
  }
  return { plan: out, unschedulable }
}
function raiseLevels(items, textOf) {                  // A2/A1 (F-37): keyword-forced verification level, in code, at return time
  let raised = 0
  for (const it of items || []) if (STAGING_RE.test(textOf(it)) && String(it.verification_level || '').startsWith('local')) { it.verification_level = 'staging-required'; raised++ }
  return raised
}
function validateCards(cards) {                        // throws at script start on a plan that cannot be built (A1 §13.1; D-1)
  const ids = new Set(cards.map(c => c.id)); if (ids.size !== cards.length) throw new Error('duplicate card ids')
  for (const c of cards) {
    if (!/^(platform|product)-[0-9]{2}[a-d]?-[a-z0-9-]+$/.test(c.id)) throw new Error(c.id + ': bad id')
    if (!(c.step >= 1 && c.step <= 14)) throw new Error(c.id + ': step out of range')
    if (!c.dod.length || c.dod.length > 8 || c.dod.some(d => !d.command || d.command.length < 3)) throw new Error(c.id + ': dod must have 1..8 runnable lines')
    if (c.dod.some(d => /(^|\s)(-k|-x|--deselect|--ignore|--lf)(\s|=)|\|\|\s*true/.test(d.command))) throw new Error(c.id + ': a dod command narrows or masks pytest')
    if (c.size === 'L') throw new Error(c.id + ': size L is not a card')
    if (c.protected_touch && c.id !== 'platform-01-gate') throw new Error(c.id + ': only platform-01-gate may touch protected paths')
    if (c.bootstrap && c.id !== 'platform-01-gate') throw new Error(c.id + ': only platform-01-gate may run the bootstrap profile')
    if (c.finding_ids.some(f => !f.corrected_text || f.corrected_text.length < 20)) throw new Error(c.id + ': every cited finding must carry its CORRECTED text (F-10)')
    if (c.risk === 'security' && !c.dod.some(d => /surface|operator|flag|unreachable/i.test(d.expect + ' ' + d.command))) throw new Error(c.id + ': a security card needs a surface/operator-flag DoD line (G-15 point 5)')
    raiseLevels(c.dod, d => d.command + ' ' + d.expect)
  }
  topoOrder(cards)
}
function assertCommon(r, what) {                       // F-1, F-5, F-35: script-level invariants on every return
  if (!r || h6IsDrop(r) || r.status === 'null') return r
  const top = r.repo_toplevel || '', cdir = r.git_common_dir || ''
  if (top && !(top === R || top.startsWith(WT + '/'))) { log('BLOCK ' + what + ': worked in ' + top); return { status: 'null', reason: 'wrong-repo' } }          // D1: prefix test — sibling worktrees pass
  if (cdir && cdir !== R + '/.git') { log('BLOCK ' + what + ': common dir ' + cdir); return { status: 'null', reason: 'wrong-store' } }
  if ((r.outward_actions_taken || []).length) { HALT = 'outward-action:' + what; log('HALT ' + HALT + ': ' + r.outward_actions_taken.join(',') + ' — no further agents; synthesizer still runs'); return { status: 'null', reason: 'outward-action' } }
  if ((r.installed_packages || []).length) { log('BLOCK ' + what + ': installed ' + r.installed_packages.join(',')); return { status: 'null', reason: 'installed-packages' } }
  if (RECEIPT_RE.test(r.notes || '') || RECEIPT_RE.test(r.strongest_disagreement || '')) { log('BLOCK ' + what + ': receipt-shaped return'); return { status: 'null', reason: 'receipt-shaped' } }
  return r
}

// ---------------------------------------------------------------------------------------------
// The single agent wrapper: ledger for every call, one narrower retry on null, typed results (F-41, F-42),
// early halt on budget exhaustion or an outward action (CG), secret redaction (CG3), sorted ledger keys
// ---------------------------------------------------------------------------------------------
const ledger = []; let agentCount = 0, HALT = null
function budgetOk(label) {
  if (HALT) { log('HALTED (' + HALT + ') before ' + label); return false }
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
    if (!budgetOk(label)) { ledger.push({ role, mode, id, attempt, status: 'budget' }); return { status: 'null', reason: HALT ? 'halt' : 'budget' } }
    agentCount++
    const p = attempt === 1 ? prompt : prompt + '\n' + NARROW + '\nattempt: 2'     // attempt suffix → cache miss by construction (F-43)
    const r = await withTimeout(() => agent(p, Object.assign({ label: label + (attempt === 2 ? ':retry' : '') }, opts)), ms, label)
    if (r && !h6IsDrop(r)) {
      redact(r, label)
      ledger.push({ role, mode, id, attempt, status: r.status || r.verdict || 'ok', sha: r.head_sha || r.sha || r.tests_head || null })
      return assertCommon(r, label)
    }
    const why = r ? r.__endReason : 'null', detail = r ? cap(r.detail, 200) : null
    ledger.push({ role, mode, id, attempt, status: why, detail })
    if (why === 'threw' && /budget|ceiling|spent/i.test(String(detail))) { HALT = 'budget-exhausted'; log('HALT budget-exhausted at ' + label + ' — no retries, loops wind down, synthesizer runs'); return { status: 'null', reason: 'budget' } }
    if (why === 'timeout') REPLAY_RISK = true            // CG: a timed-out call may still journal a result; cache resume would diverge → next_args.resume_mode = 'git'
    log('DROP ' + label + ' attempt ' + attempt + ': ' + why + (attempt === 1 ? ' — retrying narrower' : ' — parking'))
  }
  return { status: 'null', reason: 'agent-null' }
}
let REPLAY_RISK = false

// SCHEMAS: §9 pasted verbatim here (LEVELS, COMMON, COMMON_REQ, CMD, SETUP, CARD_INDEX, TESTS, BUILD, FINDING, VERDICT, MERGE, REPORT).

// ---------------------------------------------------------------------------------------------
// Prompt builders (pure functions of args + sorted results; the sha pins the cache)
// ---------------------------------------------------------------------------------------------
const testsBranch = id => 'tests/' + id + '-' + A.run_nonce
const taskBranch = id => 'task/' + id + '-' + A.run_nonce          // ONE helper for every merged branch — journeys use it too (J2 A3-1)
const cardRef = c => 'CARD: ' + R + '/plan/cards/' + c.id + '.json (plan sha ' + A.plan_sha + '; plan/ is merged into ' + INTEG + ' so the file is in every worktree). DECISIONS: plan/decisions.json. API LEDGER: plan/api-ledger.json. PRE-VERIFIED FINDINGS: plan/preverified.json.'
const PINS = ' --gate-sha256 ' + A.gate_sha256 + ' --baseline ' + A.baseline_path + ' --baseline-sha256 ' + A.baseline_sha256
const gateCmd = extra => 'VENV=' + A.venv + ' bash ' + A.gate_sh + PINS + ' ' + extra
const redriveLine = k => (k ? '\nredrive: ' + k : '')                 // D4: a stale re-drive is a different prompt → cache miss by construction
function mergedArgs(mergedIds) {                                     // --require / --xfail-allow / --tests-removed for gates on trees that contain merged cards
  const ids = [...mergedIds].sort()
  const req = [...new Set(ids.flatMap(id => REQUIRED_AFTER[id] || []))].sort()
  const cards = ids.map(id => CARD_BY_ID.get(id)).filter(Boolean)
  const xf = [...new Set(cards.flatMap(c => c.xfail_allowed || []))].sort(), removed = cards.reduce((n, c) => n + (c.tests_removed_expected || 0), 0)
  return (req.length ? ' --require ' + req.join(',') : '') + (xf.length ? ' --xfail-allow ' + xf.join(',') : '') + (removed ? ' --tests-removed ' + removed : '')
}
const CARD_BY_ID = new Map()
const P = {
  setup: () => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:setup (idempotent) + the live state probe of this invocation (launched_at ' + (A.resume_mode === 'git' ? A.launched_at : 'n/a') + '). Ensure and report:',
    '(1) ' + R + ' is a clone of the read-only snapshot ' + A.snapshot_dir + ' whose first commit is ' + A.base_sha + ' (create it if missing; never modify the snapshot; `chmod -R a-w` the snapshot and ' + A.libsrc + ');',
    '(2) venv ' + A.venv + ' from /usr/bin/python3.12 with ' + A.wheels_dir + '/*.whl + gradio-client==2.6.1 ruff pyflakes pytest pytest-socket pyyaml openai httpx (skip if present and `python -V` is 3.12.*); report nproc;',
    '(3) sha256sum of ' + A.gate_sh + ' and of ' + A.baseline_path + ' (report both; the script compares them to args); the baseline file holds {base_sha, baseline_collected, skipped_ids[]} from `pytest --collect-only -q` at ' + A.base_sha + ' — create it ONLY if absent;',
    '(4) BROKEN_SHA=' + A.base_sha + ' run ' + gateCmd('--self-test --profile bootstrap --base ' + A.base_sha) + ' in a detached worktree at ' + A.base_sha + ' and report red_proof {broken_red, false_claim_red, digest};',
    A.stage === 'plan' ? '(5) branch ' + PLAN_BRANCH + ' exists or is created at ' + A.base_sha + ';' : '(5) branch ' + INTEG + ' exists (create at ' + A.base_sha + ' if missing) and ' + PLAN_BRANCH + ' at ' + A.plan_sha + ' is merged into it (`git merge --no-ff ' + A.plan_sha + '` as its first commit if not yet; plan/** only); report plan_merged and integration_head_live (40-hex);',
    '(6) report branch_heads for every tests/*-' + A.run_nonce + ' and task/*-' + A.run_nonce + ' branch, merged_on_integration from `git ls-tree ' + INTEG + ' plan/status/` (ids whose json says merged), and `git remote -v` lines (expected: none);',
    '(7) if ' + (A.prior_status_path || 'no prior status file') + ' exists, return its rows as prior_rows and its seen_keys; else [] and [];',
    '(8) `git -C ' + R + ' worktree prune`; remove worktrees under ' + WT + ' whose branch is already merged into ' + INTEG + '; mkdir -p ' + BUNDLES + ';',
    '(9) sha256 of `git -C /workspaces/agent-skills-toolchain status --porcelain` must equal ' + A.toolchain_status_sha256 + ' — report base_sha_ok=false if any assertion fails. Never install into any other interpreter.'].join('\n'),
  preverify: fid => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:preverify (refute-first). Finding ' + fid + ' in ' + A.findings_path + ' is UNVERIFIED. Reproduce or refute it at ' + A.base_sha + ' in a detached worktree of ' + R + ' with a probe mechanically different from the finder\'s (the finder read source; you execute: render the chat template with jinja2, run the code path with a fake, diff the checkpoint index — whatever applies). Never print environment variables; never call any URL. Return verdict holds|refuted|unverified with the executed reproduction, corrected_claim, and verification_level; findings[0] carries the result.'].join('\n'),
  apiLedger: () => [PREAMBLE, AUTHORITY, 'ROLE: planner mode:api-ledger. From ' + A.libsrc + ' ONLY (gradio 6.26.0, spaces 0.51.3, transformers 5.16.1, huggingface_hub 1.32.0, gradio_client 2.6.1) write ' + R + '/plan/api-ledger.json on branch ' + PLAN_BRANCH + ': every symbol the design §4.2 cards need with module, symbol, kwargs, libsrc path:line (≥ 30 entries: gr.Blocks/ChatInterface/Chatbot/mount_gradio_app/api, spaces.GPU(size=,duration=), GenerationConfig fields incl. max_time and the ABSENCE of presence_penalty, continue_final_message bool|str, HfApi.restart_space/duplicate_repo/fetch_space_logs/wait_for_space, gradio_client.Client) plus known_bad[] as regexes with why and libsrc anchor: gr.Chatbot(type=…), gr.ChatInterface(type=…), @spaces.GPU(gpu_size=…), presence_penalty to generate, restart_space(revision=…), from gradio.client import, Path.read_text(newline=…), preexec_fn=, trust_remote_code=True, prefill_chunk_size with the VLM class, continue_final_message for thinking resumes. Commit; return the CARD_INDEX-shaped object with cards=[] is NOT accepted — return VERDICT with sha = the commit and checks[] listing the files written.'].join('\n'),
  catalog: () => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:catalog (read-only Hub reads via ToolSearch: hub_repo_details / hf_fs cat of model.safetensors.index.json and config.json). For each candidate in ' + J(A.catalog_candidates) + ' save the RAW response under ' + GRILL + '/evidence/catalog/<owner>__<name>.json with fetched_at, record revision (40-hex), inferenceProviderMapping, has_visual_tensors (any weight key starting with model.visual.), quant format; on any fetch failure after 3 tries record status unresolved for that entry — never a remembered value. Return VERDICT with findings[] one per candidate (kind omitted-obligation, verification_level local-mechanical, reproduction = the tool call you made and the saved path).'].join('\n'),
  plan: pre => [PREAMBLE, AUTHORITY, 'ROLE: planner mode:plan. Inputs: ' + A.decision_queue_path + ' (Resolved decisions ONLY — decided values, never recommendations; record the DQ line number of each), ' + A.lens4_path + ' (§B layout, §C duplication list, §D 14 steps, §E ship-but-flag, §F pins), ' + A.findings_path + ' (use ONLY the CORRECTED CLAIM / CORRECTED RECOMMENDATION lines), ' + A.redteam_path + ' §1-§3, plan/api-ledger.json, and these pre-verified findings (a REFUTED id must not become a card; an UNVERIFIED one may only be cited at verification_level unverified):', J(pre),
    'On branch ' + PLAN_BRANCH + ' write: plan/decisions.json (one row per G-/M- id and per clarification the design §4.0 lists: id, decided_value, against_recommendation, consequences[], dq_line; the ids ' + J(AGAINST) + ' are against_recommendation=true); plan/preverified.json (the list above); plan/cards/<id>.json for the design §4.2 split (22 cards, S/M only, files_allowed/tests_allowed/new_modules/deps_allowed/xfail_allowed (lens-4 §F known-bads only)/tests_removed_expected/est_lines/est_minutes, dod[] ≤ 8 runnable CPU commands with expect and verification_level, risk, protected_touch and bootstrap only on platform-01-gate, decision_ids, finding_ids with corrected_text, apis_expected, owner_precondition: fixture1_path on platform-04-streamparser, persona_boundary_fixture_path on product-13b-personas-readme, worker_checkpoint_decision on platform-08c-worker-checkpoint); plan/index.json; AGENTS.md (this preamble + gate usage). Locate code by symbol (`git grep -n "def <name>"`), never by line. Card platform-05a-registry quotes G-15 point (5) verbatim. Cards 08a/08b quote the token-level continuation (gpu-lease-3 CORRECTED + critic-4), the VLM-class precondition (inference-perf-2/-5/-7 CORRECTED), the find_spec probe (inference-perf-4 CORRECTED) and the presence_penalty decision. The persona card lists only the G-19 role names and forbids reading system_prompt.py history. Commit and return CARD_INDEX (decisions[] echoes the sheet rows).'].join('\n'),
  planCheck: idx => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:plan (refute-first). Read every card under ' + R + '/plan/cards at ' + idx.plan_sha + ', plan/decisions.json and plan/preverified.json. REFUTE: (a) any DoD command that is not runnable on CPU under the venv (run it — it may fail, it must not be unrunnable); (b) any card whose text contradicts a decided value or quotes an original recommendation instead of the CORRECTED line; (c) any decision row whose decided_value or dq_line does not match ' + A.decision_queue_path + '; (d) any confirmed finding id no card cites, any REFUTED id a card cites; (e) any staging/quota/lease claim at a local verification_level; (f) any xfail_allowed id that is not a lens-4 §F known-bad; (g) any lens-4 §C duplication item without a DoD line on some card. Return findings with reproduction (the command you ran) and verdict pass|fail.'].join('\n'),
  index: () => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:evidence. Read ' + R + '/plan/index.json and plan/decisions.json at ' + A.plan_sha + ' and return them as the `cards` and `decisions` arrays of CARD_INDEX (no changes); status FAILED if the sha or a file is missing.'].join('\n'),
  author: (c, base, k, rd) => [PREAMBLE, AUTHORITY, 'ROLE: author mode:tests for ' + c.id + ' (attempt ' + k + '). ' + cardRef(c), 'Base: ' + base + '. Create worktree ' + WT + '/tests-' + c.id + '-' + A.run_nonce + ' on NEW branch ' + testsBranch(c.id) + ' from the base (if the branch exists and its tests already exist, verify them and return status reused).',
    c.risk === 'persona' ? 'PERSONA BOUNDARY: create the worktree as a history-free clone instead: `git clone --depth 1 --single-branch --branch ' + INTEG + ' file://' + R + ' ' + WT + '/tests-' + c.id + '-' + A.run_nonce + '` at ' + base + ', commit there, then `git -C "' + R + '" fetch "' + WT + '/tests-' + c.id + '-' + A.run_nonce + '" HEAD:refs/heads/' + testsBranch(c.id) + '`. The absence test reads ONLY tests/fixtures/persona_boundary.json (hashed 6-word shingles the owner generated) and asserts no persona text shingle matches; it never contains or reads the excluded clause.' : '',
    'Write ONLY the tests that prove the card\'s DoD lines (files listed in tests_allowed, or new files under tests/); no implementation code; never modify tests/protected.txt unless the card is platform-01-gate; xfail/skip markers only for ids in the card\'s xfail_allowed. Commit "tests(' + c.id + '): …" with trailer "Card: ' + c.id + '". Run ' + gateCmd('--only-tests <your test paths> --card plan/cards/' + c.id + '.json --base ' + base) + ' and quote its confirm-red line and LEDGER_DIGEST; the tests MUST fail for the expected reason (assertion / NotImplemented, or ImportError only for modules in new_modules). Suggest up to 3 one-line mutants (file, find, replace) in files_allowed that your tests should catch. Remove your worktree (branch survives).' + redriveLine(rd)].join('\n'),
  red: (c, t, base, rd) => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:red for ' + c.id + '. ' + cardRef(c), 'Detached worktree ' + WT + '/red-' + c.id + '-' + A.run_nonce + ' at ' + t.tests_head + '. Run ' + gateCmd('--only-tests ' + t.test_paths.join(' ') + ' --card plan/cards/' + c.id + '.json --base ' + base) + ' yourself (return its LEDGER_DIGEST as gate_digest) and `pytest --collect-only -q` on the rest of the suite. verdict pass ONLY if every new test fails for the expected reason (rc 1 or 2; not SyntaxError/ImportError outside new_modules; not rc 5) and the author-tamper step is green. Remove the worktree.' + redriveLine(rd)].join('\n'),
  build: (c, t, base, k, fails, mergedIds, rd) => [PREAMBLE, AUTHORITY, 'ROLE: builder mode:' + (fails ? 'fix' : 'implement') + ' for ' + c.id + ' (build call ' + k + '/' + MAX_BUILD + '). ' + cardRef(c),
    'Branch ' + taskBranch(c.id) + (fails ? ' already exists: worktree ' + WT + '/task-' + c.id + '-' + A.run_nonce + '-fix' + k + ' on it' : ': create worktree ' + WT + '/task-' + c.id + '-' + A.run_nonce + ' on that NEW branch from ' + testsBranch(c.id) + ' (head ' + t.tests_head + '); if the branch already exists and is green on the card\'s DoD, report status reused') + '.',
    c.risk === 'persona' ? 'PERSONA BOUNDARY: use a history-free clone (`git clone --depth 1 --single-branch --branch ' + testsBranch(c.id) + ' file://' + R + ' <worktree>`) and `git -C "' + R + '" fetch <worktree> HEAD:refs/heads/' + taskBranch(c.id) + '` when done.' : '',
    'Make the card\'s tests pass by implementing exactly the card (files_allowed only; you may ADD tests under tests/unit/ but never modify or delete an existing test; never touch plan/). Every gradio/spaces/transformers/huggingface_hub call must cite plan/api-ledger.json (apis_used[].ledger_ref) — never memory. Commit per coherent step; each message has a "Claims:" block naming symbols/files that ARE in that diff, and trailer "Card: ' + c.id + '". Run every DoD command and ' + gateCmd('--card plan/cards/' + c.id + '.json --base ' + t.tests_head + ' --oracle ' + t.tests_head + (c.bootstrap ? ' --profile bootstrap' : '') + mergedArgs(mergedIds)) + ' (advisory; return its LEDGER_DIGEST as gate_digest and its profile). Return head_sha, dod[] with one row per card DoD id and exit codes, apis_used[]. Remove your worktree at the end.',
    fails ? 'FAILING EVIDENCE (from an independent verifier; fix the cause, never the test):\n' + J(fails) : '', redriveLine(rd)].join('\n'),
  verify: (c, t, b, k, mergedIds, rd) => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:verify for ' + c.id + ' (verify ' + k + '). ' + cardRef(c), 'Detached worktree ' + WT + '/verify-' + c.id + '-' + A.run_nonce + '-' + k + ' at ' + b.head_sha + '. Do NOT trust the builder: (1) run ' + gateCmd('--card plan/cards/' + c.id + '.json --base ' + t.tests_head + ' --oracle ' + t.tests_head + (c.bootstrap ? ' --profile bootstrap' : '') + mergedArgs(mergedIds)) + ' yourself and return its LEDGER_DIGEST as gate_digest, its LEDGER_SHA256, the head_sha in the ledger, the profile, IDIOM_HITS as idiom_hits, and `sha256sum ' + A.gate_sh + '` as gate_sha256_observed;',
    '(1b) write .gate/card-' + c.id + '.json = the card with apis_expected extended by the builder-reported APIS_USED below and pass THAT path as --card so apicheck covers what was actually called; APIS_USED: ' + J([...(b.apis_used || [])].sort((x, y) => (x.module + x.symbol < y.module + y.symbol ? -1 : 1))) + '; (2) re-run every DoD command (dod_reruns[] one per card DoD id); (3) read `git diff ' + t.tests_head + '..' + b.head_sha + '` and cite hunks; report diff_stats from --numstat; (4) write .gate/mutants/' + c.id + '.json ({"tests":[the author\'s test paths],"mutants":[3 one-line breaks inside files_allowed that the card\'s tests must catch; start from the author\'s suggestions if any]}) and run ' + gateCmd('--mutants .gate/mutants/' + c.id + '.json --tests ' + t.test_paths.join(',') + ' --out .gate/mutants-' + c.id + '.json') + ' (written ≥ 1, ALL killed); (5) run ' + gateCmd('--revert-proof ' + t.tests_head + ' --tests ' + t.test_paths.join(',') + ' --out .gate/revert-' + c.id + '.json') + ' and report revert_proof.observed;',
    '(6) clear every idiom-lint warning by idiom with a reason, or fail; (7) verdict fail on ANY failure, on a bootstrap profile for a non-bootstrap card, on collected 0, on a missing DoD row. Default to fail when uncertain; state your strongest disagreement even on pass. Remove the worktree.' + redriveLine(rd)].join('\n'),
  merge: (c, b, head, mergedIds) => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:merge (single writer of ' + INTEG + '). In ' + R + ': ensure ' + INTEG + ' is at ' + head + '; if ' + b.head_sha + ' is already an ancestor (`git merge-base --is-ancestor`; exit 128 = unknown → status missing-ref) return status already-merged with the current head; else `git merge --no-ff ' + taskBranch(c.id) + '` (head ' + b.head_sha + '). If the ref is missing → status missing-ref. On ANY conflict: `git merge --abort`, return status conflict with the hunks (ours/theirs) — do not resolve.',
    'On a clean merge: run ' + gateCmd('--base ' + head + mergedArgs([...mergedIds, c.id])) + '; if red → `git revert -m 1 HEAD` and return status reverted with the ledger; if green → assert `git cherry ' + INTEG + ' ' + taskBranch(c.id) + '` is empty and every `git patch-id` of the task commits appears in ' + head + '..HEAD; write plan/status/' + c.id + '.json {state:"merged", head_sha, gate_digest} and commit "status(' + c.id + '): merged"; `git bundle create ' + BUNDLES + '/' + c.id + '.bundle ' + head + '..' + INTEG + '` (incremental) and report bundle_bytes; remove worktrees of ' + taskBranch(c.id) + ' and ' + testsBranch(c.id) + '; return status merged + head_sha (after the status commit) + LEDGER_DIGEST as gate_digest + gate_sha256_observed + `git remote -v` lines.'].join('\n'),
  conflict: (c, b, head, hunks) => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:conflict (fresh). Worktree ' + WT + '/conflict-' + c.id + '-' + A.run_nonce + ' on ' + INTEG + ' at ' + head + '. Merge ' + taskBranch(c.id) + ' (' + b.head_sha + ') resolving ONLY these hunks so that this card\'s DoD AND the already-merged cards still hold; run ' + gateCmd('--base ' + head) + '; commit the merge; return head_sha + LEDGER_DIGEST (status merged) or gate-red. ' + cardRef(c), 'HUNKS:', J(hunks)].join('\n'),
  ff: (c, sha, mergedIds) => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:ff. Fast-forward ' + INTEG + ' in ' + R + ' to ' + sha + ' (a merge commit made in a worktree); run ' + gateCmd('--base ' + sha + '~1' + mergedArgs([...mergedIds, c.id])) + '; cherry/patch-id assertions for ' + taskBranch(c.id) + '; write plan/status/' + c.id + '.json and commit; bundle to ' + BUNDLES + '/' + c.id + '.bundle; return status merged + head_sha + LEDGER_DIGEST.'].join('\n'),
  revert: (id, head, mergedIds) => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:revert (single writer of ' + INTEG + '). In ' + R + ' on ' + INTEG + ' at ' + head + ': `git revert -m 1 HEAD` reverting the merge of ' + taskBranch(id) + ' (if HEAD is the status commit, revert the merge commit beneath it and also remove plan/status/' + id + '.json in the same commit); run ' + gateCmd('--base ' + head + mergedArgs(mergedIds)) + ' on the result; return status merged with the new head_sha and LEDGER_DIGEST when the gate is green, else status gate-red with the ledger. Do nothing else.'].join('\n'),
  clean: (w, head, mergedIds) => [PREAMBLE, AUTHORITY, 'ROLE: integrator mode:clean-gate for wave ' + w + '. `git -C ' + R + ' worktree add --detach ' + WT + '/clean-w' + w + '-' + A.run_nonce + ' ' + head + '`; inside it run BROKEN_SHA=' + A.base_sha + ' ' + gateCmd('--clean --self-test --journeys --base ' + A.base_sha + mergedArgs(mergedIds)) + ' (full suite twice, conformance on the fake backend, journeys with needs= skips counted, README check, red-proofs, gate integrity); return LEDGER_DIGEST as gate_digest, head_sha, journeys {collected, failed, skipped_needs[]}, self_test, gate_sha256_observed, `git -C ' + R + ' remote -v` lines and `git -C ' + R + ' branch --list` count; remove the worktree. Also report sha256 of `git -C /workspaces/agent-skills-toolchain status --porcelain` as toolchain_status_sha256 (must equal ' + A.toolchain_status_sha256 + ').'].join('\n'),
  journeys: (tag, head, seams) => [PREAMBLE, AUTHORITY, 'ROLE: author mode:journeys (' + tag + ') at ' + head + '. Seams whose card merged this wave: ' + seams.join(', ') + '. On NEW branch ' + taskBranch('journeys-' + tag) + ' from ' + head + ' write composition tests under tests/journeys/ for those seams (H1 tool loop × streaming × Continue at TOKEN level: turn 2 contains turn 1\'s tool results, finish_reason length → Continue resumes from prefix_ids; H2 /v1 × identity: x-ip-token bound inside the generator body, 429 on the non-blocking semaphore; H3 MCP ask→poll→status→preflight with chat hidden; H4 python_eval × operator flag × every surface: UI checkbox alone cannot enable it, unreachable over /v1 and MCP; H5 catalog admission × models.yaml schema × harness zero-call × pending entries hidden; H6 session isolation × TTL sweep × no rmtree on unload; H7 error taxonomy quota/illegal-duration/abort → titled notice in UI, {"error":…} event on /v1, partial text kept; J1 QWEN_STUB=1 boot serves UI + /healthz{git_sha from build_info.json} in < 10 s on a free port). Each journey that needs an unmerged card is marked `pytest.mark.skip(reason="needs=<card-id>")`. Commit, run ' + gateCmd('--only-tests tests/journeys --base ' + head) + ' (they may pass — composition tests are allowed to be green; report the confirm-red line as is), return tests_head and test_paths.'].join('\n'),
  review: (lens, head, seenKeys, round) => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:review, lens ' + lens + ', round ' + round + '. Branch ' + INTEG + ' at ' + head + ' in a detached worktree ' + WT + '/review-' + lens + '-r' + round + '-' + A.run_nonce + '. Read plan/decisions.json, plan/index.json and `git diff ' + A.base_sha + '..' + head + '` (use --color-moved to skip pure moves).',
    'Report ONLY problems that affect correctness, a decided value, scope, test integrity, security or secrets — each with a reproduction (command + exit code + excerpt) at ' + head + ' and a files_allowed[] for its fix; no style findings. List probes_used[] (the commands/angles you used). Known finding keys to skip: ' + J(seenKeys) + '. Remove the worktree.'].join('\n'),
  refute: (f, head) => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:refute. Try to REFUTE this finding at ' + head + ' in a detached worktree; default to refuted if uncertain; holds ONLY with a reproduction you executed (command, exit code, excerpt). Return the finding back as findings[0] with your corrected_claim.', J(f)].join('\n'),
  veto: (head, rows, last, probes) => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:veto (you may only VETO with a reproduction; you can never approve). ' + INTEG + ' at ' + head + '. Inputs: plan/decisions.json, plan/index.json, the clean-gate ledger, and this status table: ' + J(rows), last ? 'LAST ROUND MANDATE (DoD inversion): start from the decided values and the cards; independently try to falsify every claimed end-state or find an omitted obligation; you may NOT reuse these probes: ' + J(probes) : 'Cite hunks; each veto is a finding with a reproduction; otherwise return verdict no-veto with your strongest disagreement.'].join('\n'),
  evidence: (dir, head) => [PREAMBLE, AUTHORITY, 'ROLE: verifier mode:evidence for stage ' + A.stage + '. Read ONLY files under ' + dir + ' (space-runtime.json, healthz.json, canary.json, build-log.txt, rollback-drill.json, hardening-selftest.json) and ' + R + '/evidence/staging/' + head + '/EXPECTED.json. For every expected number report a finding (kind staging-evidence) with reproduction (the jq/python command you ran on the file) when the evidence is missing or contradicts EXPECTED; healthz.git_sha must equal the pushed sha and must not be "unknown"; the python version in space-runtime.json and the resolved requirements in build-log.txt must match requirements.lock (a difference is a finding at verification_level local-mechanical). Never call any URL.'].join('\n'),
  synth: (rows, checkpoint, stop, seenKeys, ledgerSummary) => [PREAMBLE, AUTHORITY, 'ROLE: synthesizer (never edits code). Write ' + GRILL + '/RUN-REPORT-' + A.run_nonce + '.md and ' + STATUS_JSON + ' ({rows, seen_keys, head_sha, last_clean_gate, halt}) from ONLY these mechanical inputs: STOP=' + stop + '; ROWS=' + J(rows) + '; CHECKPOINT=' + J(checkpoint) + '; SEEN_KEYS=' + J(seenKeys) + '; LEDGER (sorted by role,mode,id,attempt)=' + J(ledgerSummary) + '; ledgers under ' + R + '/.gate and ' + R + '/plan/status. Rows in your return must equal the ROWS given (they will be overwritten otherwise). Include the persona absence-test result, deferred DoD lines by verification_level, blocked_on_owner first, the owner\'s Hub post-checks (`gh repo list`, namespace listing unchanged), and "what would most improve confidence". Return report_path, report_bytes, status_json_path.'].join('\n'),
  synthFix: (path, rows) => [PREAMBLE, AUTHORITY, 'ROLE: synthesizer mode:fix (bash). The rows table in ' + path + ' differs from the script\'s ledger. Rewrite ONLY the rows table (and the matching rows in ' + STATUS_JSON + ') from these rows, nothing else: ' + J(rows) + '. Return report_path, report_bytes, status_json_path and the same rows.'].join('\n'),
}

// ---------------------------------------------------------------------------------------------
// Inner loop per card (§5) — returns a typed result, never throws; rd = re-drive counter (prompt suffix)
// ---------------------------------------------------------------------------------------------
const localLevel = lvl => !/staging|owner|unverified/.test(String(lvl))
function okSemantics(c, t, b, v) {                     // taskDone(): every condition a judge asked for, in code
  const ok = []
  ok[1] = v.verdict === 'pass' && v.gate_exit_code === 0 && v.status !== 'null'
  ok[2] = v.ledger_head_sha === b.head_sha && isSha(b.head_sha) && v.sha === b.head_sha
  ok[3] = isHex64(v.gate_digest) && v.gate_digest === b.gate_digest                                   // A1 G1: two independent executions agree (F-12)
  ok[4] = v.gate_sha256_observed === A.gate_sha256 && (c.bootstrap ? true : v.gate_profile === 'full') && (c.bootstrap ? true : b.gate_profile === 'full')   // pinned gate, recorded profile (CG1, A2 G9)
  ok[5] = (v.hunks_cited || []).length >= 1 && (v.checks || []).some(x => /gate\.sh/.test(x.command || ''))
  ok[6] = v.mutants && v.mutants.written >= 1 && v.mutants.killed === v.mutants.written                // mutants mandatory, all killed (F-20)
  ok[7] = v.revert_proof && v.revert_proof.observed === 'red'                                          // negative control (A1 ok[7]/ok[8])
  ok[8] = (b.dod || []).length === c.dod.length && c.dod.every(d => !localLevel(d.verification_level) || ((b.dod || []).some(x => x.id === d.id && x.exit_code === 0) && (v.dod_reruns || []).some(x => x.id === d.id && x.exit_code === 0)))   // every local DoD id exit 0 on BOTH sides (A1 ok[6])
  ok[9] = (v.warnings_cleared || []).length >= (v.idiom_hits || 0)                                     // F-10 in code (A2 G14)
  ok[10] = !(v.diff_stats && (v.diff_stats.insertions + v.diff_stats.deletions) > 2 * (c.est_lines || 300))   // scope expansion (A2 G8)
  ok[11] = !b.__secret_redacted && !v.__secret_redacted                                               // CG3: a secret-shaped output blocks the card
  ok[12] = (b.commits_made >= 1 || b.status === 'reused') && b.status !== 'partial' && (b.apis_used || []).every(a => !!a.ledger_ref)   // F-8: every API the builder used is anchored in the ledger
  const line = [1,2,3,4,5,6,7,8,9,10,11,12].map(k => k + (ok[k] ? '✓' : '✗')).join(' ')
  log(c.id + ' taskDone: ' + line)
  return [1,2,3,4,5,6,7,8,9,10,11,12].every(k => ok[k])
}
async function buildTask(c, base, mergedIds, rd) {
  const trail = []; let t = null
  try {
    for (let k = 1; k <= MAX_AUTHOR; k++) {
      const a = await run('author', 'tests', c.id + ':' + k, P.author(c, base, k, rd), { phase: 'Build', schema: TESTS, effort: 'medium' })
      if (a.status === 'null') return { card: c, state: 'blocked', reason: 'agent-null:author:' + a.reason, trail }
      if (!isSha(a.tests_head) || !(a.commits_made >= 1 || a.status === 'reused')) return { card: c, state: 'blocked', reason: 'author-no-commit', trail }
      const red = await run('verifier', 'red', c.id + ':' + k, P.red(c, a, base, rd), { phase: 'Build', schema: VERDICT, effort: 'low' })
      trail.push({ author: k, red: red.verdict || red.status })
      if (red.status === 'null') return { card: c, state: 'blocked', reason: 'agent-null:red', trail }
      if (red.verdict === 'pass' && red.gate_exit_code === 0 && red.sha === a.tests_head && isHex64(red.gate_digest)) { t = a; break }
      if (k === MAX_AUTHOR) return { card: c, state: 'blocked', reason: 'tests-not-red', trail }
      log(c.id + ': confirm-RED failed (' + k + '/' + MAX_AUTHOR + ') — re-driving the author')
    }
    let b = null, v = null, fails = null, prevFp = null, fps = []
    for (let k = 1; k <= MAX_BUILD; k++) {
      b = await run('builder', k === 1 ? 'build' : 'fix', c.id + ':' + k, P.build(c, t, base, k, fails, mergedIds, rd), { phase: 'Build', schema: BUILD, effort: 'high' })
      if (b.status === 'null' || b.status === 'failed') return { card: c, state: 'blocked', reason: 'agent-null:builder:' + (b.reason || b.status), trail, tests: t }
      if (!(b.commits_made >= 1) && b.status !== 'reused') return { card: c, state: 'blocked', reason: 'no-commits', trail, tests: t }
      v = await run('verifier', 'verify', c.id + ':' + k, P.verify(c, t, b, k, mergedIds, rd), { phase: 'Build', schema: VERDICT, effort: c.risk === 'security' ? 'xhigh' : 'medium' })
      if (v.status === 'null') return { card: c, state: 'blocked', reason: 'agent-null:verifier', trail, tests: t, build: b }
      raiseLevels(v.findings, f => f.title + ' ' + (f.reproduction || {}).command)
      trail.push({ build: k, verdict: v.verdict || v.status, digestOk: v.gate_digest === b.gate_digest })
      if (okSemantics(c, t, b, v)) break
      if (b.__secret_redacted || v.__secret_redacted) return { card: c, state: 'blocked', reason: 'secret-shaped-output', trail, tests: t, build: b, verify: v }
      const fp = fingerprint(v.failures); fps.push(fp)
      if (fp && fp === prevFp) return { card: c, state: 'blocked', reason: 'no-progress', trail, tests: t, build: b, verify: v }          // two strikes (D-8)
      if (fps.length >= 3 && fps[fps.length - 1] === fps[fps.length - 3]) return { card: c, state: 'blocked', reason: 'oscillation', trail, tests: t, build: b, verify: v }
      if (k === MAX_BUILD) return { card: c, state: 'blocked', reason: 'fix-exhausted', trail, tests: t, build: b, verify: v }
      prevFp = fp; fails = { failures: v.failures, checks_failed: (v.checks || []).filter(x => x.exit_code !== 0), dod_reruns_failed: (v.dod_reruns || []).filter(x => x.exit_code !== 0), mutants: v.mutants, revert_proof: v.revert_proof, strongest_disagreement: cap(v.strongest_disagreement, 600) }
      log(c.id + ': verify FAILED (' + k + '/' + MAX_BUILD + ') fp=' + fp.slice(0, 60) + ' — fixing')
    }
    const deferred = c.dod.filter(d => !localLevel(d.verification_level)).map(d => d.id)
    return { card: c, state: 'built', tests: t, build: b, verify: v, deferred, trail }        // taskDone() true
  } catch (e) { log(c.id + ': stage threw ' + String(e && e.message)); return { card: c, state: 'blocked', reason: 'threw', trail } }
}

// ---------------------------------------------------------------------------------------------
// Serial integration of one built card (§4.5) — mutates `head` via the returned value only
// ---------------------------------------------------------------------------------------------
const mergeOk = m => m.status === 'merged' && isSha(m.head_sha) && m.gate_exit_code === 0 && isHex64(m.gate_digest) && m.gate_sha256_observed === A.gate_sha256 && !(m.cherry_unmerged || []).length && !(m.patch_ids_missing || []).length
async function integrate(r, head, mergedIds) {
  let m = await run('integrator', 'merge', r.card.id, P.merge(r.card, r.build, head, mergedIds), { phase: 'Integrate', schema: MERGE, effort: 'low' })
  if (m.status === 'conflict') {
    log(r.card.id + ': conflict in ' + m.conflicts.map(x => x.file).join(',') + ' — fresh conflict call')
    const res = await run('integrator', 'conflict', r.card.id, P.conflict(r.card, r.build, head, m.conflicts), { phase: 'Integrate', schema: MERGE, effort: 'high' })
    m = res.status === 'merged' ? await run('integrator', 'ff', r.card.id + ':ff', P.ff(r.card, res.head_sha, mergedIds), { phase: 'Integrate', schema: MERGE, effort: 'low' }) : res
  }
  if (m.status === 'missing-ref') { log(r.card.id + ': ref missing (stale sha) — will re-drive live'); return { head, state: 'stale' } }
  if (m.status === 'already-merged' && isSha(m.head_sha)) return { head: m.head_sha, state: 'merged', digest: m.gate_digest || null }
  if (m.status === 'reverted') return { head, state: 'blocked', reason: 'integration:gate-red-after-merge(reverted)' }
  if (!mergeOk(m)) { log(r.card.id + ': NOT integrated (' + m.status + (m.reason ? ':' + m.reason : '') + ')'); return { head, state: 'blocked', reason: 'integration:' + (m.status === 'null' ? 'agent-null' : m.status) } }
  if ((m.remotes || []).length && !OA.github_repo_url) { HALT = 'remote-added:' + r.card.id; log('HALT ' + HALT) }   // CG5: mechanical post-check, not self-report
  return { head: m.head_sha, state: 'merged', digest: m.gate_digest }
}

// ---------------------------------------------------------------------------------------------
// Build + integrate a list of cards in barrier waves (used for the plan and for review fix tasks)
// ---------------------------------------------------------------------------------------------
const status = new Map()                    // card id → typed state (the script's own row table; F-40)
let lastClean = { verdict: 'gate-unavailable', head_sha: null, digest: null }, INTEG_DIRTY = false
const syntheticFindings = []
const mergedSet = () => new Set([...status.entries()].filter(([, s]) => s.state === 'merged').map(([id]) => id))
async function buildAndIntegrate(cards, head, tag) {
  cards.forEach(c => CARD_BY_ID.set(c.id, c))
  for (const c of cards) { const pre = c.owner_precondition; if (pre && !OA[pre] && !status.has(c.id)) { status.set(c.id, { state: 'blocked_on_owner', field: pre, reason: 'owner-precondition:' + pre }); log(c.id + ': blocked on owner_approvals.' + pre) } }
  const blockedIds = [...status.entries()].filter(([, s]) => s.state !== 'merged').map(([id]) => id)
  const { plan, unschedulable } = waves(cards, WAVE, [...mergedSet()], blockedIds)
  unschedulable.forEach(u => { if (!status.has(u.id)) { status.set(u.id, { state: 'not_attempted', reason: 'dependency-blocked:' + u.unmet.join('/') }); log(u.id + ': not attempted (deps ' + u.unmet.join('/') + ' blocked)') } })
  log(tag + ': ' + cards.length + ' card(s) in ' + plan.length + ' wave(s) of ≤' + WAVE + '; unschedulable ' + unschedulable.length)
  for (let w = 0; w < plan.length; w++) {
    const wave = plan[w]
    if (INTEG_DIRTY || !budgetOk(tag + ' wave ' + (w + 1)) || !agentsOk(tag + ' wave ' + (w + 1), RESERVE_PER_CHAIN * wave.length + 4)) {
      plan.slice(w).flat().forEach(c => status.set(c.id, { state: 'not_attempted', reason: INTEG_DIRTY ? 'integration-dirty' : (HALT ? 'halt:' + HALT : 'agent-slice-or-budget') }))
      log(tag + ': waves ' + (w + 1) + '..' + plan.length + ' NOT attempted (' + (INTEG_DIRTY ? 'integration dirty' : HALT || 'agent slice / budget') + ')'); break
    }
    const mergedBefore = [...mergedSet()]
    log(tag + ' wave ' + (w + 1) + '/' + plan.length + ': ' + wave.map(c => c.id).join(', ') + ' on ' + head.slice(0, 12))
    const results = await pipeline(wave, c => buildTask(c, head, mergedBefore, 0))
    let dropped = 0; results.forEach((r, i) => { if (!r) { dropped++; status.set(wave[i].id, { state: 'dropped_null', reason: 'chain-null' }) } })
    if (dropped) log(tag + ' wave ' + (w + 1) + ': ' + dropped + ' chain(s) resolved null (typed dropped_null)')
    phase('Integrate')
    const merged = []
    for (const r of results.filter(Boolean).sort((x, y) => byId(x.card, y.card))) {      // serial, ties by id
      if (r.state !== 'built') { status.set(r.card.id, { state: 'parked', reason: r.reason, head_sha: r.build ? r.build.head_sha : null, dod: r.build ? r.build.dod : [] }); continue }
      let it = await integrate(r, head, [...mergedSet()])
      if (it.state === 'stale') { const again = await buildTask(r.card, head, [...mergedSet()], 1); it = again.state === 'built' ? await integrate(again, head, [...mergedSet()]) : { state: 'blocked', reason: again.reason, head } }
      if (it.state === 'merged') { head = it.head; merged.push(r.card.id); status.set(r.card.id, { state: 'merged', head_sha: head, dod: r.build.dod, deferred: r.deferred, digest: it.digest }); log(r.card.id + ' merged → ' + head.slice(0, 12)) }
      else status.set(r.card.id, { state: /reverted/.test(it.reason || '') ? 'reverted' : 'parked', reason: it.reason, head_sha: r.build.head_sha, dod: r.build.dod })
    }
    const seams = Object.keys(JOURNEY_NEEDS).filter(s => merged.includes(JOURNEY_NEEDS[s])).sort()
    if (seams.length && !A.smoke) {
      const jw = await run('author', 'journeys', tag + ':w' + (w + 1), P.journeys(tag + '-w' + (w + 1), head, seams), { phase: 'Integrate', schema: TESTS, effort: 'medium' })
      if (jw.status === 'SUCCESS' && isSha(jw.tests_head)) { const jm = await integrate({ card: { id: 'journeys-' + tag + '-w' + (w + 1) }, build: { head_sha: jw.tests_head } }, head, [...mergedSet()]); if (jm.state === 'merged') head = jm.head; else log('journeys ' + tag + '-w' + (w + 1) + ' NOT merged: ' + jm.reason) }
      else log('journeys author ' + tag + '-w' + (w + 1) + ' dropped/failed: ' + (jw.reason || jw.status))
    }
    const cg = await run('integrator', 'clean', tag + ':w' + (w + 1), P.clean(tag + '-w' + (w + 1), head, [...mergedSet()]), { phase: 'Integrate', schema: MERGE, effort: 'low' })
    if (cg.status === 'null') { lastClean = { verdict: 'gate-unavailable', head_sha: head, digest: null, wave: tag + ':w' + (w + 1) }; log(tag + ' wave ' + (w + 1) + ': clean-gate UNAVAILABLE (' + cg.reason + ') — no revert; satisfied() stays false') }   // J2 A3-2: a drop is never RED
    else {
      const pass = cg.gate_exit_code === 0 && cg.head_sha === head && isHex64(cg.gate_digest) && cg.gate_sha256_observed === A.gate_sha256 && (cg.self_test ? cg.self_test.broken_red === true : false)
      lastClean = { verdict: pass ? 'pass' : 'fail', head_sha: cg.head_sha, digest: cg.gate_digest, wave: tag + ':w' + (w + 1) }
      if (cg.toolchain_status_sha256 && cg.toolchain_status_sha256 !== A.toolchain_status_sha256) { HALT = 'toolchain-mutated'; log('HALT ' + HALT + ' (F-1)') }
      if ((cg.remotes || []).length && !OA.github_repo_url) { HALT = 'remote-added:clean-gate'; log('HALT ' + HALT) }
      const stillSkipped = ((cg.journeys || {}).skipped_needs || []).filter(n => mergedSet().has(n)).sort()
      if (stillSkipped.length) { log('journeys still skipped although their card merged: ' + stillSkipped.join(',') + ' → synthetic finding'); syntheticFindings.push({ id: 'journey-needs-' + stillSkipped.join('+'), title: 'journey skipped after its card merged', file: 'tests/journeys', severity: 'high', kind: 'interaction', reproduction: { command: gateCmd('--clean --journeys'), exit_code: 1, output_tail: 'skipped_needs=' + stillSkipped.join(',') }, verification_level: 'local-stub', files_allowed: ['tests/journeys'] }) }
      if (!pass) {
        const last = merged[merged.length - 1]; log(tag + ' wave ' + (w + 1) + ': clean-gate RED at ' + head.slice(0, 12) + (last ? ' — reverting ' + last : ''))
        if (last) {
          const rv = await run('integrator', 'revert', last + ':revert', P.revert(last, head, [...mergedSet()].filter(id => id !== last)), { phase: 'Integrate', schema: MERGE, effort: 'low' })
          if (rv.status === 'merged' && isSha(rv.head_sha) && rv.gate_exit_code === 0 && isHex64(rv.gate_digest)) { head = rv.head_sha; status.set(last, { state: 'reverted', reason: 'clean-gate-red', head_sha: head }); lastClean = { verdict: 'pass', head_sha: head, digest: rv.gate_digest, wave: tag + ':w' + (w + 1) + ':after-revert' } }
          else { INTEG_DIRTY = true; status.set(last, { state: 'revert-failed', reason: 'revert:' + (rv.status || 'null'), head_sha: head }); log('REVERT FAILED for ' + last + ' — integration branch marked dirty; no further merges (CG12)') }   // J2 gap 12: checked revert
        }
      }
    }
    phase('Build')
  }
  return head
}

// ---------------------------------------------------------------------------------------------
// satisfied() — the ONLY way the run says the tree is done (D-24, C-D); evidence stages use the same predicate
// ---------------------------------------------------------------------------------------------
const openBlocking = [], seen = new Set(), probesUsed = new Set()
function satisfied(head, allCards) {
  const parked = [...status.entries()].filter(([, s]) => /parked|reverted|revert-failed|dropped_null/.test(s.state)).map(([id]) => id)
  const parkedCritical = parked.filter(id => allCards.some(c => c.depends_on.includes(id) && !(status.get(c.id) || {}).state))
  const unreviewed = allCards.filter(c => !status.has(c.id)).length
  const ok = !HALT && !INTEG_DIRTY && lastClean.verdict === 'pass' && lastClean.head_sha === head && openBlocking.length === 0 && unreviewed === 0 && parkedCritical.length === 0
  log('satisfied()=' + ok + ' clean=' + lastClean.verdict + '@' + String(lastClean.head_sha).slice(0, 12) + ' openBlocking=' + openBlocking.length + ' unreviewed=' + unreviewed + ' parked=' + parked.length + ' parkedCritical=' + parkedCritical.length + (HALT ? ' HALT=' + HALT : ''))
  return ok
}
const toFixCard = (f, round, i) => ({ id: 'platform-00-rf' + round + '-' + String(i + 1).padStart(2, '0') + '-' + f.id.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 24), step: 1, depends_on: [], files_allowed: f.files_allowed || [f.file], tests_allowed: [], new_modules: [], deps_allowed: [], xfail_allowed: [], tests_removed_expected: 0, est_lines: 120, est_minutes: 20,
  dod: [{ id: 'D1', command: f.reproduction.command, expect: 'exit0', verification_level: localLevel(f.verification_level) ? f.verification_level : 'local-stub' }], size: 'S', risk: f.kind === 'security' || f.kind === 'secrets' ? 'security' : 'none', protected_touch: false, bootstrap: false, decision_ids: [], finding_ids: [{ id: f.id, corrected_text: cap(f.corrected_claim || f.title, 600) }], apis_expected: [], owner_precondition: '', finding: f })

// ---------------------------------------------------------------------------------------------
// Whole-tree review loop (§6.2)
// ---------------------------------------------------------------------------------------------
async function reviewLoop(head, allCards) {
  phase('Review')
  const LENSES = ['decision-fidelity+scope', 'correctness+tests-integrity', 'security+secrets']
  let round = 0, dry = 0, stop = null, vetoes = []
  while (true) {
    if (satisfied(head, allCards) && vetoes.length === 0 && round > 0) { stop = 'satisfied'; break }
    if (HALT) { stop = 'halt:' + HALT; break }
    if (round >= MAX_ROUNDS) { stop = 'max-rounds(' + MAX_ROUNDS + ')'; break }
    if (dry >= 2) { stop = 'dry(2)'; break }
    if (!budgetOk('review round ' + (round + 1)) || !agentsOk('review round ' + (round + 1), 3 + 4)) { stop = 'budget-or-agent-cap'; break }
    round++
    const seenKeys = [...seen].sort()
    const reviews = await parallel(LENSES.map(lens => () => run('verifier', 'review', lens + ':r' + round, P.review(lens, head, seenKeys, round), { phase: 'Review', schema: VERDICT, effort: 'high' }, LENSES.length)))   // barrier: dedup needs all
    const lensDrops = reviews.filter(r => !r || r.status === 'null').length
    reviews.filter(r => r && r.status !== 'null').forEach(r => (r.probes_used || []).forEach(p => probesUsed.add(cap(p, 200))))
    const found = reviews.filter(r => r && r.status !== 'null').flatMap(r => r.findings || []).concat(syntheticFindings.splice(0)).filter(f => f.reproduction && f.verification_level !== 'unverified').sort(byId)
    raiseLevels(found, f => f.title + ' ' + (f.reproduction || {}).command)
    const fresh = found.filter(f => !seen.has(fkey(f))); fresh.forEach(f => seen.add(fkey(f)))
    log('review r' + round + ': ' + found.length + ' found, ' + fresh.length + ' fresh, ' + lensDrops + ' lens(es) dropped')
    const judged = await pipeline(fresh, f => run('verifier', 'refute', f.id + ':r' + round, P.refute(f, head), { phase: 'Review', schema: VERDICT, effort: 'medium' }, fresh.length).then(v => ({ f, v })))
    const judgeDrops = judged.filter(j => !j).length; if (judgeDrops) log('review r' + round + ': ' + judgeDrops + ' refute chain(s) resolved null (counted, not queued)')   // J1 D5
    const confirmed = judged.filter(Boolean).filter(({ v }) => v.status !== 'null' && v.verdict === 'holds' && v.findings && v.findings[0] && v.findings[0].reproduction).map(({ f, v }) => Object.assign({}, f, v.findings[0]))
    log('review r' + round + ': ' + confirmed.length + '/' + fresh.length + ' hold after refutation')
    const ownerOnly = confirmed.filter(f => !localLevel(f.verification_level)); ownerOnly.forEach(f => { if (!status.has('finding:' + f.id)) status.set('finding:' + f.id, { state: 'blocked_on_owner', field: 'staging_evidence_dir', reason: 'finding ' + f.id + ' is ' + f.verification_level }) })
    const fixable = confirmed.filter(f => localLevel(f.verification_level))
    const blocking = fixable.filter(f => f.severity === 'critical' || f.severity === 'high'); openBlocking.push(...blocking.map(f => f.id))
    const fixCards = [...fixable, ...vetoes].map((f, i) => toFixCard(f, round, i))
    if (fixCards.length) { head = await buildAndIntegrate(fixCards, head, 'fix-r' + round); fixCards.forEach(c => { if ((status.get(c.id) || {}).state === 'merged') { const k = openBlocking.indexOf(c.finding_ids[0].id); if (k >= 0) openBlocking.splice(k, 1) } }) }
    vetoes = []
    if (satisfied(head, allCards)) {
      const rows = [...status.entries()].sort().map(([id, s]) => ({ id, state: s.state, reason: s.reason || null }))
      const vj = await run('verifier', 'veto', 'r' + round, P.veto(head, rows, round === MAX_ROUNDS || dry === 1, [...probesUsed].sort()), { phase: 'Review', schema: VERDICT, effort: 'xhigh' })
      if (vj.status === 'null') { stop = 'veto-unavailable'; log('veto r' + round + ': judge dropped → NOT satisfied (fail closed)'); break }   // A1 §13.7 fail-closed judging
      vetoes = (vj.findings || []).filter(f => f.reproduction && f.verification_level !== 'unverified'); const notes = (vj.findings || []).length - vetoes.length
      ;(vj.probes_used || []).forEach(p => probesUsed.add(cap(p, 200)))
      log('veto r' + round + ': ' + vetoes.length + ' veto(es) with reproduction, ' + notes + ' note(s) without')
    }
    dry = (fresh.length === 0 && vetoes.length === 0) ? dry + 1 : 0
  }
  log('review loop ended: ' + stop + ' after ' + round + ' round(s); seen=' + seen.size + ' openBlocking=' + openBlocking.length)
  return { head, stop, round }
}

// ---------------------------------------------------------------------------------------------
// Checkpoint object (computed by the script; the synthesizer only renders it) — §2.2
// ---------------------------------------------------------------------------------------------
function checkpoint(stage, head, stop) {
  const rows = [...status.entries()].filter(([id]) => !id.startsWith('finding:')).sort().map(([task_id, s]) => ({ task_id, state: s.state === 'merged' ? 'merged+gate-green' : s.state, head_sha: s.head_sha || 'none', dod_done: (s.dod || []).filter(d => d.exit_code === 0).length, dod_total: (s.dod || []).length, dod_deferred: (s.deferred || []).length }))
  const actions = [], blocked_on_owner = []
  const act = (id, kind, why, steps, blast, rollback, cost) => actions.push({ id, kind, why, exact_steps: steps, blast_radius: blast, rollback, cost_estimate: cost, evidence_paths: [R + '/.gate/last_run.json', STATUS_JSON] })
  for (const [id, s] of status) if (s.state === 'blocked_on_owner') blocked_on_owner.push({ task_id: id, field: s.field, why: s.reason })
  for (const [id, s] of status) if (s.state === 'merged' && (s.deferred || []).length) blocked_on_owner.push({ task_id: id, field: 'staging_evidence_dir', why: 'DoD lines ' + s.deferred.join(',') + ' are staging/owner-required' })
  const complete = stage === 'plan' || rows.every(r => /^(merged\+gate-green|parked|reverted)$/.test(r.state))   // a card blocked on the owner or not attempted ⇒ the stage is not done
  let ready = !HALT && !INTEG_DIRTY && stop === 'satisfied' && complete
  if (stage === 'plan') {
    act('C0-1', 'approve-plan', 'F-9: the owner approves plan/decisions.json (incl. the five against-recommendation rows and the clarifications) and plan/index.json before any code is written', ['read ' + R + '/plan/decisions.json and plan/index.json at ' + (A.plan_sha || '<plan_sha from the CARD_INDEX>'), 'launch stage=build with plan_sha=<that sha>'], 'none', 'none', '0')
    act('C0-2', 'record-fixture-1', 'lens-4 biggest risk: ONE metered streamed router call (tool + thinking on) decides where the parser lives; card platform-04-streamparser is blocked_on_owner until owner_approvals.fixture1_path is set (the thin slice 03b must exist first — expect this stop after R1\'s first invocation)', ['after cards 01-03b merge: python tools/record_fixture.py --i-accept-cost 0.10 --out tests/fixtures/recorded/hosted-1.json', 'pass owner_approvals.fixture1_path'], 'cents', 'none', '< $0.10')
    act('C0-3', 'record-boundary-fixture', 'G-19/F-17: the persona absence test needs owner-generated shingle hashes of the excluded clause (the workflow never sees the clause); card product-13b is blocked until owner_approvals.persona_boundary_fixture_path is set', ['python tools/make_boundary_fixture.py --clause-file <owner-only path> --out tests/fixtures/persona_boundary.json (off-workflow)', 'pass owner_approvals.persona_boundary_fixture_path'], 'none', 'none', '0')
    act('C0-4', 'decide-worker-checkpoint', 'M-2 + inference-perf-2/-5/-7 CORRECTED: the resident checkpoint must carry model.visual.* (VLM class kept for G-16); plan/catalog-provenance records has_visual_tensors per candidate; if neither candidate has them a VLM-class export HF Job precedes staging', ['read evidence/catalog/*.json has_visual_tensors', 'set owner_approvals.worker_checkpoint_decision = {candidate, needs_export: true|false}'], 'none (decision only)', 'none', '0')
  }
  if (stage === 'build') {
    if (!OA.github_repo_url) act('C1-1', 'create-github-repo', 'G-1a: GitHub is the SSOT, CI the only production writer', ['gh repo create <owner>/<name> --private', 'git -C ' + R + ' remote add origin <url>', 'git -C ' + R + ' push -u origin ' + INTEG + ' ' + PLAN_BRANCH, 'post-check: gh repo list --json name shows exactly one new repo'], 'new private repo', 'delete the repo (irreversible) or leave it', '0')
    if (!(OA.staging_space_ids || []).length) act('C1-2', 'create-staging-spaces', 'G-27/M-2: CPU front + ZeroGPU worker staging Spaces (private)', ['hf repos duplicate <prod> <ns>/<name>-staging --type space --private --exist-ok', 'same for the worker Space (ZeroGPU large)', 'post-check: namespace listing shows exactly two new private Spaces'], 'two private Spaces', 'delete Spaces', 'PRO quota only')
    act('C1-3', 'set-staging-secrets', 'G-15/G-24 clarification (owner must approve): the UI/API Space holds ONE fine-grained token scoped to inference-provider calls + read access to the private worker Space; if HF cannot combine those scopes, a second read-only token for the worker is the only alternative — record owner_approvals.token_topology = one-token|two-tokens', ['create the fine-grained token in the Hub UI (never in chat)', 'set it as the staging secret', 'pass owner_approvals.token_topology'], 'staging only', 'revoke token', '0')
    if (!OA.fixture1_path) act('C1-4', 'record-fixture-1', 'card platform-04-streamparser and every card downstream of it stay blocked until fixture #1 exists', ['python tools/record_fixture.py --i-accept-cost 0.10 --out tests/fixtures/recorded/hosted-1.json', 'pass owner_approvals.fixture1_path'], 'cents', 'none', '< $0.10')
    if (!OA.persona_boundary_fixture_path) act('C1-5', 'record-boundary-fixture', 'card product-13b-personas-readme stays blocked until the shingle-hash fixture exists', ['see C0-3'], 'none', 'none', '0')
    if (!OA.worker_checkpoint_decision) act('C1-6', 'decide-worker-checkpoint', 'card platform-08c-worker-checkpoint stays blocked until the resident checkpoint (with visual tensors) is decided', ['see C0-4'], 'none', 'none', '0')
  }
  if (stage === 'stage') {
    if (OA.worker_checkpoint_decision && OA.worker_checkpoint_decision.needs_export) act('C2-1', 'run-hf-job-quantize', 'inference-perf-2 CORRECTED: quantise/export offline with the VLM class (never inside a lease); keep the bf16 mount until one boot on the exported checkpoint is observed', ['hf jobs run … tools/export_checkpoint.py --class AutoModelForImageTextToText --budget <usd>'], 'paid HF Job', 'delete the exported repo', OA.hf_job_budget_usd ? '<= $' + OA.hf_job_budget_usd : 'owner sets hf_job_budget_usd')
    act('C2-2', 'run-harness', 'M-3: admission only after the 12-prompt harness; release 1 needs at least one entry with admission: passed (pending entries are hidden from the selector and /v1/models)', ['python tools/harness.py --backend hosted --i-accept-cost --budget ' + (OA.hosted_call_budget_usd || '<usd>') + ' on staging', 'config PR flips admission for the measured entries'], 'provider spend', 'none', OA.hosted_call_budget_usd ? '<= $' + OA.hosted_call_budget_usd : 'owner sets hosted_call_budget_usd')
    const headOk = OA.production_space_head === A.base_sha || !!OA.adopted_delta_sha
    if (!headOk) { ready = false; blocked_on_owner.push({ task_id: 'promotion', field: 'production_space_head', why: 'F-38: read the production Space HEAD (read-only Hub read) and record it; it must equal base ' + A.base_sha.slice(0, 12) + ' or the delta must be adopted explicitly (adopted_delta_sha)' }) }
    if (ready && headOk) act('C2-3', 'promote-production', 'G-2/M-5: the single production promotion from staging', ['trigger the production environment job (required reviewer = owner)', 'watch /healthz git_sha == pushed sha; canary ×3; keep the rollback command at hand'], 'production', 'tools/promote.py --to <last_good_sha>', '0')
  }
  if (stage === 'promote' && !ready) act('C3-1', 'rollback', 'post-promotion evidence contradicts EXPECTED.json', ['tools/promote.py --to <last_good_sha>'], 'production', 'none', '0')
  return { stage, nonce: A.run_nonce, status: HALT || INTEG_DIRTY ? 'failed' : ready ? 'ready' : (blocked_on_owner.length ? 'blocked' : 'failed'), halt: HALT, head_sha: head, integration_branch: INTEG, actions, blocked_on_owner, parked: rows.filter(r => /parked|reverted|revert-failed|dropped/.test(r.state)), rows, stop_reason: stop, agents: agentCount, replay_risk: REPLAY_RISK,
    next_args: { stage: stage === 'plan' ? 'build' : stage === 'build' ? (rows.some(r => /not_attempted|blocked_on_owner/.test(r.state)) ? 'build' : 'stage') : stage === 'stage' ? (ready ? 'promote' : 'stage') : 'done', plan_sha: A.plan_sha || null, integration_sha_at_launch: head, resume_mode: REPLAY_RISK ? 'git' : A.resume_mode, prior_status_path: STATUS_JSON, last_clean_gate: { head_sha: lastClean.head_sha, digest: lastClean.digest } } }
}

// ---------------------------------------------------------------------------------------------
// Main: one run per args.stage
// ---------------------------------------------------------------------------------------------
let head = A.integration_sha_at_launch || A.base_sha, stop = 'not-run', allCards = []
try {
  phase('Setup')
  const setup = await run('integrator', 'setup', A.run_nonce, P.setup(), { phase: 'Setup', schema: SETUP, effort: 'medium' })
  if (setup.status === 'null' || setup.status === 'FAILED' || !setup.base_sha_ok) throw new Error('setup failed: ' + cap(J(setup), 600))
  if (setup.gate_sha256 !== A.gate_sha256 || setup.baseline_sha256 !== A.baseline_sha256) throw new Error('gate/baseline pin mismatch: the tools dir does not hold the bytes args pin (CG1)')
  if (Math.min(16, setup.nproc - 2) !== CAP) throw new Error('cap-mismatch: nproc ' + setup.nproc + ' → cap ' + Math.min(16, setup.nproc - 2) + ' but args.cap=' + CAP + ' (stale args after a resize?)')
  if (!setup.red_proof.broken_red) throw new Error('gate red-proof failed: the gate is not RED on the broken base (D-14)')
  if ((setup.remotes || []).length && !OA.github_repo_url) throw new Error('remote present without approval: ' + setup.remotes.join(' | ') + ' (F-35 post-check)')
  if (A.stage !== 'plan') {
    if (!setup.plan_merged) throw new Error('plan/' + A.run_nonce + '@' + A.plan_sha.slice(0, 12) + ' is not merged into ' + INTEG)
    if (!isSha(setup.integration_head_live)) throw new Error('integration head unreadable')
    if (A.integration_sha_at_launch && setup.integration_head_live !== A.integration_sha_at_launch) throw new Error('stale-launch-args: live ' + INTEG + ' is ' + setup.integration_head_live.slice(0, 12) + ' but args say ' + A.integration_sha_at_launch.slice(0, 12) + ' — recompute args and launch fresh (F-43 as a script invariant)')
    head = setup.integration_head_live
    const liveMerged = new Set(setup.merged_on_integration || [])
    liveMerged.forEach(id => status.set(id, { state: 'merged', head_sha: 'on-' + INTEG, dod: [], deferred: [] }))   // git is the truth for "merged"
    for (const row of setup.prior_rows || []) {      // CG7: prior rows add detail only where git agrees; parked rows persist unless retry_parked names them
      if (row.state === 'merged+gate-green' && liveMerged.has(row.task_id)) status.set(row.task_id, { state: 'merged', head_sha: row.head_sha, dod: [], deferred: [] })
      else if (/parked|reverted|revert-failed/.test(row.state) && !liveMerged.has(row.task_id) && !(A.retry_parked || []).includes(row.task_id)) status.set(row.task_id, { state: 'parked', reason: 'prior:' + row.state, head_sha: row.head_sha })
    }
    ;(setup.seen_keys || []).forEach(k => seen.add(k))
    if (A.last_clean_gate && A.last_clean_gate.head_sha === head && isHex64(A.last_clean_gate.digest)) lastClean = { verdict: 'pass', head_sha: head, digest: A.last_clean_gate.digest, wave: 'prior' }
    log('resume state: ' + status.size + ' prior rows adopted (' + liveMerged.size + ' merged per git), seen=' + seen.size + ', lastClean=' + lastClean.verdict)
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
    const idx = await run('planner', 'plan', A.run_nonce, P.plan(preverified), { phase: 'Plan', schema: CARD_INDEX, effort: 'high' })
    if (idx.status !== 'SUCCESS' || !isSha(idx.plan_sha)) throw new Error('planner failed')
    const defects = []
    try { validateCards(idx.cards) } catch (e) { defects.push(String(e.message)) }
    for (const id of AGAINST) { const row = (idx.decisions || []).find(d => d.id === id); if (!row || row.against_recommendation !== true) defects.push('decision ' + id + ' must be marked against_recommendation (F-9)') }
    const refuted = new Set(preverified.filter(p => p.verdict === 'refuted').map(p => p.id))
    idx.cards.forEach(c => c.finding_ids.forEach(f => { if (refuted.has(f.id)) defects.push(c.id + ' cites REFUTED finding ' + f.id) }))
    for (const [cid, files] of Object.entries(REQUIRED_AFTER)) if (!idx.cards.some(c => c.id === cid)) defects.push('required-files manifest names card ' + cid + ' which the plan lacks')
    if ((idx.unmapped_finding_ids || []).length) defects.push('unmapped findings: ' + idx.unmapped_finding_ids.join(','))
    const chk = await run('verifier', 'plan', idx.plan_sha, P.planCheck(idx), { phase: 'Plan', schema: VERDICT, effort: 'medium' })
    stop = chk.verdict === 'pass' && !defects.length ? 'plan-verified' : 'plan-needs-repair'
    log('plan: ' + idx.cards.length + ' cards; ' + stop + '; defects: ' + (defects.join('; ') || 'none') + '; plan findings: ' + (chk.findings || []).length)
    A.plan_sha = idx.plan_sha
    const cp = checkpoint('plan', A.base_sha, stop === 'plan-verified' ? 'satisfied' : stop); cp.plan_sha = idx.plan_sha; cp.plan_defects = defects; cp.plan_findings = chk.findings || []; cp.preverified = preverified
    phase('Synthesize'); await run('synthesizer', 'synth', A.run_nonce, P.synth([], cp, stop, [], []), { phase: 'Synthesize', schema: REPORT, effort: 'low' })
    return cp
  }

  phase('Plan')
  const idx = await run('verifier', 'index', 'index@' + A.plan_sha, P.index(), { phase: 'Plan', schema: CARD_INDEX, effort: 'low' })
  if (idx.status !== 'SUCCESS') throw new Error('plan index unreadable at ' + A.plan_sha)
  validateCards(idx.cards)
  allCards = A.smoke ? topoOrder(idx.cards).slice(0, 1) : idx.cards
  allCards.forEach(c => CARD_BY_ID.set(c.id, c))
  if (A.stage === 'build') {
    phase('Build'); head = await buildAndIntegrate(allCards, head, 'plan')
    const rl = await reviewLoop(head, allCards); head = rl.head; stop = rl.stop
  }
  if (A.stage === 'stage' || A.stage === 'promote') {
    const dir = A.stage === 'stage' ? OA.staging_evidence_dir : OA.production_evidence_dir
    if (!dir) { stop = 'blocked:evidence-dir-missing'; status.set('evidence', { state: 'blocked_on_owner', field: A.stage === 'stage' ? 'staging_evidence_dir' : 'production_evidence_dir', reason: 'no evidence directory' }) } else {
      phase('Review')
      const ev = await run('verifier', 'evidence', A.stage + ':' + A.run_nonce, P.evidence(dir, head), { phase: 'Review', schema: VERDICT, effort: 'medium' })
      if (ev.status === 'null') { stop = 'evidence-unavailable' } else {
        syntheticFindings.push(...(ev.findings || []).filter(f => f.reproduction))
        const rl = await reviewLoop(head, allCards); head = rl.head; stop = rl.stop
      }
    }
  }
} catch (e) { stop = 'FAILED:' + String(e && e.message); log(stop) }

phase('Synthesize')                                                                 // always runs (F-45)
const cp = checkpoint(A.stage, head, stop)
try {
  const seenKeys = [...seen].sort(), ledgerSummary = ledger.map(l => ({ role: l.role, mode: l.mode, id: l.id, attempt: l.attempt, status: l.status })).sort((x, y) => (ledgerKey(x) < ledgerKey(y) ? -1 : 1))
  let s = await run('synthesizer', 'synth', A.run_nonce, P.synth(cp.rows, cp, stop, seenKeys, ledgerSummary), { phase: 'Synthesize', schema: REPORT, effort: 'low' })
  const same = r => r && r.status === 'SUCCESS' && J(r.rows.map(x => [x.task_id, x.state]).sort()) === J(cp.rows.map(x => [x.task_id, x.state]).sort())
  if (s.status === 'SUCCESS' && !same(s)) { log('SYNTH ROWS DIFFER from the ledger — rewriting the on-disk rows (J1 G13)'); s = await run('synthesizer', 'synthfix', A.run_nonce, P.synthFix(s.report_path, cp.rows), { phase: 'Synthesize', schema: REPORT, effort: 'low' }) }
  if (s.status === 'SUCCESS') { cp.report_path = s.report_path; cp.status_json_path = s.status_json_path; cp.owner_actions = s.owner_actions; cp.rows_consistent = same(s) }
  else cp.rows_consistent = false
} catch (e) { log('synthesizer threw: ' + String(e && e.message)) }
log('RUN END stage=' + A.stage + ' stop=' + stop + ' head=' + String(head).slice(0, 12) + ' agents=' + agentCount + ' ledger=' + ledger.length + ' dropped=' + ledger.filter(l => /null|timeout|threw/.test(l.status)).length + (HALT ? ' HALT=' + HALT : ''))
return cp
