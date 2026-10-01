# Design A3 — Minimal scaffold (anti-overfit): the implementation workflow for the Space rebuild

- **Architect:** A3 · **Angle:** the SMALLEST set of mechanisms that still guards every failure mode F-1..F-47 and every anti-pattern (D/T/S/AP lenses) · **Written:** 2026-09-19 · read-only research; nothing under `/workspaces/agent-skills-toolchain` was modified; no `*.hf.space` URL was called; no token was sought.
- **Inputs read in full:** `DESIGN_BRIEF.md`, `DECISION-QUEUE.md` (Situation, Resolved decisions, Lens digests, Review workflow digest, Simplification RETRY), `evidence/workflow-findings.md` (all titles + every CORRECTED line), `reports/lens-4-simplification-retry.md`, `WORKFLOW_TOOL_REFERENCE.md` + the live `workflow-authoring` skill text, `research-1-doctrine.md`, `research-2-tool-native.md`, `research-3-external-sota.md`, `research-3-external-sota-DEEP.md`, `research-4-red-team.md`, `skills/workflow-authoring/templates/h6-timeout-heartbeat.md` (the tested `withTimeout`/`settle` block).
- **Facts re-measured on this box (2026-09-19, read-only):** `nproc` = 4 (workflow cap 2); `python3` = 3.14.2; `/usr/bin/python3.12` = **3.12.3** (the Space image is 3.12.12 — same minor, different patch); `pytest`, `gh`, `node`, `jq`, `docker`, `git-lfs` present; `uv`, `ruff`, `pyflakes`, `gitleaks`, `mutmut` **missing**; `libsrc/wheels/` holds gradio 6.26.0, spaces 0.51.3, transformers 5.16.1, huggingface_hub 1.32.0 (no `gradio_client`); snapshots `space-src` = `17dce0cd6bdc`, `space-latest` = `f88b1204a6af` (29 tracked files, 6 test modules); at `f88b120` `app.py`, `file_bench.py`, `openai_protocol.py`, `maintenance/keepalive.log` are `i/crlf w/crlf` and `tests/test_web_tools.py` is `i/mixed`; `claude mcp list` → "No MCP servers configured" and the session's deferred-tool list carries no `mcp__codex__*` entry → **the Codex cross-vendor rail is unavailable in this environment**; the grill folder is **not a git repo** — `save-to-repo.sh` rsyncs it into the toolchain repo every 5 min with `git add -A` → a build repo placed under the grill folder would be swept (nested `.git`, worktrees, venv) into toolchain commits.
- **UNVERIFIED (designed around, marked inline):** whether `setTimeout` exists in the Workflow sandbox (the h6 template guards for its absence; this design copies the guard); the fate of a changed `isolation:'worktree'` tree (moot: this design never uses `isolation`); implementer durations (no implementer has run — every wall-clock number below is an extrapolation from the observed 13-16 min finders / 4-5 min verifiers); whether `GITHUB_TOKEN` in this Codespace can create repos (moot: agents never try); how permission prompts surface for many concurrent subagents (guarded by the smoke run); Codespaces idle-timeout behaviour for unattended processes (owner checkpoint).

## Thesis in one paragraph

Every lens converged on the same four facts: an agent's report is not evidence; the author must not grade; loops must be bounded by counters; outward actions need a human. The doctrine's own gem-hunt warning and the DEEP lens's measurements (a 100-line agent scores >74 % on SWE-bench Verified; harness choice moves pass rate 0-8 pp but cost 40×; three agents beat five) say the rest of an elaborate scaffold is overfit. So this design has **one deterministic gate script**, **one script with four `args.stage` runs**, **six agent roles** (planner, author, builder, verifier, integrator, synthesizer — the verifier is one well-specified fresh-context role with a `mode`, not four overlapping agents), **plain-JS control flow for everything mechanical** (DAG, waves, dedup, fingerprints, counters, the `taskDone`/`satisfied` predicates, the synthesizer's row table), and **owner checkpoints as data** (`args.owner_approvals`). Each cut below is proven by pointing at the mechanism that still covers the failure mode; the coverage matrix (§12) has one row per F-1..F-47 and per anti-pattern id of all four lenses (102 rows).

---

## 1. Adopted principles (ids) and how conflicts between lenses were resolved

### 1.1 Principles adopted verbatim (they cost nothing or are non-negotiable)

| Lens | Adopted | Adopted with a narrower mechanism | Cut (see §1.4) |
|---|---|---|---|
| Doctrine D-n | D-2 freeze+hash contract · D-3 ground first (base sha via `args`) · D-5 file-disjoint units, real DAG · D-6 TDD red-proof (confirm-RED by a fresh agent) · D-7 smallest check ladder, empty check set = fail · D-8 two strikes then pivot/park (fingerprint in JS) · D-12 one shared `taskDone()` reducer · D-13 two mechanically independent signals (gate ledger ≠ verifier claim) · D-14 both-states proof of every gate (red-proof step) · D-15 verifier never authored · D-16 refute-first, enumerated verdicts · D-17 overclaim = rewrite the sentence, scoped residual never blocks · D-19 write the algorithm · D-20 typed terminal state per agent · D-21 null-tolerant, typed drop receipts, no silent caps · D-22 resume-safe by construction · D-24 gates decide, judge vetoes · D-25 journeys against the packaged deliverable · D-27 structured handoffs, synthesizer reads artifacts · D-28 owner-only actions · D-30(b,c,d) measure before seeding constants; blast-radius on deletions | D-1 (card content lives on disk at a sha; the prompt carries the path + the DoD lines, not the whole plan) · D-11 (the "artifact" is the branch + `.gate/last_run.json` + `plan/status/<id>.json`, not a prose report) · D-23 (dry counter kept; DoD-inversion folded into the veto judge's final-round mandate) · D-26 (spec compliance before quality is one verifier with an ordered rubric, not two agents) | D-4 scout:reuse per family · D-10 de-sloppify stage · D-18 ideation prompt tail (no ideation lanes in a build) · D-29 minority report (no design-choice stage inside the build; decisions are already taken) |
| Tool-native T-n | T-1 one script, several runs, checkpoint between · T-2 trigger message = only authority, carries no secret · T-4 four stop conditions, each logged · T-5 separate bounded counters · T-6 voters never authored · T-7 pipeline per task, barrier only at wave/round · T-8 enqueue order is the schedule at cap 2 · T-10 one writer per mutable thing · T-11 conflicts by a fresh call, re-gated · T-12 the gate agent's verdict is the truth · T-13 sha in every code-reading prompt · T-14/T-15 prompts and control flow pure in (args, results) · T-16 PR-sized tasks, idempotent on an existing branch · T-17 null is a result · T-18 schema every stage · T-19 effort by role · T-20 static scaling from args, budget reserve · T-21 log decisions not payloads · T-22 smoke run · T-23 characterisation pins first · T-24 synthesizer last, never edits · T-25 read the journal first | T-3 (only the JS predicate can say `satisfied`; the judge can only veto) · T-9 (worktree per mutating agent, but created by the agent with `git -C $BUILD_REPO worktree add`, never `isolation:'worktree'` — F-1) | — |
| External S-n (research-3) | S-1 executable spec · S-2 script flips `passes` · S-3 outcome in the environment (ledger) · S-5 locked oracle · S-6 tamper detection from the diff, deterministic · S-7 structure not instructions · S-11 refute-first with reproduction · S-12 complete suite from a clean checkout · S-14 handoff schema · S-15 fix driven by a failing signal · S-16 fix loop ≤3, dry/oscillation → park · S-17 deterministic gates layered · S-18 replay-safe · S-19 HITL for outward actions · S-20 claims reconciled with the diff · S-21 zero secrets in the runtime, OIDC in CI · S-22 headless Gradio contract · S-23 Spaces CI contract (written + unit-tested, never executed by agents) · S-24 scale to the ask | S-4 (composition journeys are authored AFTER the wave by the author role — hidden by time, not by ACL) · S-8 (three scripted one-line mutants per task applied by the gate, not `mutmut` — not installed, whole-suite mutation is wall-clock-prohibitive at cap 2) · S-9 (`hypothesis` properties optional, never a gate) · S-10 (fresh context + binary rubric; no 3-judge panel, no pairwise swap) · S-13 (context-centric split accepted for the builder's OWN additive unit tests only; DoD tests stay with the author) | S-25 transcript monitor |
| External DEEP S-n / AP-n | S-1..S-9, S-12, S-14..S-22 as above; **S-11** (never position-swap alone on adversarial checks — no swaps used at all) | S-10 (structured verdict; no S8 pairwise protocol because no A/B comparison exists inside a build) · S-13 (three lenses in the whole-tree review, one refuter per finding; no cross-family — unavailable) | — |

### 1.2 Where the two external runs disagree, and which I follow

| Topic | research-3 | research-3-DEEP | Followed | Why |
|---|---|---|---|---|
| Pairwise judging | S-10: pairwise with position swap | S-11: swap alone hurts −3..−13 pp on adversarial/clear-cut checks | DEEP | Every judgement in a build is a clear-cut check (does the evidence hold?), not an A/B preference; no pairwise stage exists, so the question is moot but the rule is recorded. |
| Held-out tests | S-4: hidden compositional tests, applied like SWE-bench gold patches | notes EvilGenie found little gain from held-out tests on small functions; stresses verification diversity | DEEP, adapted | Hiding a branch from a builder in one object store is not enforceable; composition journeys are written after the wave by the author role, so the builder could not have seen them. Same effect, no ACL fiction. |
| Mutation testing | S-8: `mutmut` incremental, ≥70 % kill rate | Meta ACH: a few targeted mutants per concern | DEEP | `mutmut` is not installed; three scripted one-line mutants per task, applied by `gate.sh --mutants`, are deterministic and cheap. |
| Process monitor | S-25: cheap transcript monitor after each implementer | "don't optimise against the monitor" | neither | The script has no filesystem access and the subagent transcript path is a harness internal; the guard would be UNVERIFIED by construction. Covered instead by the gate's tamper/idiom/claim lints (matrix rows S-AP-3, S-AP-6). |
| Cross-family critic | S-10: strongest model as judge | S-13: one refuter via Codex "if reachable" | degrade | Codex MCP is not mounted (verified). Fresh Claude verifier at `effort:'xhigh'` on the three irreversible surfaces; the degradation is logged in the run report. |

### 1.3 Conflicts between lenses and decisions, and the resolution

| # | Conflict | Resolution |
|---|---|---|
| C-A | D-1 "embed the full work-unit text in the prompt" vs F-15/T-10 "carriers are files + git" | Files + git win. The card is committed at `plan/cards/<id>.json` on the plan branch; the prompt carries the card path, the plan sha and the DoD lines verbatim (small). Prompts stay stable and cacheable; the content is pinned by sha. |
| C-B | D-5/T-9 `isolation:'worktree'` vs F-1 (cwd is the toolchain repo) | Never `isolation`. Every mutating agent runs `git -C "$BUILD_REPO" worktree add "$WT/<id>-<nonce>" -b <branch> <base>` itself and returns `repo_toplevel`; the script asserts it equals `args.build_repo`. |
| C-C | S-13 "the feature agent handles its own tests" vs the brief's non-negotiable "test author ≠ implementer" | The decision wins. DoD tests are written by the author role before the builder exists; the builder may ADD unit tests (additive only) — `gate.sh` fails any modification or deletion of a test file that existed at the author's commit. |
| C-D | T-3 three-lens judge majority emits `satisfied` vs D-24 "judges veto, never grant" and the brief's "deterministic gates decide" | `satisfied()` is a JS predicate over the ledger (clean-checkout gate green ∧ no open reproduced blocking finding ∧ no unreviewed task ∧ no veto). One fresh judge agent per round may only add vetoes, each with a reproduction. |
| C-E | D-23 two dry rounds + a DoD-inversion scout vs minimal agent count | The dry counter is kept (it is a counter). The inversion mandate ("start from the decision sheet and the cards; find an omitted obligation") is the veto judge's prompt on the last round — one agent, not two. |
| C-F | research-3 S-19 rates "push branch / deploy staging" as medium-risk autonomous vs the brief: outward actions never unattended | Brief wins. No agent pushes anything; CI pushes; the owner triggers CI. R2/R3 consume evidence directories the owner/CI produced. |
| C-G | D-28 terminal state "PRs open on the private GitHub repo" vs F-35 (no repo exists; creation is owner-gated) | R1's terminal state is a local integration branch + bundles under the grill folder (synced by the owner's script) + a checkpoint request that lists the exact `gh repo create --private` / `git push` commands for the owner. |
| C-H | Decision M-5 "everything in one release" vs S-24/DEEP "fewer parallel tasks, minimal scaffold" | The decision wins on scope; the design keeps the work PR-sized (18-24 cards) and integrates incrementally on the local integration branch; production still sees one promotion. |
| C-I | D-10 de-sloppify stage | Cut. The reason for D-10 (negative instructions in the implementer prompt degrade testing) is removed at the root: the builder prompt carries intent and the card; every "do not" lives in `gate.sh`. |
| C-J | D-15/C-8 cross-vendor second judge on irreversible surfaces | Unavailable (verified). Fresh Claude verifier, `effort:'xhigh'`, on the hardening, credential and promotion-readiness cards; recorded as `judge_rail: 'claude-fresh'` in the ledger. |
| C-K | Decision G-15 (in-container hardened `python_eval`) vs the lens recommendation of a sandbox; decision G-19 (personas without the filter-evasion clause) vs any "SOTA on all levels" reading | Decisions win; the planner emits `plan/decisions.json` (id → decided value → consequence) and cards cite only the decided value; the review lens `decision-fidelity` diffs behaviour against the sheet; the persona card forbids reading `system_prompt.py` history. |
| C-L | Owner instruction "verify → audit → implement → fix → critic → review loop until satisfied, then a final synthesizer" vs minimal roles | All six verbs exist as stages; four of them are the same `verifier` role in different modes (`red`, `verify`, `review`, `veto`), which is what keeps the author/judge separation exact while cutting overlapping agents. |

### 1.4 What I cut and why it is still covered (each cut names the mechanism and the matrix rows)

| Cut | Was proposed by | Still covered by | Matrix rows |
|---|---|---|---|
| Separate **refuter** agents (3 per finding, majority) | T-n §4.7, S-11, DEEP S-8 | One `verifier` call in `mode:'refute'` per fresh finding, refute-first mandate, `reproduction` required for `holds`; no reproduction → `unverified`, logged, never actioned | F-12, F-30, S-AP-1, S-AP-14, SD-AP-4 |
| Separate **auditor** (decision fidelity) per task | T-n §3.2 | `plan/decisions.json` + cards quoting only CORRECTED text (planner rule, checked by `verifier mode:'plan'` and the owner at C0) + whole-tree review lens `decision-fidelity` | F-9, F-10, F-16 |
| Separate **critic** per task | T-n §4.5, D-29 | DoD lines are commands with exit codes (`taskDone()`), composition journeys after each wave, whole-tree review with 3 lenses whose findings need reproduction | F-19, F-20, S-AP-4, S-AP-2 |
| **Judge panel** (3 votes → `satisfied`) | T-3 | `satisfied()` predicate in JS + one veto-only judge with reproduction | AP-6, C-2, S-AP-11 |
| **Synthesizer-verifier** agent | F-40 guard | The script computes the per-task status table from `ledger[]` and passes it as the only input; the synthesizer's `rows` are compared to the script's rows in JS and overwritten on mismatch (logged) | F-40, AP-2, AP-15 |
| Per-**wave LLM review** | brief §6 wording | `gate.sh` after every merge on the merged tree, `gate.sh --clean` from a detached clean checkout after every wave, composition journeys per wave; the LLM review runs once per whole-tree round | F-34, F-32, AP-15 |
| Dedicated **conflict-resolver role** | T-11 | Same `integrator` role, fresh call, `mode:'conflict'`, receives only the conflicting hunks + both cards; re-gated | F-32, T-AP-7 |
| **Transcript monitor** | S-25 | Deterministic tamper/idiom/claim lints in `gate.sh`; commit-per-step; nothing routes on prose | S-AP-3, S-AP-6, SD-AP-2 |
| **`mutmut`** kill-rate gate | S-8 | `gate.sh --mutants`: three scripted one-line breaks authored by the verifier after reading the diff, each must turn the task's tests red; deterministic application | F-20, SD-AP-3 |
| **Hidden held-out branch** | S-4 | Composition journeys written after the wave by the author role (builder could not have seen them); run by the gate in the next round | S-AP-4 |
| `isolation:'worktree'` | T-9, D-5 | Agent-created worktrees inside `$BUILD_REPO`; `repo_toplevel` asserted by the script | F-1, F-33, AP-14 |
| **Plan-critic** as a separate role | T-n §4.3 | `verifier mode:'plan'` (same fresh-context role) + JS checks (acyclic DAG, disjoint `files_allowed`, non-empty DoD commands) + owner checkpoint C0 | F-13, F-14, F-46 |
| **DoD-inversion scout** | D-23 | Veto judge's last-round mandate | AP-11 |
| **Cross-vendor judge** | D-15, DEEP S-13 | Unavailable; fresh Claude at `xhigh`; logged | AP-6 |
| **Scout:reuse / de-sloppify / minority report** | D-4, D-10, D-29 | Not failure modes in the matrix; the plan is already fixed by the decisions and the 14 steps | — |
| **State-probe agent before every cached sha** | F-43 guard | The integrator's merge of a missing ref returns `status:'missing-ref'`; the script re-drives the builder with an `attempt` suffix in the prompt (cache miss by construction) | F-43 |

---

## 2. Run structure

One script, `space-rebuild.js`, four runs selected by `args.stage`. A run never pauses for a human (the harness cannot grant consent inside a run — T-1/T-2); every outward-facing action is a **checkpoint object** returned by the script, executed or approved by the owner in their own message, whose words launch the next run. The orchestrator computes `args` with `git rev-parse` immediately before each invocation (F-43).

### 2.0 P0 — orchestrator pre-flight (outside the script, before R0)

1. `mkdir -p /workspaces/space-build` (durable, outside the cwd repo and outside the grill rsync); copy `libsrc/` to `/workspaces/space-build-libsrc` (the scratchpad copy is volatile); `chmod -R a-w` both snapshots.
2. Snapshot the toolchain repo status: `git -C /workspaces/agent-skills-toolchain status --porcelain > <grill>/build-bundles/toolchain-status.txt` → `args.toolchain_status_sha256`.
3. Regex-scan every file the agents will read (`DECISION-QUEUE.md`, `evidence/**`, the snapshots) for `ghp_|github_pat_|sk-ant-|hf_[A-Za-z0-9]{20,}`; redact hits before launch (F-7). The trigger message contains no secret and states the authority rules verbatim (§13 `AUTHORITY`).
4. Owner checklist (recorded in the run report as owner actions, never done by agents): send the other agent's stop notice; disable both Windows scheduled tasks; rotate the token that agent uses; revoke the pasted token; delete `NF4_EXPORT`/`NF4_UPLOAD_TOKEN` secrets; set the Codespace idle timeout to the maximum and keep a client attached; disable the HF connector's write tools for the build session (F-6, F-35, F-38, F-44).
5. Smoke run: `args.smoke = true` (R1 with one S-sized card) to surface permission prompts, the worktree mechanics and every schema (F-46, F-47).

### 2.1 The four runs

| Run | `args.stage` | Preconditions (asserted by the script from `args`) | Produces (durable) | Checkpoint object emitted |
|---|---|---|---|---|
| **R0 plan** | `plan` | `build_repo` exists and `git rev-parse HEAD == base_sha` (`f88b1204a6af…`); venv built by the setup stage (idempotent); snapshots read-only | branch `plan/<nonce>`: `plan/decisions.json` (one line per G/M id → decided value → consequence), `plan/cards/*.json` (18-24 cards), `plan/index.json` (DAG), `plan/api-ledger.json` (symbols the plan needs with `libsrc` path:line), `AGENTS.md` for the build repo | **C0** `kind:'approve-plan'`: the owner reads `decisions.json` + `index.json`; approves by passing `args.plan_sha` to R1. Also lists `kind:'record-fixture-1'` (one metered router call, cents) as OPTIONAL-before-R1 with the consequence if skipped (§15 Q2). |
| **R1 build** | `build` | `plan_sha` approved; `integration_sha_at_launch == git rev-parse integration/<nonce>` (or absent on first launch); `owner_approvals` present (all outward fields may be null) | branch `integration/<nonce>`; per-task branches `tests/<id>-<nonce>`, `task/<id>-<nonce>`; `.gate/last_run.json` per checkout; `plan/status/<id>.json`; bundles `<grill>/build-bundles/<nonce>/*.bundle` after every merge; `RUN-REPORT-<nonce>.md`; `deploy.yml`/`promote.py` written and unit-tested against fakes, never executed | **C1** `kind:'create-github-repo' + 'push-integration' + 'create-staging-spaces' + 'set-staging-secrets' + 'record-fixture-1'` with exact commands, blast radius, rollback, cost; plus `blocked_on_owner[]` and `parked[]` |
| **R2 stage** | `stage` | `owner_approvals.github_repo_url`, `staging_evidence_dir` (CI artifacts the owner's pipeline produced: `space-runtime.json`, `build-log.txt`, `canary.json`, `healthz.json`), `fixture1_path` (or null) | staging-only failures turned into fix tasks through the same inner loop; `evidence/staging/<sha>/` copied into the repo; updated bundles; report | **C2** `kind:'run-hf-job-quantize'` (paid; only if the worker card is in scope) · `kind:'promote-production'` with the promotion runbook (step 0: assert Space HEAD == base or adopt the delta — F-38) |
| **R3 promote** | `promote` | `production_evidence_dir` (post-promotion CI artifacts: running sha, canary ×3, rollback-drill record) | final synthesizer report; `owner_actions[]` (token revocations, scheduled-task cleanup, Dev Mode off) | **C3** `kind:'none'` or `kind:'rollback'` with the exact `promote.py --to <last_good_sha>` command |

The R2/R3 verifiers read files; they never call a Space. The canary and the rollback drill are executed by the CI workflow the R1 build wrote (Trusted Publisher OIDC; `hf spaces wait --timeout`; `fetch_space_logs(build=True)` on failure; 16-token generation ×3 = pass^3; `/healthz` sha == pushed sha; visibility assertion `private`) — and the owner triggers that CI run. This is what makes "never call `*.hf.space` from an agent" an invariant of the workflow, not only of this research session.

### 2.2 The checkpoint object (returned by the script; the synthesizer only renders it)

```json
{
  "stage": "build", "nonce": "r1a", "status": "ready|blocked|failed",
  "head_sha": "…", "integration_branch": "integration/r1a",
  "actions": [
    { "id": "C1-1", "kind": "create-github-repo", "why": "G-1a: GitHub is the SSOT; CI the only production writer",
      "exact_steps": ["gh repo create Prekzursil/qwen38-heretic-space --private --disable-wiki", "git -C /workspaces/space-build remote add origin <url>", "git -C /workspaces/space-build push -u origin integration/r1a plan/r1a"],
      "blast_radius": "new private repo; nothing public", "rollback": "gh repo delete (irreversible) — or leave empty", "cost_estimate": "0", "evidence_paths": [".gate/last_run.json"] }
  ],
  "blocked_on_owner": [ { "task_id": "platform-14", "field": "owner_approvals.github_repo_url", "why": "promotion pipeline cannot be exercised without a remote" } ],
  "parked": [ { "task_id": "…", "reason": "fix-exhausted|agent-null×2|gate-red-after-merge|no-progress" } ],
  "next_args": { "stage": "stage", "plan_sha": "…", "integration_sha_at_launch": "…" }
}
```

`kind` is an enum: `approve-plan · record-fixture-1 · create-github-repo · push-integration · create-staging-spaces · set-staging-secrets · run-hf-job-quantize · promote-production · rollback · revoke-token · disable-scheduled-tasks · none`. Every entry is computed in JS from typed ledger states; no agent can add or remove an action.

---

## 3. Agent roles and the separation table

Six roles. A role is a prompt preamble + a schema + a fixed set of allowed actions; a `mode` narrows the task without changing the role's rights. Every call is a fresh `agent()` (fresh context); nothing is ever passed the previous agent's narrative — only card paths, shas, diff ranges and the gate ledger.

| Role | Modes | May write | May never | Votes on | Effort | Model | Reading-list cap |
|---|---|---|---|---|---|---|---|
| **planner** (R0 only) | `plan` | `plan/**`, `AGENTS.md` on branch `plan/<nonce>` | code, tests, gate files | nothing | high | inherit | DECISION-QUEUE resolved decisions + lens-4 §B/§D/§E/§F + every CORRECTED line + red-team §1-§3 |
| **author** | `tests`, `journeys` | new test files under `tests/` on branch `tests/<id>-<nonce>` (or `tests/journeys-w<k>-<nonce>`); `tests/protected.txt` only from the gate card | any non-test file; any existing test file unless the card lists it; `system_prompt.py` history | nothing | medium | inherit | the card + `core` interfaces named in the card + `plan/api-ledger.json` |
| **builder** | `implement`, `fix` | files in `card.files_allowed` + NEW files under `tests/unit/` on branch `task/<id>-<nonce>` | existing test files, protected files, gate files, requirements outside `deps_allowed`, anything outside `files_allowed`; installing packages; any outward action | nothing (returns evidence, not verdicts) | high | inherit (retry after a null: narrower reading list, same model) | the card + `plan/decisions.json` + `plan/api-ledger.json` + the files in `files_allowed` (+ `libsrc` paths the ledger names) |
| **verifier** | `plan`, `red`, `verify`, `refute`, `review`, `veto`, `evidence` | `.gate/mutants/<id>.json` (mode `verify`), `plan/findings/<round>.json` (mode `review`) — nothing on any branch | any source or test file; any branch; approving | the ONLY role that returns a verdict; verdicts are `pass|fail|unverified|refuted|holds|veto` and a `pass` requires `ledger_sha256 == sha256(.gate/last_run.json)` for `head_sha` | medium; **xhigh** for `veto` and for cards tagged `risk:'security'` | inherit | mode-specific: `verify` = card + `git diff base..head` + ledger; `review` = one lens + the integration diff since last round; `veto` = decision sheet + index + ledger |
| **integrator** | `setup`, `merge`, `conflict`, `clean-gate`, `bundle` | `integration/<nonce>` (serial, single writer); venv/gate files under `/workspaces/space-build*` (mode `setup` only); bundles | task branches; source edits except conflict hunks (mode `conflict`, in its own worktree, re-gated) | nothing | medium; high for `conflict` | inherit | two cards + hunks (`conflict`); nothing else |
| **synthesizer** | `report` | `RUN-REPORT-<nonce>.md` under the grill folder | any branch, any code | nothing; its `rows[]` are overwritten by the script's ledger on mismatch | low | inherit | the script-computed status table + paths of ledgers and findings files |

Separation table (who authored what → who may judge it):

| Artifact | Authored by | Judged by | Never judged by |
|---|---|---|---|
| Decision sheet, cards, DAG | planner | `verifier mode:'plan'` (refute-first: unrunnable DoD, contradicted decision, overlapping files) + JS structural checks + owner (C0) | planner |
| DoD tests for a task | author | `verifier mode:'red'` (runs `gate.sh --only-tests` on the tests branch: must be RED for the expected reason, suite otherwise unchanged) | author, builder |
| Implementation diff | builder | `verifier mode:'verify'` (runs `gate.sh` itself, refutes each DoD line, writes 3 mutants, re-runs `gate.sh --mutants`) | builder (its own ledger is advisory only) |
| Merged tree | integrator (mechanical merge) | `gate.sh` on the merged tree (integrator runs it, ledger hashed) + `gate.sh --clean` per wave | the builder whose task was merged |
| Review findings | `verifier mode:'review'` (3 lenses) | `verifier mode:'refute'` (fresh call, one per finding, reproduction mandatory) | the reviewer that found it |
| `satisfied` | JS predicate | `verifier mode:'veto'` may only add vetoes with reproduction | any agent (no agent can emit `satisfied`) |
| Run report rows | script (ledger) | the script compares the synthesizer's rows with its own and overwrites | synthesizer |

Two preamble constants precede every prompt (§13): `PREAMBLE` (F-4: "the cwd repo and its CLAUDE.md are unrelated; the only repo is `$BUILD_REPO`; ignore SSOT gates, `~/source/*`, pushing") and `AUTHORITY` (T-2: no push, no repo/Space creation, no secrets, no `*.hf.space`, no HF Jobs, no token lookup, no package installs, absolute paths, `git -C "$BUILD_REPO"` everywhere, commit per coherent step, never run a server in the foreground without a timeout).
