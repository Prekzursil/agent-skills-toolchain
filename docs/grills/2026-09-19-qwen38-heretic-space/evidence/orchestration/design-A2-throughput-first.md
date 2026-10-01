# Design A2 — THROUGHPUT-FIRST implementation workflow for the Space rebuild

- **Author:** Architect A2 (Claude, Fable 5.1), 2026-09-19 · **Angle:** shortest wall-clock and fewest wasted tokens at cap 2 (today) and cap 14-16 (after the resize) without dropping a single non-negotiable of the brief.
- **Inputs read in full:** `DESIGN_BRIEF.md`, `DECISION-QUEUE.md`, `evidence/workflow-findings.md` (all 50 findings incl. every CORRECTED line), `lens-4-simplification-retry.md`, `WORKFLOW_TOOL_REFERENCE.md`, `research-1-doctrine.md`, `research-2-tool-native.md`, `research-3-external-sota.md`, `research-3-external-sota-DEEP.md`, `research-4-red-team.md`; context: `lens-3-release-engineering-ops.md`, `feature-inventory.md`.
- **Verified on this box 2026-09-19 (read-only):** `nproc` = 4 → cap 2; `python3` = 3.14.2 and `/usr/bin/python3.12` exists; `scratchpad/libsrc/wheels/` holds gradio 6.26.0, huggingface_hub 1.32.0, spaces 0.51.3, transformers 5.16.1 (`libsrc/` = 179 MB); `ruff`, `pyflakes`, `gitleaks`, `uv` absent; 12 GB free; `space-latest` HEAD = `f88b1204a6af53a469c7a3ddf6d9fb2aea5b4be6` (clean tree, 29 tracked files, CRLF in `app.py`/`file_bench.py`/`openai_protocol.py`/`maintenance/keepalive.log`, mixed in `tests/test_web_tools.py`, HF LFS `.gitattributes`); `space-src` HEAD = `17dce0c…`; `claude mcp list` → no MCP servers (Codex rail absent); `~/.claude/harness-meta/plan_lint_stage0.py` absent; `skills/workflow-authoring/templates/h6-timeout-heartbeat.md` present (timers are injected globals); the grill folder is rsynced with `--delete` into the toolchain repo every 5 min by `save-to-repo.sh`.
- **Evidence tags:** `[V]` verified above or in the cited research · `[M]` measured in `research-2 §1.4` · `[E]` extrapolated from measurements (stated) · **UNVERIFIED** inline where the design is defensive around a fact nobody could check.

### Preface — the throughput thesis in one page (not one of the 15 required sections)

1. **Agent-minutes are the currency at cap 2; the dependency spine is the currency at cap 14.** At cap 2 wall-clock ≈ Σ agent-minutes ÷ 2 whenever no slot idles [M: 11 agents ≈ 52.5 min, 3,147 s, all slots busy except the tail]. At cap 14 the same 11 agents project to ≈ 26 min, bounded by the longest finder→verifier chain [M]. So the design (a) removes agents that a deterministic script can replace, (b) never lets a slot idle at cap 2 (DAG-readiness admission, no barrier waves), and (c) shortens the spine at cap 14 (parallel spine branches, front-loaded test authoring, optional speculative dependencies).
2. **The tool schedules FIFO by `queuedAt`** [M: `verify:inference-perf` queued +736 s, started +1,749 s behind three finders queued at +0.2 s]. Therefore enqueue order *is* the schedule at cap 2: the admission scheduler admits ready tasks in critical-path rank order and keeps the number of queued agents at or below the cap so a critical-path verifier never waits behind a non-critical implementer.
3. **A deterministic gate line costs 0 agents; an LLM role costs 4-16 minutes and 60-230k tokens** [M: finders 735-953 s / 153-231k tokens; verifiers 258-317 s / 92-107k; critic 305 s / 123k]. Every guard in §12 is tagged with its cost class; only guards that need judgement are agents, and each expensive one is justified.
4. **Tokens are wasted mostly by re-reading** (the 210 KB findings file, the 47 KB decision queue, library sources) and by discarded work (blocked chains, refuted findings, superseded implementations). Cards inline exactly what an agent needs (F-15), a byte-identical prompt prefix is shared by every agent, and every discard is counted so the waste ratio is measured, not guessed.
5. **Nothing here weakens the non-negotiables:** PR-sized cards sized to the cap; critical-path-first enqueue; per-task pipeline with barriers only at the two-vote reduce, the serial merge queue, the clean-checkout gate and the judge panels; wave (in-flight) sizing from `args`; cached replay on resume plus git-state idempotency; smoke-one-task-first; honest timing ledger; all 47 failure modes and all 55 anti-patterns guarded (§12).

**Headline numbers (derivation in §11):** ≈ 25 task chains + ≈ 5 review fix chains → ≈ 300 agents (range 260-340), ≈ 1,900 agent-minutes. Cap 2: ≈ 16-18 h of wall-clock, run as 3 invocations of ≈ 5.5 h each (`knobs.maxAgentsThisRun`), resumable. Cap 14: ≈ 6.5 h (spine of 9 tasks × ≈ 33 min + ≈ 70 min review tail), ≈ 5.5 h with speculative spine dependencies on. Every number that rests on implementer durations is `[E]` — no implementer has run in this session.

---

## 1. Adopted principles (ids) and how conflicts between lenses were resolved

### 1a. Adopted, by lens

- **Doctrine (research-1):** D-1 cold-executable cards · D-2 freeze + hash the contract before launch · D-3 ground first (base SHA, access methods, assumption ledger) · D-4 simplest probe first (the smoke task) · D-5 file-disjoint units in a real DAG · D-6 red-proof (adapted: confirm-RED + one mutant, §5) · D-7 smallest check ladder, empty check set never passes · D-8 root cause first, two strikes then pivot, never a 4th identical attempt · D-9 the pipeline proves it cannot lie (gate self-test) · D-11 write-as-you-go (adapted: code + ledgers + small JSON, not prose reports, C13) · D-12 one shared `unitDone()` reducer · D-13 two independent signals with declared probes · D-14 both-states control on every detector · D-15 verifier separation · D-16 refute-first, full text, enumerated verdicts, resolver never votes · D-17 overclaims repaired by scoping the sentence · D-18 anchors carry the SHA · D-19 write the algorithm, agents only for judgement · D-20 terminal state on every return · D-21 bounded fan-out with typed drop receipts · D-22 resume-safe by construction · D-23 bounded convergence (rounds, dry, budget, DoD inversion) · D-24 gates decide, judges veto · D-25 journeys against the packaged deliverable · D-26 spec before quality (folded into the verifier's ordered checklist) · D-27 structured hand-offs · D-28 owner checkpoints at phase ends only · D-29 completeness critic (as the tree-level lens reviewers) · D-30 the product is an agent system: measure before seeding constants, blast-radius on deletions.
- **Tool-native (research-2):** T-1 one script, several runs, checkpoint between · T-2 trigger message is broadcast and is the only authority · T-3 only the judge enum can say `satisfied` · T-4 four independent stop conditions · T-5 bounded fix loops with separate counters · T-6 whoever votes did not author · T-7 pipeline per task, barrier only where needed · T-8 enqueue order is the schedule · T-9 refs and bundles outlive worktrees · T-10 one writer per mutable thing · T-11 conflicts to a fresh resolver, then re-gate · T-12 the gate's verdict is the truth · T-13 pin the SHA in every code-reading prompt · T-14 prompts are pure functions of `args` and results · T-15 replay-deterministic control flow · T-16 only completed results replay → PR-sized tasks + idempotent branch reuse · T-17 null is a result · T-18 schema every stage · T-19 effort by role, model inherited · T-20 static scaling from `args`, `budget.total &&` guard, reserve · T-21 log decisions not payloads · T-22 smoke the permissions · T-23 pins first, verified by a different agent · T-24 synthesizer last, never edits · T-25 read the journal before diagnosing.
- **External SOTA (research-3, ids S-n) and the DEEP run (ids written SD-n here to disambiguate):** S-1/SD-1 executable acceptance file frozen before code · S-2/S-3 grade the outcome in the environment, evidence not assertions · S-4/SD-3 test author ≠ implementer, held-out compositional journeys · S-5/SD-5 lock the oracle · S-6/SD-6 deterministic diff signals for test weakening · S-7 structure not instructions · SD-4 one mutant per criterion (over S-8's mutmut, C3) · S-9/SD-7 property tests on the four invariant modules · S-10/SD-10 fresh-context structured judges · SD-11 no position-swap on adversarial checks (over S-10, C5) · S-11/SD-8/SD-9 refute-first with an empirical gate · S-12 complete suite from a clean checkout · S-14/SD-16 hand-off contract · S-15 external failing signal only · S-16/SD-14 fix loops capped at 3, stop on dry/oscillation/expansion · S-17 deterministic gates layered · S-18/SD-18 replay-safe, idempotent side effects · S-19/SD-19 outward actions are requests executed by gated CI · S-20/SD-20 claims reconciled against the diff · S-21/SD-21 zero secrets in the agent runtime, OIDC at the edge · S-22/SD-22 headless Gradio/Spaces primitives · S-23 canary with a decision rule and a control · S-24/SD-13 verification diversity, not more agents · SD-15 feedback is the exact failing output · SD-17 snapshot the revision every agent reads.
- **Red team (research-4):** all 47 failure modes are guarded (§12); the §2 invariants and the §3 gate of that report are adopted almost verbatim and extended (`--confirm-red`, `--mutate`, `--journeys`, `--clean`, profiles).

### 1b. Conflicts and who wins (the decision log always wins over any principle)

| # | Conflict | Resolution and why |
|---|---|---|
| C1 | `isolation:'worktree'` (T-9, D-5, research-2 §4.5) vs F-1: the harness worktrees the **cwd** repo, which is the unrelated toolchain repo | **F-1 wins.** Every mutating agent creates its own worktree with `git -C "$BUILD_REPO" worktree add "$WT/<task>-<nonce>" -b impl/<task>-<nonce> <base>`; readers use detached `ro-<sha>` worktrees made by `gate.sh --clean`. Cheaper too: no harness worktree of a 178-checkout repo. |
| C2 | Plan authored by agents (T-1 R0 spec authors, research-2 §4.3) vs D-1 (`const WUS` literal, cold-executable) and F-9 (a human approves the decision sheet) | **Hybrid, throughput-first.** The orchestrator drafts `plan/` (decision sheet, 25 cards with CORRECTED text inlined, journeys spec) from the inputs it has already read; `args.plan_hash` freezes it (D-2); R0 spends agents only on what needs reading or judgement: symbolizing findings at `base_sha` (F-11), the API ledger from `libsrc` (F-8), catalog provenance (F-25), two plan critics, one bounded repair. Transcription is not a job for 6 agents. |
| C3 | S-8 (mutmut ≥ 70 % kill on changed files) vs SD-4/[37] (one scripted mutant per criterion) | **SD wins.** mutmut on a 5 k-line tree costs minutes to hours per task at cap 2; one verifier-crafted one-line mutant per DoD line, run by `gate.sh --mutate`, proves sufficiency for ≈ 30 s of CPU and 0 extra agents. |
| C4 | S-4 held-out compositional tests hidden from implementers vs single-writer reality (no deny hooks provably active inside Workflow subagents — **UNVERIFIED**) and SD's "held-out added little" | **Cheap version kept.** The six journeys (D-25) live on a branch `journeys/<nonce>` that no card names; the clean-checkout gate merges it into a temp worktree every K merges. Not enforceably hidden; compositional by construction, so teaching-to-the-test is hard, and the mutant + assertion-loss checks cover weakening. |
| C5 | S-10 pairwise with position swap vs SD-11 (swap alone hurts −3 to −13 pp on adversarial pairs) | **SD-11 wins**; this workflow has no A/B design judgments (the owner already decided), refutation gates use forced-CoT single-order prompts with a required executed command. |
| C6 | research-2 §4.5 per-task chain verify → fix → audit → fix → critic (5 sequential LLM legs) vs S-24/SD-13 (verification diversity, not more agents) and the cap-2 arithmetic | **Fold, don't stack.** The audit becomes the verifier's ordered decision-fidelity checklist (reads `plan/decisions.json`, not the queue) plus two deterministic gate steps (apicheck, idiom lint); the per-task critic becomes the refuter (kill mandate) plus the tree-level lens reviewers. Per task: 2 parallel fresh legs + 1 veto-only judge instead of 5 sequential. Saves ≈ 2 agents and ≈ 12 wall-minutes per task with no loss of separation (T-6). |
| C7 | D-10 de-sloppify stage per unit | **Dropped per task**; the outer-loop `tests-and-gate` lens does it once at tree level (one pass instead of 25). |
| C8 | D-15/SD-13 cross-vendor second judge vs `claude mcp list` → none `[V]` | **Fallback rail** (acceptance-review degradation ladder): a fresh Claude agent at `effort:'xhigh'` whose only input is the review prompt; the script logs `reviewer_rail=fallback-claude` so nobody mistakes it for cross-vendor. |
| C9 | sdd "never dispatch parallel implementers" vs D-5/T-7 | **D-5/T-7** under three conditions: disjoint `files_allowed` (JS check adds an ordering edge on overlap), own worktrees, serial single-writer integration. |
| C10 | Anthropic Jan-2026 context-centric split (S-13: the feature's implementer writes its tests) vs the brief's non-negotiable "test authors ≠ implementers" | **The brief wins.** Telephone-game loss is mitigated because the card carries the frozen interface and the test author's return is data (paths + red ledger hash), not prose the implementer must re-interpret. |
| C11 | D-21 timeouts: H6 unblocks the barrier but the agent keeps its slot | **Generous timeouts + log**, never a retry while the loser still runs; at cap 2 a hung agent halves throughput, so the owner keeps a client attached (F-44) and the orchestrator can kill the run and resume. |
| C12 | S-2 "only the harness flips `passes`" vs the Workflow tool having no non-LLM stage | **The gate ledger is the flip.** `gate.sh` writes `.gate/last_run.json` with a self-hash; the script's reducer reads the verifier's copy of that hash. No agent's opinion flips anything. |
| C13 | D-11 write-as-you-go prose artifacts per agent vs the harness rule "do not write report `.md` files" and F-15 "carriers are files + git" | Agents write **code, ledgers, and small JSON results** (`plan/findings/*.json`, `.gate/*.json`); the synthesizer writes the one report; reviewers' full findings are JSON on disk (data for the next agent), which satisfies the owner's "keep every full report" instruction without prose artifacts. |
| C14 | D-16/S-10 "≥ 3 judges everywhere" vs S-24 scale-to-blast-radius | Per task: three **different fresh roles** (verifier, refuter, judge), not three identical judges; outer loop: 3-lens refute per fresh finding and a 3-lens panel. No 5-agent panels (SD [20]: 3 beat 5). |
| C15 | research-2 R2 "staging verification agents (canary, logs)" vs SD §12 "staging stage in CI, never the workflow's agents" and the hard rule never to call a Space | **CI does staging + canary + promotion (G-1a is law); R2/R3 agents only read CI artifacts** (`gh run view/download`, read-only Hub metadata) and fix staging-only failures locally. |
| C16 | D-1 "full text embedded in the prompt (never 'read the plan')" vs F-15 "carriers are files + git, prompts point at paths" | Both: the card is small (≤ 2 KB) and is embedded verbatim; large context (diff, ledger, api ledger) is referenced by path + SHA. |
| C17 | T-19 "model omitted" vs F-31/F-42 "hardening cards on `model:'fable'`" | Session model is Fable already; hardening cards set `model:'fable'` explicitly (defensive, zero cost) and carry narrow reading lists. |

**Decisions that override principles, stated (brief non-negotiable):** G-1 revised (Claude single writer) makes every "two-agent lane" guard a guard against Claude's own mistakes and the other agent's *scheduled tasks* (F-38); G-2/M-5 (production stays down; one release, many staging promotions) mean R1 never touches production and the first promotion is CI's; G-15/G-24 (in-container hardened `python_eval`, not a sandbox) fixes the hardening card spec verbatim; G-19 fixes the persona boundary; M-2/M-1/M-3 fix the architecture the cards implement; the owner's "SOTA maximum, keep vision/video, expand tools" turns simplification into sequencing (ship-but-flag list, §4).

---

## 2. Run structure: one script, several `args.stage` runs, an owner checkpoint between runs

A Workflow script cannot receive consent mid-run (T-1/T-2: the relayed trigger message is the only user voice; a string inside a prompt is script output). So outward-facing actions live **between** runs, as checkpoint objects the owner executes or approves in their own message, and the next run's trigger carries that authority. Every run is resumable (`resumeFromRunId`) and re-invocable for a cache replay.

| Run | `args.stage` | Preconditions (checked by the script or the setup agent; a missing one → typed `blocked_on_owner`, never an action) | What it produces | Checkpoint object it emits (`SYNTH.checkpoint`) |
|---|---|---|---|---|
| **R0** | `plan` | `plan_hash` = sha256 of the orchestrator-drafted `plan/` dir (decision sheet + cards + journeys spec); `base_sha` = `f88b120…` `[V]`; `libsrc` present; snapshots read-only | Grounded plan: `plan/findings-symbolized.json`, `plan/api-ledger.json` (+ `.md`), `evidence/catalog/<repo>.json` raw Hub reads, critic verdicts, repaired cards; `plan/READY.json` `{ready:bool, must_fix[]}` | `approve-plan`: "read `plan/decisions.json` and the card table; reply with the plan hash to launch R1", plus `create-github-repo` (optional, recommended before R1 so integration pushes branches) |
| **R1** (smoke) | `build-local` with `knobs.smoke=true` | Setup preconditions (durable `$BUILD_ROOT`, 3.12 venv, wheels, gate self-test green); plan approved (`args.plan_hash` echoed by the owner's message) | Setup done (idempotent), **T01a built, verified, judged and integrated** through the full chain; permission prompts surfaced; first timing rows | `smoke-ok` (or `smoke-failed` with the ledger): "add the allow rules you were prompted for; relaunch with `knobs.smoke=false`" |
| **R1** (full) | `build-local` | As above; `knobs.smoke=false`; `integration_sha_at_launch` computed by the orchestrator | All local tasks built → integrated on `integration/<nonce>` → clean gates green → outer review loop to `satisfied`/dry/cap; bundles in the grill folder (or branch pushed if `approvals.push_remote`); `RUNBOOK.md`, `PROMOTION_REQUEST.md`, `SYNTHESIS.md`, `timing.json` | `push-and-stage`: exact steps to create/point the private GitHub repo, staging UI Space + staging worker Space (duplicate, private, secrets re-entered), Trusted Publisher, GitHub environments, the fine-grained staging read token, the one metered hosted call (fixture #1), `hosted_call_budget_usd`; or `resume` (agent cap reached) or `blocked` (with the blocked list first) |
| **R2** | `stage` | `approvals.github_repo_url`, `approvals.staging_space`, `approvals.worker_space` non-null; CI staging deploy run id supplied in `args.ci_runs[]`; local repo head == pushed head | Read-only verification of CI artifacts (running sha == pushed sha, boot seconds, canary pass^3, measurements); staging-only failures → fix chains (same inner loop) → new commits for the owner/CI; measured constants seeded from artifacts (`worker/lease.py` EMA seed, cold-start margin) with citations | `promote-production` (with the evidence table, rollback sha, cost) or `restage` (fix commits to push) |
| **R3** | `promote` | Owner approved the `production` environment job; CI promoted; `args.ci_runs[]` includes the promotion + rollback-drill runs | Post-promotion read-only verification (sha, canary, visibility private, rollback drill fired on a known-bad staging deploy); final synthesis; residual list; owner actions (revoke pasted token, disable the other agent's scheduled tasks, delete `NF4_*` secrets) | `done` or `rollback-requested` |

**Between-run mechanics.** The orchestrator (main turn) reads `result.synth.checkpoint`, asks the owner in plain words, and on a go performs or lets the owner perform the outward action **outside** any run; then it computes fresh `args` (`git rev-parse` of the integration head, new `run_nonce` only if a new logical run starts) and relaunches with the owner's authorising words in the trigger message. Secrets never enter `args` or the trigger (F-7, T-2).

**Why the smoke run is not wasted work.** The smoke task is the real root task T01a. On the full run its chain replays from cache (if the key is content-addressed — see §10) or is reused via the idempotent `impl/T01a-<nonce>` branch (`status:'reused'`, ≈ 2 min instead of ≈ 30). Either way the permission prompts were surfaced at the price of one task, not a throwaway.

---

## 3. Agent roles and the separation table (who may author, who may vote, effort per role)

Rule (T-6, D-15, brief): whoever votes did not author what it votes on; every voter is a fresh `agent()` call that receives the card, the diff range/SHAs, ledger paths and the decision sheet — never the author's narrative, never another voter's verdict (except the explicit resolver and the fixer, which receive verbatim failures). `model` is inherited (Fable 5.1) everywhere except the three hardening cards (`model:'fable'`, explicit). Timeouts are H6 `withTimeout` values (unblock, do not kill).

| Role | Run | Authors (writes) | Votes / decides | Fresh context? | Effort | Own worktree? | Timeout | Est. duration / tokens |
|---|---|---|---|---|---|---|---|---|
| setup | R1 | `$BUILD_ROOT` (clone, venv, wheels, `gate.sh` copy, `AGENTS.md`, `.gate/baseline.json`), `chmod a-w` snapshots | — (returns facts; gate self-test verdict is machine-written) | n/a | medium | none (main checkout) | 25 min | 8 min / 40k `[E]` |
| symbolizer | R0 | `plan/findings-symbolized.json` | classifies UNVERIFIED critic findings by reproduction (confirmed/refuted/unverified) | yes | medium | none | 20 | 8 / 70k `[E]` |
| api-ledger | R0 | `plan/api-ledger.json` from `libsrc` (path:line per symbol/kwarg; known-bad idioms) | — | yes | medium | none | 25 | 10 / 90k `[E]` |
| catalog-provenance | R0 | `evidence/catalog/<repo>.json` (raw read-only Hub responses) | — | yes | low | none | 15 | 6 / 30k `[E]` |
| plan critic ×2 (lenses: decision-fidelity+completeness; sizing+overlap+runnable-acceptance) | R0 | nothing | `ready`/`not-ready` + `must_fix[]` | yes | high | none | 20 | 8 / 80k `[E]` |
| plan repair | R0 | corrected cards in `plan/cards/` | — | yes | medium | none | 15 | 6 / 50k `[E]` |
| test author (per task) | R1 | `tests/<task>/…` on branch `tests/<task>-<nonce>`; runs `gate.sh --confirm-red` | — (the red ledger decides) | yes | medium | own | 25 | 7 / 60k `[E]` |
| journeys author | R1 | `tests/journeys/` on `journeys/<nonce>` | — | yes | medium | own | 30 | 10 / 80k `[E]` |
| implementer (per task) | R1 | code on `impl/<task>-<nonce>`; runs `gate.sh`; commits per step; bundle | — (returns DoD rows with exit codes; the gate ledger decides) | yes | high | own | 45 | 12-18 / 120-180k `[E]` |
| fixer / pivot fixer | R1 | same branch (new commits) | — | yes (receives verbatim failures + fingerprint) | high | own (same tree) | 30 | 8 / 100k `[E]` |
| verifier (per task) | R1 | nothing (may write mutant patches under `$WT/mutants/`) | `pass`/`fail`/`unverifiable` + checks with exit codes; decision-fidelity checklist; idiom warnings cleared | yes | medium | `ro-<sha>` | 20 | 5 / 90k `[M class]` |
| refuter (per task) | R1 | nothing | `refuted` (default true) with an executed reproduction | yes | medium | `ro-<sha>` | 20 | 5 / 80k `[M class]` |
| task judge | R1 | nothing | `veto` only if reproduced; DoD YES/NO/UNBACKED with citations | yes | medium | `ro-<sha>` | 15 | 4 / 60k `[E]` |
| integrator | R1 | `integration/<nonce>` in the main checkout — **the only writer of that branch**; bundles; optional push | `merged`/`conflict`/`gate-failed` (gate ledger decides) | yes | low | main checkout | 15 | 2.5 / 25k `[E]` |
| conflict resolver | R1 | merge commit on a worktree of `integration/<nonce>` | — | yes | xhigh | own | 30 | 10 / 120k `[E]` |
| integration fixer | R1 | commits on `integration/<nonce>` worktree (≤ 2 rounds, then revert + park) | — | yes | high | own | 30 | 8 / 100k `[E]` |
| clean-checkout gate agent | R1 | nothing | `GATE_RUN` (machine ledger) incl. journeys and self-test | yes | low | `clean-<sha>` | 15 | 3 / 25k `[E]` |
| lens reviewer ×5 (correctness · security-and-secrets · zerogpu-quota-and-cost · api-and-mcp-contract · tests-and-gate) | R1/R2 | `plan/findings/r<N>-<lens>.json` | findings with reproduction | yes | high | `ro-<sha>` | 30 | 12 / 170k `[M class]` |
| finding refuter ×3 (reproduce · read-the-source · in-scope-and-decided) | R1/R2 | nothing | `refuted` | yes | medium | `ro-<sha>` | 15 | 4 / 70k `[E]` |
| panel judge ×3 (spec-compliance · test-evidence · release-readiness) | R1/R2/R3 | nothing | `satisfied` / `not-satisfied` / `blocked-needs-owner` | yes | xhigh | `ro-<sha>` | 20 | 6 / 90k `[E]` |
| ci-reader | R2/R3 | `evidence/orchestration/ci/<run>.json` | typed facts only (`verification_level: staging-verified`) | yes | medium | none | 20 | 6 / 50k `[E]` |
| synthesizer | all | `SYNTHESIS.md`, `RUNBOOK.md`, `PROMOTION_REQUEST.md`, `timing.json` | none (rows are copied from the ledger) | yes | high | none | 25 | 8 / 80k `[E]` |
| synth verifier | all | rewrites rows that do not match `git log`/ledgers | `accepted`/`rewritten` | yes | medium | none | 15 | 5 / 60k `[E]` |

**Separation invariants enforced in JS, not by prompt:** (1) label = `role:task:attempt` and the same `(role, task)` never appears twice with the same attempt; (2) a verifier/refuter/judge prompt string never contains an `IMPL_RESULT.notes` field (the prompt builder takes only `head_sha`, `base_sha`, `branch`, `bundle_path`); (3) the fixer prompt contains the verbatim `failures[]`/`reproduction` and the fingerprint, nothing else from voters; (4) the synthesizer prompt is built from the `ledger[]` array and file paths only.

---

## 4. Task model: schema of a PR-sized task, plan → tasks, DAG/waves, sizing, worktree → branch → bundle/SHA lifecycle, integration order, conflict-resolution agent, integration-test agent

### 4a. The decision sheet (`plan/decisions.json`) — law, written by the orchestrator, approved by the owner (F-9)

Implementers receive only this sheet and their card, never the raw queue. One line per id → decided value → build consequence:

| id | decided | build consequence |
|---|---|---|
| G-1 (revised) | Claude is the single writer | no hand-off brief; guards protect against Claude's own mistakes and the other agent's still-registered scheduled tasks (F-38) |
| G-1a / G-26 / G-27 / G-28 / G-29 | private GitHub repo = SSOT; CI (Trusted Publisher OIDC) the only production writer; staging Space + 16-token canary; auto-rollback on hard signals; gate = undefined-name lint + tests + import smoke + claim-vs-diff | T01b gate, T16 CI/promotion-as-code (written + unit-tested, never executed in R1) |
| G-2 | production stays down until the pipeline promotes | no rollback commit, no touch of the production Space anywhere in the workflow |
| M-5 | one production release, many staging promotions | every task is PR-sized and must be staging-promotable; "everything" = the card set below |
| G-3 | workbench AND gateway equally | core/UI/API split (T03-T08), API items first-class (T08, T12) |
| M-1 / M-1a (open) | hosted first (featherless via HF router), ZeroGPU fallback | `backends/hosted.py` first; worker second; automatic fallback ships OFF (flag) |
| M-2 | CPU UI/API Space + one ZeroGPU worker Space, one resident model | `worker/` package; no `spaces` import outside `worker/app.py`; draft model deleted; `gpu_size` is catalog config, never a request field |
| M-3 / M-4 | curated evidence-gated `models.yaml`, no free-text ids, admission after the 12-prompt harness | T13 harness, T14 catalog with provenance files; entries `status: unverified` until measured |
| G-15 + G-24 | in-container hardened `python_eval` (env allowlist; `prctl(PR_SET_DUMPABLE,0)` in the parent; rlimits + `start_new_session` + `killpg`; fresh cwd + output cap; operator secret flag, never API/MCP; no token files; exports off-Space; one narrow inference token) | T10a red-proofs per spec point; registry is THE gate (T06a) |
| G-19 | neutral persona set, cleaned, improved and extended by Claude, WITHOUT the excluded clause; README + tests consistent; no off-repo archive | T01c absence test (protected), T15 persona card with no history access |
| G-13 / G-6 / G-14 / G-16 / D-1..D-3 | maximal scope, multi-model selector, expand tool use, keep vision/video, SOTA on all levels | ship-but-flag list decides sequencing (§4e); video OFF at launch, images ON |
| Work split (revised) | Claude does platform and product | product cards (T07, T11, T15) are ordinary cards in the DAG |
| Owner process instructions | run fan-outs at max concurrency; resize before the implementation workflow; keep full reports | `args.cap`, `knobs` from the cap; JSON findings on disk |

Open decision ids (M-1a, G-25, G-18, G-4 budget) are listed in §15; the cards carry the proposed default and a `decision_pending` flag so the implementation is flag-switchable.

### 4b. Card schema (`plan/cards/<id>.json`)

```json
{
  "id": "T06b", "title": "core/agent.py run_turn", "area": "core", "spine": true, "size": "M",
  "est_minutes": {"impl": 18, "tests": 7}, "est_lines": 300,
  "dependsOn": ["T05", "T06a"], "speculativeOk": true,
  "files_allowed": ["core/agent.py", "core/engine.py", "tests/T06b/"],
  "deps_allowed": [],
  "interface": {"core/agent.py": ["def run_turn(req: GenerationRequest, session: Session, backend: Backend, tools: Registry) -> Iterator[Event]"]},
  "decision_ids": ["G-3", "M-2", "G-15"],
  "findings": [{"id": "chat-loop-ui-1", "corrected": "<verbatim CORRECTED RECOMMENDATION>", "symbol": "app.py::chat"},
               {"id": "chat-loop-ui-6", "corrected": "…", "symbol": "app.py::chat"}],
  "in_scope": ["…"], "out_of_scope": ["cross-turn preserve_thinking (flag OFF)"],
  "dod": [{"line": "rounds capped at MAX_TOOL_ROUNDS with a titled notice, never a bare '…'", "command": "$VENV/bin/python -m pytest tests/T06b/test_rounds.py -q", "expect": "exit 0"},
          {"line": "exactly one rejection-feedback round per turn, counted against the cap", "command": "…", "expect": "exit 0"}],
  "acceptance_tests": ["tests/T06b/test_rounds.py", "tests/T06b/test_pairing.py"],
  "gate_profile": "full", "model_override": null,
  "reading_list": ["plan/api-ledger.md#gradio", "core/types.py", "core/parsing.py"],
  "verification_level_expected": "local-stub",
  "outward_facing": false, "needs_gpu": false, "decision_pending": []
}
```

A card with empty `dod[]`, `acceptance_tests[]` or `files_allowed[]`, or a `dod[].command` that is not runnable under the venv, is rejected at script start (`validateCards()` throws) — D-1's "a spec entry with no acceptance check must FAIL validation".

### 4c. How the plan's 14 steps become 25 cards (plus 3 test-only cards)

Sizing rule: ≤ `knobs.taskMaxLines` changed lines (300 at cap ≤ 4, 220 at cap ≥ 8 — fewer, slightly larger chains where agent bootstrap overhead dominates; more, smaller chains where parallel slots are free), ≤ 12 files, one coherent commit per DoD line, every DoD line a command. The plan critic rejects oversize cards; the repair agent splits them.

| id | lens-4 step | title (what it builds) | deps | spine | files (owned) | ≈ lines |
|---|---|---|---|---|---|---|
| T01a | 1 | repo hygiene (smoke task): clone `f88b120`, delete `idx.json`, `runlog_tail.txt`, `maintenance/`, `deploy_space.py`, `keepalive.log`; `.gitignore` (`__pycache__/`, `*.pyc`, `.venv/`, `*.whl`, `*.log`); `.gitattributes` `* text=auto eol=lf` (commit 1) then `git add --renormalize .` (commit 2, `Renormalize-Only: yes`); `.editorconfig`; README front matter `python_version: "3.12"`; `AGENTS.md` (build rules) | — | yes | root files | 80 + renormalize |
| T01b | 1 | gate tooling: `tools/gate.sh` (repo copy of §7), `tools/claim_lint.py`, `tools/apicheck.py`, `tools/idiom_lint.py`, `tools/secrets_scan.py`, `tools/catalog_check.py`, `tests/protected.txt`, `tests/test_constants_pin.py`, `tests/test_import_contract.py`, `ruff.toml`, `requirements-dev.lock` (3.12), red-proof fixtures (`tests/fixtures/gate/{broken,false-claim}`) | T01a | yes | `tools/`, `tests/protected.txt`, `ruff.toml` | 300 |
| T01c | 1 | persona-archive test made repo-local; persona **absence** test (protected, minimal fragments) | T01a | no | `tests/test_personas.py` | 40 |
| T02a/b/c | 2 | characterisation pins in three batches: (a) `_as_messages`, `_render`, positional-inputs sync, import smoke; (b) `chat()` with scripted generator, `_estimate` table, gen-kwargs; (c) encode ladder, golden `/v1`, tool_parse xfails | T01b | yes | `tests/char/` | 150 each |
| T03 | 2 | lift-and-pin: pure functions moved verbatim into `core/{prompting,parsing,session}.py`, `core/tools/*`; `app.py` imports them; pins green; `--color-moved` shows moves only | T02a,b,c | yes | `app.py`, `core/*` | 300 (moves) |
| T04 | 3 | thin slice (new files only): `core/types.py`, `backends/{base,hosted,fake}.py`, `FakeEngine`, `api/app.py` (`/healthz` with git sha, `/v1/chat/completions` relay, `/v1/models`), `ui/placeholder.py`, `main.py` composition root, `models.yaml` (one entry with provenance), conformance suite skeleton (`fake` row; `recorded-hosted` row skipped-needs-owner) | T01b | yes | listed | 300 |
| T04c | 3 | cutover: `app.py` → 20-line composition root, README `app_file`, import smoke < 5 s | T03, T04 | yes | `app.py`, README | 40 |
| T05 | 4 | `StreamParser` + typed events + error taxonomy + `reasoning_content` in/out (openai-api-3/5/9, chat-loop-ui-4 corrected) | T04c | yes | `core/parsing.py`, `api/protocol.py` | 300 |
| T06a | 5 | tool registry (THE `python_eval` gate; families; flags) + `SessionStore` (TTL sweep, explicit keys, per-call throwaway bench for API/MCP; chat-loop-ui-2, security-tools-8 corrected) | T04c | yes | `core/tools/registry.py`, `core/session.py` | 250 |
| T06b | 5 | `core/agent.py` `run_turn`: rounds cap, one rejection-feedback round, call/result pairing, prompt-token budget before any backend call, titled notices (chat-loop-ui-1/3/6 corrected) | T05, T06a | yes | `core/agent.py`, `core/engine.py` | 300 |
| T07 | 6 | `build_ui(FakeEngine)`: selector, presets (no `gpu_size` knob), personas dropdown (edit-preserving), render, history replay as JSON content in the FINAL yield, Continue option, bench download/reset, grouped settings (chat-loop-ui-1/8/9 corrected) | T06b | yes | `ui/build.py` | 300 |
| T08 | 7 | gateway hardening: `X-API-Key` opt-in, size/role/range validation before any backend call, `run_in_threadpool` + `iterate_in_threadpool` + disconnect watcher, non-blocking semaphore → 429, ledger + `/v1/preflight` + `/status` (openai-api-1/2/7/8, gpu-lease-6 corrected) | T05 | no | `api/app.py`, `api/protocol.py` | 300 |
| T09a | 8 | worker Space code: `worker/app.py` (import-time load, `@spaces.GPU(size=…)` from catalog), `worker/encode.py` (encode ladder catching ValueError, `continue_final_message="reasoning_content"`), `worker/lease.py` (estimate from a measured EMA seeded conservatively, `max_time` from worker entry minus a *measured* cold-start margin, control dict intercepted for both consumers, stats record, StoppingCriteria on a stop event, heartbeat) — pure modules CPU-tested (gpu-lease-1/3/5/7/8, inference-perf-6 corrected) | T04c | no | `worker/*` | 300 |
| T09b | 8 | `backends/worker.py` (gradio_client with the scoped token from env only) + fallback order (flag OFF) + cancel plumbing | T09a, T05 | no | `backends/worker.py`, `core/catalog.py` | 200 |
| T10a | 9 | `python_eval` hardening per G-15 (1)-(6): runner with `setrlimit` inside the child (no `preexec_fn`), env allowlist, `prctl(PR_SET_DUMPABLE,0)` at startup, `start_new_session` + `killpg`, fresh cwd, output cap, operator flag; red-proofs with `CANARY_SECRET` (never prints environ) | T06a | no | `core/tools/sandbox.py`, `main.py`, `tests/T10a/` | 250 (`model:'fable'`) |
| T10b | 9 | SSRF: one opener (resolve once, `is_global`, unwrap v4-mapped, dial the literal IP, TLS SNI kept), redirect validated before the hop, auth stripped on host change, port allowlist, `pdf_read` through it, Firecrawl exemption, total wall-clock budget (security-tools-3/9 corrected) | T06a | no | `core/tools/web.py` | 250 (`model:'fable'`) |
| T10c | 9 | `regex` timeout, calculator allowlist + `bit_length` bound, archive caps before read, `apply_patch` ambiguity/offset/EOL/newline, network-origin neutraliser + narrow taint rule (security-tools-4/5/6/7 corrected) | T06a | no | `core/tools/file_bench.py`, `core/tools/knowledge.py` | 300 (`model:'fable'`) |
| T11 | 10 | vision/video as OpenAI parts end-to-end; images ON, video flag OFF; caps; `vision:false` → 400 with zero backend calls; `_user_text` reads both shapes (critic-2) | T07, T08 | yes | `core/prompting.py`, `ui/build.py`, `api/protocol.py` | 200 |
| T12 | 11 | MCP `ask/poll/status/preflight` via `gr.api`; `chat` hidden; clamps; listing snapshot test (chat-loop-ui-7, security-tools-2 corrected) | T08 | no | `api/mcp.py` | 200 |
| T13 | 12 | eval harness: 12 prompts, backend-agnostic, `--backend fake --dry-run` default, `--i-accept-cost` + owner env var, `max_retries=0`, cost ledger, zero-call test; admission schema | T04 | no | `evals/`, `tools/harness.py` | 300 |
| T14 | 13 | catalog fill from `evidence/catalog/*.json` (status `unverified` where not measured), README table generator (`tools/render_readme.py --check`) | T13, T04c | no | `models.yaml`, `tools/render_readme.py` | 150 |
| T15 | 13 | personas (G-19 set: Analyst default · Research Analyst · Prompt & Agent-spec Architect (cleaned) · Code Engineer · Security Reviewer · Document & Vision Analyst · Planner/Operator · Custom) with role/output contract/tool guidance/quota-aware behaviour; wiring; README generated (test count, tools, catalog) | T07, T14, T01c | yes | `core/personas.py`, README | 250 |
| T16 | 14 | CI + promotion as code: `.github/workflows/{gate,deploy-staging,promote,health}.yml` (OIDC, `permissions:` blocks, SHA-pinned actions, `production` environment), `space.yaml` + drift check, `tools/promote.py` (sha check, `hf spaces wait`, canary decision rule with last-known-good control, rollback = redeploy known-good), scheduled health job; unit-tested against fakes; **never executed in R1** | T01b | no | `.github/`, `tools/promote.py`, `space.yaml` | 300 |
| J | — | journeys J1-J6 (held-out, own branch): stub boot < 10 s; tool transcript survives a turn; two sessions → two benches; `/v1` streams, stops on disconnect, `finish_reason: length`; MCP lists only typed tools, never `python_eval`; `python_eval` child cannot read the parent env (canary) | T01b | no | `tests/journeys/` | 250 |

Spine (longest chain): T01a → T01b → T02{a,b,c} → T03 → T04c → {T05 ‖ T06a} → T06b → T07 → T11 → T15 — **depth 9-10**. T04 and T16 and T13 and J are off-spine and fill idle slots early (they depend only on T01b). Review fix tasks (`RF<round>-<key>`) are cards generated by the script from confirmed findings with `dependsOn: []`, `files_allowed: [finding.file]`, `size: 'S'`.

### 4d. DAG, ranks, admission "waves", overlap rule

- `rank(t)` = longest path from `t` to any sink in estimated minutes (`est_minutes.impl + 14` per node, the +14 being the average verify/judge/integrate tail) — computed in JS from the cards, deterministic.
- `mergeOrder` = tasks sorted by `(-rank, id)`. Dependencies always precede dependents (a dependency's rank is strictly larger).
- **Overlap rule (D-5/F-14):** for every unordered pair (neither is an ancestor of the other) whose `files_allowed` intersect, the script adds a synthetic edge from the earlier `mergeOrder` task to the later one and logs it. No two concurrently in-flight tasks share a file.
- **Admission = the wave:** at most `knobs.waveSize` tasks in the build phase at once; when a slot frees, the highest-rank *ready* task (all deps integrated — or built, if `knobs.speculativeDeps` and the card says `speculativeOk`) is admitted. Defaults: cap 2 → `waveSize 2`; cap 14 → 4; cap 16 → 5 (each chain uses ≤ 2 concurrent agents, so queued agents ≤ cap and FIFO starvation cannot occur). A barrier wave (all of wave k before any of wave k+1) idles every slot during the wave's tail; admission does not, and it degenerates to exactly research-2's waves when every task depends on the previous one.
- **Test authoring:** `knobs.frontLoadTests` (cap ≥ 8) runs test authors for all tasks up-front under a second semaphore `taSlots = cap − 2·waveSize` so implementers are never queued behind them; at cap 2 the test author runs as the first link of its task's chain (no idle slot exists to front-load into).

### 4e. Ship-but-flag (sequencing under "maximal"): automatic hosted→worker fallback OFF · server-side tools for `/v1`/MCP OFF · `http_request` POST + third-party reader OFF · video OFF (images ON) · automatic lease chaining OFF (explicit Continue ON) · cross-turn `preserve_thinking` OFF · `python_eval` operator-flag only · `xlarge` operator config only. Each flag is a `config.py` constant with a constants-pin test row, so flipping one is a one-line PR through the same gate.

### 4f. Worktree → branch → bundle/SHA lifecycle (T-9, F-2, F-33, F-43)

```
test author   git -C $REPO worktree add $WT/tests-<id>-<nonce> -b tests/<id>-<nonce> <base>   → commits → gate.sh --confirm-red <base> tests/<id>-<nonce>
implementer   git -C $REPO worktree add $WT/impl-<id>-<nonce>  -b impl/<id>-<nonce>  <base>   → git merge --no-ff tests/<id>-<nonce> → commits per DoD line
              → gate.sh --tree $WT/impl-<id>-<nonce> --range <base>..HEAD → .gate/last_run.json (ledger_hash)
              → git bundle create $BUNDLES/<id>-<nonce>.bundle <base>..HEAD   (survives worktree AND branch deletion)
              idempotent re-run: if impl/<id>-<nonce> exists and gate.sh is GREEN on it → status:'reused'
verifier/refuter/judge   read-only worktree $WT/ro-<head_sha> (created by gate.sh --clean if absent); never edit
integrator    main checkout: integration/<nonce> ← git merge --no-ff <head_sha>; gate.sh --range <prev>..HEAD;
              git cherry integration/<nonce> impl/<id>-<nonce> must be empty; git bundle create $GRILL/evidence/build-bundles/<n>-<id>.bundle <prev>..HEAD
              (small incremental bundle → synced to GitHub by save-to-repo.sh within 5 min: durable even if the Codespace is deleted)
              optional: git push <approvals.push_remote> integration/<nonce> impl/<id>-<nonce>   (only if the owner named the remote)
              then: git worktree remove $WT/impl-<id>-<nonce> (only after cherry is empty); prune ro-* worktrees of merged SHAs
```

`$BUILD_ROOT = /workspaces/qwen38-space-build` (durable, outside both the toolchain repo and the rsync'd grill folder; a nested `.git` inside the grill folder would be swept into the toolchain repo by `save-to-repo.sh --delete`); `$REPO = $BUILD_ROOT/space`; `$WT = $BUILD_ROOT/wt`; `$VENV = $BUILD_ROOT/venv312`; `$BUNDLES = $BUILD_ROOT/bundles`. The snapshots under the scratchpad are `chmod -R a-w` by setup and used only as clone sources.

### 4g. Integration order, conflict-resolution agent, integration-test agent

- **Order:** the merge queue processes `mergeOrder` strictly (deterministic → every integration head SHA is a pure function of results → prompts cache). Task *k* merges when it is built **and** task *k−1* has merged (or was skipped as blocked). A blocked task is a no-op in the queue and blocks its dependents with reason `dep-blocked`.
- **Integrator (effort low):** merge `--no-ff`, run `gate.sh --range`, assert `git cherry` empty, bundle, optional push. On any conflict: `git merge --abort`, return the hunks (`ours`/`theirs`), **do not resolve**.
- **Conflict resolver (effort xhigh, fresh, own worktree on `integration/<nonce>` at `prev`):** receives the two cards and the hunks only; resolves so both DoD sets hold; runs the gate; commits; bundles to `$BUNDLES/merge-<id>.bundle`; the integrator fast-forwards and re-gates. One resolver attempt; failure → `parked:conflict`.
- **Gate-red after a clean merge (F-34):** an integration fixer scoped to `integration/<nonce>` with both cards, ≤ 2 rounds, else `git revert -m 1` of the merge and `parked:integration-red`; the revert is itself gated.
- **Integration-test agent = clean-checkout gate (effort low):** after every `knobs.cleanGateEvery` (4) merges and after the last: `gate.sh --clean <head> --journeys --self-test` in a fresh detached worktree; its `GATE_RUN` ledger is what the judges see (T-12). A red clean gate stops admissions (typed `blocked:gate-red-upstream` for every not-yet-admitted task), triggers one integration-fix round, and resumes admissions only when green.

---

## 5. Inner loop per task (test author → confirm-RED → implementer → gate → fresh verifier → refuter → bounded fixer → judge) with exact counters and exit conditions

```
                 ┌────────────── knobs.frontLoadTests ? (Tests phase) : (first link of the chain) ──────────────┐
[test author] ──► gate.sh --confirm-red <base> tests/<id>   (deterministic; RED ledger; exit 5 is NOT red)
      │  ok
[implementer] ──► gate.sh --tree --range  (GREEN ledger required; DoD rows with exit codes)   ── status failed → blocked:implement
      │
      ├──► [verifier]  ─┐   parallel (2 fresh, read-only, both re-run gate.sh; verifier also runs --confirm-red and --mutate)
      └──► [refuter]   ─┘
      │  reduceVerdicts(): [] = pass   (deterministic; §5b)
      │  failures → fingerprint → fixer (≤ MAX_FIX total) ─► back to verifier ‖ refuter
      │
[judge] ── veto only if reproduced ── veto → fixer (counts against MAX_FIX, ≤ MAX_VETO vetoes) → verifier ‖ refuter → judge
      │  no-veto
   built ──► merge queue (§4g)
```

### 5a. Counters (all `const` from `args.knobs`, all logged when they fire)

| counter | value | scope | exhaustion → typed result |
|---|---|---|---|
| `MAX_FIX` | 3 | total fixer agents per task (verify-driven + veto-driven combined) | `blocked:verify-exhausted` |
| two-strikes | fingerprint of `failures[]` equal to the previous attempt's | per task | attempt 2 with the same fingerprint → **pivot fixer** (schema requires `alternatives: minItems 2` and `chosen`); a third identical fingerprint → `blocked:fingerprint-repeat` (never a 4th identical attempt, D-8) |
| `MAX_VETO` | 1 | reproduced judge vetoes per task | second reproduced veto → `blocked:judge-veto` |
| null retries | 1 cheap identical retry for verifier/refuter/judge/integrator; 1 **narrower** retry (`model:'fable'`, reading list halved, "continue from the last commit") for test author/implementer/fixer | per `(role, task)` | second null → `blocked:agent-null:<role>` (F-41/F-42) |
| oscillation | `failures` fingerprint sequence A→B→A | per task | → `blocked:oscillation` (SD-14) |
| expansion | fixer diff touches > 2 files outside `files_allowed` or `changed_lines > 2 × est_lines` | per fixer return | → the fixer's result is rejected (`blocked:scope-expansion` after MAX_FIX) and logged; the reviewer never sees an out-of-allowlist diff as green |
| timeout | H6 `withTimeout` per role (§3) | per agent | drop receipt → treated as null (retry policy above), never green (D-21) |
| outward action | `outward_actions_taken.length > 0` on any return | run | **run aborts** to the synthesizer with `abort:outward-action` (F-35) |
| install | `installed_packages.length > 0` on any non-setup return | per return | result rejected → `blocked:installed-packages` (F-5) |

### 5b. The deterministic reduce (`reduceVerdicts`) — what "pass" means

A task's verify leg passes iff **all** hold (D-12's predicate as one shared reducer, `unitDone()` in §13):

1. `impl.status ∈ {ok, reused}`, `impl.head_sha` non-empty, `impl.repo_toplevel === args.build_repo`, `impl.commits ≥ 1`.
2. `impl.dod.every(d => d.exit_code === 0)` and `impl.dod.length === card.dod.length` (F-19: DoD lines done, not "item done").
3. `verify.verdict === 'pass'` **and** `verify.ledger_hash_observed === impl.ledger_hash` **and** `verify.gate_profile === card.gate_profile` **and** `verify.pytest.collected > 0` (exit 5 is red) **and** `verify.red_confirmed === true` **and** `verify.mutants.length ≥ 1 && verify.mutants.every(m => m.killed)` **and** `verify.hunks_cited.length ≥ 1` **and** `verify.decision_fidelity.every(d => d.ok)` **and** every idiom warning in the ledger appears in `verify.idiom_warnings_cleared` with a justification.
4. `refute.refuted === false` **or** `refute.reproduction.exit_code === 0` (a refutation whose reproduction command did not fail is not a refutation; the refuter's default is `refuted:true`, so an empty reproduction kills nothing but is logged as `refute:no-evidence`).
5. `verify.protected_touched.length === 0` unless the card lists the file **and** the range carries `Protected-Edit: <card-id>`.
6. `impl.claims` ⊆ diff (checked by the gate's claim lint; the verifier copies the step's exit code).

`failures[]` = the union of `verify.failures` (verbatim) and `refute.reproduction` (when it refutes) — the exact failing output, never a summary (SD-15). The fingerprint is FNV-1a over the sorted, whitespace-normalised failure lines with hex digits stripped (so line numbers and SHAs do not change it).

### 5c. Exit conditions (exactly one fires; every one is logged with the reason)

`built` · `blocked:tests-missing` · `blocked:red-not-confirmed` · `blocked:implement` · `blocked:verify-exhausted` · `blocked:fingerprint-repeat` · `blocked:oscillation` · `blocked:judge-veto` · `blocked:agent-null:<role>` · `blocked:scope-expansion` · `blocked:installed-packages` · `blocked:dep-blocked` · `blocked:gate-red-upstream` · `blocked:budget` · `deferred:agent-cap` · `abort:outward-action`.

### 5d. Why this loop is cheap where research-2's is not

Research-2 §4.5 runs verify → fix → audit → fix → critic → fix (three sequential LLM legs plus their fixers) per task; measured at 4-5 min per fresh reader, that is ≥ 15 min of critical path and ≥ 3 agents before the first line of the next task can start. Here the audit's content (decision fidelity, claim-vs-diff, API correctness) is a checklist inside the verifier plus two deterministic gate steps, and the critic's content (what is missing) is the refuter's kill mandate plus the tree-level lens review that has to happen anyway. Per task: 2 parallel fresh legs (≈ 5 min wall) + 1 judge (≈ 4 min), ≈ 12 wall-minutes and ≈ 2 agents saved per task; ≈ 25 tasks → ≈ 50 agents and ≈ 5 h of agent-time saved at no loss of separation.

---

## 6. Outer loop per wave and for the whole tree (review → refute → judge panel `satisfied`; dry counter; MAX_ROUNDS; budget reserve)

### 6a. Per "wave" (every `cleanGateEvery` merges) — the incremental half

After each clean-checkout gate (`GATE_RUN`), if `knobs.incrementalReview` (cap ≥ 8): the five lens reviewers are spawned on the **delta** `lastReviewed..head` while the build continues (they read `ro-<head>`, so the build's later merges cannot move under them). Their findings are deduped against `seen` (key = `file::symbol::normalised-title`), fresh ones go through the 3-lens refute immediately, and confirmed ones become `RF` cards **held** until the build's `runDag` completes (fixed merge order per phase). At cap 2 (`incrementalReview:false`) no reviewer runs during the build — there is no idle slot to review in, and the same reviewers would be paid again at the end.

### 6b. Whole tree — the loop

```
round = 0; dry = 0; verdict = null; seen = Set(); confirmedAll = []
loop:
  stop if verdict.satisfied            → 'judge-satisfied'
  stop if round ≥ MAX_ROUNDS (3)       → 'max-rounds'
  stop if dry ≥ DRY_ROUNDS (2)         → 'dry-rounds'       (only after a DoD-inversion pass also returned nothing new)
  stop if !budgetOk('review')          → 'budget-reserve'
  stop if agentCount ≥ AGENT_CAP_SOFT  → 'agent-cap'
  round++
  reviews  = parallel(5 lenses on delta since lastReviewed, KNOWN = sorted(seen))          barrier: the refute step needs the deduped set
  fresh    = dedup(reviews.findings, seen)   (vs seen, never vs confirmed)
  alive    = for each fresh finding: parallel(3 refuter lenses) → alive iff ≥ 2 not-refuted AND ≥ 1 cites an executed failing reproduction
  dry      = alive.length ? 0 : dry + 1
  if alive: RF cards → runDag(RF cards) (same inner loop, same merge queue, appended after existing mergeOrder) → clean gate
  if dry ≥ DRY_ROUNDS and !inversionDone: one DoD-inversion reviewer (forbidden to reuse the lenses' probes; starts from the decision sheet + DoD rows and tries to falsify each end-state) → its findings re-enter as fresh; inversionDone = true
  votes    = parallel(3 panel judges: spec-compliance · test-evidence · release-readiness)   barrier: majority
  verdict  = satisfied iff ≥ 2 votes AND deterministic preconditions hold:
             blocked.filter(severity high).length === 0, last clean gate GREEN with journeys all pass, open reproduced findings === 0
  if any vote === 'blocked-needs-owner' → stop 'judge-blocked-needs-owner'
```

Only the panel schema has the `satisfied` enum (T-3); the script may downgrade a `satisfied` majority when the deterministic preconditions fail (D-24: gates decide, judges veto), never upgrade one. Every stop reason is logged with the round count, confirmed total and blocked count.

### 6c. Bounds and reserve

- `MAX_ROUNDS` = 3 (SD-14/S-16: gains flatten after 3-4 repair rounds; regressions start), `DRY_ROUNDS` = 2, `MAX_FIX` = 3 per RF card.
- `RESERVE` = `knobs.reserveTokens` (default 200k output tokens: last clean gate + 3 judges + synthesizer + verifier + slack); `budgetOk()` is `!budget.total || budget.remaining() > RESERVE` — with no `+Nk` directive `budget.total` is null and the round/agent caps are the backstop (T-20, F-45).
- `AGENT_CAP_SOFT` = 850 of the 1,000 lifetime cap; `knobs.maxAgentsThisRun` (110 at cap 2) stops **admissions** earlier so a run ends inside the Codespace's attention span and resumes cleanly; the synthesizer always runs (§10).
- Refuted findings are recorded in `plan/findings/refuted.json` with the reproduction that killed them (D-17: recorded, not deleted); style-only findings (`affects_correctness_or_requirement:false`) are logged and never queued (S-11/AP-14).

### 6d. Throughput accounting for the outer loop

Per round at cap 2: 5 reviewers × 12 min = 60 agent-min, + 3 refuters × ≈ 6-8 fresh findings × 4 min ≈ 72-96, + RF chains (≈ 4 × 51 ≈ 204 in round 1, ≈ 1 × 51 later), + 3 judges × 6 = 18 → round 1 ≈ 370 agent-min, round 2 ≈ 170, round 3 (dry) ≈ 80 → ≈ 620 agent-min ≈ 5.2 h of wall at cap 2, ≈ 70 min at cap 14 when round 1 overlaps the build. This is why `incrementalReview` is on only when slots are idle.

---

## 7. Deterministic gates: exact `gate.sh` contents and where each runs (in-worktree pre-merge, on the merged tree, from a clean checkout)

`gate.sh` is written by the **setup agent** verbatim from this section into `$BUILD_ROOT/gate.sh` (the copy every verifier runs) and by **T01b** into `tools/gate.sh` (the copy CI runs); step 12 makes the two tamper-evident against each other. The ledger it writes is the only admissible evidence of verification (F-12). Every Python invocation runs with an **allow-listed environment** (`env -i`), so no test can read `GITHUB_TOKEN`/`ANTHROPIC_API_KEY` even if it dumps `os.environ` (F-7), the network is black-holed (F-29), `SPACES_ZERO_GPU` is unset (worker code is exercised as plain functions and the ledger says so), and only Python 3.12 is accepted (F-5/F-23).

```bash
#!/usr/bin/env bash
# gate.sh v1 — deterministic gate for the qwen38 Space rebuild.
# The ledger it writes (.gate/last_run.json, self-hashed) is the ONLY admissible evidence of verification.
# Runs ONLY under the 3.12 venv; installs nothing; opens no network; never echoes an environment.
set -u
GATE_VERSION=1
BUILD_ROOT="${BUILD_ROOT:?BUILD_ROOT is required}"          # durable root: space/, venv312/, wt/, bundles/, ledgers/, mutants/
VENV="${VENV:-$BUILD_ROOT/venv312}"; PY="$VENV/bin/python"
REPO="${REPO:-$BUILD_ROOT/space}"; WT="$BUILD_ROOT/wt"; LEDGERS="$BUILD_ROOT/ledgers"
TREE=""; RANGE=""; PROFILE="full"; OUT=""; MUTANT=""; RED_BASE=""; RED_TESTS=""; RED_PATHS=""
JOURNEYS=0; SELFTEST=0; CLEAN_SHA=""; TASK_TESTS=""
while [ $# -gt 0 ]; do case "$1" in
  --tree) TREE="$2"; shift 2;;                 # worktree under test (default: $REPO)
  --range) RANGE="$2"; shift 2;;               # BASE..HEAD for range checks (claim lint, blobs, secrets, protected paths)
  --profile) PROFILE="$2"; shift 2;;           # full | bootstrap  (bootstrap is recorded in the ledger; the script rejects it unless the card allows it)
  --confirm-red) RED_BASE="$2"; RED_TESTS="$3"; RED_PATHS="$4"; shift 4;;   # tests-only diff of RED_TESTS on RED_BASE must FAIL on RED_PATHS
  --mutate) MUTANT="$2"; TASK_TESTS="$3"; shift 3;;                          # apply one-line patch; TASK_TESTS must go red; revert
  --journeys) JOURNEYS=1; shift;;              # run tests/journeys (held-out compositional)
  --clean) CLEAN_SHA="$2"; shift 2;;           # fresh detached worktree at sha, then everything
  --self-test) SELFTEST=1; shift;;             # red-proofs: RED on f88b120, RED on the false-claim fixture, GREEN on the cleaned base
  --out) OUT="$2"; shift 2;;
  *) echo "gate: unknown arg $1" >&2; exit 64;;
esac; done
mkdir -p "$WT" "$LEDGERS" "$BUILD_ROOT/tmp"
STEPS="$(mktemp "$BUILD_ROOT/tmp/steps.XXXXXX")"; : > "$STEPS"
T0=$SECONDS; STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; RED=0
LOGDIR="$(mktemp -d "$BUILD_ROOT/tmp/gatelog.XXXXXX")"

# ---- env allow-list: EVERY python run goes through here (no inherited secrets, no network, no ZeroGPU emulation) ----
SAFEHOME="$(mktemp -d "$BUILD_ROOT/tmp/home.XXXXXX")"
run_py() {  # run_py <cwd> <args...>
  local cwd="$1"; shift
  ( cd "$cwd" && env -i PATH="$VENV/bin:/usr/bin:/bin" HOME="$SAFEHOME" LANG=C.UTF-8 LC_ALL=C.UTF-8 TMPDIR="$BUILD_ROOT/tmp" \
      PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 PYTHONNOUSERSITE=1 \
      HF_HUB_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 HF_HUB_DISABLE_TELEMETRY=1 TRANSFORMERS_OFFLINE=1 \
      GRADIO_ANALYTICS_ENABLED=False HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 NO_PROXY=127.0.0.1,localhost \
      GATE_CANARY="gate-canary-$$" "$PY" "$@" )
}
step() {  # step <name> <cmd...>  → records name, exit code, seconds, log path; RED on non-zero
  local name="$1"; shift; local s=$SECONDS; local log="$LOGDIR/$name.log"
  "$@" >"$log" 2>&1; local rc=$?
  printf '%s\t%s\t%s\t%s\n' "$name" "$rc" "$((SECONDS - s))" "$log" >> "$STEPS"
  [ "$rc" -eq 0 ] || RED=1
  return $rc
}
skip() { printf '%s\t%s\t%s\t%s\n' "$1" "skipped" "0" "-" >> "$STEPS"; }

# ---- 0. pre-step: interpreter, stray servers, stale locks (fail closed) ----
case "$("$PY" -V 2>&1)" in "Python 3.12."*) ;; *) echo "gate: refusing: $PY is not 3.12.x" >&2; printf 'python\t1\t0\t-\n' >> "$STEPS"; RED=1;; esac
for pid in $(ss -ltnp 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u); do
  case "$(readlink "/proc/$pid/cwd" 2>/dev/null)" in "$BUILD_ROOT"*) kill "$pid" 2>/dev/null && echo "gate: killed stray listener $pid";; esac
done
find "$REPO/.git" "$WT" -name index.lock -mmin +10 -delete 2>/dev/null
[ "$RED" -eq 0 ] || { echo "GATE RED (pre-step)"; exit 1; }

# ---- clean-checkout mode: fresh detached worktree ----
if [ -n "$CLEAN_SHA" ]; then
  TREE="$WT/clean-$CLEAN_SHA"
  [ -d "$TREE" ] || git -C "$REPO" worktree add --detach "$TREE" "$CLEAN_SHA" >/dev/null 2>&1 || { echo "gate: cannot create clean worktree" >&2; exit 1; }
  [ -n "$RANGE" ] || RANGE="$(git -C "$REPO" merge-base "$CLEAN_SHA" "${GATE_BASE_SHA:-$CLEAN_SHA}")..$CLEAN_SHA"
fi
[ -n "$TREE" ] || TREE="$REPO"
HEAD_SHA="$(git -C "$TREE" rev-parse HEAD)"; BASE_OF_RANGE="${RANGE%%..*}"
[ "$(git -C "$TREE" rev-parse --show-toplevel)" = "$TREE" ] || { echo "gate: $TREE is not a worktree toplevel" >&2; exit 1; }

# ---- 1. repo hygiene: line endings, LFS, blobs, junk ----
hyg() {
  git -C "$TREE" ls-files --eol | grep -E 'w/crlf|w/mixed|i/crlf' && { echo "CRLF/mixed endings present"; return 1; }
  [ -z "$(git -C "$TREE" lfs ls-files 2>/dev/null)" ] || { echo "LFS-tracked files present"; return 1; }
  git -C "$TREE" ls-files | grep -E '(^|/)(__pycache__/|\.venv/)|\.pyc$|\.whl$|\.log$|^idx\.json$|^runlog_tail\.txt$' && { echo "junk tracked"; return 1; }
  if [ -n "$RANGE" ]; then
    git -C "$TREE" rev-list --objects "$RANGE" | git -C "$TREE" cat-file --batch-check='%(objecttype) %(objectsize) %(rest)' \
      | awk '$1=="blob" && $2>5242880 {print "blob >5MB: "$3; bad=1} END {exit bad}' || return 1
  fi
  return 0
}
step hygiene hyg

# ---- 2. undefined names / syntax under py312 ----
if [ -x "$VENV/bin/ruff" ]; then step ruff run_py "$TREE" -m ruff check --select F821,F811,F401,E9 --target-version py312 .
elif run_py "$TREE" -c "import pyflakes" 2>/dev/null; then step pyflakes run_py "$TREE" -m pyflakes .
else printf 'ruff\t1\t0\t-\n' >> "$STEPS"; RED=1; echo "gate: no undefined-name linter installed (tool-missing = RED)"; fi
step compileall run_py "$TREE" -m compileall -q -x '(\.venv|wt|node_modules)' .

# ---- 3. apicheck: every call into gradio/spaces/huggingface_hub/transformers/gradio_client/fastapi has kwargs the pinned wheel accepts ----
if [ "$PROFILE" = "full" ]; then
  if [ -f "$TREE/tools/apicheck.py" ]; then step apicheck run_py "$TREE" tools/apicheck.py ${RANGE:+--range "$RANGE"}
  else printf 'apicheck\t1\t0\t-\n' >> "$STEPS"; RED=1; echo "gate: tools/apicheck.py missing (full profile requires it)"; fi
else skip apicheck; fi

# ---- 4. pytest twice, sockets off, counts vs baseline, skip/xfail non-increasing ----
PYT_ARGS=(-q -p no:cacheprovider --disable-socket --allow-hosts=127.0.0.1 -p no:randomly)
run_pytest() { run_py "$TREE" -m pytest "${PYT_ARGS[@]}" --junitxml="$LOGDIR/junit-$1.xml" tests; }
step pytest1 run_pytest 1; RC1=$?
step pytest2 run_pytest 2; RC2=$?
counts() { run_py "$TREE" - "$LOGDIR/junit-$1.xml" <<'EOF'
import sys, xml.etree.ElementTree as ET
r = ET.parse(sys.argv[1]).getroot(); s = r if r.tag == 'testsuite' else r.find('testsuite')
t = int(s.get('tests', 0)); f = int(s.get('failures', 0)); e = int(s.get('errors', 0)); k = int(s.get('skipped', 0))
xf = sum(1 for c in s.iter('testcase') if c.find('skipped') is not None and 'xfail' in (c.find('skipped').get('type') or '').lower())
print(t, t - f - e - k, f + e, k - xf, xf)
EOF
}
C1="$(counts 1 2>/dev/null || echo '0 0 0 0 0')"; C2="$(counts 2 2>/dev/null || echo '0 0 0 0 0')"
[ "$C1" = "$C2" ] || { printf 'pytest-deterministic\t1\t0\t-\n' >> "$STEPS"; RED=1; echo "gate: two pytest runs disagree: [$C1] vs [$C2] (flaky)"; }
set -- $C1; COLLECTED=$1; PASSED=$2; FAILED=$3; SKIPPED=$4; XFAILED=$5
[ "$COLLECTED" -gt 0 ] || { printf 'pytest-collected\t1\t0\t-\n' >> "$STEPS"; RED=1; echo "gate: 0 tests collected (exit 5 is RED)"; }
if [ -f "$BUILD_ROOT/.gate-baseline.json" ]; then
  BASE_COLLECTED="$(run_py "$TREE" -c "import json;print(json.load(open('$BUILD_ROOT/.gate-baseline.json'))['collected'])")"
  REMOVED=0; [ -n "$RANGE" ] && REMOVED="$(git -C "$TREE" log --format=%B "$RANGE" | grep -c '^Tests-Removed:' || true)"
  [ "$COLLECTED" -ge $((BASE_COLLECTED - REMOVED)) ] || { printf 'pytest-count\t1\t0\t-\n' >> "$STEPS"; RED=1; echo "gate: collected $COLLECTED < baseline $BASE_COLLECTED - removed $REMOVED"; }
  BASE_SKIP="$(run_py "$TREE" -c "import json;d=json.load(open('$BUILD_ROOT/.gate-baseline.json'));print(d['skipped']+d['xfailed'])")"
  if [ $((SKIPPED + XFAILED)) -gt "$BASE_SKIP" ] && ! { [ -n "$RANGE" ] && git -C "$TREE" log --format=%B "$RANGE" | grep -q '^Skip-Added:'; }; then
    printf 'pytest-skips\t1\t0\t-\n' >> "$STEPS"; RED=1; echo "gate: skip/xfail count rose without a Skip-Added trailer"; fi
fi

# ---- 5. import smoke (<5 s, no models, no ZeroGPU) + worker import with stubs + import contract ----
smoke_app() { timeout 5 env -i PATH="$VENV/bin:/usr/bin:/bin" HOME="$SAFEHOME" HF_HUB_OFFLINE=1 GRADIO_ANALYTICS_ENABLED=False \
  HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 QWEN_STUB=1 "$PY" -c "import app" ; }
( cd "$TREE" && step import-smoke smoke_app )
if [ -d "$TREE/worker" ]; then
  smoke_worker() { timeout 10 env -i PATH="$VENV/bin:/usr/bin:/bin" HOME="$SAFEHOME" HF_HUB_OFFLINE=1 PYTHONPATH="$TREE/tests/stubs" "$PY" -c "import worker.app"; }
  ( cd "$TREE" && step import-smoke-worker smoke_worker )
else skip import-smoke-worker; fi
[ -f "$TREE/tests/test_import_contract.py" ] && step import-contract run_py "$TREE" -m pytest -q -p no:cacheprovider tests/test_import_contract.py || skip import-contract

# ---- 6. claim-vs-diff lint over every commit in the range (numbers, identifiers, "N tests" must appear in the whitespace-insensitive diff) ----
if [ -n "$RANGE" ] && [ "$PROFILE" = "full" ]; then
  [ -f "$TREE/tools/claim_lint.py" ] && step claim-lint run_py "$TREE" tools/claim_lint.py --range "$RANGE" || { printf 'claim-lint\t1\t0\t-\n' >> "$STEPS"; RED=1; }
else skip claim-lint; fi

# ---- 7. idiom lint: known-bad idioms from the CORRECTED lines (warnings the verifier must clear) + test-detection idioms (errors) ----
idiom() {
  local warn=0 err=0 files
  files="$( [ -n "$RANGE" ] && git -C "$TREE" diff --name-only "$RANGE" -- '*.py' || git -C "$TREE" ls-files '*.py')"
  [ -n "$files" ] || return 0
  ( cd "$TREE" && grep -nE 'preexec_fn=|__wrapped__|lease_s *- *30|shutil\.rmtree\(.*(unload|_drop)|prefill_chunk_size' $files ) && warn=1
  ( cd "$TREE" && grep -nE 'PYTEST_CURRENT_TEST|sys\.modules\.get\("pytest"\)|"pytest" in sys\.modules' $(echo "$files" | grep -v '^tests/') ) && err=1
  [ "$warn" -eq 1 ] && echo "IDIOM-WARN (verifier must clear each with a justification)"
  [ "$err" -eq 0 ]
}
step idiom-lint idiom
grep -q 'IDIOM-WARN' "$LOGDIR/idiom-lint.log" 2>/dev/null && IDIOM_WARN=1 || IDIOM_WARN=0

# ---- 8. generated README, constants pin, persona absence, catalog schema + provenance ----
[ -f "$TREE/tools/render_readme.py" ] && step readme-check run_py "$TREE" tools/render_readme.py --check || skip readme-check
[ -f "$TREE/tests/test_constants_pin.py" ] && step constants-pin run_py "$TREE" -m pytest -q -p no:cacheprovider tests/test_constants_pin.py || skip constants-pin
[ -f "$TREE/tests/test_personas.py" ] && step persona-absence run_py "$TREE" -m pytest -q -p no:cacheprovider tests/test_personas.py -k absence || skip persona-absence
[ -f "$TREE/tools/catalog_check.py" ] && step catalog-check run_py "$TREE" tools/catalog_check.py models.yaml || skip catalog-check

# ---- 9. secrets scan over the range diff and over the gate's own outputs ----
SECRET_RE='(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)'
secrets() {
  if [ -f "$TREE/tools/secrets_scan.py" ]; then run_py "$TREE" tools/secrets_scan.py ${RANGE:+--range "$RANGE"}; else
    [ -n "$RANGE" ] && git -C "$TREE" diff "$RANGE" | grep -E "$SECRET_RE" && { echo "secret-shaped string in diff"; return 1; }; fi
  grep -rE "$SECRET_RE" "$LOGDIR" && { echo "secret-shaped string in gate logs"; return 1; }; return 0
}
step secrets secrets

# ---- 10. protected files (only with a Protected-Edit trailer naming a card; the verifier confirms the card lists the file) ----
prot() {
  [ -f "$TREE/tests/protected.txt" ] && [ -n "$RANGE" ] || return 0
  local touched; touched="$(git -C "$TREE" diff --name-only "$RANGE" | grep -F -x -f "$TREE/tests/protected.txt" || true)"
  [ -z "$touched" ] && return 0
  echo "protected touched: $touched"
  git -C "$TREE" log --format=%B "$RANGE" | grep -q '^Protected-Edit: T[0-9]' || { echo "no Protected-Edit trailer"; return 1; }
}
step protected prot

# ---- 11. confirm-RED (tests-only diff applied on the base must FAIL on the named paths; exit 5 is not red) ----
RED_OK="n/a"; RED_CLASSES=""
if [ -n "$RED_BASE" ]; then
  RWT="$WT/red-$(printf '%s' "$RED_BASE$RED_TESTS" | sha256sum | cut -c1-12)"
  [ -d "$RWT" ] || git -C "$REPO" worktree add --detach "$RWT" "$RED_BASE" >/dev/null 2>&1
  git -C "$REPO" diff "$RED_BASE..$RED_TESTS" -- tests/ | git -C "$RWT" apply --index 2>"$LOGDIR/red-apply.log" || true
  run_py "$RWT" -m pytest "${PYT_ARGS[@]}" $RED_PATHS >"$LOGDIR/confirm-red.log" 2>&1; RRC=$?
  if [ "$RRC" -eq 1 ] || [ "$RRC" -eq 2 ]; then RED_OK="true"; else RED_OK="false"; RED=1; printf 'confirm-red\t1\t0\t-\n' >> "$STEPS"; fi
  RED_CLASSES="$(grep -oE 'ImportError|ModuleNotFoundError|AssertionError|AttributeError|TypeError|ValueError' "$LOGDIR/confirm-red.log" | sort -u | tr '\n' ',')"
  git -C "$RWT" reset --hard -q; git -C "$REPO" worktree remove --force "$RWT" >/dev/null 2>&1
fi

# ---- 12. mutant (sufficiency): apply one-line patch, task tests must go RED, revert, tree unchanged ----
MUT_KILLED="n/a"
if [ -n "$MUTANT" ]; then
  BEFORE="$(git -C "$TREE" status --porcelain | sha256sum)"
  if git -C "$TREE" apply --check "$MUTANT" 2>"$LOGDIR/mutant-apply.log" && git -C "$TREE" apply "$MUTANT"; then
    run_py "$TREE" -m pytest "${PYT_ARGS[@]}" $TASK_TESTS >"$LOGDIR/mutant.log" 2>&1; MRC=$?
    git -C "$TREE" apply -R "$MUTANT"
    if [ "$MRC" -eq 1 ] || [ "$MRC" -eq 2 ]; then MUT_KILLED="true"; else MUT_KILLED="false"; RED=1; printf 'mutant\t1\t0\t-\n' >> "$STEPS"; fi
  else MUT_KILLED="unapplicable"; RED=1; printf 'mutant\t1\t0\t-\n' >> "$STEPS"; fi
  [ "$(git -C "$TREE" status --porcelain | sha256sum)" = "$BEFORE" ] || { echo "gate: tree changed by mutant round-trip" >&2; RED=1; }
fi

# ---- 13. journeys (held-out compositional; each marks the task it needs and is skipped-with-reason until that task is merged) ----
J_PASS=0; J_FAIL=0; J_SKIP=""
if [ "$JOURNEYS" -eq 1 ]; then
  JB="$(git -C "$REPO" for-each-ref --format='%(refname:short)' 'refs/heads/journeys/*' | head -1)"
  if [ -n "$JB" ]; then
    JWT="$WT/journeys-$HEAD_SHA"; [ -d "$JWT" ] || git -C "$REPO" worktree add --detach "$JWT" "$HEAD_SHA" >/dev/null 2>&1
    git -C "$REPO" diff "$(git -C "$REPO" merge-base "$JB" "$HEAD_SHA")..$JB" -- tests/journeys | git -C "$JWT" apply 2>/dev/null
    step journeys run_py "$JWT" -m pytest "${PYT_ARGS[@]}" --junitxml="$LOGDIR/junit-j.xml" -rs tests/journeys
    set -- $(counts j 2>/dev/null || echo '0 0 0 0 0'); J_PASS=$2; J_FAIL=$3
    J_SKIP="$(grep -oE 'SKIPPED.*needs=[A-Za-z0-9]+' "$LOGDIR/journeys.log" | grep -oE 'needs=[A-Za-z0-9]+' | sort -u | tr '\n' ',')"
    git -C "$REPO" worktree remove --force "$JWT" >/dev/null 2>&1
    [ "$J_FAIL" -eq 0 ] || RED=1
  else skip journeys; fi
fi

# ---- 14. tamper-evidence: repo copy of the gate equals the root copy ----
if [ -f "$TREE/tools/gate.sh" ]; then
  [ "$(sha256sum < "$TREE/tools/gate.sh")" = "$(sha256sum < "$BUILD_ROOT/gate.sh")" ] && printf 'gate-integrity\t0\t0\t-\n' >> "$STEPS" \
    || { printf 'gate-integrity\t1\t0\t-\n' >> "$STEPS"; RED=1; echo "gate: tools/gate.sh differs from $BUILD_ROOT/gate.sh"; }
fi

# ---- 15. self-test (red-proofs): the gate must go RED on the known-broken tree and on the false-claim fixture, GREEN on the cleaned base ----
SELF="n/a"
if [ "$SELFTEST" -eq 1 ]; then
  BAD="${GATE_BROKEN_SHA:-f88b1204a6af53a469c7a3ddf6d9fb2aea5b4be6}"; BWT="$WT/selftest-broken"
  [ -d "$BWT" ] || git -C "$REPO" worktree add --detach "$BWT" "$BAD" >/dev/null 2>&1
  n="$(run_py "$BWT" -m ruff check --select F821 --output-format concise . 2>/dev/null | grep -c F821 || true)"
  ok1=0; [ "${n:-0}" -ge 3 ] && ok1=1                       # the three undefined names of f88b120 (DECISION-QUEUE ops digest)
  ok2=0; if [ -f "$TREE/tests/fixtures/gate/false-claim.patch" ] && [ -f "$TREE/tools/claim_lint.py" ]; then
    FWT="$WT/selftest-claim"; [ -d "$FWT" ] || git -C "$REPO" worktree add --detach "$FWT" "$HEAD_SHA" >/dev/null 2>&1
    ( cd "$FWT" && git apply "$TREE/tests/fixtures/gate/false-claim.patch" && git -c user.name=g -c user.email=g@x commit -qam "feat: set TOK_PER_SEC to 9.2 and add 4 tests" ) >/dev/null 2>&1
    run_py "$FWT" "$TREE/tools/claim_lint.py" --range "HEAD~1..HEAD" >/dev/null 2>&1 || ok2=1
    git -C "$REPO" worktree remove --force "$FWT" >/dev/null 2>&1; fi
  git -C "$REPO" worktree remove --force "$BWT" >/dev/null 2>&1
  ok3=$(( RED == 0 ? 1 : 0 ))                                # this very run on the tree under test
  if [ $ok1 -eq 1 ] && [ $ok2 -eq 1 ]; then SELF="pass"; printf 'self-test\t0\t0\t-\n' >> "$STEPS"; else SELF="fail:broken=$ok1,claim=$ok2"; RED=1; printf 'self-test\t1\t0\t-\n' >> "$STEPS"; fi
fi

# ---- 16. ledger (machine-written; self-hashed; copied outside the tree) ----
DUR=$((SECONDS - T0)); VERDICT=$([ "$RED" -eq 0 ] && echo GREEN || echo RED)
mkdir -p "$TREE/.gate"
run_py "$TREE" - "$STEPS" "$TREE/.gate/last_run.json" <<EOF
import json, sys, hashlib
steps = [dict(zip(('name','exit','seconds','log'), l.rstrip('\n').split('\t'))) for l in open(sys.argv[1]) if l.strip()]
led = {"gate_version": $GATE_VERSION, "verdict": "$VERDICT", "head_sha": "$HEAD_SHA", "range": "$RANGE", "profile": "$PROFILE",
       "python": "$("$PY" -V 2>&1)", "started_at": "$STARTED_AT", "duration_s": $DUR, "tree": "$TREE",
       "steps": steps, "pytest": {"collected": $COLLECTED, "passed": $PASSED, "failed": $FAILED, "skipped": $SKIPPED, "xfailed": $XFAILED},
       "idiom_warnings": $IDIOM_WARN, "confirm_red": {"ok": "$RED_OK", "classes": "$RED_CLASSES", "base": "$RED_BASE", "tests": "$RED_TESTS"},
       "mutant": {"patch": "$MUTANT", "killed": "$MUT_KILLED"}, "journeys": {"pass": $J_PASS, "fail": $J_FAIL, "skipped_needs": "$J_SKIP"},
       "self_test": "$SELF", "spaces_zero_gpu": "unset (worker code ran as plain functions; platform behaviour is staging-required)"}
body = json.dumps(led, sort_keys=True, indent=1)
led["ledger_sha256"] = hashlib.sha256(body.encode()).hexdigest()
out = json.dumps(led, sort_keys=True, indent=1)
open(sys.argv[2], 'w').write(out); open("$LEDGERS/$HEAD_SHA-$PROFILE-$(printf '%s' "$RANGE$MUTANT$RED_TESTS$JOURNEYS$CLEAN_SHA" | sha256sum | cut -c1-8).json", 'w').write(out)
print("GATE", led["verdict"], "ledger_sha256=" + led["ledger_sha256"], "collected=" + str(led["pytest"]["collected"]))
EOF
[ -n "$OUT" ] && cp "$TREE/.gate/last_run.json" "$OUT"
rm -rf "$SAFEHOME" "$STEPS"
[ "$RED" -eq 0 ]
```

**Deterministic tools the gate calls (built by T01b, each with a red-proof fixture):** `tools/claim_lint.py` (message numbers/identifiers/"N tests" must appear in the whitespace-insensitive diff; trailers `Renormalize-Only: yes`, `Tests-Removed: <name> — <reason>`, `Skip-Added: <reason>`, `Protected-Edit: <card>`, `Claim-Waiver: <verifier label>` at most once per range), `tools/apicheck.py` (AST walk of the range's Python files; every call whose callee resolves to `gradio`, `spaces`, `huggingface_hub`, `transformers`, `gradio_client`, `fastapi` is checked against `inspect.signature` in the venv, `GenerationConfig().__dict__` for generate kwargs; known-bad list from `plan/api-ledger.json`: `gr.Chatbot(type=…)`, `gr.ChatInterface(type=…)`, `@spaces.GPU(gpu_size=…)`, `presence_penalty` to `generate`, `restart_space(revision=…)`, `from gradio.client import …`, `Path.read_text(newline=…)`), `tools/idiom_lint.py` (the CORRECTED-line idioms, superset of step 7's grep), `tools/secrets_scan.py` (regex + entropy over the range and `.gate/`), `tools/catalog_check.py` (schema: pinned `revision` 40-hex, `provenance.{source_url,fetched_at,fetched_by,saved_path}` with the saved file existing, `admission ∈ {pending, passed, failed}`, no free-text ids), `tools/render_readme.py --check`.

### Where each gate mode runs

| Mode | Who runs it | Tree | Purpose |
|---|---|---|---|
| `gate.sh --tree $WT/impl-… --range <base>..HEAD` | implementer (to get GREEN before returning) and **again** the verifier (never trusts the implementer's ledger) | the task worktree | in-worktree pre-merge |
| `gate.sh --confirm-red <base> tests/<id> <paths>` | test author (its RED proof) and the verifier (re-check) | temp `red-*` worktree | necessity |
| `gate.sh --tree … --mutate $WT/mutants/<id>-<n>.patch <paths>` | verifier (1-3 mutants it crafts) | the task worktree, round-tripped | sufficiency |
| `gate.sh --range <prev>..HEAD` on `integration/<nonce>` | integrator after every merge; integration fixer | main checkout | merged tree |
| `gate.sh --clean <head> --journeys --self-test` | clean-checkout gate agent every K merges and at the end; lens reviewers read that worktree | fresh detached `clean-<sha>` | clean checkout, held-out journeys, red-proofs (D-9/F-28) |
| `gate.sh --tree $REPO --profile bootstrap` | T01a/T01b only (the tools do not exist yet); the ledger records `profile`, the reducer rejects `bootstrap` for any other card | | chicken-and-egg of the gate building itself |
| `tools/gate.sh` in `.github/workflows/gate.yml` | CI (T16), on every PR, from a fresh clone under `python-version: 3.12` | runner | the same bytes (step 14) |

---

## 8. Testability table: proven locally (stub engine, unit, import smoke, gradio_client) vs requires staging Space vs requires the owner; how staging/promotion requests are represented

Every schema carries `verification_level ∈ {local-mechanical, local-stub, staging-required, owner-required, unverified}`; a keyword list in `safeAgent` (lease, quota, ZeroGPU, worker fork, Triton, fla, `x-ip-token`, MCP transport, Space rebuild, cold-start, tok/s, FP8, GPTQ, provider) forces at least `staging-required` on any claim text that mentions them (F-37), and the synthesizer aggregates by level.

| Area (cards) | Proven locally in R1 (3.12 venv, no GPU, no tokens) | Requires the staging Space (CI job in R2 reads the artifact) | Requires the owner (checkpoint) |
|---|---|---|---|
| Gate + hygiene (T01a/b/c) | static gate steps 1-10; red-proofs (RED on `f88b120`, RED on the false-claim fixture, GREEN on the cleaned base); persona absence test; constants pin | CI runs the same `tools/gate.sh` on a fresh clone (proves the clean-checkout path on a different box) | approve the plan hash; create the private GitHub repo |
| Pins + lift + cutover (T02, T03, T04c) | 10 characterisation pins green-on-old; `--color-moved` shows moves only; import smoke < 5 s with `QWEN_STUB=1` | CPU Space boots and `/healthz` echoes the pushed sha | — |
| Thin slice + backends (T04, T09b) | conformance suite on `fake`; recorded-hosted row **skipped-needs-owner** (counted); FastAPI `TestClient` for `/healthz`, `/v1/models`, relay shape; disconnect stops the generator (repro from openai-api-2, fake backend) | first request through the router from CI (`hosted_call_budget_usd`); `x-ip-token` presence logged on the worker | the one metered streamed call with a tool and thinking on → `fixture #1` (decides where the parser lives; cents) |
| Parser + agent loop (T05, T06b) | property tests (round-trip markup, `</parameter>` literal, split tags, truncated thinking), golden SSE parsed with the `openai` SDK models, journeys J2/J4 | — | — |
| Registry + session + hardening (T06a, T10a-c) | `python_eval` unreachable over `/v1` and MCP (zero request shapes enable it); child sees only the allow-listed env (`CANARY_SECRET` absent); `/proc/<ppid>/environ` → EACCES after `PR_SET_DUMPABLE=0`; rlimits trip; `killpg` leaves no orphans; SSRF: single lookup, redirect validated before the hop, CGNAT/ports blocked; regex timeout; calculator bounds; archive caps; `apply_patch` ambiguity/EOL/newline; TTL eviction; per-call bench for API/MCP | whether `RLIMIT_NPROC=0`/`RLIMIT_AS` behave the same under the Spaces runtime (**UNVERIFIED**, security-tools-1 verifier note) — a hardening self-test endpoint runs once on staging and its output is a CI artifact | accept the residual risk already recorded in G-15 |
| UI (T07, T11, T15) | `build_ui(FakeEngine)` builds offline; events → message snapshot; transcript survives a turn (J2); two sessions → two benches (J3); `gradio_client` `view_api()` snapshot on a free local port with `/healthz` sha asserted; `_user_text` both shapes; persona set present, excluded clause absent | Gradio SSR/queue behaviour behind the HF proxy | look at the UI once on staging (subjective, not a gate) |
| Gateway + MCP (T08, T12) | `TestClient` table: 401/429/413/400, SSE framing, `[DONE]\n\n`, `finish_reason: length`, `reasoning_content` round-trip; MCP schema snapshot lists exactly `ask/poll/status/preflight` (if `gradio[mcp]` installs; else `skipped-needs-staging`, counted) | MCP over HTTP with a real client; bearer auth through the proxy; whether `Authorization` reaches the app (openai-api-8 note) | decide whether MCP is used at all (G-18, §15) |
| Worker (T09a) | pure modules: estimator rows at 9 tok/s **and** at a measured rate placeholder, `max_time` arithmetic, encode ladder catching ValueError, `continue_final_message="reasoning_content"` render against the real template (jinja2 sandbox), control-dict interception for both consumers, stop event → StoppingCriteria (CPU tensor), heartbeat | **everything ZeroGPU**: import-time load under CUDA emulation, cold-start margin, measured tok/s and prefill rate, quota bucket of `gradio_client` calls with the scoped token (quota before/after one 16-token call), `fla`/Triton in the forked worker, FP8 vs GPTQ load on `large`, requirements resolution on rebuild | create the staging worker Space; choose the resident checkpoint from harness numbers |
| Harness + catalog (T13, T14) | `--backend fake --dry-run` makes zero backend calls (asserted); schema + provenance files exist; README table == `models.yaml` | the real 12-prompt run per entry under `gpu_seconds_budget`/`hosted_call_budget_usd`, evidence JSON per entry | set the budgets; run the quantization HF Job if a self-built FP8 copy is wanted (paid) |
| CI + promotion (T16) | workflows lint (`ci-silent-pass-lint` shapes: no `continue-on-error`, no `\|\| true`, SHA-pinned actions, `permissions:` blocks); `tools/promote.py` unit-tested against fakes (sha mismatch → rollback, not-ready in 12 min → rollback, canary p95 vs last-known-good control); Trusted Publisher config present | staging deploy via OIDC; `hf spaces wait --timeout`; canary pass^3; rollback drill on a deliberately broken staging deploy | configure the Trusted Publisher, the `production` environment with the owner as required reviewer, the staging read token; approve the promotion |

**How staging/promotion requests are represented.** Three durable artifacts, all written by the synthesizer from mechanical inputs and cross-checked by the synth verifier:

1. `SYNTH.checkpoint` (schema §9): `{action, why, exact_steps[], blast_radius, rollback, cost_estimate, approvals_needed[], evidence_paths[]}` — the orchestrator relays it verbatim.
2. `$REPO/RUNBOOK.md` — one row per `staging-required` and `owner-required` claim: the exact measurement step and the number it must record (cold-start margin s, tok/s, quota before/after, boot seconds, `x-ip-token` present y/n), plus the owner pre-flight list (send the stop notice, disable both Windows scheduled tasks, revoke the pasted token and the other agent's token, delete `NF4_EXPORT`/`NF4_UPLOAD_TOKEN`, Dev Mode off, set the Codespace idle timeout to the maximum).
3. `$REPO/PROMOTION_REQUEST.md` (R2) — what/why/evidence table (per-backend canary numbers vs the last-known-good control)/rollback sha/cost; it is the body of the `production`-environment job's summary that the owner approves in GitHub.

---

## 9. Schemas for every stage (JSON Schema, `required ⊆ properties`, enum verdicts, `sha` wherever code was read)

Rules: small (paths, SHAs, enums, counts; strings ≤ 2 k; no diffs), floor-only `required`, `minItems` on evidence arrays, semantics re-validated in JS (`done === dod.every(exit_code===0)`), one common fragment on every return so the script can assert repo, outward actions and installs uniformly (F-1/F-5/F-35).

```js
// ---------- common fragment (every agent) ----------
const LEVELS = ['local-mechanical', 'local-stub', 'staging-required', 'owner-required', 'unverified']
const COMMON = {
  status: { type: 'string', enum: ['ok', 'failed', 'blocked_on_owner', 'stale', 'reused'] },
  item_id: { type: 'string' },
  repo_toplevel: { type: 'string', description: 'output of git rev-parse --show-toplevel in the tree you worked in' },
  base_sha: { type: 'string' }, head_sha: { type: 'string', description: '40-hex of the tree you read/produced' },
  ledger_hash: { type: 'string', description: 'ledger_sha256 printed by gate.sh, or "" if you did not run it' },
  verification_level: { type: 'string', enum: LEVELS },
  outward_actions_taken: { type: 'array', items: { type: 'string' }, description: 'MUST be empty; list anything outward you did' },
  installed_packages: { type: 'array', items: { type: 'string' }, description: 'MUST be empty except for the setup role' },
  t_start: { type: 'string', description: 'date -u +%FT%TZ at start (narrative only)' }, t_end: { type: 'string' },
  reason: { type: 'string', description: 'required when status != ok (enforced in JS)' },
  notes: { type: 'string', description: '<=120 words; never a summary of another agent' },
}
const COMMON_REQ = ['status', 'item_id', 'repo_toplevel', 'base_sha', 'head_sha', 'ledger_hash', 'verification_level',
  'outward_actions_taken', 'installed_packages', 't_start', 't_end']
const S = (props, req) => ({ type: 'object', properties: Object.assign({}, COMMON, props), required: COMMON_REQ.concat(req) })
const EXEC = { type: 'object', properties: { command: { type: 'string' }, exit_code: { type: 'integer' }, output_tail: { type: 'string', description: '<=40 lines' } }, required: ['command', 'exit_code', 'output_tail'] }
const SEV = { type: 'string', enum: ['critical', 'high', 'medium', 'low'] }

// ---------- R1 setup ----------
const SETUP = S({
  venv_python: { type: 'string' }, wheels_copied: { type: 'boolean' }, snapshots_readonly: { type: 'boolean' },
  packages_installed: { type: 'array', items: { type: 'string' } },          // the ONE role allowed a non-empty list
  gate_self_test: { type: 'string', enum: ['pass', 'fail'] }, baseline_collected: { type: 'integer' },
  stale_worktrees_pruned: { type: 'integer' }, reused: { type: 'boolean' },
}, ['venv_python', 'wheels_copied', 'snapshots_readonly', 'packages_installed', 'gate_self_test', 'baseline_collected', 'reused'])

// ---------- R0 plan grounding ----------
const SYMBOLIZE = S({ entries: { type: 'array', minItems: 1, items: { type: 'object', properties: {
  finding_id: { type: 'string' }, file: { type: 'string' }, symbol: { type: 'string' }, exists_at_base: { type: 'boolean' },
  verification: { type: 'string', enum: ['confirmed', 'refuted', 'unverified'] }, reproduction: EXEC, note: { type: 'string' } },
  required: ['finding_id', 'file', 'symbol', 'exists_at_base', 'verification'] } } }, ['entries'])
const API_LEDGER = S({ entries: { type: 'array', minItems: 20, items: { type: 'object', properties: {
  module: { type: 'string' }, symbol: { type: 'string' }, kwargs: { type: 'array', items: { type: 'string' } },
  libsrc_path: { type: 'string' }, line: { type: 'integer' } }, required: ['module', 'symbol', 'kwargs', 'libsrc_path', 'line'] } },
  known_bad: { type: 'array', items: { type: 'object', properties: { idiom: { type: 'string' }, why: { type: 'string' }, libsrc_path: { type: 'string' } }, required: ['idiom', 'why', 'libsrc_path'] } },
}, ['entries', 'known_bad'])
const CATALOG_PROV = S({ entries: { type: 'array', items: { type: 'object', properties: {
  repo: { type: 'string' }, saved_path: { type: 'string' }, revision: { type: 'string' }, hosted: { type: 'boolean' },
  fetched_at: { type: 'string' }, status: { type: 'string', enum: ['saved', 'unresolved'] } }, required: ['repo', 'saved_path', 'revision', 'hosted', 'fetched_at', 'status'] } } }, ['entries'])
const PLAN_CRITIC = S({
  verdict: { type: 'string', enum: ['ready', 'not-ready'] },
  must_fix: { type: 'array', items: { type: 'object', properties: { card: { type: 'string' }, problem: { type: 'string' }, fix: { type: 'string' }, kind: { type: 'string', enum: ['decision-conflict', 'missing-obligation', 'oversize', 'overlap', 'unrunnable-acceptance', 'stale-symbol', 'interface-drift'] } }, required: ['card', 'problem', 'fix', 'kind'] } },
}, ['verdict', 'must_fix'])
const PLAN_REPAIR = S({ cards_rewritten: { type: 'array', items: { type: 'string' } }, plan_hash_after: { type: 'string' } }, ['cards_rewritten', 'plan_hash_after'])

// ---------- per-task chain ----------
const TESTS = S({
  tests_branch: { type: 'string' }, test_paths: { type: 'array', minItems: 1, items: { type: 'string' } },
  red_ledger_hash: { type: 'string' }, red_failure_classes: { type: 'string' },
  properties_written: { type: 'array', items: { type: 'string' } },
}, ['tests_branch', 'test_paths', 'red_ledger_hash', 'red_failure_classes'])
const IMPL = S({
  branch: { type: 'string' }, bundle_path: { type: 'string' }, commits: { type: 'integer' },
  changed_files: { type: 'array', items: { type: 'string' } }, changed_lines: { type: 'integer' },
  dod: { type: 'array', minItems: 1, items: { type: 'object', properties: { line: { type: 'string' }, command: { type: 'string' }, exit_code: { type: 'integer' } }, required: ['line', 'command', 'exit_code'] } },
  claims: { type: 'array', items: { type: 'string' }, description: 'each must be visible in the diff (claim lint)' },
  apis_cited: { type: 'array', items: { type: 'string' }, description: 'api-ledger entry ids you relied on' },
  interface_conforms: { type: 'boolean' }, protected_touched: { type: 'array', items: { type: 'string' } },
  alternatives: { type: 'array', items: { type: 'object', properties: { text: { type: 'string' }, chosen: { type: 'boolean' } }, required: ['text', 'chosen'] }, description: 'pivot fixer only: minItems 2 enforced in JS' },
  root_cause: { type: 'string', description: 'fixers only: one sentence with a file:symbol anchor' },
}, ['branch', 'bundle_path', 'commits', 'changed_files', 'changed_lines', 'dod', 'claims', 'apis_cited', 'interface_conforms', 'protected_touched'])
const VERIFY = S({
  verdict: { type: 'string', enum: ['pass', 'fail', 'unverifiable'] },
  ledger_hash_observed: { type: 'string' }, gate_profile: { type: 'string', enum: ['full', 'bootstrap'] },
  pytest: { type: 'object', properties: { collected: { type: 'integer' }, passed: { type: 'integer' }, failed: { type: 'integer' }, skipped: { type: 'integer' }, xfailed: { type: 'integer' } }, required: ['collected', 'passed', 'failed', 'skipped', 'xfailed'] },
  checks: { type: 'array', minItems: 1, items: { type: 'object', properties: { name: { type: 'string' }, exec: EXEC, result: { type: 'string', enum: ['pass', 'fail'] } }, required: ['name', 'exec', 'result'] } },
  red_confirmed: { type: 'boolean' },
  mutants: { type: 'array', items: { type: 'object', properties: { patch: { type: 'string' }, killed: { type: 'boolean' } }, required: ['patch', 'killed'] } },
  hunks_cited: { type: 'array', items: { type: 'string', description: 'path:line@sha' } },
  decision_fidelity: { type: 'array', items: { type: 'object', properties: { decision_id: { type: 'string' }, ok: { type: 'boolean' }, note: { type: 'string' } }, required: ['decision_id', 'ok'] } },
  idiom_warnings_cleared: { type: 'array', items: { type: 'object', properties: { pattern: { type: 'string' }, file: { type: 'string' }, justification: { type: 'string' } }, required: ['pattern', 'file', 'justification'] } },
  protected_touched: { type: 'array', items: { type: 'string' } },
  failures: { type: 'array', items: { type: 'string' }, description: 'verbatim failing lines; fed to the fixer unchanged' },
}, ['verdict', 'ledger_hash_observed', 'gate_profile', 'pytest', 'checks', 'red_confirmed', 'mutants', 'hunks_cited', 'decision_fidelity', 'idiom_warnings_cleared', 'protected_touched', 'failures'])
const REFUTE = S({
  refuted: { type: 'boolean', description: 'default TRUE if uncertain' }, reproduction: EXEC,
  strongest_disagreement: { type: 'string' }, severity_after: { type: 'string', enum: ['critical', 'high', 'medium', 'low', 'none'] },
  hunks_cited: { type: 'array', items: { type: 'string' } },
}, ['refuted', 'reproduction', 'strongest_disagreement', 'severity_after', 'hunks_cited'])
const JUDGE_TASK = S({
  verdict: { type: 'string', enum: ['no-veto', 'veto'] }, reproduced: { type: 'boolean' }, veto_reproduction: EXEC,
  dod_items: { type: 'array', minItems: 1, items: { type: 'object', properties: { line: { type: 'string' }, opinion: { type: 'string', enum: ['YES', 'NO', 'UNBACKED'] }, citation: { type: 'string' } }, required: ['line', 'opinion', 'citation'] } },
  veto_reason: { type: 'string' },
}, ['verdict', 'reproduced', 'dod_items'])
const INTEGRATION = S({
  result: { type: 'string', enum: ['merged', 'conflict', 'gate-failed', 'skipped'] }, branch: { type: 'string' },
  conflicts: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, ours_hunk: { type: 'string' }, theirs_hunk: { type: 'string' } }, required: ['file', 'ours_hunk', 'theirs_hunk'] } },
  cherry_unmerged: { type: 'array', items: { type: 'string' } }, gate_ledger_hash: { type: 'string' },
  bundle_path: { type: 'string' }, pushed: { type: 'boolean' }, worktree_removed: { type: 'boolean' },
}, ['result', 'branch', 'conflicts', 'cherry_unmerged', 'gate_ledger_hash', 'bundle_path', 'pushed', 'worktree_removed'])
const GATE_RUN = S({
  verdict: { type: 'string', enum: ['GREEN', 'RED'] },
  pytest: VERIFY.properties.pytest,
  journeys: { type: 'object', properties: { pass: { type: 'integer' }, fail: { type: 'integer' }, skipped_needs: { type: 'array', items: { type: 'string' } } }, required: ['pass', 'fail', 'skipped_needs'] },
  self_test: { type: 'string', enum: ['pass', 'fail', 'n/a'] }, ledger_path: { type: 'string' },
}, ['verdict', 'pytest', 'journeys', 'self_test', 'ledger_path'])

// ---------- outer loop ----------
const REVIEW_FINDINGS = S({
  findings: { type: 'array', items: { type: 'object', properties: {
    id: { type: 'string' }, title: { type: 'string' }, file: { type: 'string' }, symbol: { type: 'string' },
    evidence: { type: 'string' }, severity: SEV, affects_correctness_or_requirement: { type: 'boolean' },
    reproduction: EXEC, recommendation: { type: 'string' }, decision_ids: { type: 'array', items: { type: 'string' } } },
    required: ['id', 'title', 'file', 'symbol', 'evidence', 'severity', 'affects_correctness_or_requirement', 'reproduction', 'recommendation'] } },
  coverage_notes: { type: 'string' }, findings_path: { type: 'string', description: 'plan/findings/r<N>-<lens>.json you wrote' },
}, ['findings', 'coverage_notes', 'findings_path'])
const REFUTE_FINDING = S({ finding_id: { type: 'string' }, refuted: { type: 'boolean' }, reproduction: EXEC, strongest_disagreement: { type: 'string' }, severity_after: REFUTE.properties.severity_after }, ['finding_id', 'refuted', 'reproduction', 'strongest_disagreement', 'severity_after'])
const JUDGE_PANEL = S({
  verdict: { type: 'string', enum: ['satisfied', 'not-satisfied', 'blocked-needs-owner'] },
  reasons: { type: 'array', minItems: 1, items: { type: 'string' } },
  must_fix: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, title: { type: 'string' }, file: { type: 'string' }, evidence: { type: 'string' }, severity: SEV, reproduced: { type: 'boolean' } }, required: ['id', 'title', 'file', 'evidence', 'severity', 'reproduced'] } },
}, ['verdict', 'reasons', 'must_fix'])

// ---------- R2 / R3 ----------
const CI_READ = S({
  run_id: { type: 'string' }, conclusion: { type: 'string', enum: ['success', 'failure', 'cancelled', 'unknown'] },
  deployed_sha: { type: 'string' }, running_sha: { type: 'string' }, boot_seconds: { type: 'integer' },
  canary: { type: 'object', properties: { attempts: { type: 'integer' }, passes: { type: 'integer' }, p95_ms: { type: 'integer' }, finish_reasons: { type: 'array', items: { type: 'string' } } }, required: ['attempts', 'passes', 'p95_ms', 'finish_reasons'] },
  measurements: { type: 'object', properties: { cold_start_margin_s: { type: 'number' }, tok_per_s: { type: 'number' }, prefill_tok_per_s: { type: 'number' }, quota_before_s: { type: 'integer' }, quota_after_s: { type: 'integer' }, x_ip_token_present: { type: 'boolean' } } },
  visibility_private: { type: 'boolean' }, artifact_paths: { type: 'array', items: { type: 'string' } }, logs_tail_path: { type: 'string' },
}, ['run_id', 'conclusion', 'deployed_sha', 'running_sha', 'canary', 'artifact_paths'])

// ---------- synthesis ----------
const ROW_STATUS = ['merged+gate-green', 'merged+gate-red', 'parked', 'reverted', 'blocked_on_owner', 'blocked', 'deferred', 'dropped-null', 'not_attempted']
const SYNTH = S({
  summary: { type: 'string' },
  rows: { type: 'array', minItems: 1, items: { type: 'object', properties: { item_id: { type: 'string' }, status: { type: 'string', enum: ROW_STATUS }, head_sha: { type: 'string' }, reason: { type: 'string' }, dod_done: { type: 'integer' }, dod_total: { type: 'integer' } }, required: ['item_id', 'status', 'reason', 'dod_done', 'dod_total'] } },
  staging_required_claims: { type: 'array', items: { type: 'string' } }, owner_actions: { type: 'array', items: { type: 'string' } },
  checkpoint: { type: 'object', properties: {
    action: { type: 'string', enum: ['none', 'approve-plan', 'smoke-ok', 'smoke-failed', 'resume', 'create-github-repo', 'push-and-stage', 'restage', 'promote-production', 'rollback-requested', 'done', 'blocked'] },
    why: { type: 'string' }, exact_steps: { type: 'array', items: { type: 'string' } }, blast_radius: { type: 'string' }, rollback: { type: 'string' }, cost_estimate: { type: 'string' },
    approvals_needed: { type: 'array', items: { type: 'string' } }, evidence_paths: { type: 'array', items: { type: 'string' } } },
    required: ['action', 'why', 'exact_steps', 'blast_radius', 'rollback', 'cost_estimate', 'approvals_needed', 'evidence_paths'] },
  artifact_paths: { type: 'array', minItems: 1, items: { type: 'string' } }, timing_path: { type: 'string' },
}, ['summary', 'rows', 'staging_required_claims', 'owner_actions', 'checkpoint', 'artifact_paths', 'timing_path'])
const SYNTH_VERIFY = S({
  verdict: { type: 'string', enum: ['accepted', 'rewritten'] }, ledger_matches: { type: 'boolean' },
  rows_corrected: { type: 'array', items: { type: 'object', properties: { item_id: { type: 'string' }, was: { type: 'string' }, now: { type: 'string' }, evidence: { type: 'string' } }, required: ['item_id', 'was', 'now', 'evidence'] } },
  waste_ratio: { type: 'number', description: 'tokens of discarded work / total, from the ledger rows' },
}, ['verdict', 'ledger_matches', 'rows_corrected', 'waste_ratio'])
```

**JS-side semantic re-validation (F-46) applied to every return in `safeAgent`:** `status !== 'ok' ⇒ reason non-empty`; `outward_actions_taken.length === 0` else abort; `installed_packages.length === 0` unless role is `setup`; `repo_toplevel` equals the expected tree; for `IMPL`: `dod.length === card.dod.length`, `commits ≥ 1`, `changed_lines ≤ 2 × est_lines`; for `VERIFY`: `checks.some(c => c.name === 'gate.sh')`; for `REFUTE`: `refuted && reproduction.exit_code === 0 ⇒` downgraded to `no-evidence`; for `JUDGE_*`: `veto ⇒ reproduced`; for the pivot fixer: `alternatives.length ≥ 2 && alternatives.filter(a => a.chosen).length === 1`. A validated object is still **agent-claimed** until the ledger hash it names matches a file the next stage re-reads (research-1 §6 item 7).

---

## 10. Replay/resume, null-result, safeguard-kill and concurrency handling (cap 2 vs cap 14: wave sizing from `args`)

### 10a. Replay and resume — correctness never depends on the cache; speed benefits from it

- **What the harness gives** `[M]`: only completed `result` events replay; a killed run re-runs in-flight agents from scratch; the journal key is `v2:<sha256>` per call; its composition is **UNVERIFIED** (35 serialisations tried, none matched). Inference, stated as such: a content hash is only useful if the cache is content-addressed (a positional cache needs no hash), and the tool's own default primitive `pipeline()` issues stage-2 calls in completion order, which would make it unresumable under a purely positional cache. Settling experiment (cheap, in the smoke run): resume the smoke run once with an unchanged script and count `key` matches in the journal; then change a non-prompt knob and resume again.
- **Design consequences:** (1) every prompt is a pure function of `args` and prior results — `run_nonce`, `base_sha`, `integration_sha_at_launch`, card text, result SHAs; never a timestamp, run id, completion-order-dependent list or scratch path; arrays are sorted by id before `JSON.stringify` (T-14/T-15); (2) control knobs that do not belong in prompts (`waveSize`, `maxAgentsThisRun`, `incrementalReview`…) live under `args.knobs` and are never interpolated into prompt strings, so raising an agent cap between invocations cannot invalidate cached calls; (3) **git state is the real checkpoint**: implementers reuse `impl/<id>-<nonce>` if the gate is GREEN on it (`status:'reused'`, minutes not tens of minutes), test authors reuse `tests/<id>-<nonce>`, integrators skip a merge whose commit is already an ancestor of `integration/<nonce>` (`git merge-base --is-ancestor`, exit code compared `=== 0` — research-4's own refutation of `== 0` comparisons on rc 128 is avoided by treating 128 as "could not be asked" = stale); (4) **stale-state guard (F-43)**: the orchestrator recomputes `integration_sha_at_launch` with `git rev-parse` before every invocation; a moved repo changes the build-stage prefix → those calls miss the cache deliberately and re-run against the live tree with branch reuse. Resume from a run id is allowed only when the live integration head equals that run's `integration_sha_at_launch`; otherwise it is a fresh invocation that still benefits from git reuse.
- **Journal hygiene:** the orchestrator reads `journal.jsonl` before diagnosing empty results (T-25) and scans any journal export with the secrets regex before saving it under `evidence/` (F-7).

### 10b. Null results and safeguard kills

- `safeAgent()` wraps every call: H6 `withTimeout` (typed drop receipt), then null/receipt handling by role: cheap roles (verifier, refuter, judge, integrator, gate) get **one identical retry**; authoring roles (test author, implementer, fixer, resolver) get **one narrower retry** (`model:'fable'`, reading list halved, prompt prefix "inspect `git status`/`git log` in your worktree; continue from the last commit; discard uncommitted edits only if they do not compile"); a second failure → `blocked:agent-null:<role>` and the ledger row keeps the receipt's `__endReason` (timeout | threw | null). Nothing is ever `.filter(Boolean)`-ed away; every drop is pushed to `dropped[]` and logged (F-41, T-17).
- Hardening cards (T10a-c) are pre-split with narrow reading lists and `model:'fable'` because the platform safeguard killed a reader on exactly that material once `[V research-4 §0]`; a null there parks the card as `unreviewed → needs_owner`, never as pass (F-31).
- Kill hygiene: implementers commit per DoD line (a kill loses ≤ one step); `gate.sh` pre-step removes stale `index.lock` and kills stray listeners whose cwd is under `$BUILD_ROOT` (F-26/F-42).

### 10c. Concurrency: what changes between cap 2 and cap 14, and what does not

| knob (`args.knobs`) | cap 2 (now) | cap 14 | cap 16 | why |
|---|---|---|---|---|
| `waveSize` (tasks in flight) | 2 | 4 | 5 | each chain uses ≤ 2 concurrent agents → queued agents ≤ cap → no FIFO starvation of a critical-path verifier `[M §1.4]` |
| `taSlots` (front-loaded test authors) | 0 (in-chain) | 4 | 5 | `cap − 2·waveSize`; at cap 2 there is no idle slot to front-load into |
| `frontLoadTests` | false | true | true | removes ≈ 7 min per spine link from the critical path at cap 14; changes nothing at cap 2 |
| `speculativeDeps` (spine children start on the dep's *built* branch) | false | true | true | saves ver‖ref + judge + integ ≈ 12 min per spine link (≈ 1.5 h over the spine); costs a rebase and, with p(fix)·p(interface change) ≈ 0.12, occasional wasted work — only worth it when slots are idle |
| `incrementalReview` | false | true | true | round-1 lens reviews overlap the build tail (≈ 60 agent-min hidden) only when slots idle |
| `taskMaxLines` (plan critic rule) | 300 | 220 | 220 | fewer chains where per-agent bootstrap dominates; more parallel chains where slots are free |
| `cleanGateEvery` | 4 | 4 | 4 | a clean gate is ≈ 3 agent-min; K = 4 bounds the blast radius of "green on branch, red on tree" (F-34) |
| `maxAgentsThisRun` | 110 | 1000 | 1000 | ≈ 5.5 h at cap 2 so a run ends inside the Codespace's attention span (F-44); the synthesizer always runs; the next invocation raises it and resumes |
| `parallelVerify` | true | true | true | verifier ‖ refuter always (2 agents, one reduce); the judge runs after because it must see the final head |

Same script, same schemas, same prompts; only `args.knobs` differ, and they are logged on the first narrator line together with `cap`. A wrong knob cannot make the run incorrect, only slower.

### 10d. Barriers, and why each one exists

`parallel([verifier, refuter])` (the reduce needs both) · the serial merge queue (integration needs the predecessor head) · `parallel(5 lens reviewers)` (dedup needs the set) · `parallel(3 refuters)` per fresh finding (majority) · `parallel(3 panel judges)` (majority) · `parallel(2 plan critics)`. Everything else is a per-task promise chain with no barrier; `pipeline()` is used only for fixed item lists (per-finding refutes), the DAG scheduler for tasks. Every barrier is wrapped in `settle()` (H6) so one hung unit costs that unit, not the phase (D-21).

---

## 11. Budget and effort plan by role; estimated agent counts and wall-clock at cap 2 and at cap 14

### 11a. Empirical baseline (the only measured scheduling data, research-2 §1.4)

| class | n | duration | tokens | tool calls | note |
|---|---|---|---|---|---|
| read-heavy finder (≈ lens reviewer) | 5 | 735-953 s (mean 835 s) | 153-231k | 46-65 | FIFO wait up to 1,580 s at cap 2 |
| verifier | 5 | 258-317 s (mean 282 s) | 92-107k | 25-30 | queued 113-1,216 s behind finders |
| completeness critic | 1 | 305 s | 123k | 21 | |
| whole run | 11 agents | 3,147 s (52.5 min) at cap 2; projected 26 min at cap 14 | 1.55 M | 442 | run-record token semantics (input+output?) **UNVERIFIED** |

### 11b. Per-role model (`[E]` where no agent of that role has run)

| role | effort | min | tokens | per task / per round |
|---|---|---|---|---|
| test author | medium | 7 | 60k | 1 per task |
| implementer | high | 15 (S 12 / M 18) | 150k | 1 per task |
| verifier ‖ refuter | medium | 5 each (wall 5) | 85k each | 1 pair per task + 1 pair per fix |
| task judge | medium | 4 | 60k | 1 per task (+1 after a veto fix) |
| fixer / pivot | high | 8 | 100k | p(fix) = 0.4 × 1.2 rounds; p(veto) = 0.1 |
| integrator | low | 2.5 | 25k | 1 per task |
| conflict resolver | xhigh | 10 | 120k | p = 0.15 |
| clean gate | low | 3 | 25k | every 4 merges + final (≈ 8) |
| lens reviewer | high | 12 (delta-scoped) | 170k | 5 per round |
| finding refuter | medium | 4 | 70k | 3 per fresh finding (≈ 8, 3, 2 per round) |
| panel judge | xhigh | 6 | 90k | 3 per round |
| synth + verifier | high / medium | 8 + 5 | 140k | once per run |
| R0 (symbolizer, api-ledger, catalog-prov, 2 critics, repair) + setup | mixed | 46 + 8 | ≈ 400k | once |

**Per task (expected):** agents = 6 base + 0.4·1.2·3 (fix + re-pair) + 0.1·4 (veto path) + 0.15·2 (conflict) ≈ **8.1**; agent-minutes = 7 + 15 + 5 + 5 + 4 + 2.5 + 0.48·18 + 0.1·22 + 0.15·12.5 ≈ **51**.

### 11c. Totals for R0 + R1 (25 cards + 3 test-only + ≈ 5 review-fix chains)

| block | agents | agent-min |
|---|---|---|
| setup + R0 | 7 | 54 |
| 25 task chains | 203 | 1,275 |
| journeys + pins test-only | 4 | 34 |
| clean gates | 8 | 24 |
| outer loop (3 rounds: 15 reviewers, ≈ 39 refuters, ≈ 5 RF chains, 9 judges, 1 inversion) | ≈ 100 | ≈ 620 |
| synth + verifier | 2 | 13 |
| **total** | **≈ 325 (range 260-340)** | **≈ 2,020 (≈ 34 agent-hours)** |

Tokens: ≈ 325 × ≈ 105k ≈ **34 M run-record tokens** (≈ 45 M if the measured 141k/agent mean holds); output-token budget (what `budget` counts) is a fraction of that — **UNVERIFIED** which fraction; the reserve is sized in output tokens (200k) and the agent caps are the real backstop.

### 11d. Wall-clock

- **Cap 2:** 2,020 ÷ 2 ≈ 1,010 min ≈ **17 h** with perfect packing (the admission scheduler keeps both slots busy; the only forced idle is the final synth pair) → realistically **16-18 h**, run as **3 invocations of ≈ 5.5 h** (`maxAgentsThisRun: 110`) with resume (git reuse + cache). Spine depth does not matter at cap 2; total work does.
- **Cap 14:** critical path = spine of 9-10 tasks × (impl 15 + ver‖ref 5 + judge 4 + integ 2.5 + expected fix 6) ≈ 33 min ≈ **300 min**, + setup/R0 ≈ 15 min (parallel), + review tail ≈ 70 min (round 1 overlapped by `incrementalReview`; one RF chain 33 + reviewers 12 + refuters 4 + judges 6 + synth 13) ≈ **6.5 h**; with `speculativeDeps` ≈ 9 × 21 ≈ 190 min + 85 ≈ **4.8-5.5 h**. Utilisation ≈ 2,020 ÷ (390 × 14) ≈ 37 % — the spine, not the cap, is the limit; the levers are spine depth (T03 ‖ T04, T05 ‖ T06a already applied) and speculation.
- **Cap 16:** ≈ 5 min better than cap 14 (one more test-author slot); not worth waiting for.

### 11e. Honest measurement of where the time goes (instrumentation)

1. Every return carries `t_start`/`t_end` from `date -u` (strings; narrative only) → the synth verifier writes `evidence/orchestration/timing.json`: per role `{planned_min, actual_min_p50, actual_min_max, n}`, per task chain wall, critical-path actual vs planned, FIFO wait (from the run record's `queuedAt/startedAt`, added by the orchestrator after the run), utilisation = Σ agent-min ÷ (wall × cap).
2. `gate.sh` records per-step seconds in every ledger → the share of the pipeline spent in pytest vs lint vs mutants is measured, so `cleanGateEvery` and the twice-run pytest rule can be tuned from data next run.
3. **Waste ledger:** tokens of discarded work = blocked chains + superseded implementations (a fix replaces its predecessor's diff) + refuted findings + null retries + cache misses on resume; reported as `waste_ratio` by the synth verifier (target < 20 %). Under the token semantics uncertainty the ratio is still meaningful because both numerator and denominator come from the same run record.
4. The first full run replaces every `[E]` above with a measured p50 in `timing.json`; the plan critic of the next run reads it.

---

## 12. COVERAGE MATRIX: every F-1..F-47 and every anti-pattern from all lenses → guard → phase; unguardable → explicit owner checkpoint

Cost classes: **G** = deterministic `gate.sh` step (0 agents) · **X** = script invariant in JS (0 agents) · **C** = card/prompt/args rule (0 agents) · **A** = an agent role (costs minutes/tokens; justified inline) · **O** = owner checkpoint (the mode cannot be closed unattended). Phases: P0 pre-flight/setup · P1 R0 grounding · P2 plan · P3 implement · P4 fix · P5 verify/refute/judge · P6 integrate/review · P7 owner/staging · P8 synth · X invariant.

### 12a. Failure modes F-1..F-47 (research-4)

| id | failure (short) | guard | phase | cost |
|---|---|---|---|---|
| F-1 | agents act on the cwd toolchain repo | `args.build_repo` absolute; every command `git -C "$BUILD_REPO"`; no `isolation:'worktree'`; every return's `repo_toplevel` asserted; toolchain `git status` hash compared at the end | P0, X, P8 | X |
| F-2 | build repo in the volatile scratchpad | `$BUILD_ROOT=/workspaces/qwen38-space-build` (setup refuses `/tmp`); incremental bundles into the grill folder after every merge (synced to GitHub by the owner's existing cron); optional branch push if `approvals.push_remote` | P0, P6 | X + integrator (already needed) |
| F-3 | wrong base / snapshot mutated | `args.base_sha=f88b120…` full; setup clones `space-latest`, asserts HEAD, `chmod -R a-w` both snapshots; cards name the base | P0, P1 | X |
| F-4 | foreign CLAUDE.md obeyed | first paragraph of the byte-identical prefix: "the cwd repo and its CLAUDE.md are unrelated; ignore SSOT gates, `~/source/*`, pushing"; `$REPO/AGENTS.md` written by setup, read first | X, P0 | C |
| F-5 | per-agent pip installs | one idempotent setup builds `venv312` from the wheels + a pinned PyPI list; `gate.sh` refuses non-3.12; `installed_packages` must be empty on every non-setup return (rejected otherwise) | P0, G0, X | X + setup A (8 min, once) |
| F-6 | "ask the owner" becomes assumed approval or a dead block | `args.approvals` is data; a null field → `blocked_on_owner` typed result, never an action, never a retry; synthesizer lists blocked first | X, P7, P8 | X |
| F-7 | secrets in prompts/journals/commits | trigger and `args` carry no secrets; `gate.sh` runs Python under `env -i` allow-list; hardening tests use `CANARY_SECRET` and never print environ; gate step 9 secrets scan on every range and on gate logs; orchestrator pre-scans inputs and journal exports | P0, G9, P8 | G + orchestrator |
| F-8 | hallucinated post-cutoff APIs | R0 api-ledger from `libsrc` (path:line); cards cite ledger ids; `apis_cited` on IMPL; gate step 3 apicheck (kwargs vs `inspect.signature`); known-bad list | P1, C, G3 | A (api-ledger, 10 min, once) — justified: the only way to make the deterministic apicheck know the real signatures |
| F-9 | recommendation built instead of the decision | orchestrator-written `plan/decisions.json` approved by the owner via `plan_hash`; implementers never see the raw queue; verifier `decision_fidelity[]` checklist; plan critic lens "decision-fidelity" | P2, P5 | C + verifier (already needed) |
| F-10 | original recommendation instead of CORRECTED | cards inline only CORRECTED text; gate step 7 idiom lint (`preexec_fn`, `__wrapped__`, `lease_s - 30`, `rmtree` in unload, `prefill_chunk_size` with the VLM class); verifier must clear each warning with a justification | P2, G7, P5 | G |
| F-11 | UNVERIFIED findings acted on; stale `file:line` | R0 symbolizer maps every finding to `file::symbol` at `base_sha` and reproduces/refutes the UNVERIFIED critic findings; cards locate by symbol | P1, P2 | A (symbolizer, 8 min, once) — justified: reading the tree once beats 25 implementers guessing |
| F-12 | verification theater | the ledger (self-hashed, machine-written) is the only evidence; verifier must run `gate.sh` itself and return `ledger_hash_observed === impl.ledger_hash`; `collected > 0`; `spaces_zero_gpu: unset` recorded → lease claims forced to `staging-required` | G16, X, P5 | G + X |
| F-13 | monolithic items | `taskMaxLines` from the cap; ≤ 12 files; commit per DoD line; `commits ≥ 1` asserted; plan critic rejects oversize; `changed_lines ≤ 2 × est_lines` | P2, X | X + plan critic (already needed) |
| F-14 | dependency order ignored; collisions | DAG from cards; overlap rule adds ordering edges; admission by readiness; serial merge queue in rank order; gate after every merge | X, P6 | X |
| F-15 | context loss between stages | carriers are cards on disk + git + ledgers; returns are small structural objects; prompts point at paths + SHAs; no blobs | X, C | C |
| F-16 | scope creep | `files_allowed`/`deps_allowed`/`out_of_scope` on the card; expansion guard rejects fixer diffs outside the allowlist; reviewer lens "traceability" (every hunk maps to a DoD line or finding id); deferred list for the owner | X, P5, P6 | X |
| F-17 | persona boundary violated | persona card carries the boundary as a hard rule and only the G-19 role list; no `git log/show` on `system_prompt.py`; protected absence test (minimal fragments); `security-and-secrets` lens checks boundary on every persona/README/test change; synthesizer reports the absence test result | P2, G8, P6, P8 | G + C |
| F-18 | tests weakened/deleted/skipped | gate step 4 counts vs baseline with `Tests-Removed:`/`Skip-Added:` trailers; `tests/protected.txt` + step 10; idiom lint for test-detection; confirm-RED + mutant per DoD line; verifier diff-reads every test change; test author ≠ implementer | G4, G7, G10-12, P5 | G |
| F-19 | over-claiming commits, partial completion | ruff F821/F811/F401/E9 under py312 + compileall + import smoke (G2, G5); claim lint (G6); IMPL `dod[]` with exit codes, `dod.length === card.dod.length`; judge re-runs DoD commands; synthesizer counts DoD lines | G2, G5, G6, X, P5, P8 | G |
| F-20 | mocks testing the mock; fake fidelity | conformance suite parametrised over `fake` / `recorded-hosted` / `recorded-worker` with recorded rows skipped-needs-owner and counted; fixture `provenance` fields checked by `catalog_check`-style test; verifier mutants (one flips `finish_reason`, one drops a tool-call event) must turn a test red | P3, G12, P5, **O** | G + owner's metered call |
| F-21 | line-ending drift | T01a two commits (attrs, `--renormalize` with `Renormalize-Only: yes`); gate step 1 fails on any CRLF/mixed thereafter; reviewers use `--ignore-all-space --color-moved` | P3, G1 | G |
| F-22 | LFS, big blobs, junk | gate step 1 (LFS empty, blob > 5 MB, forbidden paths); `.gitignore` in T01a; fixtures generated in `tmp_path` | G1 | G |
| F-23 | 3.14 vs 3.12 drift | gate refuses non-3.12; `ruff --target-version py312`; `requirements-dev.lock` + front/worker locks under 3.12; README front-matter pin test; R2 observes the rebuild resolution | G0, G2, G8, P7 | G |
| F-24 | README/UI/commit claims diverge from constants | `tools/render_readme.py --check` (G8), constants-pin test (protected), claim lint on every commit, UI copy reads the constants module (card rule) | G6, G8, C | G |
| F-25 | catalog entries with invented provenance | R0 catalog-provenance saves raw read-only Hub reads under `evidence/catalog/`; `catalog_check` requires `provenance.saved_path` to exist and a 40-hex revision; `status: unverified` otherwise; owner list | P1, G8, P8 | A (catalog-prov, 6 min, once) |
| F-26 | leaked servers / foreground `launch()` | test harness picks a free port, `prevent_thread_lock=True`, `try/finally kill`; `/healthz` returns the git sha and the client asserts it; gate pre-step kills stray listeners under `$BUILD_ROOT`; prompt rule: never a foreground server without a timeout | P3, G0, C | G |
| F-27 | infinite/oscillating fix loops | `MAX_FIX=3`, fingerprint two-strikes pivot, oscillation A→B→A, `MAX_ROUNDS=3`, `DRY_ROUNDS=2`, findings ledger with stable ids; a re-opened id after a close goes to the resolver, never a vote | X | X |
| F-28 | the fix agent fixes the gate | `tests/protected.txt` (gate files, ruff.toml, pytest config, claim lint) + step 10 trailer rule; step 14 gate integrity vs the root copy; step 15 self-test red-proofs on every clean gate; waiver trailer once per range naming the verifier; only exit 0 is green | G10, G14, G15 | G |
| F-29 | flaky / network tests | `pytest-socket` `--disable-socket --allow-hosts=127.0.0.1`, proxy black-hole, `HF_HUB_OFFLINE`; pytest run twice, identical counts required; `tests/live/` excluded unless `approvals.hosted_call_budget_usd > 0` | G4 | G |
| F-30 | critic captured by self-report; same-model blind spots | verifier/refuter/judge prompts contain no implementer narrative (prompt builder takes SHAs/paths only); mechanical-first lenses (apicheck, idiom lint, mutants, decision sheet); `hunks_cited minItems 1` for any pass; cross-vendor unavailable (`[V]`) → fallback logged | X, P5 | X |
| F-31 | safeguard kill on security code | hardening split into 3 cards, `model:'fable'`, narrow reading lists, defensive framing; null → narrower retry → `unreviewed → needs_owner`, never pass | P2, X | C + X |
| F-32 | conflicts resolved by "pick one side" | integrator aborts on conflict; fresh xhigh resolver with both cards and the hunks; `git cherry` must be empty; patch-id spot check; gate after merge; bundle per merge | P6, X | A (resolver, 10 min, p≈0.15) — justified: the only judgement-bearing step in integration |
| F-33 | worktree lifecycle | all worktrees under `$WT`; names carry the nonce; removal only after `cherry_unmerged == []`; P0 prune after bundling; `ro-*` pruned when merged | P0, P6 | X |
| F-34 | green on branch, red on merged tree | gate after every merge; clean-checkout gate every 4 merges + final with journeys; integration fixer ≤ 2 rounds then `git revert -m 1` + park | P6 | G + integration fixer (rare) |
| F-35 | outward actions without approval | `args.approvals` data; prefix forbids `gh repo create`, `git push` (unless `push_remote`), any `HfApi` write, write MCP tools; `outward_actions_taken` non-empty → run aborts; pipeline code written + unit-tested, never executed; owner disables the HF connector's write tools and confirms `gh auth status` scope | X, P0, **O** | X + owner pre-flight |
| F-36 | harness burns quota or provider money | `--backend fake --dry-run` default; real backends need `--i-accept-cost` + an owner-only env var; preflight refuses above `approvals.*_budget`; `max_retries=0`; zero-call test in the gate | P3, G4, **O** | G + owner runs it |
| F-37 | staging-only behaviour reported as verified | `verification_level` enum on every return; keyword list forces ≥ `staging-required`; `spaces_zero_gpu: unset` in every ledger; RUNBOOK rows with the exact measurement; R2 ci-reader ingests the numbers | X, P8, **O** | X + owner/CI |
| F-38 | the other agent's scheduled tasks push mid-build | workflow never touches the Space; RUNBOOK step 0 asserts Space HEAD == base or adopts the delta (read-only); owner checklist: stop notice, disable both tasks, rotate its token, delete `NF4_*` secrets | P7, **O** | O |
| F-39 | flaky Hub/docs fetch → fabricated values | R0 fetch wrappers retry 3× then return `unresolved`; `source.saved_path` required; unresolved facts committed as `TODO(owner-verify)`, never numbers | P1, G8 | C + G |
| F-40 | synthesizer summarises work that did not happen | synthesizer gets only the mechanical `ledger[]`, `git log --stat`, final gate ledger path, skip counts; one row per card with the enum status; synth verifier re-checks every `merged` row against `git log` and every ledger hash | P8 | A (synth verifier, 5 min, once) — justified: F-40 is Critical and the check is a comparison the LLM must do against files (D-19 says write the algorithm; the cross-check of prose rows against git is the residual judgement) |
| F-41 | null contract mishandled | `safeAgent` records every call incl. nulls/receipts; typed `{status:'null'}` objects; no bare `.filter(Boolean)`; `dropped[]` logged | X | X |
| F-42 | mid-task kill, half-written files | commit per DoD line; retry prompt continues from the last commit; gate pre-step removes stale `index.lock`, kills stray servers; hardening cards narrow + `model:'fable'`; two nulls → park | P3, X, G0 | X |
| F-43 | resume replays stale results | orchestrator computes `base_sha`/`integration_sha_at_launch`/`run_nonce` before every invocation; those are in every build-stage prompt; resume only if the live head matches; git reuse instead of cached SHAs | P0, X | X |
| F-44 | cap-2 wall-clock explodes; host stops | admission scheduler (no barrier waves); `maxAgentsThisRun` slices; setup pre-builds the venv; single-vote chains; owner sets the idle timeout to max and keeps a client attached; `log()` of estimated remaining agent-minutes at each admission | X, P0, **O** | X + O |
| F-45 | budget exhaustion; `budget.total` null; 1000-agent cap | iteration caps first, `budgetOk()` with `budget.total &&`, `RESERVE`, `AGENT_CAP_SOFT=850`; synthesizer always runs inside `try/catch` with whatever state exists | X | X |
| F-46 | schema failures / valid-but-empty | small schemas, `minItems` on evidence, JS semantic re-validation, the smoke run exercises every schema on one task before the wave | X, P0 | X |
| F-47 | script-level bugs | `meta` pure literal with matching `phase()` titles; no `Date`/`Math.random`; `try/catch` around every stage; `phase:` per agent call; state derived from `ledger[]`; smoke run mandatory | X, P0 | X |

### 12b. Doctrine anti-patterns (research-1, AP-1..AP-17)

| id | anti-pattern | guard | phase | cost |
|---|---|---|---|---|
| D/AP-1 | receipt-as-result / fire-and-forget | `status` enum + `reason`; fan-in regex rejects `started in the background|Check /codex:status|based on the digest`; no rescue forwarders | X | X |
| D/AP-2 | digest theatre | reviewers/refuters/judges read the tree at `ro-<sha>` and the ledger files, never a digest; `hunks_cited minItems 1` | P5, P6 | X |
| D/AP-3 | evidence-tag theatre (same broken probe re-run) | verifier re-runs `gate.sh` itself (different process, tree and shell from the implementer); refuter must cite an executed command that differs from the verifier's (`reproduction.command` compared in JS) | P5, X | X |
| D/AP-4 | silent-in-both-states detector | gate self-test red-proofs (RED on `f88b120`, RED on the false-claim fixture, GREEN on the cleaned base) on every clean gate; confirm-RED requires a real failure (exit 5 is not red); mutant must be killed | G11, G12, G15 | G |
| D/AP-5 | Goodhart-green (tests after code, coverage, `xfail`/`skip`/`|| true`) | tests before code by a different agent; skip/xfail trailer rule; `ci-silent-pass-lint` shapes checked on `.github/**` in T16's tests; coverage never used as evidence | G4, P3 | G |
| D/AP-6 | self-certification | verifier/refuter/judge are fresh calls with SHAs only; the implementer's ledger is never trusted (re-run) | X | X |
| D/AP-7 | the grind | fingerprint two-strikes pivot (alternatives ≥ 2), never a 4th identical attempt, re-decompose = park + owner | X | X |
| D/AP-8 | fat barrier, no timeout | H6 `withTimeout`/`settle` on every barrier; per-task chains; typed drop receipts | X | X |
| D/AP-9 | over-broad `required[]` | floor-only `required`, prose in one capped string, deliverables in git/ledgers | §9 | X |
| D/AP-10 | mid-run contract edits | `plan_hash` frozen in `args`; a failed card is fixed by a one-off standalone `agent()` writing the same artifact, never by editing shared consts and resuming | P0, X | X |
| D/AP-11 | unbounded loop / dedup vs confirmed | `MAX_ROUNDS`, `DRY_ROUNDS`, `budget.total &&`, `seen` set, DoD inversion before closure | X | X |
| D/AP-12 | negative instructions in the implementer prompt | prefix holds only the safety hard rules; no "don't test X" lists; test hygiene handled by the `tests-and-gate` lens once | C | C |
| D/AP-13 | LLM doing a mechanical comparison | overlap check, rank/topo, fingerprint, reduce, dedup, counts, claim lint, apicheck, secrets scan are all code | X, G | X |
| D/AP-14 | parallel mutators on one index | own worktree per mutator, disjoint `files_allowed`, single-writer integration | X | X |
| D/AP-15 | trusting a "done" mark / working-tree green | `unitDone()` reads the verifier's re-run ledger; clean-checkout gate from a fresh detached worktree; timeouts → FAILED-TO-RUN | X, G | X |
| D/AP-16 | performative agreement in the fix loop | fixer must cite `root_cause` with an anchor; resolver reads probes on a re-opened finding; refuter must state `strongest_disagreement` | X | X |
| D/AP-17 | trailing limitations section | synthesizer schema has inline `staging_required_claims[]` per row; `RUNBOOK.md` rows are inline per claim; the synth verifier rejects a report whose UNVERIFIED items sit only in a tail section (regex on the last 15 % of the file) | P8 | X |

### 12c. Tool-native anti-patterns (research-2 §6, 1-12)

| id | anti-pattern | guard | phase | cost |
|---|---|---|---|---|
| T/AP-1 | consent-in-prompt | approvals are `args` data; outward actions between runs; the trigger carries the owner's words | X, P7 | X |
| T/AP-2 | secret-in-trigger | the launching message contains no secret (orchestrator pre-scan); `args` never carry tokens | P0 | orchestrator |
| T/AP-3 | self-certifying implementer | DoD exit codes + re-run gate by a fresh verifier + claim lint | P5, G6 | G |
| T/AP-4 | unbounded until-satisfied loop | four stop conditions + agent caps | X | X |
| T/AP-5 | dedup against `confirmed` | `seen` set keyed by `file::symbol::title` | X | X |
| T/AP-6 | barrier between per-item stages | DAG admission + per-task promise chains; barriers only at reduces/queue/panels | X | X |
| T/AP-7 | parallel writers on one checkout/branch | one integrator at a time (merge queue), own worktrees | X | X |
| T/AP-8 | worktree as the checkpoint | deterministic branch names + bundles per task and per merge + grill-folder bundles | P3, P6 | X |
| T/AP-9 | volatile prompt content | prompts built from `args` + sorted results; knobs excluded; no scratch paths | X | X |
| T/AP-10 | stale-SHA evidence | every code-reading prompt pins a SHA; findings carry `symbol` + sha; symbolizer at R0 | X, P1 | X |
| T/AP-11 | silent truncation | every `slice`/drop logged with counts; `dropped[]`; deferred tasks named | X | X |
| T/AP-12 | one giant implementer | PR-sized cards; commit per DoD line; oversize rejected by the plan critic | P2 | X |

### 12d. External-SOTA anti-patterns (research-3, AP-1..AP-14)

| id | anti-pattern | guard | phase | cost |
|---|---|---|---|---|
| S/AP-1 | self-grading | fresh verifier/refuter/judge; prompt builder excludes author narrative | X | X |
| S/AP-2 | early victory | complete suite twice with counts; `collected` vs baseline; the ledger flips, not the agent | G4 | G |
| S/AP-3 | oracle tampering | protected paths + trailer rule; count/skip deltas; idiom lint; mutants | G4, G7, G10, G12 | G |
| S/AP-4 | hollow feature-isolated implementation | held-out journeys on a separate branch, run at every clean gate; conformance suite parametrised over backends; staging canary in CI | G13, P7 | G + journeys author (10 min, once) — justified: compositional bugs were the observed failure class (chat-loop-ui-1/2, critic-2) |
| S/AP-5 | telephone-game decomposition | one implementer lineage per card (fixer receives verbatim failures, not summaries); interface frozen in the card; test author's return is data | C, X | C |
| S/AP-6 | unbounded fix loop / thrash | `MAX_FIX=3`, dry/oscillation/expansion detectors, re-plan = park | X | X |
| S/AP-7 | claims without diffs | claim lint on every commit; `claims[]` ⊆ diff; reviewers treat claims as hypotheses | G6, P6 | G |
| S/AP-8 | secret sprawl | zero secrets in agent env for tests (`env -i`); OIDC in CI (T16); `HF_HUB_DISABLE_IMPLICIT_TOKEN=1`; staging secrets re-entered by the owner, asserted by CI | G, T16, O | G |
| S/AP-9 | non-resumable / non-idempotent script | no clock/random; `exist_ok`-style checks before every side effect (branch exists, merge is ancestor); `run_nonce` in names | X | X |
| S/AP-10 | irreversible action inside the loop | outward tools forbidden; `production` environment with required reviewer; promotion request artifact | X, T16, O | X |
| S/AP-11 | biased judging protocol | binary rubric rows with citations; forced-CoT single order; three different roles/lenses; strongest model (session) as judge; no pairwise comparisons | P5, P6 | X |
| S/AP-12 | canary checks the wrong thing | `tools/promote.py` decision rule: `/status` echoes the sha, authenticated 16-token generation ×3 with `finish_reason` and p95 vs the last-known-good control, visibility private assert, log tail on failure (unit-tested against fakes; run by CI) | T16, P7 | G (tests) + CI |
| S/AP-13 | context overflow / kitchen-sink agent | one card per agent; ≤ 2 KB card + paths; returns are data | C | C |
| S/AP-14 | reviewer over-reporting → churn | findings need a reproduction to be queued; `affects_correctness_or_requirement` required; style findings logged only; refute majority | P6, X | X |

### 12e. DEEP anti-patterns (research-3-DEEP, AP-1..AP-12)

| id | anti-pattern | guard | phase | cost |
|---|---|---|---|---|
| SD/AP-1 | author-graded work | as S/AP-1 + tests read-only to the implementer by protected paths + count deltas | X, G | X |
| SD/AP-2 | green-by-weakening | assertion-loss/skip/matcher checks in `tools/idiom_lint.py` (AST: assert count per test file must not drop, `approx`/`is not None` widening flagged), protected `.github/**` and pytest config | G7, G10 | G |
| SD/AP-3 | vacuous or tautological tests | confirm-RED (real failure class recorded) + one killed mutant per DoD line | G11, G12 | G |
| SD/AP-4 | unanimous-LLM "verification" | every pass needs the machine ledger; every refutation needs an executed reproduction; the reducer ignores opinions without exit codes | X | X |
| SD/AP-5 | endless / oscillating fix loops | as S/AP-6 | X | X |
| SD/AP-6 | summary-of-summary hand-offs | schemas carry `decisions`-equivalent fields (`root_cause`, `alternatives`, `strongest_disagreement`) verbatim; cards carry invariants (`interface`, `out_of_scope`); no free-text-only returns | §9 | X |
| SD/AP-7 | parallel implementers on shared files | overlap rule + own worktrees + serial merge | X | X |
| SD/AP-8 | phantom-change commits | claim lint + DoD exit codes + judge re-runs DoD commands | G6, P5 | G |
| SD/AP-9 | secrets in reach of the agent | `env -i` for every gate Python; no `.env` in the checkout (gate step 1 forbids tracked `.env*` — added to the junk regex); orchestrator pre-scan; hardening tests with canaries | G1, G9, P0 | G |
| SD/AP-10 | agent-executed irreversible actions | as S/AP-10 | X, O | X |
| SD/AP-11 | non-replayable script | as S/AP-9 | X | X |
| SD/AP-12 | scaffold maximalism | 3 fresh roles per task instead of 5 sequential legs; no per-task critic/audit/de-sloppify agents; verification diversity (execution + refute + rubric) over more implementers; `waste_ratio` measured | §5d, P8 | X |

**Modes that can only be closed with an owner checkpoint:** F-6/F-35 (approvals as data; the owner executes outward actions), F-36 (the owner runs paid harness/backends under a stated budget), F-37 (ZeroGPU/quota/provider behaviour is measured on staging by CI the owner configures), F-38 (stop notice, scheduled tasks, token rotation), F-44 (idle timeout, resize), F-20 partially (the one metered hosted call = fixture #1), F-25 partially (unverifiable catalog entries stay `unverified` until the owner's harness run). Everything else closes unattended.

---

## 13. JavaScript skeletons: `meta` pure literal, `args` contract, helpers, every loop (plain JS; no Date.now/Math.random; stable prompts; sorted ids)

One script, run per `args.stage`. Everything below is plain JS for the Workflow sandbox: only injected globals (`agent`, `pipeline`, `parallel`, `phase`, `log`, `args`, `budget`, `setTimeout`, `clearTimeout`), standard built-ins, no `Date.now()`/`Math.random()`/argless `new Date()`, no filesystem. The H6 block is pasted verbatim from `skills/workflow-authoring/templates/h6-timeout-heartbeat.md` (abbreviated here to the three functions used). The schemas of §9 are pasted between the helpers and the stages (omitted here for length: `SETUP … SYNTH_VERIFY`).

```js
export const meta = {
  name: 'qwen38-space-rebuild-a2',
  description: 'Throughput-first implementation workflow for the qwen38 Space rebuild: setup → plan grounding/critique → per-task chains (test author → implementer → gate → verifier ‖ refuter → bounded fixer → veto-only judge) admitted by DAG readiness in critical-path order → fixed-order single-writer integration with clean-checkout gates → delta-scoped review / refute / judge loop → synthesizer + owner checkpoint. Outward actions never happen inside a run.',
  phases: [
    { title: 'Setup', detail: 'idempotent: durable clone at base_sha, 3.12 venv from pinned wheels, gate.sh + self-test, snapshots read-only, stale worktrees pruned' },
    { title: 'Plan', detail: 'ground the orchestrator-drafted plan: symbolize findings, api ledger from libsrc, catalog provenance; two plan critics; one bounded repair' },
    { title: 'Tests', detail: 'test authors (never implementers) write each task\'s tests against the card interface; confirm-RED recorded by gate.sh' },
    { title: 'Build', detail: 'per task: implementer → gate → verifier ‖ refuter → fixer (≤3, two-strikes pivot) → veto-only judge' },
    { title: 'Integrate', detail: 'single-writer merge queue in critical-path order; conflict resolver; gate after every merge; clean-checkout gate every K merges; bundles' },
    { title: 'Review', detail: 'delta-scoped lens reviewers → 3-lens refuters per fresh finding → fix chains → 3-lens judge panel; dry/round/budget bounded' },
    { title: 'Stage', detail: 'read CI staging artifacts (sha, boot, canary, measurements); staging-only fixes; never calls a Space' },
    { title: 'Promote', detail: 'read post-promotion CI artifacts and the rollback drill; final verdict' },
    { title: 'Synthesize', detail: 'mechanical inputs only; one row per card; owner runbook and the next checkpoint; verified by a second agent' },
  ],
  whenToUse: 'Only from the orchestrator turn that holds the owner-approved plan hash; one run per args.stage; smoke first',
}

// =====================================================================================
// args contract — every value comes from the orchestrator; nothing is derived from time or randomness.
// args = {
//   stage: 'plan' | 'build-local' | 'stage' | 'promote',
//   run_nonce: 'r1a',                          // owner-chosen, stable per logical run; part of branch names and prompts
//   launched_at: '2026-09-19T12:00Z',          // narrative only, never in prompts
//   cap: 2,                                    // min(16, CPUs-2) as the owner measured it; drives knob defaults
//   base_sha: 'f88b1204a6af53a469c7a3ddf6d9fb2aea5b4be6',
//   integration_sha_at_launch: '<git rev-parse integration/<nonce> or base_sha>',   // recomputed before EVERY invocation (F-43)
//   build_root: '/workspaces/qwen38-space-build', build_repo: '/workspaces/qwen38-space-build/space',
//   snapshot_src: '/tmp/.../scratchpad/space-latest', libsrc: '/tmp/.../scratchpad/libsrc',
//   grill: '/home/codespace/grills/2026-09-19-qwen38-heretic-space',
//   plan_dir: '<grill>/evidence/orchestration/plan', plan_hash: '<sha256 of plan_dir, owner-approved>',
//   cards: [ {...card...}, ... ],              // the SAME cards as plan_dir/cards/*.json, passed as JSON so the script can schedule without fs
//   toolchain_status_hash: '<sha256 of `git -C /workspaces/agent-skills-toolchain status --porcelain`>',
//   approvals: { push_remote: null, github_repo_url: null, staging_space: null, worker_space: null,
//                hosted_call_budget_usd: 0, gpu_seconds_budget: 0, hf_job: false, promote: false },
//   ci_runs: [],                               // R2/R3: run ids the owner names
//   authority: 'local-only',
//   knobs: { smoke: false, waveSize: 2, taSlots: 0, frontLoadTests: false, speculativeDeps: false, incrementalReview: false,
//            taskMaxLines: 300, cleanGateEvery: 4, maxAgentsThisRun: 110, reserveTokens: 200000,
//            maxFix: 3, maxVeto: 1, maxOuterRounds: 3, dryRounds: 2, agentCapSoft: 850 }
// }
// =====================================================================================
const A = args || {}
for (const k of ['stage', 'run_nonce', 'cap', 'base_sha', 'integration_sha_at_launch', 'build_root', 'build_repo', 'snapshot_src', 'libsrc', 'grill', 'plan_dir', 'plan_hash', 'cards', 'toolchain_status_hash', 'approvals', 'knobs'])
  if (A[k] === undefined || A[k] === null) throw new Error('args.' + k + ' is required')
if (!/^[0-9a-f]{40}$/.test(A.base_sha)) throw new Error('args.base_sha must be a full 40-hex sha')
if (A.build_root.indexOf('/tmp/') === 0) throw new Error('args.build_root must be durable, not /tmp (F-2)')
const K = A.knobs
const CAP = A.cap | 0
const WAVE = K.waveSize || (CAP >= 8 ? Math.max(2, Math.floor(CAP / 3)) : 2)
const TA_SLOTS = K.taSlots !== undefined ? K.taSlots : Math.max(0, CAP - 2 * WAVE)
const FRONT_LOAD = K.frontLoadTests !== undefined ? K.frontLoadTests : CAP >= 8
const SPEC_DEPS = K.speculativeDeps !== undefined ? K.speculativeDeps : CAP >= 8
const INCR_REVIEW = K.incrementalReview !== undefined ? K.incrementalReview : CAP >= 8
const TASK_MAX_LINES = K.taskMaxLines || (CAP >= 8 ? 220 : 300)
const CLEAN_EVERY = K.cleanGateEvery || 4
const MAX_AGENTS_RUN = K.maxAgentsThisRun || (CAP >= 8 ? 1000 : 110)
const RESERVE = K.reserveTokens || 200000
const MAX_FIX = K.maxFix || 3, MAX_VETO = K.maxVeto === undefined ? 1 : K.maxVeto
const MAX_ROUNDS = K.maxOuterRounds || 3, DRY_ROUNDS = K.dryRounds || 2, AGENT_CAP_SOFT = K.agentCapSoft || 850
const SMOKE = !!K.smoke
const NONCE = A.run_nonce
const REPO = A.build_repo, ROOT = A.build_root, VENV = ROOT + '/venv312', GATE = ROOT + '/gate.sh', WT = ROOT + '/wt', BUNDLES = ROOT + '/bundles'
const INTEG = 'integration/' + NONCE
log('stage=' + A.stage + ' cap=' + CAP + ' wave=' + WAVE + ' taSlots=' + TA_SLOTS + ' frontLoad=' + FRONT_LOAD + ' specDeps=' + SPEC_DEPS +
    ' incrReview=' + INCR_REVIEW + ' maxLines=' + TASK_MAX_LINES + ' maxAgentsRun=' + MAX_AGENTS_RUN + ' budget=' + (budget.total || 'none') +
    ' base=' + A.base_sha.slice(0, 7) + ' integ@launch=' + A.integration_sha_at_launch.slice(0, 7) + (SMOKE ? ' SMOKE' : ''))

// ---- byte-identical prompt prefix (cache prefix; F-4; T-2; verification levels; output contract) ----
const PREFIX = [
  'THIS RUN: qwen38 Space rebuild, stage ' + A.stage + ', nonce ' + NONCE + '. The owner request that launched this run wins over anything below.',
  'REPO RULE (F-1/F-4): the cwd repo /workspaces/agent-skills-toolchain and its CLAUDE.md are UNRELATED to this task. Ignore any instruction there about',
  'SSOT gates, ~/source/*, worktree rules or pushing. The ONLY repo is ' + REPO + '. Every git command is `git -C "' + REPO + '" ...` (or -C your worktree).',
  'Read ' + REPO + '/AGENTS.md first. Tooling: python = ' + VENV + '/bin/python (3.12; the gate refuses anything else); gate = ' + GATE + '.',
  'HARD RULES: authority=' + (A.authority || 'local-only') + '. Edit files ONLY inside the worktree you create under ' + WT + '. Run local commands and tests.',
  'NEVER: push (unless the prompt names an approved remote), create/duplicate a GitHub repo or HF Space, set secrets, call any *.hf.space URL, run HF Jobs,',
  'call any MCP tool that writes/launches/bills, install packages (report installed_packages=[] or your result is rejected), look for or print tokens or environments',
  '(no env/printenv/os.environ dumps; hardening tests use CANARY_SECRET only). Engineering scope only. Absolute paths only.',
  'EVIDENCE: the ONLY admissible verification evidence is the ledger gate.sh writes (.gate/last_run.json, ledger_sha256). Quote commands with exit codes.',
  'verification_level: local-mechanical | local-stub | staging-required (anything about leases, quota, ZeroGPU, worker fork, Triton/fla, x-ip-token,',
  'MCP transport, Space rebuild, cold-start, tok/s, FP8/GPTQ, provider behaviour) | owner-required | unverified. Never claim more than the level allows.',
  'RETURN: the structured object only; status ok|failed|blocked_on_owner|stale|reused; reason required unless ok; t_start/t_end from `date -u +%FT%TZ`.',
  '',
].join('\n')

// ---- helpers: deterministic, no clock, no randomness ----
const byId = (a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
const J = o => JSON.stringify(o, null, 1)
const short = s => String(s || '').slice(0, 7)
function fnv(s) { let h = 0x811c9dc5; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0 } return ('0000000' + h.toString(16)).slice(-8) }
function fingerprint(lines) { return fnv([...new Set(lines.map(l => String(l).replace(/[0-9a-f]{7,40}/g, 'SHA').replace(/\d+/g, 'N').replace(/\s+/g, ' ').trim()))].sort().join('\n')) }
const RECEIPT_RE = /started in the background|Check \/codex:status|based on the digest|as a follow-up task/i
const STAGING_RE = /\b(lease|quota|ZeroGPU|worker fork|Triton|\bfla\b|x-ip-token|MCP transport|Space rebuild|cold[- ]start|tok\/s|FP8|GPTQ|provider)\b/i

// H6 (pasted verbatim from the template; abbreviated): withTimeout / settle / h6IsDrop
const H6_TIMEOUT_MS = 1800000, H6_STALL_MS = 90000
function h6Receipt(endReason, label, ms, detail) { return { __h6: true, __endReason: endReason, label: label, ms: ms, detail: detail === undefined ? null : detail } }
function h6IsDrop(r) { return !!r && r.__h6 === true }
async function withTimeout(thunk, ms, label) {
  const budgetMs = ms === undefined ? H6_TIMEOUT_MS : ms
  if (typeof setTimeout !== 'function') { try { return await thunk() } catch (e) { return h6Receipt('threw', label, budgetMs, String(e && e.message || e)) } }
  let timer = null; const beat = setTimeout(() => log('H6 heartbeat: still waiting on ' + label + ' after ' + H6_STALL_MS + 'ms'), H6_STALL_MS)
  const expiry = new Promise(res => { timer = setTimeout(() => res(h6Receipt('timeout', label, budgetMs, null)), budgetMs) })
  try { return await Promise.race([Promise.resolve().then(thunk), expiry]) }
  catch (e) { return h6Receipt('threw', label, budgetMs, String(e && e.message || e)) }
  finally { if (timer !== null) clearTimeout(timer); clearTimeout(beat) }
}
async function settle(thunks, ms, labels) {
  const raw = await parallel(thunks.map((t, i) => () => withTimeout(t, ms, labels ? labels[i] : 'unit-' + i)))
  return raw.map((r, i) => (r === null || r === undefined) ? h6Receipt('null', labels ? labels[i] : 'unit-' + i, ms, null) : r)
}

// ---- the ledger: every agent call, every drop, every state transition; rebuilt identically on replay ----
const ledger = [], dropped = []
let agentCount = 0
const TIMEOUT_MS = { setup: 1500000, symbolize: 1200000, apiledger: 1500000, catalog: 900000, plancritic: 1200000, planrepair: 900000,
  testauthor: 1500000, journeys: 1800000, impl: 2700000, fix: 1800000, verify: 1200000, refute: 1200000, judge: 900000, integrate: 900000,
  resolve: 1800000, integfix: 1800000, cleangate: 900000, review: 1800000, refutef: 900000, panel: 1200000, ciread: 1200000, synth: 1500000, synthverify: 900000, inversion: 1800000 }
const CHEAP = new Set(['verify', 'refute', 'judge', 'integrate', 'cleangate', 'refutef', 'panel', 'ciread', 'synthverify', 'plancritic'])

function budgetOk(label) {
  if (!budget.total) return true
  const ok = budget.remaining() > RESERVE
  if (!ok) log('BUDGET GUARD: ' + label + ' skipped (remaining ' + budget.remaining() + ' < reserve ' + RESERVE + ')')
  return ok
}
function agentsOk(label, need) {
  const ok = agentCount + (need || 1) <= Math.min(MAX_AGENTS_RUN, AGENT_CAP_SOFT)
  if (!ok) log('AGENT CAP: ' + label + ' deferred (count ' + agentCount + ' + ' + (need || 1) + ' > ' + Math.min(MAX_AGENTS_RUN, AGENT_CAP_SOFT) + ')')
  return ok
}

// JS-side semantic validation of a schema-valid return (F-46); returns a reason string or ''
function semantic(role, r, expectTree) {
  if (r.status !== 'ok' && r.status !== 'reused' && !(r.reason && r.reason.length)) return 'status ' + r.status + ' without reason'
  if (r.outward_actions_taken && r.outward_actions_taken.length) return 'OUTWARD ACTION: ' + r.outward_actions_taken.join('; ')
  if (role !== 'setup' && r.installed_packages && r.installed_packages.length) return 'installed packages: ' + r.installed_packages.join(', ')
  if (expectTree && r.repo_toplevel && r.repo_toplevel.indexOf(ROOT) !== 0) return 'repo_toplevel outside build root: ' + r.repo_toplevel
  if (role === 'impl' || role === 'fix') { if (!(r.commits >= 1)) return 'no commits'; if (r.status === 'ok' && !r.dod.every(d => d.exit_code === 0)) return 'dod not all exit 0' }
  if (role === 'verify' && r.verdict === 'pass' && !(r.checks || []).some(c => /gate\.sh/.test(c.exec && c.exec.command))) return 'verifier passed without running gate.sh'
  if (role === 'judge' && r.verdict === 'veto' && !r.reproduced) return 'veto without reproduction'
  if ((r.notes || '').match(RECEIPT_RE)) return 'receipt-shaped return'
  return ''
}

// safeAgent: timeout → typed receipt; null/receipt → role-based retry (cheap: identical; authoring: narrower); semantic re-validation; ledger row.
async function safeAgent(role, item, prompt, opts, attempt) {
  attempt = attempt || 1
  const label = role + ':' + item + ':' + attempt
  const o = Object.assign({ label: label }, opts)
  if (!agentsOk(label)) return { status: 'deferred', reason: 'agent-cap', role, item }
  agentCount++
  const r = await withTimeout(() => agent(prompt, o), TIMEOUT_MS[role] || H6_TIMEOUT_MS, label)
  if (h6IsDrop(r)) {
    dropped.push({ label, reason: r.__endReason, detail: r.detail }); log('DROP ' + label + ' reason=' + r.__endReason)
    if (attempt >= 2) { ledger.push({ role, item, attempt, status: 'null', reason: r.__endReason }); return { status: 'null', reason: 'agent-null:' + role + ':' + r.__endReason, role, item } }
    const narrower = CHEAP.has(role) ? prompt : prompt + '\nRETRY: inspect `git status` and `git log --oneline -20` in your worktree first; continue from the last commit; discard uncommitted edits only if they do not compile; halve your reading list.'
    return safeAgent(role, item, narrower, CHEAP.has(role) ? opts : Object.assign({}, opts, { model: 'fable' }), attempt + 1)
  }
  if (r.status === 'ok' || r.status === 'reused') {
    const why = semantic(role, r, true)
    if (why) {
      if (/^OUTWARD ACTION/.test(why)) { ledger.push({ role, item, attempt, status: 'abort', reason: why }); throw new Error('ABORT ' + label + ': ' + why) }
      log('REJECT ' + label + ': ' + why); ledger.push({ role, item, attempt, status: 'rejected', reason: why })
      return { status: 'failed', reason: why, role, item, value: r }
    }
  }
  if (r.verification_level && STAGING_RE.test(r.notes || '') && r.verification_level.indexOf('local') === 0) r.verification_level = 'staging-required'
  ledger.push({ role, item, attempt, status: r.status, head_sha: r.head_sha || '', ledger_hash: r.ledger_hash || '', level: r.verification_level, t_start: r.t_start, t_end: r.t_end })
  return { status: r.status, role, item, value: r }
}

// ---- cards → DAG → ranks → merge order (all deterministic) ----
function validateCards(cards) {
  const ids = new Set(cards.map(c => c.id))
  for (const c of cards) {
    if (!c.dod || !c.dod.length || !c.acceptance_tests || !c.acceptance_tests.length || !c.files_allowed || !c.files_allowed.length) throw new Error('card ' + c.id + ' has no runnable acceptance (D-1)')
    for (const d of c.dependsOn) if (!ids.has(d)) throw new Error('card ' + c.id + ' depends on unknown ' + d)
    if (c.est_lines > TASK_MAX_LINES) log('WARN card ' + c.id + ' est_lines ' + c.est_lines + ' > ' + TASK_MAX_LINES + ' (plan critic must have split it)')
  }
}
function ancestors(cards) {
  const by = new Map(cards.map(c => [c.id, c])), memo = new Map()
  const anc = id => { if (memo.has(id)) return memo.get(id); const s = new Set(); for (const d of by.get(id).dependsOn) { s.add(d); for (const x of anc(d)) s.add(x) } memo.set(id, s); return s }
  cards.forEach(c => anc(c.id)); return memo
}
function rankCards(cards) {                       // rank = longest path to a sink in estimated minutes; deps strictly outrank dependents
  const by = new Map(cards.map(c => [c.id, c])), children = new Map(cards.map(c => [c.id, []]))
  for (const c of cards) for (const d of c.dependsOn) children.get(d).push(c.id)
  const memo = new Map()
  const rank = id => { if (memo.has(id)) return memo.get(id); const c = by.get(id); const own = ((c.est_minutes && c.est_minutes.impl) || 15) + 14
    const r = own + Math.max(0, ...children.get(id).map(rank)); memo.set(id, r); return r }
  cards.forEach(c => rank(c.id)); return memo
}
function planDag(cards) {
  validateCards(cards)
  const anc = ancestors(cards)
  const sorted = [...cards].sort(byId)
  for (let i = 0; i < sorted.length; i++) for (let j = i + 1; j < sorted.length; j++) {   // overlap rule (D-5/F-14): unordered pair sharing a file → ordering edge
    const a = sorted[i], b = sorted[j]
    if (anc.get(a.id).has(b.id) || anc.get(b.id).has(a.id)) continue
    const shared = a.files_allowed.filter(f => b.files_allowed.some(g => f === g || f.indexOf(g) === 0 || g.indexOf(f) === 0))
    if (shared.length) { b.dependsOn = [...new Set(b.dependsOn.concat([a.id]))].sort(); log('overlap edge ' + a.id + ' → ' + b.id + ' on ' + shared.join(',')) }
  }
  const rank = rankCards(cards)
  const mergeOrder = [...cards].sort((x, y) => (rank.get(y.id) - rank.get(x.id)) || byId(x, y))
  const spine = new Set(mergeOrder.filter(c => c.spine).map(c => c.id))
  log('dag: ' + cards.length + ' cards; spine ' + [...spine].join('→') + '; max rank ' + rank.get(mergeOrder[0].id) + ' min')
  return { mergeOrder, rank, spine }
}
// priority semaphore: highest rank first, ties by id (deterministic given the same ready set)
function makeSemaphore(n) {
  let free = n; const waiters = []
  function pump() { while (free > 0 && waiters.length) { waiters.sort((a, b) => (b.rank - a.rank) || (a.id < b.id ? -1 : 1)); const w = waiters.shift(); free--; w.res() } }
  return { acquire(rank, id) { return new Promise(res => { waiters.push({ rank, id, res }); pump() }) }, release() { free++; pump() } }
}
```

```js
// =====================================================================================
// Prompt builders — pure functions of args + prior results (never a voter's narrative, never a timestamp)
// =====================================================================================
const cardText = c => 'CARD ' + c.id + ' (' + c.title + '):\n' + J(c)
function pTests(c, base) {
  return PREFIX + ['ROLE: test author for ' + c.id + ' (you are NOT the implementer and will never see its code).',
    'Worktree: git -C "' + REPO + '" worktree add "' + WT + '/tests-' + c.id + '-' + NONCE + '" -b tests/' + c.id + '-' + NONCE + ' ' + base + ' (reuse if it exists and its tests are committed).',
    'Write the acceptance tests named in the card under tests/' + c.id + '/ against the card INTERFACE only; one hypothesis property per contract-type DoD line.',
    'Then run: BUILD_ROOT=' + ROOT + ' ' + GATE + ' --confirm-red ' + base + ' tests/' + c.id + '-' + NONCE + ' "' + c.acceptance_tests.join(' ') + '" and return the printed ledger_sha256 as red_ledger_hash.',
    'A test that passes on the base tree, or collects nothing, is a failure of YOUR task. Commit; do not touch files outside tests/' + c.id + '/.',
    '', cardText(c)].join('\n')
}
function pImpl(c, base, tests, fixInput, pivot) {
  return PREFIX + ['ROLE: ' + (fixInput ? (pivot ? 'PIVOT fixer (your previous fix repeated the same failure fingerprint: enumerate ≥2 alternative root causes, choose one, state why)' : 'fixer') : 'implementer') + ' for ' + c.id + ' — ' + c.title,
    'Worktree: git -C "' + REPO + '" worktree add "' + WT + '/impl-' + c.id + '-' + NONCE + '" -b impl/' + c.id + '-' + NONCE + ' ' + base + '.',
    'If the branch already exists: run the gate on it; if GREEN and the DoD commands pass, return status=reused (do not redo the work).',
    'First: git merge --no-ff tests/' + c.id + '-' + NONCE + ' (the tests you must make pass; NEVER edit them: paths ' + tests.test_paths.join(', ') + ').',
    'Build exactly the card; commit after EVERY DoD line ("' + c.id + ': <dod line>" with Claims:/Verified: trailers); cite plan/api-ledger.json ids for every gradio/spaces/hub/transformers call.',
    'Before returning: BUILD_ROOT=' + ROOT + ' ' + GATE + ' --tree "' + WT + '/impl-' + c.id + '-' + NONCE + '" --range ' + base + '..HEAD' + (c.gate_profile === 'bootstrap' ? ' --profile bootstrap' : '') + ' must print GATE GREEN;',
    'then git bundle create ' + BUNDLES + '/' + c.id + '-' + NONCE + '.bundle ' + base + '..HEAD. Return head_sha, ledger_hash, dod[] with exit codes, changed_files, changed_lines.',
    'Decision sheet: ' + A.plan_dir + '/decisions.json (law). Read only: the card reading_list, plan/api-ledger.md, the files in files_allowed.',
    fixInput ? '\nFAILING EVIDENCE (verbatim, from independent verifiers; fix the CAUSE, never the test; state root_cause with a file:symbol anchor):\n' + J(fixInput) : '',
    '', cardText(c)].join('\n')
}
function pVerify(c, impl, tests) {
  return PREFIX + ['ROLE: verifier for ' + c.id + '. Fresh context: you have NOT seen the implementer. Read-only worktree: BUILD_ROOT=' + ROOT + ' ' + GATE + ' --clean ' + impl.head_sha + ' creates ' + WT + '/clean-' + impl.head_sha + ' (or fetch ' + impl.bundle_path + ').',
    'Do, in this order, and quote every command with its exit code: (1) run the gate yourself on ' + impl.branch + ' at ' + impl.head_sha + ' with --range ' + impl.base_sha + '..' + impl.head_sha + ' and compare its ledger_sha256 to ' + impl.ledger_hash + ';',
    '(2) re-run --confirm-red ' + impl.base_sha + ' tests/' + c.id + '-' + NONCE + ' "' + c.acceptance_tests.join(' ') + '"; (3) write 1-3 one-line mutant patches under ' + WT + '/mutants/' + c.id + '-N.patch that would break each DoD line and run the gate with --mutate <patch> "<tests>" (each must be killed);',
    '(4) re-run every DoD command; (5) decision fidelity: for each id in the card, does the diff obey ' + A.plan_dir + '/decisions.json? (6) clear every idiom warning in the ledger with a justification or fail;',
    '(7) list protected files touched; (8) cite hunks (path:line@' + short(impl.head_sha) + ') for anything you assert. verdict=fail on ANY failure, on a claim not visible in the diff, on collected=0, on a bootstrap profile for a non-bootstrap card.',
    'failures[] must be verbatim failing lines (they go to the fixer unchanged).', '', cardText(c), 'IMPL CLAIMS: ' + J(impl.claims)].join('\n')
}
function pRefute(c, impl) {
  return PREFIX + ['ROLE: refuter for ' + c.id + ' (kill mandate). Default refuted=true if uncertain, but a refutation COUNTS only with an executed reproduction whose exit code is non-zero.',
    'Tree: ' + impl.branch + ' at ' + impl.head_sha + ' (read-only worktree ' + WT + '/clean-' + impl.head_sha + '; create it with ' + GATE + ' --clean ' + impl.head_sha + ' if absent).',
    'Try to break the card\'s DoD lines with inputs the tests did not use (composition with dependencies ' + c.dependsOn.join(', ') + ', error paths, the CORRECTED findings text). Reasoning alone refutes nothing.',
    'State your strongest disagreement even if you cannot refute. Cite hunks.', '', cardText(c)].join('\n')
}
function pJudge(c, impl) {
  return PREFIX + ['ROLE: task judge for ' + c.id + ' (veto layer, never a grant layer). You may veto ONLY with a reproduced, cited defect (command + exit code).',
    'Tree: ' + impl.branch + ' at ' + impl.head_sha + '; ledger ' + short(impl.ledger_hash) + ' at ' + WT + '/clean-' + impl.head_sha + '/.gate/last_run.json.',
    'For every DoD line: YES/NO/UNBACKED with a citation (re-run its command). Subjective residue (naming, structure) is a note, not a veto.', '', cardText(c)].join('\n')
}
function pIntegrate(c, impl, prev, n) {
  return PREFIX + ['ROLE: integrator (the ONLY writer of ' + INTEG + '). In the main checkout ' + REPO + ': ensure branch ' + INTEG + ' exists at ' + prev + ' (create from ' + A.integration_sha_at_launch + ' if missing).',
    'If ' + impl.head_sha + ' is already an ancestor of ' + INTEG + ' (git merge-base --is-ancestor; treat exit 128 as "unknown" and report stale), return result=merged with the current head.',
    'Else: git merge --no-ff ' + impl.head_sha + ' -m "merge ' + c.id + '". On ANY conflict: git merge --abort, return result=conflict with the ours/theirs hunks; do NOT resolve.',
    'On a clean merge: BUILD_ROOT=' + ROOT + ' ' + GATE + ' --range ' + prev + '..HEAD (result=gate-failed with the ledger hash if RED); git cherry ' + INTEG + ' impl/' + c.id + '-' + NONCE + ' must be empty;',
    'git bundle create ' + A.grill + '/evidence/build-bundles/' + String(n).padStart(3, '0') + '-' + c.id + '.bundle ' + prev + '..HEAD;',
    (A.approvals.push_remote ? 'git push ' + A.approvals.push_remote + ' ' + INTEG + ' impl/' + c.id + '-' + NONCE + ' (approved remote); ' : 'do NOT push (no approved remote); ') +
    'remove the impl worktree only after cherry is empty; prune clean-*/ro-* worktrees of shas already merged.'].join('\n')
}
function pResolve(c, impl, prev, integ) {
  return PREFIX + ['ROLE: conflict resolver (fresh). Worktree: git -C "' + REPO + '" worktree add "' + WT + '/merge-' + c.id + '-' + NONCE + '" --detach ' + prev + '. Merge ' + impl.head_sha + ' and resolve ONLY the hunks below so that BOTH cards\' DoD lines still hold.',
    'Run ' + GATE + ' --tree <worktree> --range ' + prev + '..HEAD; commit the merge; git bundle create ' + BUNDLES + '/merge-' + c.id + '-' + NONCE + '.bundle ' + prev + '..HEAD; return head_sha and the ledger hash.',
    'CONFLICTS: ' + J(integ.conflicts), 'THIS CARD: ' + cardText(c)].join('\n')
}
function pCleanGate(head) {
  return PREFIX + ['ROLE: clean-checkout gate. Run exactly: BUILD_ROOT=' + ROOT + ' GATE_BASE_SHA=' + A.base_sha + ' ' + GATE + ' --clean ' + head + ' --journeys --self-test',
    'Return the ledger verdict, pytest counts, journeys {pass, fail, skipped_needs}, self_test, and the ledger path. Do not edit anything.'].join('\n')
}

// =====================================================================================
// Per-task chain (§5): test author → implementer → gate → verifier ‖ refuter → fixer (bounded) → judge (veto-only)
// =====================================================================================
function reduceVerdicts(c, impl, ver, ref) {
  const f = []
  const v = ver.value, r = ref.value
  if (ver.status !== 'ok') f.push('verifier unavailable: ' + ver.reason)
  else {
    if (v.verdict !== 'pass') f.push(...(v.failures.length ? v.failures : ['verifier verdict ' + v.verdict]))
    if (v.ledger_hash_observed !== impl.ledger_hash) f.push('ledger hash mismatch: verifier saw ' + short(v.ledger_hash_observed) + ' implementer reported ' + short(impl.ledger_hash))
    if (v.gate_profile !== (c.gate_profile || 'full')) f.push('gate profile ' + v.gate_profile + ' not allowed for ' + c.id)
    if (!(v.pytest.collected > 0)) f.push('pytest collected 0')
    if (!v.red_confirmed) f.push('confirm-RED not confirmed')
    if (!v.mutants.length || !v.mutants.every(m => m.killed)) f.push('mutant survived or none written')
    if (!v.hunks_cited.length) f.push('verifier cited no hunks')
    for (const d of v.decision_fidelity) if (!d.ok) f.push('decision ' + d.decision_id + ' violated: ' + (d.note || ''))
    if (v.protected_touched.length && !(c.protected_ok || []).length) f.push('protected files touched: ' + v.protected_touched.join(','))
  }
  if (ref.status === 'ok' && r.refuted && r.reproduction && r.reproduction.exit_code !== 0) f.push('REFUTED: ' + r.reproduction.command + ' → exit ' + r.reproduction.exit_code + '\n' + r.reproduction.output_tail)
  else if (ref.status === 'ok' && r.refuted) log('refute:' + c.id + ' claimed refuted without a failing reproduction — ignored (no-evidence)')
  if (impl.dod.length !== c.dod.length) f.push('dod rows ' + impl.dod.length + ' != card ' + c.dod.length)
  if (impl.changed_lines > 2 * (c.est_lines || 300)) f.push('scope expansion: ' + impl.changed_lines + ' lines changed vs est ' + c.est_lines)
  return f
}
async function verifyLeg(c, impl, tests, tag) {
  const [ver, ref] = await Promise.all([
    safeAgent('verify', c.id + ':' + tag, pVerify(c, impl, tests), { schema: VERIFY, effort: 'medium', phase: 'Build' }),
    safeAgent('refute', c.id + ':' + tag, pRefute(c, impl), { schema: REFUTE, effort: 'medium', phase: 'Build' }),
  ])
  return { ver, ref, failures: reduceVerdicts(c, impl, ver, ref) }
}
function block(rec, reason) { rec.state = 'blocked'; rec.reason = reason; log(rec.id + ' BLOCKED: ' + reason); return rec }

async function runTask(c, base, tests, opts) {
  const rec = { id: c.id, state: 'pending', base, fixes: 0, vetoes: 0, fps: [], trail: [] }
  if (!tests || tests.status !== 'ok') return block(rec, 'tests-missing:' + (tests ? tests.reason : 'none'))
  if (!budgetOk('task ' + c.id)) return block(rec, 'budget')
  const implOpts = { schema: IMPL, effort: 'high', phase: 'Build' }; if (c.model_override) implOpts.model = c.model_override
  let impl = await safeAgent('impl', c.id, pImpl(c, base, tests.value, null, false), implOpts)
  if (impl.status !== 'ok' && impl.status !== 'reused') return block(rec, 'implement:' + impl.reason)
  let leg = await verifyLeg(c, impl.value, tests.value, 'v' + rec.fixes)
  while (leg.failures.length) {
    const fp = fingerprint(leg.failures); rec.fps.push(fp); rec.trail.push({ fixes: rec.fixes, fp })
    if (rec.fixes >= MAX_FIX) return block(rec, 'verify-exhausted')
    if (rec.fps.length >= 3 && rec.fps[rec.fps.length - 1] === rec.fps[rec.fps.length - 3] && rec.fps[rec.fps.length - 1] !== rec.fps[rec.fps.length - 2]) return block(rec, 'oscillation')
    const repeat = rec.fps.length >= 2 && fp === rec.fps[rec.fps.length - 2]
    if (repeat && rec.pivoted) return block(rec, 'fingerprint-repeat')
    rec.fixes++; rec.pivoted = rec.pivoted || repeat
    log(c.id + ': fix ' + rec.fixes + '/' + MAX_FIX + (repeat ? ' (two strikes → pivot)' : '') + ' fp=' + fp)
    const fixed = await safeAgent('fix', c.id + ':' + rec.fixes, pImpl(c, base, tests.value, { failures: leg.failures, fingerprint: fp }, repeat), implOpts)
    if (fixed.status !== 'ok') return block(rec, 'agent-null:fix')
    if (repeat && !(fixed.value.alternatives && fixed.value.alternatives.length >= 2 && fixed.value.alternatives.filter(a => a.chosen).length === 1)) return block(rec, 'pivot-without-alternatives')
    impl = fixed
    leg = await verifyLeg(c, impl.value, tests.value, 'v' + rec.fixes)
  }
  while (true) {
    const judge = await safeAgent('judge', c.id + ':j' + rec.vetoes, pJudge(c, impl.value), { schema: JUDGE_TASK, effort: 'medium', phase: 'Build' })
    const veto = judge.status === 'ok' && judge.value.verdict === 'veto' && judge.value.reproduced
    if (judge.status !== 'ok') { log(c.id + ': judge unavailable (' + judge.reason + ') — no veto possible, recorded'); break }
    if (!veto) break
    if (rec.vetoes >= MAX_VETO || rec.fixes >= MAX_FIX) return block(rec, 'judge-veto:' + judge.value.veto_reason)
    rec.vetoes++; rec.fixes++
    const fixed = await safeAgent('fix', c.id + ':veto' + rec.vetoes, pImpl(c, base, tests.value, { veto: judge.value.veto_reason, reproduction: judge.value.veto_reproduction }, false), implOpts)
    if (fixed.status !== 'ok') return block(rec, 'agent-null:fix-after-veto')
    impl = fixed
    leg = await verifyLeg(c, impl.value, tests.value, 'veto' + rec.vetoes)
    if (leg.failures.length) return block(rec, 'reverify-after-veto')
  }
  rec.state = 'built'; rec.impl = impl.value; rec.tests = tests.value
  log(c.id + ' BUILT head=' + short(rec.impl.head_sha) + ' fixes=' + rec.fixes + ' vetoes=' + rec.vetoes + (impl.status === 'reused' ? ' (reused)' : ''))
  return rec
}

// =====================================================================================
// Integration (§4g): fixed-order merge queue, conflict resolver, gate after every merge, clean gate every K merges
// =====================================================================================
let mergeCount = 0, lastCleanHead = A.integration_sha_at_launch, gateRedUpstream = false
const cleanGates = [], reviewJobs = []
async function integrateOne(c, rec, prev, n) {
  if (rec.state !== 'built') return { head: prev, status: 'skipped', reason: rec.reason }
  if (gateRedUpstream) { block(rec, 'gate-red-upstream'); return { head: prev, status: 'skipped', reason: 'gate-red-upstream' } }
  let integ = await safeAgent('integrate', c.id, pIntegrate(c, rec.impl, prev, n), { schema: INTEGRATION, effort: 'low', phase: 'Integrate' })
  if (integ.status === 'ok' && integ.value.result === 'conflict') {
    log(c.id + ': conflict in ' + integ.value.conflicts.map(x => x.file).join(',') + ' → resolver')
    const res = await safeAgent('resolve', c.id, pResolve(c, rec.impl, prev, integ.value), { schema: INTEGRATION, effort: 'xhigh', phase: 'Integrate' })
    if (res.status === 'ok' && res.value.result === 'merged') {
      integ = await safeAgent('integrate', c.id + ':ff', PREFIX + 'ROLE: integrator. Fast-forward ' + INTEG + ' in ' + REPO + ' to ' + res.value.head_sha + ' (fetch ' + res.value.bundle_path + '); run ' + GATE + ' --range ' + prev + '..HEAD; git cherry must be empty; bundle as the integrator does; return result.', { schema: INTEGRATION, effort: 'low', phase: 'Integrate' })
    } else { block(rec, 'conflict-unresolved'); return { head: prev, status: 'skipped', reason: 'conflict' } }
  }
  if (integ.status === 'ok' && integ.value.result === 'gate-failed') {
    for (let round = 1; round <= 2 && integ.value.result === 'gate-failed'; round++) {
      log(c.id + ': merged tree RED (round ' + round + '/2) → integration fixer')
      const fx = await safeAgent('integfix', c.id + ':' + round, PREFIX + 'ROLE: integration fixer. Worktree of ' + INTEG + ' at its head; the merged tree is RED (ledger ' + short(integ.value.gate_ledger_hash) + '). Fix on ' + INTEG + ' so BOTH cards hold; run the gate; commit; return head_sha and ledger. CARD: ' + cardText(c), { schema: IMPL, effort: 'high', phase: 'Integrate' })
      if (fx.status !== 'ok') break
      integ = await safeAgent('integrate', c.id + ':regate' + round, PREFIX + 'ROLE: integrator. On ' + INTEG + ' at ' + fx.value.head_sha + ' run ' + GATE + ' --range ' + prev + '..HEAD; return result merged or gate-failed with the ledger hash; bundle; git cherry check.', { schema: INTEGRATION, effort: 'low', phase: 'Integrate' })
    }
    if (integ.status !== 'ok' || integ.value.result !== 'merged') {
      await safeAgent('integrate', c.id + ':revert', PREFIX + 'ROLE: integrator. On ' + INTEG + ': git revert -m 1 the merge of ' + c.id + ' (head ' + rec.impl.head_sha + '); run ' + GATE + ' --range ' + prev + '..HEAD; return result.', { schema: INTEGRATION, effort: 'low', phase: 'Integrate' })
      block(rec, 'integration-red:reverted'); rec.state = 'reverted'; return { head: prev, status: 'skipped', reason: 'reverted' }
    }
  }
  if (integ.status !== 'ok' || integ.value.result !== 'merged') { block(rec, 'integration:' + (integ.reason || (integ.value && integ.value.result))); return { head: prev, status: 'skipped', reason: 'integration' } }
  if (integ.value.cherry_unmerged.length) { block(rec, 'cherry-unmerged:' + integ.value.cherry_unmerged.join(',')); return { head: prev, status: 'skipped', reason: 'cherry' } }
  const head = integ.value.head_sha; mergeCount++; rec.state = 'merged'; rec.head = head
  log(c.id + ' MERGED → ' + short(head) + ' (#' + mergeCount + ')' + (integ.value.pushed ? ' pushed' : ''))
  if (mergeCount % CLEAN_EVERY === 0) await cleanGate(head)
  return { head, status: 'merged' }
}
async function cleanGate(head) {
  const g = await safeAgent('cleangate', short(head), pCleanGate(head), { schema: GATE_RUN, effort: 'low', phase: 'Integrate' })
  cleanGates.push({ head, g })
  const green = g.status === 'ok' && g.value.verdict === 'GREEN' && g.value.journeys.fail === 0 && g.value.self_test !== 'fail'
  log('clean gate @' + short(head) + ': ' + (green ? 'GREEN' : 'RED') + ' journeys ' + (g.value ? g.value.journeys.pass + '/' + g.value.journeys.fail + ' skipped-needs ' + g.value.journeys.skipped_needs.join(',') : 'n/a'))
  if (!green) { gateRedUpstream = true; log('ADMISSIONS STOPPED: clean gate red at ' + short(head)) } else gateRedUpstream = false
  if (green && INCR_REVIEW) { reviewJobs.push(reviewDelta(lastCleanHead, head, 'incr' + cleanGates.length)); lastCleanHead = head }
  return green
}

// =====================================================================================
// DAG scheduler (§4d): admission by readiness in rank order, bounded in-flight set, fixed-order merge queue
// =====================================================================================
async function runDag(cards, testsById, startHead) {
  const { mergeOrder, rank } = planDag(cards)
  const sem = makeSemaphore(WAVE)
  const builtP = new Map(), mergedP = new Map(), recs = new Map()
  let tail = Promise.resolve({ head: startHead, status: 'merged' })
  let n = 0
  for (const c of mergeOrder) {
    const deps = c.dependsOn.map(d => (SPEC_DEPS && c.speculativeOk && c.spine && recs.has(d)) ? builtP.get(d).then(r => r.state === 'built' ? { head: r.impl.head_sha, status: 'built' } : mergedP.get(d)) : mergedP.get(d))
    builtP.set(c.id, Promise.all(deps).then(async ds => {
      if (ds.some(d => d.status === 'skipped')) return block({ id: c.id, state: 'pending' }, 'dep-blocked')
      const base = ds.length ? ds[ds.length - 1].head : startHead   // deterministic: the last dependency in merge order
      await sem.acquire(rank.get(c.id), c.id)
      try {
        if (gateRedUpstream) return block({ id: c.id, state: 'pending' }, 'gate-red-upstream')
        if (!agentsOk('task ' + c.id, 6)) return { id: c.id, state: 'deferred', reason: 'agent-cap' }
        log('ADMIT ' + c.id + ' rank=' + rank.get(c.id) + ' base=' + short(base) + ' agents=' + agentCount)
        let tests = testsById.get(c.id)
        if (!tests) { tests = await safeAgent('testauthor', c.id, pTests(c, base), { schema: TESTS, effort: 'medium', phase: 'Tests' }); testsById.set(c.id, tests) }
        return await runTask(c, base, tests)
      } finally { sem.release() }
    }).then(r => { recs.set(c.id, r); return r }))
    const myN = ++n
    mergedP.set(c.id, Promise.all([builtP.get(c.id), tail]).then(([rec, prev]) => integrateOne(c, rec, prev.head, myN)))
    tail = mergedP.get(c.id)
  }
  const last = await tail
  const all = mergeOrder.map(c => recs.get(c.id) || { id: c.id, state: 'not_attempted' })
  const counts = {}; all.forEach(r => { counts[r.state] = (counts[r.state] || 0) + 1 })
  log('dag done: head=' + short(last.head) + ' ' + J(counts).replace(/\n/g, ' '))
  if (mergeCount % CLEAN_EVERY !== 0 || cleanGates.length === 0) await cleanGate(last.head)
  return { head: last.head, recs: all }
}

// front-loaded test authoring (cap ≥ 8): all cards, rank order, bounded by TA_SLOTS so implementers are never queued behind test authors
async function frontLoadTests(cards, testsById) {
  const { mergeOrder, rank } = planDag(cards)
  const sem = makeSemaphore(Math.max(1, TA_SLOTS))
  await Promise.all(mergeOrder.map(async c => {
    await sem.acquire(rank.get(c.id), c.id)
    try { if (!testsById.has(c.id)) testsById.set(c.id, await safeAgent('testauthor', c.id, pTests(c, A.integration_sha_at_launch), { schema: TESTS, effort: 'medium', phase: 'Tests' })) }
    finally { sem.release() }
  }))
  log('tests front-loaded: ' + [...testsById.values()].filter(t => t.status === 'ok').length + '/' + cards.length + ' ok')
}

// =====================================================================================
// Outer loop (§6): delta-scoped lens reviewers → 3-lens refuters → fix chains → 3-lens panel; dry/round/budget bounded
// =====================================================================================
const LENSES = ['correctness', 'security-and-secrets', 'zerogpu-quota-and-cost', 'api-and-mcp-contract', 'tests-and-gate']
const seen = new Set(), confirmedAll = [], refutedAll = []
const fkey = f => (f.file || '') + '::' + (f.symbol || '') + '::' + String(f.title || '').toLowerCase().replace(/\s+/g, ' ').trim()
async function reviewDelta(from, to, tag) {
  const known = [...seen].sort()
  const rs = await settle(LENSES.map(lens => () => safeAgent('review', lens + ':' + tag, PREFIX + ['ROLE: reviewer, lens ' + lens + '. Review ' + INTEG + ' delta ' + from + '..' + to + ' (read-only worktree ' + WT + '/clean-' + to + ').',
    'Report NEW problems only that affect correctness or a decided requirement; each needs an executed reproduction (command + exit code) and a symbol; write the full list to ' + A.plan_dir + '/findings/' + tag + '-' + lens + '.json.',
    'Decision sheet: ' + A.plan_dir + '/decisions.json. KNOWN (do not repeat): ' + J(known)].join('\n'), { schema: REVIEW_FINDINGS, effort: 'high', phase: 'Review' })), TIMEOUT_MS.review, LENSES.map(l => 'review:' + l))
  const found = rs.filter(r => r.status === 'ok').flatMap(r => r.value.findings).sort(byId)
  const fresh = found.filter(f => !seen.has(fkey(f)) && f.affects_correctness_or_requirement)
  const style = found.filter(f => !f.affects_correctness_or_requirement).length
  fresh.forEach(f => seen.add(fkey(f)))
  log('review ' + tag + ': ' + found.length + ' found, ' + fresh.length + ' fresh, ' + style + ' style-only (logged, not queued), ' + (found.length - fresh.length - style) + ' seen')
  const judged = await pipeline(fresh, f => settle(['reproduce', 'read-the-source', 'in-scope-and-decided'].map(lens => () => safeAgent('refutef', f.id + ':' + lens, PREFIX + ['ROLE: skeptic (' + lens + '). REFUTE this finding at ' + to + '. Default refuted=true if uncertain; a refutation counts only with an executed reproduction (exit code).', J(f)].join('\n'), { schema: REFUTE_FINDING, effort: 'medium', phase: 'Review' })), TIMEOUT_MS.refutef)
    .then(vs => { const ok = vs.filter(v => !h6IsDrop(v) && v.status === 'ok').map(v => v.value); const alive = ok.filter(v => !v.refuted).length >= 2 && ok.some(v => v.reproduction && v.reproduction.exit_code !== 0); return { f, alive, votes: ok.length } }))
  const alive = judged.filter(j => j && j.alive).map(j => j.f)
  judged.filter(j => j && !j.alive).forEach(j => refutedAll.push(j.f))
  log('review ' + tag + ': ' + alive.length + '/' + fresh.length + ' survived refutation')
  return alive
}
function rfCard(round, f) {
  return { id: 'RF' + round + '-' + fnv(fkey(f)), title: f.title, area: 'core', spine: false, size: 'S', est_lines: 80, est_minutes: { impl: 8, tests: 5 },
    dependsOn: [], speculativeOk: false, files_allowed: [f.file, 'tests/RF' + round + '-' + fnv(fkey(f)) + '/'], deps_allowed: [], interface: {},
    decision_ids: f.decision_ids || [], findings: [{ id: f.id, corrected: f.recommendation, symbol: f.symbol }], in_scope: [f.title], out_of_scope: [],
    dod: [{ line: 'the reproduction no longer fails: ' + f.reproduction.command, command: f.reproduction.command, expect: 'exit 0' }],
    acceptance_tests: ['tests/RF' + round + '-' + fnv(fkey(f)) + '/test_regress.py'], gate_profile: 'full', reading_list: [f.file], verification_level_expected: 'local-stub' }
}
async function outerLoop(head) {
  let round = 0, dry = 0, verdict = null, stop = null, inversionDone = false
  let pending = (await Promise.all(reviewJobs)).flat()       // findings from incremental reviews (cap ≥ 8), already refuted
  while (true) {
    if (verdict && verdict.verdict === 'satisfied') { stop = 'judge-satisfied'; break }
    if (round >= MAX_ROUNDS) { stop = 'max-rounds(' + MAX_ROUNDS + ')'; break }
    if (dry >= DRY_ROUNDS && inversionDone) { stop = 'dry-rounds(' + DRY_ROUNDS + ')'; break }
    if (!budgetOk('review round ' + (round + 1))) { stop = 'budget-reserve'; break }
    if (!agentsOk('review round ' + (round + 1), 20)) { stop = 'agent-cap'; break }
    round++
    const alive = pending.concat(await reviewDelta(lastCleanHead === head ? A.integration_sha_at_launch : lastCleanHead, head, 'r' + round)); pending = []
    if (dry >= DRY_ROUNDS && !inversionDone) {
      inversionDone = true
      const inv = await safeAgent('inversion', 'r' + round, PREFIX + 'ROLE: DoD-inversion reviewer. Start from ' + A.plan_dir + '/decisions.json and every card DoD line; independently try to falsify each claimed end-state at ' + head + ' or find an omitted obligation. Do NOT reuse these probes: ' + J([...seen].sort()) + '. Executed reproduction required.', { schema: REVIEW_FINDINGS, effort: 'high', phase: 'Review' })
      if (inv.status === 'ok') { const nf = inv.value.findings.filter(f => !seen.has(fkey(f))); nf.forEach(f => seen.add(fkey(f))); alive.push(...nf); log('DoD inversion: ' + nf.length + ' new') }
    }
    dry = alive.length ? 0 : dry + 1
    confirmedAll.push(...alive)
    if (alive.length) {
      const cards = alive.map(f => rfCard(round, f)).sort(byId)
      log('round ' + round + ': ' + cards.length + ' fix card(s) → same chain + merge queue')
      const r = await runDag(cards, new Map(), head); head = r.head
    }
    const votes = await settle(['spec-compliance', 'test-evidence', 'release-readiness'].map(lens => () => safeAgent('panel', lens + ':r' + round, PREFIX + ['ROLE: judge (' + lens + '), fresh context. Decide whether ' + INTEG + ' at ' + head + ' satisfies the decision sheet for stage ' + A.stage + '.',
      'satisfied ONLY if: no blocked task of high severity below, last clean gate GREEN with journeys all passing, no confirmed finding of severity ≥ high unfixed. Cite the ledger at ' + WT + '/clean-' + head + '/.gate/last_run.json.',
      'BLOCKED: ' + J(blockedRows()), 'CONFIRMED THIS ROUND: ' + J(alive.map(f => ({ id: f.id, severity: f.severity })))].join('\n'), { schema: JUDGE_PANEL, effort: 'xhigh', phase: 'Review' })), TIMEOUT_MS.panel)
    const ok = votes.filter(v => !h6IsDrop(v) && v.status === 'ok').map(v => v.value)
    const sat = ok.filter(v => v.verdict === 'satisfied').length
    const lastGate = cleanGates[cleanGates.length - 1], gateGreen = lastGate && lastGate.g.status === 'ok' && lastGate.g.value.verdict === 'GREEN' && lastGate.g.value.journeys.fail === 0
    const precond = gateGreen && blockedRows().filter(b => b.severity === 'high').length === 0
    verdict = { verdict: (sat >= 2 && precond) ? 'satisfied' : ok.some(v => v.verdict === 'blocked-needs-owner') ? 'blocked-needs-owner' : 'not-satisfied', votes: ok.length, sat, precond }
    log('panel r' + round + ': ' + sat + '/' + ok.length + ' satisfied, preconditions ' + precond + ' → ' + verdict.verdict)
    if (verdict.verdict === 'blocked-needs-owner') { stop = 'judge-blocked-needs-owner'; break }
  }
  log('review loop: ' + stop + ' after ' + round + ' round(s); confirmed ' + confirmedAll.length + '; refuted ' + refutedAll.length)
  return { head, verdict, stop, round }
}
const allRecs = []
function blockedRows() { return allRecs.filter(r => r.state !== 'merged' && r.state !== 'built').map(r => ({ id: r.id, state: r.state, reason: r.reason, severity: /spine|T0[1-6]|T07|T11|T15/.test(r.id) ? 'high' : 'medium' })) }
```

```js
// =====================================================================================
// Stages — top-level flow (one run per args.stage); every stage body is try/caught so the synthesizer always runs
// =====================================================================================
let head = A.integration_sha_at_launch, stopReason = 'not-run', verdict = null, plan = null, abortReason = null
const testsById = new Map()
try {
  // ---------- Setup (R1/R2/R3; idempotent) ----------
  if (A.stage !== 'plan') {
    phase('Setup')
    const setup = await safeAgent('setup', NONCE, PREFIX + [
      'ROLE: setup (idempotent; the ONLY role allowed to install packages). Durable root ' + ROOT + ' (refuse /tmp).',
      '1. If ' + REPO + ' is missing: git clone ' + A.snapshot_src + ' ' + REPO + '; assert git rev-parse HEAD == ' + A.base_sha + '; else assert ' + A.base_sha + ' is an ancestor of HEAD.',
      '2. chmod -R a-w ' + A.snapshot_src + ' and its sibling space-src (read-only snapshot sources); cp -r ' + A.libsrc + ' ' + ROOT + '/libsrc (wheels + sources; skip if present).',
      '3. venv: /usr/bin/python3.12 -m venv ' + VENV + ' (skip if ' + VENV + '/.setup-done matches the requirement list hash); pip install ' + ROOT + '/libsrc/wheels/*.whl gradio-client==2.6.1 tokenizers ruff pyflakes pytest pytest-socket pyyaml jsonschema hypothesis openai regex; NO torch.',
      '4. Write ' + GATE + ' byte-for-byte from ' + A.plan_dir + '/gate.sh (the design §7 text) and ' + REPO + '/AGENTS.md from ' + A.plan_dir + '/AGENTS.md; mkdir -p ' + WT + ' ' + BUNDLES + ' ' + ROOT + '/ledgers ' + A.grill + '/evidence/build-bundles.',
      '5. Baseline: BUILD_ROOT=' + ROOT + ' ' + VENV + '/bin/python -m pytest --collect-only -q -p no:cacheprovider tests | tail -1 → write ' + ROOT + '/.gate-baseline.json {collected, skipped:0, xfailed:0} at ' + A.base_sha + ' (expected 73).',
      '6. Prune stale worktrees from previous nonces after bundling them to ' + BUNDLES + '/stale-<name>.bundle; ensure branch ' + INTEG + ' exists at ' + A.integration_sha_at_launch + '.',
      '7. Run BUILD_ROOT=' + ROOT + ' ' + GATE + ' --clean ' + A.base_sha + ' --self-test --profile bootstrap and return gate_self_test from the printed self_test (the base is EXPECTED RED on ruff; self_test must be pass).',
      'Return packages_installed (list), venv_python, baseline_collected, reused.'].join('\n'), { schema: SETUP, effort: 'medium', phase: 'Setup' })
    if (setup.status !== 'ok' && setup.status !== 'reused') throw new Error('setup failed: ' + setup.reason)
    if (setup.value.gate_self_test !== 'pass') throw new Error('gate self-test FAILED — a gate that cannot fire is not a gate (D-14)')
    if (!/^Python 3\.12\./.test(setup.value.venv_python)) throw new Error('venv is not 3.12: ' + setup.value.venv_python)
    log('setup ok: python=' + setup.value.venv_python + ' baseline=' + setup.value.baseline_collected + ' installed=' + setup.value.packages_installed.length + (setup.value.reused ? ' (reused)' : ''))
  }

  // ---------- Plan (R0): ground the orchestrator-drafted plan; critics; one bounded repair ----------
  if (A.stage === 'plan') {
    phase('Plan')
    const ground = await settle([
      () => safeAgent('symbolize', NONCE, PREFIX + 'ROLE: findings symbolizer. For every finding id referenced in ' + A.plan_dir + '/cards/*.json map its CORRECTED text to file::symbol at ' + A.base_sha + ' in ' + REPO + ' (git grep -n "def <name>"); for the five UNVERIFIED critic findings (critic-1..5) reproduce or refute with an executed command; write ' + A.plan_dir + '/findings-symbolized.json. Never read line numbers as truth.', { schema: SYMBOLIZE, effort: 'medium', phase: 'Plan' }),
      () => safeAgent('apiledger', NONCE, PREFIX + 'ROLE: API ledger. From ' + ROOT + '/libsrc (gradio 6.26.0, spaces 0.51.3, transformers 5.16.1, huggingface_hub 1.32.0) record every symbol+kwargs the cards\' reading_list needs (≥ 20: gr.ChatInterface/Chatbot/Blocks/mount_gradio_app/api, spaces.GPU(size=,duration=), GenerationConfig fields (max_time, prefill_chunk_size, no presence_penalty), continue_final_message bool|str, HfApi.restart_space/duplicate_repo/fetch_space_logs/wait_for_space, gradio_client.Client) with libsrc path:line, plus the known-bad idiom list from research-4 F-8. Write ' + A.plan_dir + '/api-ledger.json and .md.', { schema: API_LEDGER, effort: 'medium', phase: 'Plan' }),
      () => safeAgent('catalog', NONCE, PREFIX + 'ROLE: catalog provenance. Using ONLY read-only Hub tools (hub_repo_details / hf_fs stat via ToolSearch), save the raw response for each repo in ' + A.plan_dir + '/catalog-candidates.json under ' + A.grill + '/evidence/catalog/<owner>__<name>.json with fetched_at; record revision sha and inferenceProviderMapping; on any fetch failure after 3 tries return status unresolved for that entry — never a remembered value.', { schema: CATALOG_PROV, effort: 'low', phase: 'Plan' }),
    ], TIMEOUT_MS.apiledger, ['symbolize', 'apiledger', 'catalog'])
    log('grounding: ' + ground.map(g => (h6IsDrop(g) ? 'drop' : g.status)).join('/'))
    const critique = async tag => settle([
      () => safeAgent('plancritic', 'fidelity:' + tag, PREFIX + 'ROLE: plan critic (decision-fidelity + completeness). Read ' + A.plan_dir + '/decisions.json, every card, findings-symbolized.json and the lens-4 14 steps. must_fix: any card that contradicts a decided value, any decided consequence with no card, any finding whose CORRECTED line is not carried by a card, stale symbols.', { schema: PLAN_CRITIC, effort: 'high', phase: 'Plan' }),
      () => safeAgent('plancritic', 'sizing:' + tag, PREFIX + 'ROLE: plan critic (sizing + overlap + runnability). must_fix: cards over ' + TASK_MAX_LINES + ' lines or 12 files, unordered cards sharing files, DoD commands not runnable under ' + VENV + ' on CPU, interfaces referenced by dependents that no card defines, acceptance_tests paths missing.', { schema: PLAN_CRITIC, effort: 'high', phase: 'Plan' }),
    ], TIMEOUT_MS.plancritic, ['critic-fidelity', 'critic-sizing'])
    let cr = await critique('c1')
    let mustFix = cr.filter(c => !h6IsDrop(c) && c.status === 'ok').flatMap(c => c.value.must_fix)
    let ready = cr.every(c => !h6IsDrop(c) && c.status === 'ok' && c.value.verdict === 'ready')
    log('plan critique: ' + mustFix.length + ' must_fix; ready=' + ready)
    if (!ready && mustFix.length) {
      const rep = await safeAgent('planrepair', NONCE, PREFIX + 'ROLE: plan repair. Apply these must_fix items to the cards in ' + A.plan_dir + '/cards/ (split oversize cards, add missing cards, fix symbols/interfaces); print the new sha256 of the plan dir as plan_hash_after. MUST_FIX: ' + J(mustFix), { schema: PLAN_REPAIR, effort: 'medium', phase: 'Plan' })
      cr = await critique('c2')
      mustFix = cr.filter(c => !h6IsDrop(c) && c.status === 'ok').flatMap(c => c.value.must_fix)
      ready = cr.every(c => !h6IsDrop(c) && c.status === 'ok' && c.value.verdict === 'ready')
      log('plan re-critique after repair: ' + mustFix.length + ' must_fix; ready=' + ready + '; new plan hash ' + (rep.status === 'ok' ? rep.value.plan_hash_after.slice(0, 12) : 'n/a'))
    }
    plan = { ready, mustFix }
    stopReason = ready ? 'plan-ready' : 'plan-not-ready'
  }

  // ---------- Build + Integrate (R1) ----------
  if (A.stage === 'build-local') {
    const cards = (SMOKE ? A.cards.filter(c => c.id === 'T01a') : A.cards).map(c => Object.assign({}, c, { dependsOn: [...c.dependsOn] }))
    if (SMOKE) log('SMOKE: one task only (T01a) to surface permission prompts and the worktree/gate mechanics')
    if (FRONT_LOAD && !SMOKE) { phase('Tests'); await frontLoadTests(cards, testsById) }
    phase('Build')
    const r = await runDag(cards, testsById, A.integration_sha_at_launch)
    head = r.head; allRecs.push(...r.recs)
    if (!SMOKE) { phase('Review'); const o = await outerLoop(head); head = o.head; verdict = o.verdict; stopReason = o.stop }
    else stopReason = r.recs[0] && r.recs[0].state === 'merged' ? 'smoke-ok' : 'smoke-failed:' + (r.recs[0] && r.recs[0].reason)
  }

  // ---------- Stage / Promote (R2/R3): read CI artifacts only; never call a Space ----------
  if (A.stage === 'stage' || A.stage === 'promote') {
    phase(A.stage === 'stage' ? 'Stage' : 'Promote')
    const missing = ['github_repo_url', 'staging_space'].filter(k => !A.approvals[k])
    if (missing.length) { stopReason = 'blocked_on_owner:' + missing.join(','); throw new Error('approvals missing: ' + missing.join(',')) }
    const reads = await settle((A.ci_runs || []).map(id => () => safeAgent('ciread', String(id), PREFIX + 'ROLE: CI reader (read-only). gh run view ' + id + ' --json conclusion,headSha; gh run download ' + id + ' -D ' + A.grill + '/evidence/orchestration/ci/' + id + '; parse canary.json, boot.json, measurements.json, runtime.json; report running vs deployed sha, boot seconds, canary pass^k, measurements, visibility_private. verification_level=staging-required (these numbers are the staging truth). Never call any Space URL.', { schema: CI_READ, effort: 'medium', phase: A.stage === 'stage' ? 'Stage' : 'Promote' })), TIMEOUT_MS.ciread)
    const ok = reads.filter(r => !h6IsDrop(r) && r.status === 'ok').map(r => r.value)
    const bad = ok.filter(r => r.conclusion !== 'success' || r.running_sha !== r.deployed_sha || r.canary.passes < r.canary.attempts)
    log(A.stage + ': ' + ok.length + ' CI runs read, ' + bad.length + ' failing')
    if (A.stage === 'stage' && bad.length && budgetOk('staging fixes')) {
      const cards = bad.map((r, i) => ({ id: 'SF-' + fnv(r.run_id), title: 'staging failure in run ' + r.run_id, area: 'core', spine: false, size: 'S', est_lines: 120, est_minutes: { impl: 10, tests: 5 }, dependsOn: [], speculativeOk: false,
        files_allowed: ['worker/', 'api/', 'core/', 'tests/SF-' + fnv(r.run_id) + '/'], deps_allowed: [], interface: {}, decision_ids: ['G-1a', 'M-2'], findings: [{ id: 'ci:' + r.run_id, corrected: 'see ' + r.logs_tail_path + ' and ' + r.artifact_paths.join(','), symbol: '' }],
        in_scope: ['make the staging run green'], out_of_scope: [], dod: [{ line: 'the failing CI step passes locally against the recorded artifact', command: VENV + '/bin/python -m pytest tests/SF-' + fnv(r.run_id) + ' -q', expect: 'exit 0' }],
        acceptance_tests: ['tests/SF-' + fnv(r.run_id) + '/test_staging_regress.py'], gate_profile: 'full', reading_list: r.artifact_paths, verification_level_expected: 'staging-required' })).sort(byId)
      const r = await runDag(cards, new Map(), A.integration_sha_at_launch); head = r.head; allRecs.push(...r.recs)
    }
    const measured = ok.filter(r => r.measurements && r.measurements.tok_per_s)
    if (A.stage === 'stage' && measured.length) log('measurements available: seed worker/lease.py from ' + measured.map(m => m.run_id).join(',') + ' (a constants card is emitted by the synthesizer, cited to the artifact)')
    const o = await outerLoop(head); head = o.head; verdict = o.verdict; stopReason = o.stop
  }
} catch (e) {
  abortReason = String(e && e.message || e); log('RUN ABORTED: ' + abortReason)
}

// ---------- Synthesize (always; mechanical inputs only; verified by a second agent) ----------
phase('Synthesize')
const rows = allRecs.map(r => ({ item_id: r.id, state: r.state, reason: r.reason || '', head: r.head || (r.impl && r.impl.head_sha) || '' })).sort(byId)
const nextAction = abortReason ? 'blocked' : A.stage === 'plan' ? 'approve-plan' : SMOKE ? (stopReason === 'smoke-ok' ? 'smoke-ok' : 'smoke-failed') :
  A.stage === 'build-local' ? (rows.some(r => r.state === 'deferred') ? 'resume' : (verdict && verdict.verdict === 'satisfied') ? 'push-and-stage' : 'blocked') :
  A.stage === 'stage' ? ((verdict && verdict.verdict === 'satisfied') ? 'promote-production' : 'restage') : ((verdict && verdict.verdict === 'satisfied') ? 'done' : 'rollback-requested')
let synth = null, synthVerify = null
try {
  synth = await safeAgent('synth', NONCE, PREFIX + ['ROLE: synthesizer. You may not edit code and may not re-derive facts: build the report ONLY from the mechanical inputs below and from files.',
    'Write ' + A.grill + '/evidence/orchestration/SYNTHESIS-' + NONCE + '.md (one row per card with the enum status; DoD lines done/total per card from the ledgers under ' + ROOT + '/ledgers; every staging-required claim inline with its RUNBOOK row; owner actions; the next checkpoint = ' + nextAction + '),',
    REPO + '/RUNBOOK.md (measurement rows + owner pre-flight list), ' + (A.stage !== 'plan' ? REPO + '/PROMOTION_REQUEST.md (what/why/evidence/rollback sha/cost), ' : '') + 'and ' + A.grill + '/evidence/orchestration/timing-' + NONCE + '.json (per-role planned vs actual from t_start/t_end).',
    'STOP REASON: ' + stopReason + (abortReason ? ' ABORT: ' + abortReason : ''), 'VERDICT: ' + J(verdict), 'HEAD: ' + head,
    'LEDGER (every agent call incl. nulls): ' + J(ledger), 'DROPPED: ' + J(dropped), 'ROWS: ' + J(rows), 'CLEAN GATES: ' + J(cleanGates.map(g => ({ head: g.head, verdict: g.g.value ? g.g.value.verdict : 'null', journeys: g.g.value ? g.g.value.journeys : null }))),
    'CONFIRMED FINDINGS: ' + J(confirmedAll.map(f => ({ id: f.id, severity: f.severity, file: f.file }))), 'REFUTED: ' + J(refutedAll.map(f => f.id)), 'PLAN: ' + J(plan),
    'Also run: git -C ' + REPO + ' log --oneline --stat ' + A.integration_sha_at_launch + '..' + INTEG + ' and cite it per row.'].join('\n'), { schema: SYNTH, effort: 'high', phase: 'Synthesize' })
  if (synth.status === 'ok') synthVerify = await safeAgent('synthverify', NONCE, PREFIX + ['ROLE: synthesis verifier (fresh). Cross-check EVERY row of ' + synth.value.artifact_paths.join(', ') + ' against git -C ' + REPO + ' log ' + INTEG + ', the ledgers in ' + ROOT + '/ledgers and this ledger: ' + J(ledger.map(l => ({ role: l.role, item: l.item, status: l.status, head: short(l.head_sha) }))),
    'Rewrite any row that overstates (merged without a merge commit; verified without a ledger; a staging-required claim written as verified; UNVERIFIED items parked in a trailing section). Compute waste_ratio from rows whose work was discarded (blocked, reverted, superseded fixes, refuted findings, null retries). Also check that the toolchain repo status hash equals ' + A.toolchain_status_hash + ' (sha256 of git -C /workspaces/agent-skills-toolchain status --porcelain) and report ledger_matches=false if not.'].join('\n'), { schema: SYNTH_VERIFY, effort: 'medium', phase: 'Synthesize' })
} catch (e) { log('SYNTH FAILED: ' + String(e && e.message || e) + ' — ledger has ' + ledger.length + ' rows, ' + dropped.length + ' drops') }
log('done: stage=' + A.stage + ' stop=' + stopReason + ' head=' + short(head) + ' agents=' + agentCount + ' next=' + nextAction + (synthVerify && synthVerify.status === 'ok' ? ' synth=' + synthVerify.value.verdict + ' waste=' + synthVerify.value.waste_ratio : ''))
return { stage: A.stage, nonce: NONCE, head, stopReason, abortReason, verdict, nextAction, agents: agentCount, rows, dropped, plan,
  synth: synth && synth.value, synthVerify: synthVerify && synthVerify.value, checkpoint: synth && synth.value ? synth.value.checkpoint : { action: nextAction, why: stopReason } }
```

**Orchestrator side (outside the script, in the main turn):** compute `args` with `git rev-parse` (base, integration head), `sha256` of the plan dir and of the toolchain `git status --porcelain`; pre-scan every file the agents will read with the secrets regex; launch `stage:'plan'`; on `approve-plan` show the owner the decision sheet and card table; launch `build-local` with `knobs.smoke:true`; add allow rules; relaunch with `knobs.smoke:false` and `resumeFromRunId`; on `resume`, raise `maxAgentsThisRun` and relaunch (same nonce); on `push-and-stage`, relay the checkpoint; after the owner's outward actions launch `stage`; then `promote`. After every run: read `journal.jsonl`, scan the export with the secrets regex, add the run record's `workflowProgress` FIFO waits to `timing-<nonce>.json`.

---

## 14. Authoring checklist the script author ticks before launch

**Script hygiene (X invariants)**
- [ ] `meta` is a pure literal; the nine phase titles match every `phase()` call byte-for-byte; every `agent()` call inside a chain passes `phase:`.
- [ ] `grep -nE 'Date\.now|Math\.random|new Date\(\)' script.js` → no hits; timestamps/nonces only via `args`.
- [ ] Every `agent()` goes through `safeAgent`; no bare `.filter(Boolean)`; every drop lands in `dropped[]` and a `log()` line.
- [ ] Every loop has an iteration cap that fires before the budget guard; `budgetOk()` uses `budget.total &&`; `RESERVE` and `AGENT_CAP_SOFT` set; the synthesizer runs inside the outer `try/catch` regardless.
- [ ] `semantic()` rejects outward actions (abort), installs, missing reasons, DoD rows ≠ card rows, vetoes without reproduction.
- [ ] Prompts are built only from `args` + sorted results; no `knobs` value is interpolated into a prompt; `J()` is applied to arrays sorted by id.
- [ ] Schemas: `required ⊆ properties`, enums for every verdict, `minItems` on evidence arrays, no field the script does not consume; every schema exercised by the smoke run.

**Args and pre-flight (P0)**
- [ ] `args.cap` = `min(16, nproc − 2)` measured now; `knobs` derived from it and logged on the first narrator line.
- [ ] `args.base_sha` = full `f88b1204a6af53a469c7a3ddf6d9fb2aea5b4be6`; `integration_sha_at_launch` from `git rev-parse` seconds before launch; `run_nonce` chosen; `toolchain_status_hash` computed.
- [ ] `args.build_root` durable and outside both the toolchain repo and the grill folder (`/workspaces/qwen38-space-build`); ≥ 3 GB free.
- [ ] `plan/` drafted: `decisions.json` (one line per decided id), 25 cards + journeys spec + `gate.sh` + `AGENTS.md`; `plan_hash` computed and shown to the owner; every card has runnable `dod[].command`, `acceptance_tests`, `files_allowed`, `interface`, CORRECTED text only.
- [ ] Secrets pre-scan over every file agents will read (`DECISION-QUEUE.md`, findings, cards, snapshots) with the §7 regex; hits redacted; the launching message contains no secret.
- [ ] `args.approvals` filled with `null`/`0`/`false` for everything the owner has not explicitly granted; `push_remote` only if the owner named the repo.
- [ ] Owner pre-flight relayed: HF connector write tools disabled, `gh auth status` scope confirmed, Codespace idle timeout at maximum, client attached; stop notice sent to the other agent; both Windows scheduled tasks disabled; pasted token revoked (owner only).
- [ ] Snapshots `chmod -R a-w` (setup does it; verify once by hand).

**Smoke and resume**
- [ ] `knobs.smoke:true` run completed with `smoke-ok`; permission prompts seen were added as allow rules; the T01a chain's `reused`/cache behaviour observed; `journal.jsonl` read; cache-key settling experiment noted (resume once unchanged, count `key` matches).
- [ ] Full run launched with `resumeFromRunId` of the smoke run and identical prompt-affecting args.
- [ ] Before any resume: live `integration/<nonce>` head equals the resumed run's `integration_sha_at_launch`, else launch fresh (git reuse still applies).

**Gate**
- [ ] `gate.sh` written verbatim from §7; `--self-test` passes on the base (RED on ruff for `f88b120` as expected, `self_test: pass`); `.gate-baseline.json` records 73 collected.
- [ ] `tools/protected.txt` lists: `tools/gate.sh`, `tools/claim_lint.py`, `tools/apicheck.py`, `tools/idiom_lint.py`, `tools/secrets_scan.py`, `tools/catalog_check.py`, `ruff.toml`, `pytest.ini`/`pyproject.toml [tool.pytest*]`, `conftest.py`, `tests/protected.txt`, `tests/test_constants_pin.py`, `tests/test_import_contract.py`, `tests/test_personas.py`, `.github/**`, `requirements*.txt`, `*.lock`.

**After each run**
- [ ] `SYNTHESIS-<nonce>.md` rows checked against `git log`; `synthVerify.ledger_matches === true`; toolchain repo status unchanged.
- [ ] `timing-<nonce>.json` updated with FIFO waits from the run record; `[E]` estimates in §11 replaced by measured p50 for the next invocation's plan critic.
- [ ] Journal export scanned with the secrets regex before it is saved under `evidence/`.

---

## 15. Open questions for the owner (only those whose answer changes the build)

1. **Repo before or after R1?** If the private GitHub repo exists before R1 and `approvals.push_remote` names it, the integrator pushes `integration/<nonce>` and every `impl/*` branch after each merge (durability by push, R2 can start from the pushed head, CI gate runs on the PR immediately). If not, durability is by bundles into the grill folder (synced by your cron) and the push happens at the `push-and-stage` checkpoint. Changes: integrator prompt, R2 preconditions, and whether T16's `gate.yml` gets exercised before R2.
2. **Run R1 now at cap 2, or after the resize?** Cap 2 ≈ 16-18 h in three ≈ 5.5 h invocations; cap 14 ≈ 5-6.5 h in one. Recommendation: run R0 and the R1 **smoke** at cap 2 now (≈ 1 h; it surfaces the permission prompts and the cache behaviour), resize, then the full R1. Changes: `knobs` defaults and `maxAgentsThisRun`.
3. **The one metered hosted call (fixture #1) before T04/T05 or after?** Lens-4's biggest risk is the seam being shaped by whichever backend exists first. If you run the single streamed request (tool + thinking on) before R1 and save it as `evidence/fixtures/hosted-1.json`, T04's conformance suite gets a `recorded-hosted` row that is real and T05's parser location is decided by evidence. Otherwise both cards ship with the row `skipped-needs-owner` and a T05 follow-up card is expected in R2. Changes: T04/T05 cards, `hosted_call_budget_usd`.
4. **MCP: used at all (G-18)?** If not, T12 collapses to `mcp_server=False` + a listing test (≈ 30 lines) and the `api-and-mcp-contract` lens narrows. If yes, T12 as designed (`ask/poll/status/preflight`). Changes: T12 card, J5 journey.
5. **Prompt-injection defaults (G-25):** proposed default = web tools ON in the UI but OFF when the bench holds files; `http_request` POST OFF; third-party reader OFF. Confirm or change. Changes: T06a/T10c flag defaults and the constants-pin rows.
6. **Hosted billing route (M-1a):** HF router (one HF token) vs direct provider key decides which token the CPU Space holds and which the staging duplicate needs re-entered. Changes: T04 `backends/hosted.py` base URL/headers, `space.yaml` secret names, RUNBOOK rows.
7. **May the workflow open PRs on the private repo with `gh` (medium-risk, S-19) or is that owner-only?** Changes: the integrator's final step in R1 and R2's fix delivery (branch push vs PR).
8. **Budgets as data:** `approvals.hosted_call_budget_usd` and `approvals.gpu_seconds_budget` for R2's harness run and canaries (the harness refuses above them). Changes: which `tests/live/` rows run in CI and whether the catalog can leave `unverified`.
9. **Build bundles in the grill folder:** the cron syncs everything under the grill folder into the toolchain repo branch; incremental bundles are small (KBs-low MBs) but they are Space source in the toolchain repo's history. Accept, or point durability at the pushed remote only (question 1). Changes: the integrator's bundle path.
10. **Codespace idle timeout / attendance:** whether an unattended workflow keeps the Codespace alive is UNVERIFIED; if you cannot keep a client attached for ≈ 5.5 h, `maxAgentsThisRun` should drop to ≈ 60 (≈ 3 h slices). Changes: `knobs.maxAgentsThisRun`.
