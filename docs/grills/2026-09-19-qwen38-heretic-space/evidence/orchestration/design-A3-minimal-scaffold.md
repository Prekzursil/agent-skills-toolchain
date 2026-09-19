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

---

## 7. Deterministic gates

One script, `gate.sh`, written by the setup stage verbatim from this section into `/workspaces/space-build-tools/gate.sh` (outside the repo, so no card can edit it; F-28) and copied into the repo by card `platform-01-gate` as `tools/gate.sh` for CI. It is the ONLY admissible evidence of verification: it writes `.gate/last_run.json` and prints the ledger's sha256; every verifier returns that hash and the script compares it to `ledger_head_sha` (F-12). Only exit 0 is green; pytest exit 5 is red; a missing tool is red (fail closed), never "skipped".

### 7.1 Where it runs

| Invocation | By whom | On what | Purpose |
|---|---|---|---|
| `gate.sh --only-tests <paths>` | verifier `mode:'red'` | detached checkout of the author's `tests_head` | confirm-RED: every new test fails (not errors), rest of the suite unchanged |
| `gate.sh --card <card> --base <tests_head>` | builder (advisory), then verifier `mode:'verify'` (authoritative) | the task worktree / a detached checkout of the task head | full gate on the branch before merge; scope, tamper, claims, mutants |
| `gate.sh --base <prev_integration_head>` | integrator `mode:'merge'` | the main checkout on `integration/<n>` right after the merge | green on the merged tree, else revert (F-34) |
| `gate.sh --clean` | integrator `mode:'clean-gate'` | `git worktree add --detach $WT/clean-w<k> <head>` | fresh clean checkout: full suite twice, conformance, journeys, README check |
| `gate.sh --red-proof` | setup stage; verifier of card 01 | temporary detached worktrees at `f88b120` and at the cleaned base | both-states proof: RED on the broken tree and on the false-claim fixture, GREEN on the cleaned base (F-14, F-28) |
| `gate.sh --mutants <file>` | verifier `mode:'verify'` | the task checkout | three one-line breaks each turn the task's tests red (F-20) |

### 7.2 `gate.sh` (exact contents)

```bash
#!/usr/bin/env bash
# gate.sh — the only admissible evidence of verification for the Space rebuild.
# Runs ONLY under the pinned 3.12 venv. Fails closed: a missing tool, a wrong interpreter,
# pytest exit 5, or any blocking step != 0 makes the gate RED. Writes .gate/last_run.json
# and prints "LEDGER_SHA256 <hex>" as its last line. Exit 0 == green, nothing else is.
set -u
: "${VENV:?VENV (path of the 3.12 venv) is required}"
PY="$VENV/bin/python"
MODE=full; BASE=""; CARD=""; ONLY_TESTS=(); MUTANTS=""; OUT=""; CLEAN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --base) BASE="$2"; shift 2;;      --card) CARD="$2"; shift 2;;
    --only-tests) shift; while [ $# -gt 0 ] && [ "${1#--}" = "$1" ]; do ONLY_TESTS+=("$1"); shift; done; MODE=only-tests;;
    --mutants) MUTANTS="$2"; MODE=mutants; shift 2;;
    --clean) CLEAN=1; shift;;         --red-proof) MODE=red-proof; shift;;
    --out) OUT="$2"; shift 2;;        *) echo "gate.sh: unknown arg $1" >&2; exit 64;;
  esac
done
REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "gate.sh: not inside a git checkout" >&2; exit 65; }
cd "$REPO" || exit 65
GITDIR="$(git rev-parse --git-dir)"; HEAD_SHA="$(git rev-parse HEAD)"
[ -n "$BASE" ] || BASE="$(git rev-parse HEAD~1 2>/dev/null || echo "$HEAD_SHA")"
[ -n "$OUT" ] || OUT="$REPO/.gate/last_run.json"; mkdir -p "$(dirname "$OUT")" "$REPO/.gate"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; STEPS=(); RED=0
step() { # name exit_code summary blocking(1|0)
  local n="$1" c="$2" s="$3" b="${4:-1}"
  STEPS+=("$("$PY" -c 'import json,sys; print(json.dumps({"name":sys.argv[1],"exit_code":int(sys.argv[2]),"summary":sys.argv[3][:400],"blocking":sys.argv[4]=="1"}))' "$n" "$c" "$s" "$b")")
  if [ "$b" = "1" ] && [ "$c" != "0" ]; then RED=1; fi
}
finish() { # write the ledger, print its hash, exit
  local counts="${PYCOUNTS:-null}" rp="${REDPROOF:-null}" mu="${MUTRES:-null}"
  "$PY" - "$OUT" "$HEAD_SHA" "$STARTED" "$MODE" "$counts" "$rp" "$mu" "${STEPS[@]}" <<'PYEOF'
import json, sys, hashlib, platform
out, head, started, mode, counts, rp, mu, *steps = sys.argv[1:]
led = {"head_sha": head, "python": platform.python_version(), "started_at": started, "mode": mode,
       "steps": [json.loads(s) for s in steps], "pytest": json.loads(counts), "red_proof": json.loads(rp), "mutants": json.loads(mu)}
led["green"] = all(s["exit_code"] == 0 for s in led["steps"] if s["blocking"])
data = json.dumps(led, indent=1, sort_keys=True).encode()
open(out, "wb").write(data)
print("LEDGER_SHA256", hashlib.sha256(data).hexdigest())
PYEOF
  exit "$RED"
}
# ---- 0. pre-step: interpreter, stray servers, stale lock ----------------------------------
PYV="$("$PY" -V 2>&1)"; case "$PYV" in "Python 3.12."*) step interpreter 0 "$PYV";; *) step interpreter 1 "refusing: $PYV is not 3.12.x"; finish;; esac
for t in ruff pytest; do [ -x "$VENV/bin/$t" ] || { step "tool:$t" 1 "missing in venv (fail closed)"; }; done
pgrep -f "python.*$REPO" 2>/dev/null | grep -v "^$$\$" | xargs -r kill 2>/dev/null; step stray-servers 0 "killed listeners started from $REPO" 0
find "$GITDIR" -maxdepth 1 -name index.lock -mmin +10 -delete 2>/dev/null; step index-lock 0 "stale index.lock older than 10 min removed" 0
if [ "$CLEAN" = "1" ]; then
  if [ -n "$(git status --porcelain -uall)" ] || git symbolic-ref -q HEAD >/dev/null; then step clean-checkout 1 "--clean requires a detached, pristine checkout"; else step clean-checkout 0 "detached at $HEAD_SHA, tree clean"; fi
fi
[ "$RED" = "1" ] && finish
# ---- helper: run pytest under a scrubbed env (no inherited secrets; network blackholed) -----
PYTEST_ENV=(env -i PATH="$VENV/bin:/usr/bin:/bin" HOME="$TMP" LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
            HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 NO_PROXY=127.0.0.1,localhost
            CANARY_SECRET=canary-9f3e-not-a-secret QWEN_STUB=1)
run_pytest() { # tag paths...
  local tag="$1"; shift
  "${PYTEST_ENV[@]}" "$PY" -m pytest -q -p no:cacheprovider --disable-socket --allow-hosts=127.0.0.1 \
      --junitxml="$TMP/junit-$tag.xml" "$@" >"$TMP/pytest-$tag.log" 2>&1; echo $?
}
counts() { "$PY" - "$1" <<'PYEOF'
import sys, json, xml.etree.ElementTree as ET
try:
    r = ET.parse(sys.argv[1]).getroot(); s = r if r.tag == "testsuite" else r.find("testsuite")
    c = {"collected": int(s.get("tests", 0)), "failed": int(s.get("failures", 0)) + int(s.get("errors", 0)),
         "errors": int(s.get("errors", 0)), "skipped": int(s.get("skipped", 0))}
    c["xfailed"] = sum(1 for tc in s.iter("testcase") for sk in tc.findall("skipped") if "xfail" in (sk.get("type") or "") or "xfail" in (sk.get("message") or ""))
    c["passed"] = c["collected"] - c["failed"] - c["skipped"]
    c["outcomes"] = sorted(f'{tc.get("classname")}::{tc.get("name")}:{"F" if tc.find("failure") is not None else "E" if tc.find("error") is not None else "S" if tc.find("skipped") is not None else "P"}' for tc in s.iter("testcase"))
    print(json.dumps(c))
except Exception as e:
    print(json.dumps({"collected": 0, "error": str(e)}))
PYEOF
}
# ---- MODE only-tests: confirm-RED ----------------------------------------------------------
if [ "$MODE" = "only-tests" ]; then
  rc="$(run_pytest red "${ONLY_TESTS[@]}")"; PYCOUNTS="$(counts "$TMP/junit-red.xml")"
  # RED means: exit != 0, every new test failed or errored-as-expected, none passed.
  verdict="$("$PY" - "$PYCOUNTS" "$rc" <<'PYEOF'
import json, sys; c = json.loads(sys.argv[1]); rc = int(sys.argv[2])
ok = rc != 0 and c.get("collected", 0) > 0 and c.get("passed", 1) == 0
print("0" if ok else "1", f'collected={c.get("collected")} passed={c.get("passed")} failed={c.get("failed")} errors={c.get("errors")} rc={rc}')
PYEOF
)"; step confirm-red "${verdict%% *}" "${verdict#* }"
  finish
fi
# ---- MODE mutants: each scripted break must turn the card's tests red ----------------------
if [ "$MODE" = "mutants" ]; then
  MUTRES="$("$PY" - "$MUTANTS" "$CARD" "$VENV" "$TMP" <<'PYEOF'
import json, sys, subprocess, pathlib
mut, card, venv, tmp = sys.argv[1:]; ms = json.load(open(mut)); tests = json.load(open(card)).get("tests_allowed", []) if card else []
res = {"written": len(ms), "killed": 0, "detail": []}
for m in ms[:3]:
    p = pathlib.Path(m["file"]); src = p.read_text(encoding="utf-8")
    if src.count(m["find"]) != 1: res["detail"].append({"file": m["file"], "applied": False}); continue
    p.write_text(src.replace(m["find"], m["replace"]), encoding="utf-8")
    rc = subprocess.run([f"{venv}/bin/python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--disable-socket", "--allow-hosts=127.0.0.1", *tests],
                        env={"PATH": f"{venv}/bin:/usr/bin:/bin", "HOME": tmp, "HTTP_PROXY": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9", "QWEN_STUB": "1"},
                        capture_output=True, text=True).returncode
    subprocess.run(["git", "checkout", "--", m["file"]], check=False)
    killed = rc != 0; res["killed"] += killed; res["detail"].append({"file": m["file"], "applied": True, "killed": killed})
print(json.dumps(res))
PYEOF
)"; k="$("$PY" -c 'import json,sys; r=json.loads(sys.argv[1]); print(0 if (r["written"]==0 or r["killed"]>=1) else 1)' "$MUTRES")"
  step mutants "$k" "$MUTRES"; finish
fi
# ---- MODE red-proof: the gate must fire on the known-broken tree and stay green on the clean one
if [ "$MODE" = "red-proof" ]; then
  : "${BROKEN_SHA:?BROKEN_SHA (f88b120…) required}"; : "${CLEAN_SHA:?CLEAN_SHA (cleaned base) required}"
  rp='{'
  for pair in "broken:$BROKEN_SHA:1" "clean:$CLEAN_SHA:0"; do
    IFS=: read -r name sha want <<<"$pair"; wt="$TMP/rp-$name"
    git worktree add --detach "$wt" "$sha" >/dev/null 2>&1 || { rp="$rp\"$name\":\"worktree-failed\","; continue; }
    ( cd "$wt" && "$VENV/bin/ruff" check --select F821,F811,E9 --target-version py312 . >/dev/null 2>&1 ); got=$?
    git worktree remove --force "$wt" >/dev/null 2>&1
    fired=$([ "$got" != "0" ] && echo true || echo false); rp="$rp\"${name}_red\":$fired,"
    if [ "$want" = "1" ] && [ "$got" = "0" ]; then RED=1; fi;  if [ "$want" = "0" ] && [ "$got" != "0" ]; then RED=1; fi
  done
  # false-claim fixture: a commit whose message names a symbol the diff does not add → claim lint must fail
  if [ -f tests/fixtures/gate/false-claim.patch ]; then
    wt="$TMP/rp-claim"; git worktree add --detach "$wt" "$CLEAN_SHA" >/dev/null 2>&1 && ( cd "$wt" && git apply ../../tests/fixtures/gate/false-claim.patch 2>/dev/null || git apply "$REPO/tests/fixtures/gate/false-claim.patch"; git -c user.name=gate -c user.email=gate@local commit -qam "feat: add _resolve_image_urls and set TOK_PER_SEC=9.2" )
    ( cd "$wt" && CLAIM_ONLY=1 VENV="$VENV" bash "$0" --base HEAD~1 --out "$TMP/claim.json" >/dev/null 2>&1 ); got=$?; git worktree remove --force "$wt" >/dev/null 2>&1
    rp="$rp\"false_claim_red\":$([ "$got" != "0" ] && echo true || echo false),"; [ "$got" = "0" ] && RED=1
  else rp="$rp\"false_claim_red\":\"fixture-missing\","; RED=1; fi
  REDPROOF="${rp%,}}"; step red-proof "$RED" "$REDPROOF"; finish
fi
# ---- 1. hygiene: line endings, LFS, blob size, junk ----------------------------------------
bad="$(git ls-files --eol | grep -E 'i/(crlf|mixed)|w/(crlf|mixed)' | grep -vE '\.(png|jpg|gif|bin)$' | head -5)"; step eol "$([ -z "$bad" ] && echo 0 || echo 1)" "${bad:-all tracked text files are LF}"
lfs="$(git lfs ls-files 2>/dev/null | head -3)"; step lfs "$([ -z "$lfs" ] && echo 0 || echo 1)" "${lfs:-no LFS objects}"
big="$(git rev-list --objects "$BASE..HEAD" 2>/dev/null | git cat-file --batch-check='%(objecttype) %(objectsize) %(rest)' | awk '$1=="blob" && $2>5242880' | head -3)"; step blob-cap "$([ -z "$big" ] && echo 0 || echo 1)" "${big:-no blob > 5 MB in range}"
junk="$(git ls-files | grep -E '(^|/)__pycache__/|\.pyc$|(^|/)\.venv/|\.whl$|\.log$|(^|/)idx\.json$|(^|/)runlog_tail\.txt$' | head -5)"; step junk-paths "$([ -z "$junk" ] && echo 0 || echo 1)" "${junk:-no junk tracked}"
# ---- 2. undefined names + syntax under 3.12 -------------------------------------------------
if [ "${CLAIM_ONLY:-0}" != "1" ]; then
"$VENV/bin/ruff" check --select F821,F811,F401,E9 --target-version py312 --output-format concise . >"$TMP/ruff.log" 2>&1; step ruff $? "$(tail -c 300 "$TMP/ruff.log")"
"$PY" -m compileall -q -x '(\.venv|\.gate|\.git)' . >"$TMP/compile.log" 2>&1; step compileall $? "$(tail -c 200 "$TMP/compile.log")"
# ---- 3. apicheck: every symbol/kwarg the card expects exists in the pinned wheels -----------
if [ -n "$CARD" ]; then
"$PY" - "$CARD" <<'PYEOF' >"$TMP/api.log" 2>&1; step apicheck $? "$(tail -c 300 "$TMP/api.log")"
import json, sys, importlib, inspect
bad = 0
for a in json.load(open(sys.argv[1])).get("apis_expected", []):
    try:
        obj = importlib.import_module(a["module"])
        for part in a["symbol"].split("."): obj = getattr(obj, part)
        params = set()
        if a["module"].startswith("transformers") and a["symbol"].endswith("GenerationConfig"):
            params = set(vars(obj()).keys())
        else:
            try: params = set(inspect.signature(obj).parameters)
            except (TypeError, ValueError): params = set(dir(obj))
        missing = [k for k in a.get("kwargs", []) if k not in params and "kwargs" not in params]
        if missing: bad += 1; print("MISSING", a["module"], a["symbol"], missing)
    except Exception as e:
        bad += 1; print("UNRESOLVED", a, e)
print("apicheck", "ok" if not bad else f"{bad} problems"); sys.exit(1 if bad else 0)
PYEOF
fi
# ---- 4. the suite, twice, scrubbed env, network blackholed; counts vs baseline ---------------
rc1="$(run_pytest one)"; rc2="$(run_pytest two)"; C1="$(counts "$TMP/junit-one.xml")"; C2="$(counts "$TMP/junit-two.xml")"; PYCOUNTS="$C1"
v="$("$PY" - "$C1" "$C2" "$rc1" "$rc2" "$REPO/.gate/base.json" "$BASE" <<'PYEOF'
import json, sys, subprocess
c1, c2 = json.loads(sys.argv[1]), json.loads(sys.argv[2]); rc1, rc2 = int(sys.argv[3]), int(sys.argv[4])
try: base = json.load(open(sys.argv[5]))
except Exception: base = {"baseline_collected": 0, "baseline_skipped": 0}
log = subprocess.run(["git", "log", "--format=%B", f"{sys.argv[6]}..HEAD"], capture_output=True, text=True).stdout
removed = log.count("\nTests-Removed:"); skip_added = log.count("\nSkip-Added:")
probs = []
if rc1 != 0 or rc2 != 0: probs.append(f"exit {rc1}/{rc2} (only 0 is green; 5 = nothing collected)")
if c1.get("outcomes") != c2.get("outcomes"): probs.append("two runs disagree (flaky)")
if c1.get("collected", 0) < base.get("baseline_collected", 0) - removed: probs.append(f'collected {c1.get("collected")} < baseline {base.get("baseline_collected")} - removed {removed}')
if c1.get("skipped", 0) + c1.get("xfailed", 0) > base.get("baseline_skipped", 0) + skip_added: probs.append("skip/xfail count rose without a Skip-Added trailer")
print("0" if not probs else "1", "; ".join(probs) or f'collected={c1.get("collected")} passed={c1.get("passed")} identical twice')
PYEOF
)"; step pytest-x2 "${v%% *}" "${v#* }"
# ---- 5. import smoke: CPU front must import fast with no model; worker with stubs ---------------
( unset SPACES_ZERO_GPU; "${PYTEST_ENV[@]}" timeout 20 "$PY" -c "import app" ) >"$TMP/imp.log" 2>&1; step import-app $? "$(tail -c 200 "$TMP/imp.log")"
if [ -f worker/app.py ]; then ( unset SPACES_ZERO_GPU; "${PYTEST_ENV[@]}" PYTHONPATH="$REPO/tools/stubs" timeout 30 "$PY" -c "import worker.app" ) >"$TMP/impw.log" 2>&1; step import-worker $? "$(tail -c 200 "$TMP/impw.log")"; fi
fi # CLAIM_ONLY
# ---- 6. claim-vs-diff lint over every commit in range --------------------------------------
"$PY" - "$BASE" <<'PYEOF' >"$TMP/claims.log" 2>&1; step claim-lint $? "$(tail -c 300 "$TMP/claims.log")"
import re, subprocess, sys
base = sys.argv[1]; shas = subprocess.run(["git", "rev-list", "--reverse", f"{base}..HEAD"], capture_output=True, text=True).stdout.split()
waivers = 0; bad = 0
for sha in shas:
    msg = subprocess.run(["git", "log", "-1", "--format=%B", sha], capture_output=True, text=True).stdout
    diff = subprocess.run(["git", "show", "--format=", "-w", "--unified=0", sha], capture_output=True, text=True).stdout
    names = subprocess.run(["git", "show", "--format=", "--name-only", sha], capture_output=True, text=True).stdout
    hay = re.sub(r"\s+", "", diff + names)
    if "Renormalize-Only: yes" in msg:
        if subprocess.run(["git", "show", "--format=", "-w", "--numstat", sha], capture_output=True, text=True).stdout.strip(): bad += 1; print(sha[:9], "Renormalize-Only commit has non-whitespace changes")
        continue
    if "Claim-Waiver:" in msg: waivers += 1; continue
    claims = set(re.findall(r"`([^`\n]{2,80})`", msg))
    claims |= set(re.findall(r"^\s*[-*]\s*(?:add|adds|added|define|defines|implement|implements|set|sets|fix|fixes)\s+(\S+)", msg, re.I | re.M))
    claims |= set(re.findall(r"\b(\d+(?:\.\d+)?)\s*(?:tok/s|tokens?|s\b|sec|min|tests?)", msg))
    for c in sorted(claims):
        if re.sub(r"\s+", "", c) not in hay: bad += 1; print(sha[:9], "claim not in diff:", c)
if waivers > 1: bad += 1; print("more than one Claim-Waiver in range")
print("claim-lint", "ok" if not bad else f"{bad} unsupported claims"); sys.exit(1 if bad else 0)
PYEOF
[ "${CLAIM_ONLY:-0}" = "1" ] && finish
# ---- 7. scope, protected files, oracle tamper, dependency drift ---------------------------------
changed="$(git diff --name-only "$BASE..HEAD")"
if [ -n "$CARD" ]; then
"$PY" - "$CARD" "$BASE" <<'PYEOF' >"$TMP/scope.log" 2>&1; step scope-protected-tamper $? "$(tail -c 300 "$TMP/scope.log")"
import json, sys, subprocess, re, pathlib
card = json.load(open(sys.argv[1])); base = sys.argv[2]
def git(*a): return subprocess.run(["git", *a], capture_output=True, text=True).stdout
changed = git("diff", "--name-only", f"{base}..HEAD").split()
added = git("diff", "--name-only", "--diff-filter=A", f"{base}..HEAD").split()
prot = [l.strip() for l in pathlib.Path("tests/protected.txt").read_text().splitlines() if l.strip()] if pathlib.Path("tests/protected.txt").exists() else []
allowed = set(card.get("files_allowed", [])) | set(card.get("new_modules", [])) | set(card.get("tests_allowed", []))
bad = []
for f in changed:
    if f in prot and not card.get("protected_touch"): bad.append(f"protected file touched: {f}")
    elif f not in allowed and not (f in added and f.startswith("tests/unit/")): bad.append(f"outside files_allowed: {f}")
tamper = git("diff", "--name-only", "--diff-filter=MD", f"{base}..HEAD", "--", "tests/").split()
bad += [f"existing test modified/deleted by builder: {f}" for f in tamper if f not in card.get("tests_allowed", [])]
for f in changed:
    if f.endswith(".py") and not f.startswith("tests/") and pathlib.Path(f).exists():
        s = pathlib.Path(f).read_text(errors="ignore")
        if re.search(r'PYTEST_CURRENT_TEST|sys\.modules\.get\("pytest"\)|"pytest" in sys\.modules', s): bad.append(f"test-detection idiom in {f}")
for f in changed:
    if re.match(r"(worker/)?requirements.*\.txt$", f):
        for line in git("diff", f"{base}..HEAD", "--", f).splitlines():
            if line.startswith("+") and not line.startswith("+++") and line[1:].strip() and not line[1:].lstrip().startswith("#"):
                pkg = re.split(r"[<>=!~\[ ]", line[1:].strip())[0].lower()
                if pkg not in [d.lower() for d in card.get("deps_allowed", [])]: bad.append(f"dependency not in deps_allowed: {pkg}")
print("\n".join(bad) or "scope/protected/tamper/deps ok"); sys.exit(1 if bad else 0)
PYEOF
fi
# ---- 8. idiom lint (warnings the verifier must clear; the known-bad idioms from the CORRECTED lines)
idioms='preexec_fn=|__wrapped__|shutil\.rmtree[^\n]*unload|prefill_chunk_size|lease_s *- *30|Chatbot\([^)]*type=|ChatInterface\([^)]*type=|spaces\.GPU\([^)]*gpu_size=|restart_space\([^)]*revision|from gradio\.client import|read_text\([^)]*newline=|trust_remote_code=True|max_retries=[1-9]|assisted_generation|assistant_model='
hits="$(git diff "$BASE..HEAD" -- '*.py' | grep -E '^\+' | grep -nE "$idioms" | head -8)"; step idiom-lint "$([ -z "$hits" ] && echo 0 || echo 1)" "${hits:-no known-bad idiom added}" 0
# ---- 9. generated README, catalog provenance --------------------------------------------------
if [ -f tools/render_readme.py ]; then "$PY" tools/render_readme.py --check >"$TMP/readme.log" 2>&1; step readme-render $? "$(tail -c 200 "$TMP/readme.log")"; fi
if [ -f models.yaml ]; then "$PY" - <<'PYEOF' >"$TMP/cat.log" 2>&1; step catalog-provenance $? "$(tail -c 200 "$TMP/cat.log")"
import yaml, sys, pathlib, re
bad = []
for e in (yaml.safe_load(open("models.yaml")) or {}).get("models", []):
    p = e.get("provenance", {})
    if not re.fullmatch(r"[0-9a-f]{40}", str(e.get("revision", ""))): bad.append(f'{e.get("id")}: revision is not a 40-hex sha')
    if not all(p.get(k) for k in ("source_url", "fetched_at", "saved_path")): bad.append(f'{e.get("id")}: provenance incomplete')
    elif not pathlib.Path(p["saved_path"]).exists(): bad.append(f'{e.get("id")}: saved_path missing {p["saved_path"]}')
print("\n".join(bad) or "catalog provenance ok"); sys.exit(1 if bad else 0)
PYEOF
fi
# ---- 10. secrets regex over the diff range and the ledger dir ---------------------------------------
sec="$( { git diff "$BASE..HEAD"; git log -p --format=%B "$BASE..HEAD"; } | grep -nE 'ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}' | head -3)"
step secrets-scan "$([ -z "$sec" ] && echo 0 || echo 1)" "${sec:+secret-shaped string in range}${sec:-no secret-shaped strings}"
finish
```

Notes on the script (each is a design decision, not an accident):
- The pytest environment is `env -i` with a fixed `CANARY_SECRET`: tests never see the box's real `GITHUB_TOKEN`/`ANTHROPIC_API_KEY`, and the hardening red-proofs assert `CANARY_SECRET not in child_output` without ever printing an environment (F-7).
- The suite runs **twice** and both `outcomes` lists must be identical (F-29); `--disable-socket --allow-hosts=127.0.0.1` plus a blackhole proxy make network tests fail deterministically; `tests/live/` is excluded by `pytest.ini` unless the owner's `--i-accept-cost` flag is set (F-36).
- `collected` is compared to `.gate/base.json` written by the setup stage (73 at `f88b120`) minus `Tests-Removed:` trailers; skip/xfail may rise only with a `Skip-Added:` trailer (F-18).
- The claim lint fails 5 of the 6 known over-claiming commits by construction (backtick identifiers, "add/define/set X" bullets, numbers with units must appear in the whitespace-insensitive diff); the sixth is caught by `tests/test_constants_pin.py` (F-19, F-24).
- Scope/protected/tamper are one deterministic step: hunks outside `files_allowed`, protected files without `protected_touch`, any modified or deleted pre-existing test, test-detection idioms in production code, and requirement lines outside `deps_allowed` are all red (F-16, F-18, F-23, F-28).
- The idiom lint is a **warning** step (`blocking:0`) — it appears in the ledger and the verifier's schema has `warnings_cleared[]`, which must list every idiom hit with a reason (F-10). The apicheck step is blocking (F-8).
- `--red-proof` is executable evidence that the gate can fire (D-14): RED on `f88b120` (three F821 names), RED on the false-claim fixture, GREEN on the cleaned base. The setup stage records it; card 01's verifier re-records it after the gate files land in the repo.
- Everything the gate needs is in the venv the setup stage builds once (`ruff pyflakes pytest pytest-socket pyyaml openai httpx gradio-client==2.6.1` + the four wheels); every later prompt forbids installs and the schema field `installed_packages` must be empty (F-5).

---

## 8. Testability table

`verification_level` is a fixed enum on every DoD line and every finding: `local-mechanical | local-stub | staging-required | owner-required | unverified`. A keyword list in the planner prompt (`lease, quota, ZeroGPU, worker fork, Triton, fla, x-ip-token, MCP transport, Space rebuild, requirements resolution, canary, rollback, OIDC, secret`) forces at least `staging-required` (F-37). Nothing at `staging-required` or above can be `pass` in R1; it is `deferred` and becomes a line in the C1/C2 runbook with the exact measurement and the number it should record.

| Level | Proven locally in R1 (3.12 venv, no GPU, no token, network blackholed) | Requires the staging Space (R2, executed by CI, read by the workflow as files) | Requires the owner |
|---|---|---|---|
| **Static gate** | ruff F821/F811/F401/E9 @py312, compileall, apicheck against the pinned wheels, claim-vs-diff lint, EOL/LFS/blob/junk, secrets regex, import-contract test (`core/` never imports gradio/fastapi/spaces/torch), scope/protected/tamper, idiom lint, README render check, `models.yaml` schema + provenance file existence | — | — |
| **Unit / stub** | the 73 existing tests (persona-archive test made repo-local) + the F1-F9 characterisation pins; `backends/fake` + conformance suite rows `fake` and `recorded-*` (recorded rows `skipped: needs owner recording` until fixture #1 exists — counted, F-20); `core/parsing` StreamParser incl. the tool_parse known-bads (xfail → flip); `core/agent` cap/rejection/pairing with a scripted backend; `SessionStore` TTL; `worker/encode` + `worker/lease` pure functions (estimator rows at an UNVERIFIED 9 tok/s seed, `max_time` arithmetic with a placeholder cold-start margin, resume encode with `continue_final_message="reasoning_content"`); `python_eval` hardening red-proofs with `CANARY_SECRET` (env allowlist, `/proc/<ppid>/environ` unreadable after `PR_SET_DUMPABLE=0`, rlimit trips, `killpg` leaves no orphans, OFF on every surface); SSRF connect-time guard, `regex` timeout, calculator allowlist, archive caps; constants pin; persona absence test; harness `--dry-run` zero-call test; scripted mutants ×3 per task | — | — |
| **Local integration** | FastAPI `TestClient(app)` as a context manager for `/v1/*`, `/healthz` (sha), `/status`, `/v1/preflight` (auth, 429, size/role/range limits, SSE framing validated with the `openai` SDK types, `finish_reason:'length'`, `reasoning_content` round trip); `gradio_client==2.6.1` against `demo.launch(prevent_thread_lock=True, server_port=<free>)` with the `/healthz` sha asserted equal to the checkout HEAD (F-26); MCP listing snapshot = 4 typed tools, `chat` absent, `python_eval` absent from every surface (if `gradio[mcp]` installs; else `deferred`); composition journeys J1-J6 (`QWEN_STUB=1` boot < N s; turn 2 carries turn 1's tool results; two sessions get different benches; `/v1` stream stops on disconnect; MCP exposes only typed tools; `python_eval` child cannot read the parent env) | — | — |
| **Platform behaviour** | nothing (`spaces.GPU` is a no-op off-platform: `decorator.py:99-100`) | CPU Space boot + `/healthz` sha == pushed sha; worker Space import-time load under CUDA emulation; lease sizing and the measured cold-start margin; measured tok/s; quota bucket of authenticated `gradio_client` calls (quota before/after one 16-token call); fla/Triton in the forked worker; FP8 vs GPTQ load on `large`; requirements resolution on rebuild; `x-ip-token` presence; MCP over HTTP with a real client; canary pass^3; rollback rehearsal | creates the two staging Spaces (CPU front + ZeroGPU worker), the scoped inference token, sets the staging secrets |
| **Money / identity** | nothing | — | one metered router call (fixture #1); the real 12-prompt harness under a stated budget; the quantization HF Job; GitHub repo + Trusted Publisher OIDC; revoking the pasted token and the other agent's token; disabling the Windows scheduled tasks; Dev Mode off; production promotion |

**How staging/promotion requests are represented.** They are data in two places: (1) the checkpoint object (§2.2) returned by R1/R2 — `actions[]` with `kind`, exact commands, blast radius, rollback, cost; (2) in the repo, `plan/status/<id>.json` with `dod[i].status = 'deferred'` and `verification_level`, plus `evidence/staging/<sha>/EXPECTED.json` written by the R1 verifier for card 14 (the numbers the CI canary must record: sha, `finish_reason`, tokens, p95 latency, quota delta). R2 starts by asserting `args.staging_evidence_dir` contains `space-runtime.json` (`stage == RUNNING`), `healthz.json` (`git_sha == args.pushed_sha`), `canary.json` (3 runs, each `finish_reason` present, ≥ 16 tokens), `build-log.txt`; a missing or contradicting file is `blocked:'staging-evidence-missing'`, never inferred. No agent in any run performs an outward action; `outward_actions_taken` is a required array on every schema and a non-empty one aborts the run (F-35).

---

## 9. Schemas for every stage (JSON Schema; `required ⊆ properties`; enum verdicts; `sha` wherever code was read)

Design rules: root `{type:'object', properties, required}`; every verdict an enum; no free-text field longer than ~2 k characters (`maxLength` on prose); `minItems` on evidence arrays so a schema-valid-but-empty return cannot masquerade as work (F-46); a shared fragment (`COMMON`) on every schema: `repo_toplevel`, `outward_actions_taken`, `installed_packages`, `status`. The script re-validates semantics after validation (`done === every DoD line exit 0`, `pass ⇒ ledger hash match`).

```js
const COMMON = {
  repo_toplevel: { type: 'string', description: 'output of git rev-parse --show-toplevel in the checkout you worked in' },
  outward_actions_taken: { type: 'array', items: { type: 'string' }, description: 'MUST be empty: any push/repo/Space/secret/HF-job/*.hf.space action' },
  installed_packages: { type: 'array', items: { type: 'string' }, description: 'MUST be empty: pip/uv/npm installs are forbidden' },
  notes: { type: 'string', maxLength: 1500 },
}
```

### 9.1 `CARD_INDEX` (planner → script; the cards themselves are files)
```js
const CARD_INDEX = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['SUCCESS', 'FAILED'] },
  plan_sha: { type: 'string', pattern: '^[0-9a-f]{40}$', description: 'commit on plan/<nonce> holding plan/**' },
  decisions_path: { type: 'string' }, api_ledger_path: { type: 'string' },
  cards: { type: 'array', minItems: 1, items: { type: 'object', properties: {
    id: { type: 'string', pattern: '^(platform|product)-[0-9]{2}[a-c]?-[a-z0-9-]+$' },
    path: { type: 'string' }, step: { type: 'integer', minimum: 1, maximum: 14 },
    depends_on: { type: 'array', items: { type: 'string' } },
    files_allowed: { type: 'array', items: { type: 'string' } }, tests_allowed: { type: 'array', items: { type: 'string' } },
    new_modules: { type: 'array', items: { type: 'string' } }, deps_allowed: { type: 'array', items: { type: 'string' } },
    dod: { type: 'array', minItems: 1, maxItems: 8, items: { type: 'object', properties: {
      id: { type: 'string' }, command: { type: 'string', minLength: 3 }, expect: { type: 'string' },
      verification_level: { type: 'string', enum: ['local-mechanical', 'local-stub', 'staging-required', 'owner-required'] } },
      required: ['id', 'command', 'expect', 'verification_level'] } },
    size: { type: 'string', enum: ['S', 'M'] }, risk: { type: 'string', enum: ['none', 'security', 'persona', 'catalog'] },
    protected_touch: { type: 'boolean' },
    decision_ids: { type: 'array', items: { type: 'string' } }, finding_ids: { type: 'array', items: { type: 'string' } } },
    required: ['id', 'path', 'step', 'depends_on', 'files_allowed', 'tests_allowed', 'new_modules', 'deps_allowed', 'dod', 'size', 'risk', 'protected_touch', 'decision_ids', 'finding_ids'] } },
  unmapped_finding_ids: { type: 'array', items: { type: 'string' }, description: 'confirmed/partially-confirmed finding ids no card cites (must be empty or explained)' },
}, required: ['status', 'plan_sha', 'decisions_path', 'api_ledger_path', 'cards', 'unmapped_finding_ids', 'repo_toplevel', 'outward_actions_taken', 'installed_packages'] }
```

### 9.2 `TESTS` (author, modes `tests` and `journeys`)
```js
const TESTS = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['SUCCESS', 'FAILED'] },
  card_id: { type: 'string' }, branch: { type: 'string' },
  base_sha: { type: 'string', pattern: '^[0-9a-f]{40}$' }, tests_head: { type: 'string', pattern: '^[0-9a-f]{40}$' },
  test_paths: { type: 'array', minItems: 1, items: { type: 'string' } },
  commits_made: { type: 'integer', minimum: 0 },
  red_command: { type: 'string' }, red_exit_code: { type: 'integer' }, red_excerpt: { type: 'string', maxLength: 1200 },
  known_bads_xfail: { type: 'array', items: { type: 'string' } },
  mutants_suggested: { type: 'array', maxItems: 3, items: { type: 'object', properties: { file: { type: 'string' }, find: { type: 'string' }, replace: { type: 'string' } }, required: ['file', 'find', 'replace'] } },
}, required: ['status', 'card_id', 'branch', 'base_sha', 'tests_head', 'test_paths', 'commits_made', 'red_command', 'red_exit_code', 'red_excerpt', 'repo_toplevel', 'outward_actions_taken', 'installed_packages'] }
```

### 9.3 `BUILD` (builder, modes `implement` and `fix`)
```js
const BUILD = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['done', 'partial', 'failed', 'reused'] },
  card_id: { type: 'string' }, branch: { type: 'string' },
  base_sha: { type: 'string', pattern: '^[0-9a-f]{40}$' }, head_sha: { type: 'string', pattern: '^[0-9a-f]{40}$' },
  commits_made: { type: 'integer', minimum: 0 },
  changed_files: { type: 'array', items: { type: 'string' } },
  dod: { type: 'array', minItems: 1, items: { type: 'object', properties: {
    id: { type: 'string' }, command: { type: 'string' }, exit_code: { type: 'integer' }, output_tail: { type: 'string', maxLength: 600 } },
    required: ['id', 'command', 'exit_code', 'output_tail'] } },
  apis_used: { type: 'array', items: { type: 'object', properties: { module: { type: 'string' }, symbol: { type: 'string' }, kwargs: { type: 'array', items: { type: 'string' } }, ledger_ref: { type: 'string', description: 'plan/api-ledger.json entry id or libsrc path:line' } }, required: ['module', 'symbol', 'kwargs', 'ledger_ref'] } },
  gate_exit_code: { type: 'integer', description: 'advisory: your own gate.sh run; the verifier re-runs it' },
  remaining_dod_ids: { type: 'array', items: { type: 'string' } },
}, required: ['status', 'card_id', 'branch', 'base_sha', 'head_sha', 'commits_made', 'changed_files', 'dod', 'apis_used', 'gate_exit_code', 'remaining_dod_ids', 'repo_toplevel', 'outward_actions_taken', 'installed_packages'] }
```

### 9.4 `VERDICT` (verifier; every mode; the only schema with a verdict)
```js
const VERDICT = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['SUCCESS', 'FAILED'] },
  mode: { type: 'string', enum: ['plan', 'red', 'verify', 'refute', 'review', 'veto', 'evidence'] },
  target_id: { type: 'string', description: 'card id, finding id, wave id or "tree"' },
  sha: { type: 'string', pattern: '^[0-9a-f]{40}$', description: 'the exact revision you read/ran' },
  verdict: { type: 'string', enum: ['pass', 'fail', 'unverified', 'refuted', 'holds', 'veto', 'no-veto'] },
  ledger_sha256: { type: 'string', pattern: '^[0-9a-f]{64}$|^none$' }, ledger_head_sha: { type: 'string' },
  gate_exit_code: { type: 'integer' },
  checks: { type: 'array', items: { type: 'object', properties: { name: { type: 'string' }, command: { type: 'string' }, exit_code: { type: 'integer' }, output_tail: { type: 'string', maxLength: 500 } }, required: ['name', 'command', 'exit_code', 'output_tail'] } },
  failures: { type: 'array', items: { type: 'object', properties: { test: { type: 'string' }, first_error_line: { type: 'string', maxLength: 300 }, dod_id: { type: 'string' } }, required: ['test', 'first_error_line'] } },
  hunks_cited: { type: 'array', items: { type: 'string', description: 'path:line@sha' } },
  warnings_cleared: { type: 'array', items: { type: 'object', properties: { idiom: { type: 'string' }, reason: { type: 'string', maxLength: 300 } }, required: ['idiom', 'reason'] } },
  mutants: { type: 'object', properties: { written: { type: 'integer' }, killed: { type: 'integer' }, path: { type: 'string' } }, required: ['written', 'killed'] },
  diff_stats: { type: 'object', properties: { files: { type: 'integer' }, insertions: { type: 'integer' }, deletions: { type: 'integer' }, moves_only: { type: 'boolean' } }, required: ['files', 'insertions', 'deletions'] },
  findings: { type: 'array', items: { type: 'object', properties: {
    id: { type: 'string' }, title: { type: 'string', maxLength: 200 }, file: { type: 'string' },
    severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
    kind: { type: 'string', enum: ['decision-fidelity', 'scope', 'correctness', 'tests-integrity', 'security', 'secrets', 'interaction', 'omitted-obligation'] },
    reproduction: { type: 'object', properties: { command: { type: 'string' }, exit_code: { type: 'integer' }, excerpt: { type: 'string', maxLength: 500 } }, required: ['command', 'exit_code', 'excerpt'] },
    corrected_claim: { type: 'string', maxLength: 600 }, fix_hint: { type: 'string', maxLength: 600 },
    files_allowed: { type: 'array', items: { type: 'string' } },
    verification_level: { type: 'string', enum: ['local-mechanical', 'local-stub', 'staging-required', 'owner-required', 'unverified'] } },
    required: ['id', 'title', 'file', 'severity', 'kind', 'reproduction', 'verification_level'] } },
  strongest_disagreement: { type: 'string', maxLength: 600, description: 'required even when the verdict is pass/holds' },
  judge_rail: { type: 'string', enum: ['claude-fresh'] },
}, required: ['status', 'mode', 'target_id', 'sha', 'verdict', 'ledger_sha256', 'ledger_head_sha', 'gate_exit_code', 'checks', 'failures', 'hunks_cited', 'warnings_cleared', 'findings', 'strongest_disagreement', 'repo_toplevel', 'outward_actions_taken', 'installed_packages'] }
```
Script-side semantic rules (F-46): `verify:pass` ⇒ `gate_exit_code===0 ∧ ledger_head_sha===build.head_sha ∧ hunks_cited.length≥1 ∧ (mutants.written===0 ∨ mutants.killed≥1) ∧ warnings_cleared covers every idiom hit in the ledger`; `refute:holds` ⇒ `findings[0].reproduction.exit_code` present and `!== undefined`; `review` findings without a reproduction are downgraded to `verification_level:'unverified'` and never queued; `veto` ⇒ each veto is a finding with a reproduction, else it is a note.

### 9.5 `MERGE` (integrator; modes `setup`, `merge`, `conflict`, `clean-gate`, `bundle`)
```js
const MERGE = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['merged', 'conflict', 'gate-red', 'reverted', 'missing-ref', 'ok', 'failed'] },
  mode: { type: 'string', enum: ['setup', 'merge', 'conflict', 'clean-gate', 'bundle'] },
  card_id: { type: 'string' }, branch: { type: 'string' },
  before_sha: { type: 'string' }, head_sha: { type: 'string', pattern: '^[0-9a-f]{40}$|^none$' },
  ledger_sha256: { type: 'string', pattern: '^[0-9a-f]{64}$|^none$' }, gate_exit_code: { type: 'integer' },
  cherry_unmerged: { type: 'array', items: { type: 'string' } }, patch_ids_missing: { type: 'array', items: { type: 'string' } },
  conflicts: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, ours: { type: 'string', maxLength: 1500 }, theirs: { type: 'string', maxLength: 1500 } }, required: ['file', 'ours', 'theirs'] } },
  bundle_path: { type: 'string' },
  setup: { type: 'object', properties: { venv_python: { type: 'string' }, baseline_collected: { type: 'integer' }, baseline_skipped: { type: 'integer' }, red_proof: { type: 'object', properties: { broken_red: { type: 'boolean' }, clean_red: { type: 'boolean' }, false_claim_red: { type: 'boolean' } } }, gate_sha256: { type: 'string' }, base_sha_ok: { type: 'boolean' } } },
  worktrees_pruned: { type: 'integer' },
}, required: ['status', 'mode', 'head_sha', 'ledger_sha256', 'gate_exit_code', 'cherry_unmerged', 'patch_ids_missing', 'conflicts', 'repo_toplevel', 'outward_actions_taken', 'installed_packages'] }
```

### 9.6 `REPORT` (synthesizer; rows are checked against the script's ledger)
```js
const REPORT = { type: 'object', properties: { ...COMMON,
  status: { type: 'string', enum: ['SUCCESS', 'FAILED'] },
  report_path: { type: 'string' }, report_bytes: { type: 'integer', minimum: 1 },
  rows: { type: 'array', items: { type: 'object', properties: {
    task_id: { type: 'string' },
    state: { type: 'string', enum: ['merged+gate-green', 'merged+gate-red', 'parked', 'reverted', 'blocked_on_owner', 'dropped_null', 'not_attempted', 'deferred'] },
    head_sha: { type: 'string' }, dod_done: { type: 'integer' }, dod_total: { type: 'integer' }, dod_deferred: { type: 'integer' } },
    required: ['task_id', 'state', 'head_sha', 'dod_done', 'dod_total', 'dod_deferred'] } },
  owner_actions: { type: 'array', items: { type: 'string', maxLength: 300 } },
  what_would_most_improve_confidence: { type: 'string', maxLength: 800 },
}, required: ['status', 'report_path', 'report_bytes', 'rows', 'owner_actions', 'what_would_most_improve_confidence', 'repo_toplevel', 'outward_actions_taken', 'installed_packages'] }
```

---

## 10. Replay/resume, null-result, safeguard-kill and concurrency handling

### 10.1 Replay and resume (F-43, F-47, T-14..T-16, S-18)
- `args` (computed by the orchestrator with `git rev-parse` immediately before every invocation): `{stage, run_nonce, launched_at, build_repo, venv, gate_sh, libsrc, wheels_dir, base_sha, plan_sha, integration_sha_at_launch, toolchain_status_sha256, wave_size, max_rounds, max_build, reserve_tokens, smoke, owner_approvals{github_repo_url, staging_space_ids[], staging_evidence_dir, production_evidence_dir, fixture1_path, hosted_call_budget_usd, gpu_seconds_budget}}`. Nothing time- or random-derived is computed in the script.
- Every prompt is a pure function of `args` and prior results; arrays are sorted by id before `JSON.stringify`; the integration head sha appears in every code-reading prompt, so a merge changes downstream prompts (cache miss exactly where code changed) and nothing else does.
- A re-drive of the same card in the same run carries `attempt:<k>` in the prompt → cache miss by construction; the same card in a later run carries the new integration head → cache miss by construction. The stale-cache case (a cached `head_sha` whose ref was pruned) is detected by the integrator's `status:'missing-ref'` and answered by a live re-drive; no separate probe agent.
- Resume (`{scriptPath, resumeFromRunId}`) is permitted only when `integration_sha_at_launch` still equals the live `integration/<nonce>` head — the orchestrator checks this before invoking; otherwise it launches a fresh run with new args. The journal is read before any "empty result" diagnosis (T-25).
- Tunables that only affect later stages (`max_rounds`, `reserve_tokens`, `wave_size`) live in `args`, so changing them does not invalidate the early cached prefix.

### 10.2 Null results (F-41, T-17, D-21)
- Every `agent()` goes through `run(role, mode, id, prompt, opts)`: it pushes `{role, mode, id, attempt, status}` to `ledger[]` for every call — including `null`, `threw`, `timeout` (typed receipts, never bare `null`); on a null it retries once with `attempt:2` and the `NARROW` clause (inspect `git status`/`git log` first, continue from the last commit, reading list halved), then returns `{status:'null'}`; stage callbacks branch on `status`; `.filter(Boolean)` is never used on a barrier result — drops are counted and logged.
- `pipeline` stages catch their own throws and return typed objects, so a throwing item does not vanish to `null` silently (the placeholder-not-throw pattern the review script already used).

### 10.3 Safeguard kills (F-31, F-42)
- The three hardening cards and the persona card carry reading lists ≤ 6 files and a defensive framing ("what the guard must refuse; write the red-proof test; never print an environment"); their verifiers run at `effort:'xhigh'`.
- Builders commit per coherent step; the null-retry prompt begins with the salvage rule (§4.4); two nulls on the same card → `blocked:'agent-null'`, not a third attempt; the gate pre-step removes stale `index.lock` and kills stray listeners started from the checkout; the integrator's `bundle` mode prunes worktrees of merged branches.

### 10.4 Concurrency (F-44, T-7, T-8)
- `args.wave_size` = 2 at cap 2 (4 CPUs), 12 at cap 14-16 (after the resize). Cards inside a wave run as independent `pipeline` chains; barriers exist only at the wave end (integration needs the whole wave) and around the three review lenses (dedup needs all).
- At cap 2 the enqueue order is the schedule (observed FIFO): the wave list is sorted so the critical path (01→02→03a→03b→04→05a→05b→06→10) is enqueued first; at cap 14 the same script fills the width.
- Waves are barrier-synchronised on purpose: a dependency-triggered scheduler (`Promise.race` over ready cards) would branch control flow on completion order and break the replay cache's call-order prefix (T-15). The ~20 % wall-clock it would save is not worth non-replayable control flow.
- Per-agent timeouts use the tested h6 `withTimeout`/`settle` block verbatim; it degrades to a plain `await` when `setTimeout` is absent (UNVERIFIED in the sandbox); a timeout is a typed drop receipt, the card is marked `blocked:'timeout'` and re-driven once with the `NARROW` clause. Timeouts: author 25 min, builder 50 min, verifier 25 min, integrator 20 min (conflict 30), review lens 30 min, synthesizer 15 min.
- The script logs at every wave: cards built/blocked, merges, the stop reason, and an estimated remaining wall-clock from `args.launched_at` and the count of remaining waves × the observed per-wave duration reported by agents (`date -u` in their `checks[]`).

---

## 11. Budget and effort plan by role; estimated agent counts and wall-clock

| Role · mode | effort | model | timeout | est. duration (UNVERIFIED extrapolation from 13-16 min finders / 4-5 min verifiers) |
|---|---|---|---|---|
| integrator · setup | medium | inherit | 30 min | 10-15 min (venv + wheels + tools, red-proof) |
| planner · plan | high | inherit | 40 min | 15-25 min |
| verifier · plan | medium | inherit | 20 min | 8-10 min |
| author · tests / journeys | medium | inherit | 25 min | 8-12 min |
| verifier · red | low | inherit | 10 min | 3-4 min |
| builder · implement | high | inherit | 50 min | 15-25 min (S) · 25-40 min (M) |
| verifier · verify | medium (xhigh on `risk:'security'`) | inherit | 25 min | 6-10 min |
| builder · fix | high | inherit | 40 min | 10-20 min |
| integrator · merge / bundle | low | inherit | 20 min | 3-5 min |
| integrator · conflict | high | inherit | 30 min | 10-15 min |
| integrator · clean-gate | low | inherit | 20 min | 6-8 min (suite twice + journeys) |
| verifier · review (lens) | high | inherit | 30 min | 12-15 min |
| verifier · refute | medium | inherit | 15 min | 4-6 min |
| verifier · veto | xhigh | inherit | 25 min | 8-10 min |
| synthesizer · report | low | inherit | 15 min | 5 min |

**Agent count (21 cards; expected fix mix 40 % one fix, 15 % two fixes, 10 % author re-drive, ~5 % null retries):** setup 1 · plan 2-3 · per card ≈ 5.7 → 120 · merges 21 + conflicts ~3 + fast-forwards ~2 = 26 · clean-gates 9-11 · journey authors ~6 · review lenses 9 (3 rounds) · refuters ~13 · review fix tasks ~7 × 5.7 ≈ 40 + their merges/clean-gates ~10 · veto 3 · synthesizer 1 → **≈ 240 agents (range 200-280)** at either cap — the cap changes wall-clock, not count. Comfortably under the 800 reserve threshold and the 1000 lifetime cap.

**Wall-clock (per-card chain without a fix ≈ author 10 + red 3.5 + builder 20 + verify 8 ≈ 42 min; with one fix ≈ 70 min; wave = slowest chain + serial merges × 4 min + clean-gate 7 min):**

| | cap 2 (this box) | cap 14 (after the resize) |
|---|---|---|
| Waves | ~11 (DAG width truncated to 2) | 9 (DAG depth; width 1-3 per level) |
| Build + integrate | ~11 × ~65 min ≈ 12 h | ~9 × ~80 min ≈ 12 h (the critical path is the plan's, not the cap's — see below) |
| Review loop (3 rounds, ~7 fix tasks) | ≈ 5-6 h | ≈ 3 h |
| Setup + plan + synth | ≈ 1 h | ≈ 1 h |
| **Total R1** | **≈ 18-20 h, run as 3-4 resumable invocations** (owner keeps a client attached; idle timeout at maximum) | **≈ 14-16 h, 2 invocations** |

Honest reading: the DAG the lens-4 plan implies is 9 deep, so the cap buys width (fewer waves at cap 2 truncation, parallel review lenses and refuters) but cannot shorten the critical path. The levers that would, and are deliberately NOT taken here: dependency-triggered scheduling (non-replayable control flow, §10.4) and skipping the author/red stages (violates the non-negotiable). The lever the owner CAN take is declaring cards 07, 12, 13a, 14 lower priority for R1 (they hang off 03b; §15 Q4), which drops two levels off the critical path in R1 and moves them to a second build run.

**Budget:** `budget.total` may be `null` (no directive) → all loops are bounded by counters first; `RESERVE` = 120 k output tokens for clean-gate + veto + synthesizer; the script stops scheduling new waves/rounds below the reserve or above 800 agents and always runs the synthesizer inside `try/catch` with the ledger it has (F-45).

---

## 12. COVERAGE MATRIX

Legend for "phase": **P0** orchestrator pre-flight · **R0** plan · **R1** build inner loop · **G** `gate.sh` · **I** integration · **W** whole-tree review loop · **S** synthesizer · **X** script invariant (JS) · **O** owner checkpoint. Rows whose only complete guard is an owner checkpoint are marked **O-only**.

### 12.1 Failure modes F-1..F-47 (research-4)

| id | Guard (mechanism) | Phase |
|---|---|---|
| F-1 wrong repo (cwd) | `PREAMBLE` names `$BUILD_REPO`; every git/pytest command `git -C`/absolute; no `isolation:'worktree'`; every schema returns `repo_toplevel` and the script asserts `=== args.build_repo`; toolchain status sha256 re-checked by the setup and clean-gate modes | X, G, I |
| F-2 volatile build path | `args.build_repo=/workspaces/space-build` (durable, outside the grill rsync); `libsrc` copied to a durable path; `git bundle --all` into the grill folder after every merge (synced by the owner's script) | P0, I |
| F-3 wrong base / snapshot mutated | `args.base_sha` full sha; setup asserts `git rev-parse HEAD == base_sha` and writes `.gate/base.json`; snapshots `chmod -R a-w`; card prompts carry the base | P0, R0, X |
| F-4 foreign CLAUDE.md | `PREAMBLE` first paragraph; `AGENTS.md` written into the build repo by the planner and named in every prompt | X, R0 |
| F-5 per-agent bootstrap | one idempotent setup stage builds `$VENV` (3.12) with wheels + tools; `gate.sh` refuses any other interpreter; `installed_packages` must be `[]` on every schema (script aborts the card otherwise) | P0/R1, G, X |
| F-6 "ask the owner" unattended | `args.owner_approvals` is data; a null field → `blocked_on_owner` entry in the checkpoint object, never an action, never a retry; the synthesizer lists them first | X, S, **O** |
| F-7 secrets leak | P0 regex pre-scan of all inputs; trigger message carries no secret; `gate.sh` runs pytest under `env -i` with a fixed `CANARY_SECRET`; secrets regex step over the diff range + commit messages; hardening tests assert absence only; journal export scanned before it is copied to `evidence/` | P0, G, S |
| F-8 hallucinated APIs | `plan/api-ledger.json` (symbols with `libsrc` path:line) from R0; `apis_expected` per card → `gate.sh` apicheck imports each symbol from the pinned wheels and checks kwargs; idiom lint for the known traps (`Chatbot(type=`, `gpu_size=`, `presence_penalty`, `restart_space(revision`, `from gradio.client`, `read_text(newline=`, assisted generation) | R0, G |
| F-9 recommendation vs decision | `plan/decisions.json` (id → decided value); cards cite decided values only; `verifier mode:'plan'` refutes contradictions; owner approves the sheet at C0; review lens `decision-fidelity` diffs behaviour against the sheet | R0, O, W |
| F-10 CORRECTED line ignored | planner rule: cards quote ONLY the CORRECTED text; idiom lint flags the known-bad idioms (`preexec_fn`, `__wrapped__`, `rmtree`+unload, `prefill_chunk_size`, `lease_s - 30`) as warnings the verifier must clear by id | R0, G, R1 |
| F-11 UNVERIFIED findings / stale `file:line` | cards locate by symbol (`file::function`) at `base_sha`; finding ids with UNVERIFIED status are routed to `verifier mode:'evidence'` before any card cites them; every finding carries `sha` | R0, W |
| F-12 verification theater | the gate ledger (`.gate/last_run.json`, sha256 returned) is the only admissible evidence; verifiers run `gate.sh` themselves; `pass` requires `ledger_head_sha === build.head_sha`; pytest exit 5 is red; `staging-required` lines can never be `pass` locally | G, X |
| F-13 monolithic items | cards `S`/`M` only (plan verification rejects `L`); 21 cards for 14 steps; builder `partial` with commits ≥ 1 is re-driven as a fix round; `diff_stats` logged, oversize flagged for the scope lens | R0, R1, X |
| F-14 dependency order / collisions | `topoOrder` + `waves` with disjoint write sets (JS); serial integration in DAG order with a gate after each merge | X, I |
| F-15 context loss between stages | carriers are files + git: cards, `plan/status/<id>.json`, `.gate/last_run.json`, the branch; returns are small typed objects; every prompt says "read the card at <path>, then `git diff <base>..<head>`" | X, R1 |
| F-16 scope creep | card `in_scope/out_of_scope/files_allowed/deps_allowed`; `gate.sh` scope step fails hunks outside the allowlist and requirement lines outside `deps_allowed`; review lens `scope`; ship-but-flag defaults OFF are in every card's `out_of_scope` | G, W |
| F-17 persona boundary | persona card: `risk:'persona'`, no `git log/show` on `system_prompt.py`, only G-19 role names; `tests/test_personas.py` absence test in `tests/protected.txt`; review lens `decision-fidelity` runs on persona/README/test changes; synthesizer reports the absence test result explicitly | R0, G, W, S |
| F-18 tests weakened/deleted | oracle lock: pre-existing test files modified/deleted by a builder → gate red; `collected ≥ baseline − Tests-Removed:`; skip/xfail non-increasing without `Skip-Added:`; test-detection idioms in production code → red; protected files; scripted mutants must kill | G |
| F-19 over-claiming commits | ruff F821/F811 + import smoke; claim-vs-diff lint over every commit; `dod[{command, exit_code}]` in the builder schema; `taskDone()` counts DoD lines, not items; synthesizer rows carry `dod_done/dod_total` | G, X, S |
| F-20 mocks testing the mock | conformance suite parametrised over `fake`/`recorded-hosted`/`recorded-worker` with `provenance`; recorded rows `skipped: needs owner recording` are counted; three scripted mutants per task must turn the tests red; fixture #1 (owner) replaces the synthetic golden | R1, G, O |
| F-21 line-ending drift | card 01: `.gitattributes` + `.editorconfig` commit, then a `Renormalize-Only: yes` commit (claim lint verifies whitespace-only); `gate.sh` eol step red on any CRLF/mixed tracked text file thereafter; `apply_patch` CRLF fix per security-tools-6 CORRECTED | R1, G |
| F-22 large files / LFS / junk | `gate.sh`: LFS empty, blob cap 5 MB, forbidden paths; card 01 extends `.gitignore`; fixtures generated in `tmp_path` | G, R1 |
| F-23 3.14 vs 3.12 drift | gate runs only under `$VENV` 3.12; `ruff --target-version py312`; two requirement sets each with a lock produced under 3.12; test that README front matter equals the lock's gradio pin; final resolution observed on staging (R2 evidence) | G, R1, O |
| F-24 README/UI/commit claims diverge | `tools/render_readme.py --check` in the gate; `tests/test_constants_pin.py` (protected); UI strings read the constants module; claim lint on every commit | G, R1 |
| F-25 catalog provenance | `models.yaml` schema test + gate provenance step (40-hex revision, `saved_path` exists); entries the workflow cannot verify are committed `status: unverified` and listed for the owner | G, R1, O |
| F-26 leaked servers / foreground launch | harness picks a free port, `prevent_thread_lock=True` or subprocess with `try/finally: kill()`; `/healthz` sha asserted against the checkout HEAD; gate pre-step kills stray listeners from the checkout; `AUTHORITY` forbids foreground servers without a timeout | R1, G, X |
| F-27 infinite/oscillating fix loops | `MAX_BUILD=3`, fingerprint two-strikes, oscillation A→B→A detection, `MAX_ROUNDS=3`, dry counter 2; findings ledger with stable ids (`fkey`); exhaustion → typed `blocked` | X |
| F-28 fixing the gate | `gate.sh` lives outside the repo for the run; in-repo copy + `ruff.toml`, `pytest.ini`, `tests/protected.txt`, `tools/claim_lint.py`, `.gitattributes` are protected (only card 01 may touch); red-proof mode recorded by setup and by card 01's verifier; one `Claim-Waiver:` per range; only exit 0 is green | G, X |
| F-29 flaky / network tests | suite twice with identical outcomes; `--disable-socket --allow-hosts=127.0.0.1`; blackhole proxy; `tests/live/` excluded unless the owner's cost flag | G |
| F-30 critic captured by self-report | verifiers receive the card + diff range + ledger, never the builder's narrative; must run `gate.sh` and cite hunks (`hunks_cited minItems`); `strongest_disagreement` required even on pass; mechanical lenses first | R1, X |
| F-31 safeguard kill on security code | hardening split into 09a/09b/09c with ≤ 6-file reading lists; defensive framing; null → one narrower retry → park `unreviewed → needs_owner` (never `pass`) | R0, X |
| F-32 merge conflicts "pick one side" | integrator aborts on conflict; fresh `mode:'conflict'` call with hunks + both cards, re-gated; `git cherry` empty + patch-id check asserted by the script; bundle after each merge | I, X |
| F-33 worktree lifecycle | single `$WT` root; nonce in branch names; creator removes its worktree only after the branch head is verified; integrator prunes merged worktrees; stale-run cleanup after bundling | R1, I |
| F-34 green on branch, red merged | gate after every merge on the merged tree; red → `git revert -m 1`, task parked, fix task next round on the surviving head | I, W |
| F-35 outward actions | `args.owner_approvals` only; `AUTHORITY` forbids every write tool; `outward_actions_taken` non-empty → run aborts; pipeline code written + unit-tested against fakes, never executed; owner disables connector write tools | X, P0, **O** |
| F-36 harness burns quota/money | harness defaults `--backend fake --dry-run`; real backends need `--i-accept-cost` + an env var only the owner sets; `max_retries=0`; zero-call test in the gate; the owner runs the real harness | R1, G, **O** |
| F-37 staging-only behaviour "verified" | `verification_level` enum on every DoD line/finding; keyword list forces ≥ `staging-required`; such lines are `deferred`, listed in the checkpoint runbook with the measurement to record; R2 reads CI evidence files only | X, S, **O** |
| F-38 other agent resumes pushing | the workflow never touches the Space; promotion runbook step 0 asserts Space HEAD == base or adopts the delta; owner checklist: stop notice, disable scheduled tasks, rotate its token, delete NF4 secrets | P0, S, **O** |
| F-39 flaky fetch → fabricated values | catalog/api-ledger entries need `source{url, saved_path}` and the gate checks the file exists; unresolved facts are `TODO(owner-verify)` entries, never numbers; constants seeded UNVERIFIED are marked in the config comment | R0, G |
| F-40 synthesizer summarises phantom work | synthesizer receives only the script-computed row table + ledger paths; its `rows` are compared to the script's in JS and overwritten on mismatch (logged); rows include `parked/reverted/blocked_on_owner/dropped_null/not_attempted/deferred` | S, X |
| F-41 null contract mishandled | `run()` wrapper records every call incl. nulls; typed `{status:'null'}`; one narrower retry; never `.filter(Boolean)` on a barrier without counting | X |
| F-42 mid-task kill | commit per coherent step; salvage rule in the retry prompt; gate pre-step (index.lock, stray servers); two nulls → park | R1, G, X |
| F-43 stale resume cache | args carry `base_sha`, `integration_sha_at_launch`, `run_nonce`; integration head in every prompt; `attempt` suffix on re-drives; `missing-ref` → live re-drive; resume only when the launch sha still matches | X, P0 |
| F-44 cap-2 wall-clock / host stops | one script, several resumable invocations; waves; single-vote mechanical lenses; setup pre-builds the venv; estimated remaining wall-clock logged per wave; owner sets the idle timeout to the maximum and keeps a client attached (**O** for the idle timeout) | X, **O** |
| F-45 budget exhaustion / agent cap | counters first, budget second; `RESERVE` + `agentCount > 800` stop scheduling; synthesizer always runs in `try/catch` | X |
| F-46 schema-valid-but-empty | small schemas with `minItems`, `maxLength`, patterns; script re-validates semantics (`pass ⇒ ledger match`, `done ⇒ every DoD exit 0`); smoke run validates every schema | X, P0 |
| F-47 script-level bugs | `meta` pure literal; phase titles match; no `Date.now/Math.random/new Date()`; every stage body in `try/catch` with a ledger push; `phase` passed per call inside pipelines; state derived from returns; smoke run mandatory | X, P0 |

### 12.2 Doctrine anti-patterns AP-1..AP-17 (research-1 §4)

| id | Guard | Phase |
|---|---|---|
| AP-1 receipt-as-result | `status` enum on every schema; `run()` rejects `null`/threw into typed receipts; no background forwarders; digests matching `/started in the background|based on the digest/i` are logged and treated as `FAILED` | X |
| AP-2 digest theatre | the artifact is the branch + ledger; verifiers read `git diff` and the ledger file, never a summary; the synthesizer gets the ledger table, not prose | R1, S |
| AP-3 evidence-tag theatre | the two signals are mechanically different by construction: the gate ledger (script-written) vs the verifier's own re-run of each DoD command; a `pass` needs both to agree on `head_sha` | G, X |
| AP-4 silent-in-both detector | `gate.sh --red-proof` must fire on `f88b120` and on the false-claim fixture and stay green on the cleaned base; confirm-RED for every new test; mutants must kill | G |
| AP-5 Goodhart-green | tests written before code by the author; oracle lock; skip/xfail/`-k`/`--deselect` cannot enter (gate owns the pytest command); mutants | R1, G |
| AP-6 self-certification | distinct fresh `agent()` per role; builder returns evidence not verdicts; only the JS predicate says done/satisfied; judge veto-only | X |
| AP-7 the grind | fingerprint two-strikes → park; never a 4th identical attempt; oscillation detection | X |
| AP-8 fat barrier, no timeout | pipeline per card; barriers only at wave end and review lenses; h6 `withTimeout`/`settle` with typed drops (degrades safely if timers are absent) | X |
| AP-9 over-broad `required[]` | `required` is the floor; prose in single capped strings; deliverable on the branch regardless | X |
| AP-10 mid-run contract edits | `plan_sha` frozen at C0; cards immutable during R1 (a needed card change is a new card in the next run); schemas are top-level consts | R0, X |
| AP-11 unbounded loop | `MAX_ROUNDS`, dry counter, `seen` dedup, budget/agent reserve; every stop reason logged | X |
| AP-12 negative instructions in the implementer prompt | the builder prompt carries the card and intent; every "do not" is a gate step, not a sentence | R1, G |
| AP-13 LLM doing mechanical comparison | DAG, waves, overlap, dedup, fingerprints, predicates, row table — all JS; lints — all `gate.sh` | X, G |
| AP-14 parallel mutators / overlapping files | disjoint write sets per wave (JS); agent-created worktrees; single serial integrator | X, I |
| AP-15 trusting "done"/"tests pass"/working-tree green | `taskDone()` reads the verifier's ledger hash, not the builder's status; `gate.sh --clean` from a detached pristine checkout per wave | X, G |
| AP-16 performative agreement in the fix loop | fixer receives only typed failures; `strongest_disagreement` required from every verifier; a refuted finding is recorded, not deleted | R1, W |
| AP-17 trailing limitations section | `verification_level` and `unverified` are inline fields per line/finding; the report's rows carry `deferred` counts inline | S |

### 12.3 Tool-native anti-patterns T-AP-1..12 (research-2 §6)

| id | Guard | Phase |
|---|---|---|
| T-AP-1 consent-in-prompt | approvals are `args` data; a script string can never authorise; outward actions abort the run | X |
| T-AP-2 secret-in-trigger | P0 pre-scan; the trigger message is authored from the `AUTHORITY` text and contains no token | P0 |
| T-AP-3 self-certifying implementer | builder's `gate_exit_code` is advisory; the verifier's ledger decides; claim lint | G, X |
| T-AP-4 unbounded until-satisfied | four stop conditions (§6.2) | X |
| T-AP-5 dedup against `confirmed` | `seen` set of `fkey`s across rounds | X |
| T-AP-6 barrier between per-item stages | `pipeline(wave, buildTask)`; barriers only where cross-item context is needed | X |
| T-AP-7 parallel writers on one checkout | one worktree per mutating call; one serial integrator | R1, I |
| T-AP-8 worktree as the checkpoint | branch in the shared store + bundle after every merge; idempotent reuse of an existing branch | R1, I |
| T-AP-9 volatile prompt content | prompts from `args` + sorted results; no timestamps, no scratch paths that vary per session (`/workspaces/space-build` is fixed) | X |
| T-AP-10 stale-sha evidence | `sha` required on every verdict/finding; integration head in every prompt | X |
| T-AP-11 silent truncation | every cap/drop/park/deferral is logged and in the ledger; wave truncation logs what waits | X |
| T-AP-12 one giant implementer | 21 `S`/`M` cards; `partial` re-drive; `L` rejected at plan verification | R0, X |

### 12.4 External anti-patterns S-AP-1..14 (research-3 §3)

| id | Guard | Phase |
|---|---|---|
| S-AP-1 self-grading | fresh verifier per verdict; judge sees diff + ledger + card only | R1, W |
| S-AP-2 early victory | the gate runs the complete suite (twice) — the verifier cannot choose the command; `collected` compared to baseline | G |
| S-AP-3 oracle tampering | oracle lock in the gate (pre-existing tests immutable to builders; protected paths); `pytest.ini`/`conftest.py` protected | G |
| S-AP-4 hollow feature-isolated implementation | composition journeys authored after each wave by the author role and run by the clean-gate; whole-tree review lens `correctness` with reproduction | R1, I, W |
| S-AP-5 telephone-game decomposition | one builder lineage per card (implement + fix by the same role, fed typed failures); only verification is split off; cards are self-contained | R1 |
| S-AP-6 unbounded fix loop / thrash | `MAX_BUILD=3`, fingerprints, oscillation, revert-not-fix after a red merge, `MAX_ROUNDS`, dry counter | X, I |
| S-AP-7 claims without diffs | claim-vs-diff lint per commit; `dod[{command, exit_code}]`; reviewers treat claims as hypotheses | G, W |
| S-AP-8 secret sprawl | no `.env`, no token in any run; CI written with Trusted Publisher OIDC per resource, `permissions:` blocks, SHA-pinned actions; staging secret keys asserted in the R2 evidence; child env allowlist tested with `CANARY_SECRET` | R1, G, O |
| S-AP-9 non-resumable script | §10.1 | X |
| S-AP-10 irreversible action inside the loop | `AUTHORITY` deny list; `outward_actions_taken` abort; CI + owner only | X, O |
| S-AP-11 biased judging protocol | binary evidence-backed verdicts only; no scoring, no A/B; veto-only judge; `strongest_disagreement` required | W |
| S-AP-12 canary checks the wrong thing | `EXPECTED.json` for the canary (sha echo, authenticated 16-token ×3, `finish_reason`, latency, visibility `private`, quota delta) written in R1; R2 asserts the CI evidence against it | R1, R2 |
| S-AP-13 context overflow / kitchen sink | one card per builder; reading lists capped; returns are small typed objects | R1, X |
| S-AP-14 reviewer over-reporting → churn | findings need a reproduction to be queued; severity + kind required; `low` and unreproduced findings are logged, not queued | W |

### 12.5 DEEP anti-patterns SD-AP-1..12 (research-3-DEEP Appendix B)

| id | Guard | Phase |
|---|---|---|
| SD-AP-1 author-graded work | as S-AP-1; author ≠ builder ≠ verifier by role | R1 |
| SD-AP-2 green-by-weakening | gate tamper step (assert-removal is caught by the mutants and the oracle lock; skips/xfails counted; CI/config protected) | G |
| SD-AP-3 vacuous/tautological tests | confirm-RED by a fresh verifier; scripted mutants must kill | R1, G |
| SD-AP-4 unanimous-LLM "verification" | no verdict without an executed command in `checks[]`/`reproduction`; the gate re-executes DoD commands | G, X |
| SD-AP-5 endless/oscillating fix loops | as S-AP-6 | X |
| SD-AP-6 summary-of-summary handoffs | handoffs are schemas; decisions live in `plan/decisions.json` and are passed verbatim by path + sha | X, R0 |
| SD-AP-7 parallel implementers on shared files | disjoint write sets per wave; serial integration | X, I |
| SD-AP-8 phantom-change commits | claim lint; ruff F821; `taskDone()` | G, X |
| SD-AP-9 secrets in reach | `env -i` for every test run; no token in any run; deny list; secrets scan | G, X |
| SD-AP-10 agent-executed irreversible actions | as S-AP-10 | X, O |
| SD-AP-11 non-replayable script | as S-AP-9 | X |
| SD-AP-12 scaffold maximalism | this design: 6 roles, 1 gate, 1 script; the budget goes to verification (author, confirm-RED, fresh verifier, mutants, clean-gate, refute-with-reproduction), not to more builders; agent count and stop-reason distribution are logged per run for tuning | X |

**Rows guardable only with an owner checkpoint:** F-6, F-35, F-36, F-37, F-38, F-44 (idle timeout half), S-AP-8/S-AP-10/SD-AP-10 (the outward half). Everything else has a deterministic or script-level guard.
