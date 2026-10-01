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
  gate_exit_code: { type: 'integer', description: 'exit code of YOUR own gate.sh --only-tests run; 0 is required and the JS refuses a nonzero one for journeys (v2.1 V-11)' },
  gate_digest: { type: 'string', description: 'LEDGER_DIGEST printed by gate.sh --only-tests, or ""' },
  known_bads_xfail: { type: 'array', items: { type: 'string' } },
  mutants_suggested: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, find: { type: 'string' }, replace: { type: 'string' } }, required: ['file', 'find', 'replace'] } },
}, required: ['status', 'card_id', 'branch', 'base_sha', 'tests_head', 'test_paths', 'commits_made', 'red_command', 'red_exit_code', 'red_excerpt', 'gate_exit_code', 'gate_digest', ...COMMON_REQ] }

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
