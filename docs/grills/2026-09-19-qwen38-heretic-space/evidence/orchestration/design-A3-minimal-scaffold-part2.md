
---

## 4. Task model

### 4.1 The card (one PR-sized task)

A card is a JSON file `plan/cards/<id>.json` committed on `plan/<nonce>` (schema in §9.1). Fields:

| Field | Rule |
|---|---|
| `id` | `<lane>-<nn>[a-c]-<slug>`, sorted order = default priority (`platform-01-gate` … `product-13b-personas-readme`) |
| `step` | 1-14, the lens-4 §D step it implements |
| `decision_ids[]` / `finding_ids[]` | ids from `plan/decisions.json` and `workflow-findings.md`; the card quotes ONLY the decided value / the CORRECTED line (planner rule; checked by `verifier mode:'plan'`) |
| `in_scope[]` / `out_of_scope[]` | out_of_scope always includes the lens-4 §E ship-but-flag defaults that stay OFF unless the card is the one that flags them |
| `files_allowed[]` / `deps_allowed[]` / `new_modules[]` | the builder's write set; any hunk outside it fails the gate's scope step (`gate.sh` step 7) |
| `tests_allowed[]` | test files the author may create; existing test files listed here may be modified by the author only (the gate card lists `tests/protected.txt`) |
| `dod[]` | ≤ 8 lines `{id, command, expect}`; `expect` ∈ `exit0 | exit_nonzero | regex:<pattern> | json:<path>=<value>`; every line runnable on CPU under `$VENV` |
| `verification_level` per DoD line | `local-mechanical | local-stub | staging-required | owner-required` (F-37); a `staging-required` line is never a `pass` in R1, it is `deferred` and appears in C1/C2 |
| `depends_on[]` | card ids; the DAG must be acyclic (JS check) |
| `size` | `S` (≤120 changed lines) or `M` (≤300); no `L` — an `L` fails plan verification |
| `protected_touch` | `true` only on `platform-01-gate` (the only card that may edit `gate.sh`, `tests/protected.txt`, `ruff.toml`, `pytest.ini`, `tools/claim_lint.py`, `.gitattributes`) |
| `risk` | `none | security | persona | catalog`; `security` → reading list ≤ 6 files and `effort:'xhigh'` on its verifier; `persona` → the card forbids `git log/show` on `system_prompt.py` and lists only the G-19 role names; `catalog` → provenance fields mandatory |
| `apis_expected[]` | symbols from `plan/api-ledger.json` the card will use (gate apicheck input) |

### 4.2 How the 14 steps become cards (the planner's default split; R0 may refine, C0 approves)

| Step (lens-4 §D) | Cards | depends_on | risk |
|---|---|---|---|
| 1 repo + gate | `platform-01-gate` (import, junk deletion, `.gitattributes` + renormalize commit, `tests/protected.txt`, gate red-proof fixtures, persona-archive test made repo-local, `tests/test_constants_pin.py`, import-contract test) | — | protected |
| 2 lift-and-pin | `platform-02-pins` (author writes pins F1-F9; builder moves pure functions verbatim into `core/`, `--color-moved` shows moves only) | 01 | — |
| 3 thin slice | `platform-03a-types-fake` (`core/types`, `backends/base`, `backends/fake`, FakeEngine, conformance suite skeleton with fixture provenance) · `platform-03b-thin-slice` (`api/app` `/healthz` sha, `/v1/chat/completions` relay, `backends/hosted`, one `models.yaml` entry, placeholder chat via `gr.mount_gradio_app`) | 02 · 03a | — |
| 4 StreamParser | `platform-04-streamparser` (typed events, error taxonomy, `reasoning_content`; pins flip) | 03b | — |
| 5 registry/agent/session | `platform-05a-registry` (tool registry = the single `python_eval` gate; absent from API/MCP toolsets) · `platform-05b-agent-session` (`core/agent.run_turn`, `SessionStore` TTL, explicit keys) | 04 · 05a | security (05a) |
| 6 UI | `product-06-ui` (`build_ui(FakeEngine)`, selector, presets, render, history replay chat-loop-ui-1 CORRECTED) | 05b | — |
| 7 gateway hardening | `platform-07-gateway` (API key opt-in, size/role/range validation, threadpool, 429, ledger, `/v1/preflight`, `/status`) | 03b | — |
| 8 worker | `platform-08a-worker-pure` (`worker/encode`, `worker/lease`: estimator rows at a measured-or-UNVERIFIED rate, `max_time` from worker entry minus a measured margin, resume with `continue_final_message="reasoning_content"`) · `platform-08b-worker-backend` (`worker/app.py`, `backends/worker`, fallback order OFF by default) | 03a · 08a, 04 | — |
| 9 hardening | `platform-09a-pyeval-env` (env allowlist, `prctl(PR_SET_DUMPABLE,0)`, canary-secret red-proof) · `platform-09b-pyeval-runner` (`-I runner.py` with `setrlimit`, `start_new_session`, `killpg`, fresh cwd, output cap; **no `preexec_fn`**) · `platform-09c-net-guards` (SSRF at connect time, `regex` timeout, calculator allowlist, archive caps) | 05a · 09a · 05a | security |
| 10 vision | `product-10-vision` (OpenAI content parts end-to-end on the fake backend; caps; `vision:false → 400` with zero backend calls; video OFF) | 04, 06 | — |
| 11 MCP | `platform-11-mcp` (`ask/poll/status/preflight`, `chat` hidden, listing snapshot = 4 tools) — exists only if G-18 keeps MCP (§15 Q3) | 05b, 07 | — |
| 12 harness | `platform-12-harness` (12-prompt harness, `--backend fake --dry-run` default, zero-call test, `--i-accept-cost` + env flag for real backends, `max_retries=0`) | 03b | — |
| 13 catalog + personas + README | `product-13a-catalog` (`models.yaml` with `provenance{source_url, fetched_at, saved_path}`, `admission: pending`) · `product-13b-personas-readme` (G-19 set, absence test, README rendered from catalog + registry + collected count) | 12 · 06 | catalog · persona |
| 14 promotion | `platform-14-promotion-ci` (`.github/workflows/deploy.yml` with OIDC, `tools/promote.py`, health job, rollback to last-good sha; unit-tested against fakes; never executed) | 07, 08b, 12 | — |

21 cards; the persona card and the three hardening cards carry the narrow reading lists the observed safeguard kill demands (F-31, F-42).

### 4.3 DAG, waves, sizing — all plain JS (§13)

- `topoOrder(cards)` — dependencies first, ties by id; throws on a cycle or an unknown dependency (F-14, F-47).
- `waves(ordered, size)` — greedy: a wave holds up to `args.wave_size` ready cards whose `files_allowed ∪ tests_allowed ∪ new_modules` are pairwise disjoint; a card that clashes waits for the next wave (logged, never dropped).
- `args.wave_size` = 2 at cap 2 (§10), up to 12 at cap 14. The DAG's critical path (01→02→03a→03b→04→05a→05b→06→10) is 9 deep, so the same script runs as ~11 waves at cap 2 and ~9 waves at cap 14; the cap changes width, never order.
- Sizing: a builder that returns `status:'partial'` with `commits_made ≥ 1` is re-driven as a fix round with the remaining DoD lines (counts against `MAX_BUILD`); `diff_stats` from the verifier are logged; an `M` card exceeding 300 non-move lines is flagged `oversize` for the review lens `scope`, never silently accepted.

### 4.4 Worktree → branch → bundle lifecycle (every path absolute; every git command `git -C`)

```
author    : git -C $R worktree add $WT/tests-<id>-<n> -b tests/<id>-<n> <integration_head>
            write tests; commit "tests(<id>): …" (trailer Card: <id>); gate.sh --only-tests → expect RED
            git -C $R worktree remove $WT/tests-<id>-<n>            (branch survives in the store)
verifier  : git -C $R worktree add --detach $WT/red-<id>-<n> <tests_head> ; gate.sh --only-tests ; remove
builder   : git -C $R worktree add $WT/task-<id>-<n> -b task/<id>-<n> tests/<id>-<n>
            implement in commits (Claims: block + Card: trailer); gate.sh (advisory); remove worktree
verifier  : git -C $R worktree add --detach $WT/verify-<id>-<n>-<k> <task_head>
            gate.sh --card plan/cards/<id>.json --base <tests_head> ; write .gate/mutants/<id>.json ; gate.sh --mutants ; remove
fixer     : git -C $R worktree add $WT/task-<id>-<n>-fix<k> task/<id>-<n>   (branch is free: previous worktree removed)
integrator: in $R on integration/<n>: git merge --no-ff task/<id>-<n>
            conflict → git merge --abort → return hunks → integrator mode:'conflict' in $WT/conflict-<id>-<n>
            clean  → gate.sh --base <prev_head> ; git cherry integration/<n> task/<id>-<n> == "" ;
                     git bundle create <grill>/build-bundles/<n>/<seq>-<id>.bundle --all
clean-gate: git -C $R worktree add --detach $WT/clean-w<k> <head> ; gate.sh --clean ; remove
```

- Branch names carry the run nonce (F-33); a re-drive of the same card in the same run reuses the branch (idempotent: "if `task/<id>-<n>` exists, inspect `git status`/`git log`, continue from the last commit; salvage uncommitted edits as `wip(<id>): salvage` only if they compile, else discard" — F-42, T-16).
- A worktree is removed by the agent that created it, and only after `git rev-parse <branch>` equals the head it reports; the gate pre-step prunes worktrees whose branch is already merged and removes `index.lock` older than 10 min (F-33, F-42).
- The bundle after every merge is the durability mechanism until the owner creates the remote (F-2); the grill sync carries the bundles to GitHub.

### 4.5 Integration order, conflict resolution, integration test

- **Order:** strictly serial, topological, ties by id, one `integrator` call per merge (single writer of `integration/<n>`).
- **Conflict:** the integrator never resolves; it aborts and returns `{status:'conflict', hunks[]}`. A fresh `integrator mode:'conflict'` call gets ONLY the hunks and both cards, resolves in its own worktree so both cards' DoD still hold, runs `gate.sh`, commits the merge, returns the merge sha; the serial integrator fast-forwards and re-gates. One conflict call per task; a second conflict → `blocked:conflict`.
- **Lost-hunk check:** `git cherry` empty AND every `git patch-id` of the task's commits present in the integration range (computed by the integrator, asserted by the script).
- **Red after merge (F-34):** the integrator reverts the merge (`git revert -m 1`) immediately and returns `status:'reverted'`; the task becomes `blocked:gate-red-after-merge` and a fix task (`rf-…`) is queued for the next round on top of the surviving integration head. No special "integration fixer" agent.
- **Integration test:** `integrator mode:'clean-gate'` after every wave: detached clean checkout of the integration head, `gate.sh --clean` (full suite twice, conformance on the fake backend, journeys authored so far, import smoke, README render check), returns the ledger sha256. Its ledger — not any builder's — is what `satisfied()` reads.

---

## 5. Inner loop per task (exact counters and exit conditions)

```
author → confirm-RED → builder → gate → fresh verifier (verify + refute + mutants) → [fixer → verifier]≤2 → taskDone() (JS)
```

| Counter | Value | Exhaustion → typed result |
|---|---|---|
| `MAX_AUTHOR` | 2 author calls (second only if the RED check fails for a fixable reason: tests green on base, or error instead of failure) | `blocked:'tests-not-red'` |
| `MAX_BUILD` | 3 builder calls per task = 1 `implement` + ≤ 2 `fix` | `blocked:'fix-exhausted'` |
| `MAX_VERIFY` | 3 verifier calls (one per builder call) | — (bounded by `MAX_BUILD`) |
| two-strikes | if the failure fingerprint after a fix equals the previous one → stop before the next fix | `blocked:'no-progress'` |
| `MAX_NULL_RETRY` | 1 per call slot; the retry prompt is narrower (`attempt:2`, "continue from the last commit") | `blocked:'agent-null'` |
| oscillation | fingerprint sequence A→B→A | `blocked:'oscillation'` |

Step by step, with the exact exit condition of each stage:

1. **author** (`mode:'tests'`) writes the DoD tests named by the card (and nothing else), commits on `tests/<id>-<n>`, returns `{tests_head, test_paths[], red_excerpt}`. Exit: `commits_made ≥ 1` and `test_paths ⊆ card.tests_allowed ∪ tests/**new`.
2. **confirm-RED** (`verifier mode:'red'`): runs `gate.sh --only-tests <paths>` at `tests_head`; verdict `pass` only if every new test FAILS (not errors — an `ImportError` counts as expected only for modules listed in `card.new_modules`) and `pytest --collect-only` on the rest of the suite is unchanged. `fail` → author re-drive once (`MAX_AUTHOR`), then park.
3. **builder** (`mode:'implement'`) from `tests/<id>-<n>`: implements, commits per coherent step with a `Claims:` block, runs `gate.sh` (advisory; its ledger is NOT admissible), returns `{head_sha, commits_made, dod[{id, command, exit_code}], apis_used[], installed_packages:[], outward_actions_taken:[]}`. Script assertions: `repo_toplevel === args.build_repo`, both arrays empty (else the run aborts — F-35), `commits_made ≥ 1`.
4. **verifier** (`mode:'verify'`, fresh, read-only on the branch): runs `gate.sh --card … --base <tests_head>` itself; refutes every DoD line by re-running its command; writes `.gate/mutants/<id>.json` (three one-line breaks in `files_allowed`) and runs `gate.sh --mutants`; returns `{verdict, ledger_sha256, ledger_head_sha, failures[{fingerprint_input, test, first_error_line}], mutants:{written, killed}, diff_stats, hunks_cited[]}`. `pass` requires `ledger_head_sha === builder.head_sha`, gate exit 0, `killed ≥ 1` (if `written > 0`), `hunks_cited.length ≥ 1`; otherwise the schema-valid object is downgraded to `fail` in JS (F-46).
5. **fixer** (`builder mode:'fix'`): receives ONLY the verifier's `failures[]` (verbatim first error lines + test ids) and the card; never the previous builder's narrative. Then step 4 again.
6. **taskDone()** (JS, the only exit to `built`): `verify.verdict==='pass' ∧ verify.ledger_head_sha===build.head_sha ∧ dod.every(exit_code===0 ∨ verification_level≠local) ∧ build.outward_actions_taken.length===0 ∧ build.installed_packages.length===0 ∧ build.repo_toplevel===args.build_repo ∧ build.commits_made≥1`. DoD lines with `verification_level ∈ {staging-required, owner-required}` are recorded as `deferred`, never as done (F-37).

Fingerprint = `sha`-free stable string: sorted failing test ids + the first error line with digits/paths normalised (computed in JS from the verifier's typed `failures[]`, never by an agent — D-8, D-19).

---

## 6. Outer loop per wave and for the whole tree

### 6.1 Per wave (mechanical only — no LLM review per wave)

```
pipeline(wave, buildTask)  →  serial integrate (merge → gate on merged tree → cherry/patch-id → bundle)
  →  integrator mode:'clean-gate' on the wave head  →  author mode:'journeys' for the wave (composition tests, run from the next clean-gate on)
red clean-gate → the last merged task is reverted and parked; the wave head moves back; the rest of the plan continues on the surviving head
```

### 6.2 Whole tree (after the last wave; also the body of R2 and R3 on their evidence)

```
round = 0; dry = 0; seen = Set()
while (true):
  stop if satisfied() ∧ vetoes==0            → 'satisfied'
  stop if round ≥ MAX_ROUNDS (3)             → 'max-rounds'
  stop if dry ≥ 2                            → 'dry'
  stop if budget.total ∧ remaining < RESERVE → 'budget'   (also if agentCount > 800 → 'agent-cap')
  round++
  findings  = parallel(3 lenses: decision-fidelity+scope · correctness+tests-integrity · security+secrets)   // barrier: dedup needs all
  fresh     = dedup(findings, seen)  (fkey = file + '::' + normalised title; dedup vs seen, never vs confirmed)
  confirmed = pipeline(fresh, verifier mode:'refute')  → holds only with reproduction {command, exit_code, excerpt}
  fixTasks  = confirmed.map(toFixCard)  → same buildTask + serial integrate + clean-gate
  vetoes    = satisfied() ? verifier mode:'veto' (one, xhigh; last-round mandate = DoD inversion) : []
  vetoes with reproduction → fix tasks next round; without → notes (logged)
  dry = (fresh.length==0 ∧ vetoes.length==0) ? dry+1 : 0
log stop reason; every exhaustion is typed in the ledger, never a silent drop
```

`satisfied()` (JS): `cleanGate.verdict==='pass' ∧ cleanGate.head_sha===head ∧ openBlocking===0 ∧ unreviewedTasks===0 ∧ parkedCriticalPath===0`, where `openBlocking` counts confirmed findings of severity ≥ high without a merged fix, and `parkedCriticalPath` counts parked cards that are dependencies of a not-yet-built card (a parked leaf does not block `satisfied`; it is reported).

Budget reserve: `RESERVE = args.reserve_tokens ?? 120000` output tokens (clean-gate + veto + synthesizer ≈ 4 agents × ~30k); with `budget.total === null` the guard is inert and the round/agent caps are the backstop (T-4). The synthesizer always runs, inside `try/catch`, with whatever state exists (F-45).
