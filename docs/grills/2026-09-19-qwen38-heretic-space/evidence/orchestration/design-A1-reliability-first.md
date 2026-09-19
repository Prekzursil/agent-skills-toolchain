# Design A1 — RELIABILITY-FIRST implementation workflow for the Space rebuild

- **Author:** Architect A1 (Claude, Fable 5.1) · **Written:** 2026-09-19 · **Angle:** correctness and zero blind spots; every failure mode and anti-pattern is guarded by a concrete mechanism; deterministic gates decide; LLM judges only veto; refute-first at every seam; bounded loops with typed `blocked` results; owner checkpoints at every outward action. Longer wall-clock and higher token cost are accepted and stated (§11).
- **Inputs read in full:** `DECISION-QUEUE.md`, `evidence/workflow-findings.md` (all 50 findings incl. every CORRECTED line), `reports/lens-4-simplification-retry.md`, `WORKFLOW_TOOL_REFERENCE.md`, `research-1-doctrine.md` (D-1..D-30, AP-1..17, C-1..C-9), `research-2-tool-native.md` (T-1..T-25, 12 anti-patterns), `research-3-external-sota.md` (S-1..S-25, AP-1..14), `research-3-external-sota-DEEP.md` (S-1..S-22, AP-1..12), `research-4-red-team.md` (F-1..F-47, gate §3, invariants §2). Also read: `skills/workflow-authoring/templates/h6-timeout-heartbeat.md` (the tested timeout helper), `save-to-repo.sh` (grill-folder sync semantics).
- **Facts verified on this box (read-only, 2026-09-19):** 4 CPUs → concurrency cap 2; `/usr/bin/python3.12` exists; default `python3` is 3.14.2; `ruff`, `pyflakes`, `gitleaks`, `uv`, `mutmut` are NOT installed; wheels for gradio 6.26.0 / spaces 0.51.3 / transformers 5.16.1 / huggingface_hub 1.32.0 exist under the **volatile** session scratchpad `libsrc/wheels/`; the grill folder is NOT a git repo — `save-to-repo.sh` rsyncs it (`-a --delete`) into `/workspaces/agent-skills-toolchain/docs/grills/…` every 5 min and pushes branch `grill/qwen38-heretic-space-2026-09-19`; `/home/codespace` and `/workspaces` are on durable volumes; no `mcp__codex__*` tool is mounted in this session.
- **Naming used throughout.** Principle ids: `D-n` (doctrine), `T-n` (tool-native), `S-n` (research-3), `DS-n` (research-3-DEEP), `F-n` (red-team failure modes). Anti-pattern ids are prefixed by lens to avoid collisions: `D/AP-n`, `T/AP-n`, `S/AP-n`, `DS/AP-n`. Every UNVERIFIED fact is tagged inline and carries the defensive design that neutralises it.

---

## 1. Adopted principles and how conflicts between lenses were resolved

### 1.1 Adopted (by id)

- **Doctrine (all 30 adopted):** D-1 cold-executable briefs · D-2 frozen, hashed contract · D-3 ground-first with probes and an assumption ledger · D-4 cheapest probe first · D-5 file-disjoint units in a real DAG, one writer per file · D-6 TDD red-proof + revert-proof · D-7 smallest-check ladder, empty check set = fail · D-8 root cause first, two strikes then pivot, three then re-decompose, never a 4th identical attempt · D-9 the pipeline is proven not to lie (both-states, fresh clone) · D-10 (adopted in weakened form, see C-B) · D-11 write-as-you-go artifacts · D-12 twelve-condition completion reducer, one shared implementation · D-13 two mechanically independent signals · D-14 detector self-test on every gate · D-15 verifier separation, raw evidence only · D-16 full-text adversarial review, enumerated verdicts, resolver never votes · D-17 overclaims repaired by rewriting the sentence, honest residuals do not block · D-18 anchors carry `path:line@sha` · D-19 algorithms, not agents, for mechanical questions · D-20 terminal `SUCCESS:`/`FAILED:` envelopes · D-21 timeouts + typed drop receipts · D-22 resume-safe by construction · D-23 bounded convergence with dry streak + DoD inversion · D-24 deterministic gates carry blocking weight, judges veto only · D-25 real end-to-end journeys against the packaged artifact · D-26 spec review before quality review · D-27 structured handoffs, synthesizer reads artifacts · D-28 owner-only actions · D-29 completeness critic + minority report · D-30 the deliverable is itself an agent system (12-layer audit, measure before seeding constants, blast-radius on deletions).
- **Tool-native (all 25 adopted):** T-1 one script, several runs, checkpoint between · T-2 trigger message is broadcast and is the only authority · T-3 only a judge schema carries `satisfied` · T-4 independent stop conditions, each logged · T-5 separate bounded counters · T-6 voters never author · T-7 pipeline per item, barrier only for true joins · T-8 enqueue order is the schedule at cap 2 · T-9 refs and bundles outlive worktrees · T-10 one writer per mutable thing · T-11 conflicts by a fresh agent, then re-gate · T-12 integration-test verdict is the truth · T-13 pin the SHA in every code-reading prompt · T-14 prompts are pure functions of args + prior results · T-15 replay-deterministic control flow · T-16 only `result` events replay · T-17 null is a result · T-18 schema every stage · T-19 effort by role (see C-F for the one `model` exception) · T-20 static scaling from args + budget reserve · T-21 log decisions not payloads · T-22 smoke the permissions first · T-23 characterisation pins first · T-24 synthesizer last, never an editor · T-25 read the journal before diagnosing.
- **External SOTA (research-3 S-1..S-25 and DEEP DS-1..DS-22 all adopted)**, with DEEP preferred where the two runs disagree (§1.2 C-D, C-E): executable spec and machine-owned ledger (S-1/S-2, DS-1), outcome grading in the environment (S-3, DS-9), test-author ≠ implementer with held-out compositional tests (S-4, DS-3), locked oracle (S-5, DS-5), deterministic tamper detection (S-6, DS-6), structure not prompts (S-7), mutation on changed code (S-8, DS-4), property tests hardened by a refuter (S-9, DS-7), judge hygiene (S-10, DS-10/11), refute-first with a kill mandate (S-11, DS-8), complete suite from a clean checkout (S-12), context-centric decomposition reconciled with role separation (S-13, C-A), handoff schema (S-14, DS-16), external failing signal only (S-15, DS-15), fix-loop convergence (S-16, DS-14), deterministic gates (S-17), idempotent replay (S-18, DS-18), HITL at the outward edge (S-19, DS-19), claim discipline (S-20, DS-20), zero secrets in the agent runtime (S-21, DS-21), headless Gradio/Spaces primitives (S-22/S-23, DS-22), scale to task (S-24, DS-13 — accepted knowingly, see C-J), process monitor (S-25, with its UNVERIFIED in-run form, §3).
- **Red team:** all 47 failure modes are guarded (§12); the gate contents (§7) start from red-team §3 and the script invariants from §2.

### 1.2 Conflicts and how each was resolved

| # | Conflict | Resolution (and who wins) |
|---|---|---|
| **C-A** | S-13/DS "decompose by context; the agent that owns a feature also writes its tests" vs the owner non-negotiable "test authors ≠ implementers" and D-6/S-4/DS-3 | **Owner rule wins.** Acceptance tests (visible + held-out) are written by fresh agents from the card only; the implementer may add unit tests, which count only if they kill a mutant the acceptance tests did not (DS-4). Context continuity is kept the way S-14/DS-16 prescribe: one handoff schema, decisions and invariants forwarded verbatim, fixers receive the failing evidence, never the transcript. |
| **C-B** | D-10 "separate de-sloppify agent that removes framework-behaviour tests" vs S-5/DS-5 locked oracle and F-18 (test deletion is the observed failure) | **Locked oracle wins.** No agent may delete tests except the test-author role on its own non-protected tests with a `Tests-Removed:` trailer that the gate checks against `collected`. Cleanup is an advisory note from the quality reviewer, never a deletion stage. |
| **C-C** | D-5/T-9 "`isolation:'worktree'` for mutators" vs F-1 (the Workflow's cwd is the unrelated toolchain repo; `isolation:'worktree'` would worktree the WRONG repo) | **F-1 wins.** No `isolation:'worktree'` anywhere. Every mutating agent creates its own worktree with `git -C "$BUILD_REPO" worktree add "$WT_ROOT/<card>-<nonce>" -b card/<id>-<nonce> <base>`; every stage returns `repo_toplevel`, asserted equal to `args.build_repo` in JS. |
| **C-D** | S-10 (pairwise position swap + rubric-option permutation everywhere) vs DS-11 (position swap alone HURTS on adversarial/clear-cut checks, -3 to -13 pp) | **DEEP wins** (newer, larger controlled study). Refutation and verification gates use single-order forced-CoT with the verdict as a schema field; the swap-and-tie protocol is reserved for genuine A/B design comparisons (parser placement after fixture #1, persona set variants), with the permutation passed in `args.judge_perm`. |
| **C-E** | S-4 (held-out compositional tests help, SpecBench) vs EvilGenie via S-4/DS (held-out tests add little on small functions; an LLM tamper judge is effective) | **Both, because they cover different classes.** Held-out compositional tests for the cross-feature seams (tool loop × streaming × Continue; `/v1` × identity; MCP `ask/poll`; `python_eval` × operator flag × every surface); deterministic tamper scan + fresh tamper judge for small-function hacks; mutation red-proof for both. |
| **C-F** | T-19 "omit `model` everywhere" vs F-31/F-42 (a platform safeguard killed an agent reading security-tool code; retry on `model:'fable'` succeeded) | **`model:'fable'` only on the three hardening cards and their verifiers/critics**, logged on the narrator line; everywhere else the session model is inherited. Two consecutive nulls on the same card park it (`blocked:'safeguard'`), never a third identical launch. |
| **C-G** | D-23 (dry ≥ 2 AND a DoD-inversion scout that reuses no prior probe) vs T-4 (four stop conditions) | **Union: five stop conditions**, each logged: judge-satisfied · MAX_ROUNDS · dry ≥ 2 confirmed by an inversion scout that finds nothing · budget reserve · agent-count reserve (F-45). |
| **C-H** | T-16 "implementers idempotent on an existing `impl/<id>` branch" vs F-33/F-43 (branch reuse across runs + cache replay of a stale sha) | **Branch names carry `args.run_nonce`; reuse only inside one run.** A state-probe agent verifies every cached `head_sha` exists and the branch points at it before it is consumed; mismatch → `stale → rerun live`. |
| **C-I** | S-19/DS-19 "production behind a GitHub `production` environment with required reviewers" vs decision G-1a "CI is the only production writer" | **No conflict.** The environment gate is the mechanism by which the owner "explicitly approves" promotion; the workflow never triggers it and never holds a token (S-21). |
| **C-J** | DS-13 "minimal scaffolds win; more agents give diminishing returns" vs this design's angle | **Accepted cost, spent where the evidence says it pays.** The extra agents are verifiers, refuters and probes (verification diversity: execution + rubric + refuter, DS-12/13), not extra implementers or richer tool menus; implementers keep a bash+edit surface and linear history. §11 states the price. |
| **C-K** | Decision M-5 "everything in one production release" vs S-24/DS-13 "start simple" | **Decision wins.** Many staging promotions integrate incrementally; production sees one promotion; the workflow's terminal state is a promotable integration head plus a promotion request. |
| **C-L** | Decision G-15 "in-container, hardened" vs the security literature's preference for a sandbox | **Decision wins.** The hardening cards implement the six-point spec verbatim with a red-proof per point; the residual risk (open network, shared fs) is recorded in the runbook as accepted by the owner, not re-litigated by any critic (critic preamble says so). |
| **C-M** | D-28/AGENTS §9 "agents never rotate credentials" vs findings "rotate the pasted token today" | **§9 wins.** Every run's checkpoint lists the revocation under `owner_actions`; the hardening card fixes the consumer side (no `or HF_TOKEN` fallback, no token files). |
| **C-N** | research-3 S-10 "≥3 judges, strongest model" vs DS-10 "self-preference is capability-independent; cross-family when possible" | Three judges with distinct lenses always; a cross-family (Codex) judge only if `mcp__codex__codex` is reachable at GROUND (UNVERIFIED here: not mounted in this session) — degradation ladder Codex → fresh Claude `effort:'max'` with the review prompt as its only input (D-15/C-8). |

### 1.3 Where decisions override research (stated, per the brief)
G-1 (revised): Claude is the single writer — the workflow still guards against the other agent's scheduled tasks (F-38) because they may fire regardless. G-2: production stays down; nothing in any run touches it. G-3/G-13/G-14/G-16: maximal scope, vision kept → the worker keeps the VLM class, `prefill_chunk_size` is forbidden while that class is loaded (idiom lint), and the FP8 checkpoint's visual tensors are an open question (§15 Q6). G-19: personas delegated to Claude with the boundary; the persona card has no history access (F-17). M-1/M-2/M-3: hosted-first, one worker Space, curated `models.yaml` with provenance (F-25). G-1a/G-27/G-28/G-29: GitHub SSOT, CI (Trusted Publisher OIDC) only writer, staging + canary + rollback — the workflow writes and unit-tests the pipeline code and never executes it (F-35).

---

## 2. Run structure: one script, several `args.stage` runs, an owner checkpoint between runs

The script is one file. `args.stage` selects the run. Every run is resumable (`resumeFromRunId`), replayable (same script + same args), and ends by returning a typed result whose `checkpoint` object the orchestrator relays to the owner in plain words. **No run performs an outward action** (repo/Space creation, secrets, push to a remote the owner did not name, deploy, HF Job, provider spend). Authority for the next run arrives only through the owner's own launching message, which the harness relays verbatim to every agent (T-1/T-2), plus `args.owner_approvals` as DATA (F-6).

| Run | `args.stage` | Preconditions (asserted in JS or by the setup agent; failure → `blocked_on_owner`, never a guess) | Produces (durable, synced) | Checkpoint object emitted |
|---|---|---|---|---|
| **R-S** | `smoke` | Orchestrator computed `args` with `git rev-parse` (§10); `/usr/bin/python3.12` present; `args.build_repo` under `/home/codespace/build/` (durable, outside the synced grill folder and outside the cwd repo); snapshots readable | `$RUN_DIR/smoke/` with one exercised instance of EVERY schema (a trivial card on a throwaway branch), the permission-prompt inventory, and the venv build receipt | `{action:'approve-smoke', why, exact_steps:['add these allow rules', 'set Codespace idle timeout to max', 'disable HF write connectors for the build session'], …}` |
| **R0** | `plan` | R-S returned `SUCCESS`; `args.dod_hash` absent (first run) | `$RUN_DIR/plan/decisions.json` (decision sheet), `api-ledger.json`, `symbols.json` (finding → `file::symbol@base_sha`), `cards/*.json` (DAG), `heldout-plan.json` (which seams get held-out tests), `CONTRACT-HASH.txt` | `{action:'approve-plan', exact_steps:['read decisions.json against DECISION-QUEUE', 'read cards', 'reply with the contract hash to launch build'], required_owner_approvals_fields:['plan_hash']}` |
| **R1** | `build` | `args.plan_hash` equals the hash of the frozen plan files (JS recomputes from the files via a bash probe agent); `args.integration_sha_at_launch` equals the live integration head (state probe); venv healthy; gate red-proofs pass | Integration branch `integration/<runTag>` in `$BUILD_REPO`, `$RUN_DIR/bundles/checkpoint-<n>.bundle` after every merge, `$RUN_DIR/ledger.jsonl` (every stage incl. nulls), `$RUN_DIR/build/<card>/{impl,verify,refute-*,audit,critic}.md` (full artifacts), `SYNTHESIS-build.md`, `RUNBOOK.md` | `{action:'create-github-repo-and-push', exact_steps:[…private repo, push integration/<runTag> from the bundle or the checkout, configure Trusted Publisher for staging, create staging Spaces (CPU + worker) private, set the staging inference token, run the ONE metered router call → fixture #1…], blast_radius, rollback, cost_estimate}` — or `{action:'none'}` with the blocked list if not satisfied |
| **R2** | `stage` | `args.owner_approvals.github_repo_url`, `.staging_ui_space`, `.staging_worker_space`, `.staging_evidence_dir` non-null; `args.fixture1_path` present (the recorded router call); CI has written `boot.json`, `canary.json`, `logs/*.txt` into `staging_evidence_dir` (owner/CI-produced; agents never call `*.hf.space`) | Staging-verification artifacts: per staging-required claim a row `{claim, measured_value, evidence_path, verdict}`; fix cards for staging-only failures run through the same inner loop; conformance suite re-run with fixture #1 replacing the synthetic golden; `SYNTHESIS-stage.md` | `{action:'approve-hf-job-and-promotion-rehearsal', exact_steps:[quantisation/export HF Job with stated cost cap, harness run with `--i-accept-cost`, rollback drill on staging], required_owner_approvals_fields:['hf_job_budget_usd','harness_budget_usd','gpu_seconds_budget']}` |
| **R3** | `promote` | `args.owner_approvals.harness_evidence_dir` present; staging canary pass^3 recorded; Space HEAD check (read-only Hub read) shows no foreign commits since base (F-38) or the owner adopted the delta explicitly | `PROMOTION_REQUEST.md` (what/why/evidence/rollback), the final `SYNTHESIS.md` with the DoD table (two signals per row), the claim ledger, unmet-DoD list, owner runbook | `{action:'promote-production', exact_steps:['approve the GitHub production environment deployment', 'watch /status sha', 'canary ×3', 'rollback command'], …}` |

Rules that hold for every run: the trigger message must contain no secret (T-2, F-7) and must state the authority ("edit only inside `$BUILD_REPO` worktrees; never push/create/deploy/spend"); `args` are computed immediately before launch (§10); a run always ends with the synthesizer AND the synthesis verifier, even on budget exhaustion (F-45); a run never retries a `blocked_on_owner` stage (F-6).

---

## 3. Agent roles and the separation table

Every role is a distinct `agent()` call with its own label. Nothing that votes authored what it votes on (T-6, D-15). "Fresh" means the prompt contains only the card, the diff range/bundle path, the frozen contract excerpts and the previous stage's *typed* return — never a transcript or narrative (F-30). `model` is inherited except where marked (C-F).

| Role | May author code/tests? | May vote/veto? | Sees | Effort | Schema | Notes |
|---|---|---|---|---|---|---|
| `setup` (bash) | no (writes venv, `gate.sh`, `AGENTS.md`, durable libsrc copy) | no | args only | low | `SETUP` | Idempotent; refuses if `python -V` ≠ 3.12; copies wheels + sources from the volatile scratchpad to `$DURABLE/libsrc` (F-2, F-5) |
| `ground` (read-only) | no | no | snapshots, DQ, findings | high | `GROUND` | Facts with `[probe]` tags, assumption ledger, reviewer-rail probe (Codex availability), toolchain status snapshot (D-3) |
| `decision-sheet author` | no | no | DECISION-QUEUE only | high | `DECISION_SHEET` | One line per G/M id → decided value → consequences; owner approves at R0 checkpoint (F-9) |
| `api-ledger author` | no | no | `$DURABLE/libsrc` only | high | `API_LEDGER` | ~40 symbols with `libsrc/path:line`; the only source implementers may cite for gradio/spaces/transformers/hub APIs (F-8) |
| `symbolizer` | no | no | findings + base tree | medium | `SYMBOLS` | Maps every actionable finding to `file::symbol@base_sha`; UNVERIFIED findings routed to `pre-verifier` first (F-11) |
| `pre-verifier` | no (repro scripts in `$RUN_DIR/pre/`) | verdict on a finding | one UNVERIFIED finding + snapshot | medium | `VERIFY_FINDING` | Refute-first on critic-1..5 before any card cites them |
| `spec/card author` (per area ×6) | no | no | decision sheet, symbols, LENS-4 §B/§D/§F, CORRECTED lines for its area | high | `CARD_GRAPH` | Never sees raw finder recommendations (F-10) |
| `card critic` | no | veto (must_fix) | full card graph + decision sheet | xhigh | `PLAN_JUDGE` | Completeness vs LENS-4's 14 steps, DAG sanity, CPU-runnable acceptance, sizing (F-13/F-14) |
| `plan judge` ×3 lenses | no | veto only | card graph + critique | xhigh | `PLAN_JUDGE` | `ready` requires all three not-vetoing; the owner still approves (R0 checkpoint) |
| `test author` (per card) | tests only (visible acceptance + unit skeleton) on `tests/<card>` | no | card + interfaces + `api-ledger`; NOT the implementation | medium | `TESTS_WRITTEN` | Also writes `mutants.json` (≥1 scripted one-line mutant per acceptance id) |
| `heldout author` (per seam card) | tests only, on a bundle the implementer never receives | no | card graph (composition) + spec | medium | `TESTS_WRITTEN` | Compositional seams only (§4.6); committed by the integrator after the card is built |
| `red-confirmer` | no | verdict | tests bundle + base tree | medium | `RED_PROOF` | Tests must fail on the unimplemented tree for the expected reason; `collected > 0` (D-6, S-4) |
| `implementer` | code + optional extra unit tests, in its own worktree | no | card, visible tests path, api-ledger, decision sheet, `AGENTS.md` | high (`model:'fable'` on hardening cards) | `IMPL` | Commits per coherent step; runs `gate.sh`; forbidden: tests/protected paths, installs, servers in foreground, `env` dumps |
| `verifier` | no (may write repro scripts under `$RUN_DIR`) | verdict | bundle + card + tests + mutants; NOT `IMPL.notes` | medium | `VERIFY` | Re-runs `gate.sh` (digest must equal the implementer's), revert-proof, held-out tests, mutants, tamper scan, locked-path diff, claim-vs-diff, each acceptance command |
| `refuter` ×3 lenses (correctness-reproduce · security-secrets · decision-fidelity) | no | kill (majority) | the PASS claim + bundle + card | medium | `REFUTE` | Default `refuted:true` if uncertain; a refutation counts only with an executed command (DS-8/DS-9) |
| `fixer` | code, in a fresh worktree on the card branch | no | card + verbatim failing evidence + previous fingerprint | high | `FIX` | Must state `root_cause` with an evidence anchor and a `disposition`; must reproduce before editing (S-15) |
| `pivot` | no | no | two failed attempts' evidence | high | `PIVOT` | ≥2 alternatives, one chosen with reason (D-8) |
| `re-decomposer` | no (writes sub-cards) | no | card + all attempts | high | `REDECOMPOSE` | Splits once; sub-cards enter the DAG; never a 4th identical fix |
| `arbiter` | no | decision | both rationales of a re-opened finding | xhigh | `ARBITER` | Writes `accepted_risk` or `decision`; ends oscillation (F-27) |
| `auditor` | no | veto (critical/high deviations) | diff + card + decision sheet + CORRECTED texts | high | `AUDIT` | Decision fidelity, CORRECTED fidelity, scope allowlist, deps allowlist, blast-radius on deletions (D-30) |
| `critic` (completeness) | no | veto only if reproduced | diff + card + audit; NOT implementer narrative | high | `CRITIC` | Mechanical lenses first (apicheck, idiom lint, mutation red-proof, traceability), model judges the residue; `hunks_cited minItems 1` for any pass |
| `tamper judge` | no | verdict | tamper-scan hunks only | medium | `TAMPER` | Runs only when the deterministic scan flags something; fails closed if the hunk is missing (S-6) |
| `integrator` (serial) | merge commits only, on `integration/<runTag>` | no | bundle + head sha | high | `INTEGRATION` | Aborts on conflict; runs gate on merged tree; returns `cherry_unmerged`, `patch_id_missing` |
| `conflict resolver` | resolves hunks only, in a fresh worktree on integration | no | conflict hunks + both cards | xhigh | `INTEGRATION` | Then the integrator fast-forwards and re-gates |
| `integration tester` | no | verdict | integration head sha only | medium | `VERIFY` | Fresh `git clone` of the integration head; full gate + conformance + journeys J1–J6 |
| `reviewer` ×5 lenses | no | findings (not verdicts) | integration head + KNOWN ids | high | `REVIEW_FINDINGS` | New findings only; anchors `path:line@sha` |
| `judge` ×3 lenses | no | veto; `satisfied` only through the enum | blocked list, gate ledger, open findings, DoD table | xhigh | `JUDGE` | Cannot say `satisfied` while any card is blocked or any DoD row lacks two signals |
| `inversion scout` | no | findings | GOAL + DoD + list of forbidden (already used) probes | high | `REVIEW_FINDINGS` | Runs only after dry ≥ 2 (D-23) |
| `postcondition prober` (bash) | no | booleans | artifact paths | low | `POSTCONDITION` | `test -s`, JSON parse, sentinel grep, anchor count (D-12) |
| `state prober` (bash) | no | booleans | sha + branch | low | `STATE_PROBE` | `git cat-file -e`, `git rev-parse`; guards cached results (F-43) |
| `staging evidence reader` (R2) | no | verdict per claim | CI-written `boot.json`/`canary.json`/logs, read-only Hub metadata | medium | `STAGE_CLAIM` | Never calls `*.hf.space`; a missing evidence file is `unverified`, never `pass` |
| `synthesizer` | no | no | mechanical inputs only: ledger, DAG, gate ledger, `git log --stat`, skip counts | high | `SYNTH` | One row per card with an enum status; emits the checkpoint |
| `synthesis verifier` | no | rewrites rows that do not match | synthesizer output + `git log` + ledger | high | `SYNTH_VERIFY` | Second signal on the report itself (F-40) |

**Process monitor (S-25/DS-5).** In-run transcript access for a subagent is UNVERIFIED (the script does not know its own run id, so the transcript directory cannot be named in a prompt). Defensive form: the in-run monitor reads `IMPL.commands_run[]` + the deterministic tamper scan; the transcript-reading monitor runs **between runs** on the orchestrator side (which has `<transcriptDir>`) and its findings enter the next run as `args.monitor_findings[]` (data, never instruction to the implementer).

---

## 4. Task model

### 4.1 The card (PR-sized task) — schema in §9 (`CARD`)
A card is a cold-executable brief (D-1). Required fields: `id` (stable slug, e.g. `c03-thin-slice`), `title`, `area` ∈ {platform, core, backends, api, ui, tools, worker, ci, docs, eval}, `tier` ∈ {trivial, small, medium, large}, `depends_on[]`, `files_allowed[]` (exclusive ownership), `files_read[]`, `deps_allowed[]` (requirements lines it may add), `in_scope[]`, `out_of_scope[]`, `decision_ids[]` (ids from the decision sheet, whose decided VALUE is quoted into the card), `finding_ids[]` with ONLY the CORRECTED text quoted (F-10), `symbols[]` (`file::symbol@base_sha`, F-11), `acceptance[]` = `{id, check (exact command), expect (exit code / regex / JSON path), level ∈ VERIFICATION_LEVEL}`, `must_not_change[]` (Kiro "SHALL CONTINUE TO"), `journeys[]` (J-ids the card must keep green), `heldout_seams[]`, `protected_paths_touched[]` (non-empty only on the gate card), `outward_facing`, `needs_gpu`, `owner_approval_required`, `size_budget` = `{max_changed_lines: 300, max_files: 12}`. A card with an empty `acceptance[]`, an acceptance without a command, or a `level` of `staging-required` presented as locally checkable throws at script start (D-1) — the script validates the card graph in JS before any implementer is launched.

### 4.2 From the plan's 14 steps to cards
LENS-4 §D is the seed; six area authors produce cards; the card critic and three plan judges check completeness; JS validates shape, DAG acyclicity, file-ownership disjointness within a wave, and sizing. Expected split (the authors decide the final cut; the numbers are the sizing rule applied to LENS-4's own line counts):

| LENS-4 step | Cards | Why split |
|---|---|---|
| 1 repo + gate | `c01a-hygiene` (junk deletion, `.gitignore`, `.gitattributes`+`.editorconfig`), `c01b-renormalize` (pure `git add --renormalize` commit, `Renormalize-Only: yes` trailer), `c01c-gate` (ruff/pytest/claim-lint/import-contract/protected list/red-proof fixtures), `c01d-ci` (`.github/workflows/*.yml` with Trusted Publisher, `permissions:` blocks, SHA-pinned actions; unit-tested with `act`-free YAML tests, never executed) | F-21, F-22, F-28, D-9 |
| 2 lift-and-pin | `c02a-pins` (10 characterisation tests, xfails for known-bads, written by test authors before any move), `c02b-lift` (verbatim moves, `--color-moved` shows moves only) | T-23, C-3 |
| 3 thin slice | `c03-types-fake-hosted` (core/types, backends/fake, FakeEngine, HostedBackend against a recorded/synthetic fixture with `provenance`), `c03b-app-root` (composition root, `/healthz` with sha, `gr.mount_gradio_app`) | F-20 |
| 4 StreamParser | `c04-parser-events` | — |
| 5 registry/agent/session | `c05a-registry` (THE `python_eval` gate), `c05b-agent-loop`, `c05c-session` | sizing |
| 6 UI factory | `c06-ui` | — |
| 7 gateway hardening | `c07a-api-validation` (auth, size/role/range, threadpool, 429), `c07b-ledger-preflight-status` | sizing |
| 8 worker + backend | `c08a-worker-pure` (encode/lease pure modules, estimator rows at measured-or-UNVERIFIED rate), `c08b-worker-app` (import-time load, `@spaces.GPU`, Gradio endpoint; `staging-required`), `c08c-backend-worker` (gradio_client backend + fallback order, default OFF) | F-37 |
| 9 hardening | `c09a-python-eval` (env allowlist, `PR_SET_DUMPABLE`, rlimits via runner, killpg, fresh cwd, operator flag), `c09b-ssrf` (one opener, resolve-once, redirect validation, ports), `c09c-regex-calc-archive` (`regex` timeout, calculator allowlist, archive caps) | F-31/F-42 split; `model:'fable'` |
| 10 vision/video | `c10-media-parts` (video default OFF) | — |
| 11 MCP | `c11-mcp-ask-poll` | — |
| 12 eval harness | `c12-harness` (`--backend fake --dry-run` default; zero-call test) | F-36 |
| 13 catalog/personas/README | `c13a-catalog` (`models.yaml` + provenance files), `c13b-personas` (no history access; absence test protected), `c13c-readme-render` | F-17, F-24, F-25 |
| 14 promotion | `c14-promote-scripts` (`promote.py`, rollback, health job — written and unit-tested against fakes, never run) | F-35 |

≈ 24 cards. Fix cards created by review rounds are `rf<round>-<finding-id>` with `depends_on: []` and `files_allowed` = the finding's file (integration serialises them anyway).

### 4.3 DAG, waves and sizing rules
- `topoOrder()` (deps first, ties by id) and `waves(ordered, WAVE)` are pure JS (§13). A wave admits a card only if all its deps are merged AND its `files_allowed` is disjoint from every other card in the wave; a clash is not "resolved at integration" — the later card (by id) waits for the next wave (F-14, D/AP-14).
- `WAVE = args.fleet <= 2 ? 2 : Math.min(args.fleet, 6)`; at cap 2 the spine (c01→c02→c03→c04→c05) is serial anyway; at cap 14 the fan-out after c05 (c06..c14) runs in ~2 waves. Enqueue order = critical path first (T-8).
- Oversize detection is deterministic: the verifier reports `changed_lines`/`files_changed` from `git diff --numstat`; > 300 lines or > 12 files → `blocked:'oversize'` and a re-decomposer splits the card (F-13).

### 4.4 Worktree → branch → bundle/SHA lifecycle
1. Test author: `git -C $BUILD_REPO worktree add $WT_ROOT/t-<id>-<nonce> -b tests/<id>-<nonce> <base>`; commits tests; `git bundle create $RUN_DIR/bundles/tests-<id>.bundle <base>..tests/<id>-<nonce>`; returns branch/base/head/bundle/`repo_toplevel`.
2. Held-out author: same, branch `heldout/<id>-<nonce>`, bundle `$RUN_DIR/heldout/<id>.bundle` — the path is never placed in an implementer prompt.
3. Implementer: worktree on `card/<id>-<nonce>` from `<base>` with the visible tests branch merged in first (`git merge --no-ff tests/<id>-<nonce>`); commits per step; `gate.sh`; bundle `$RUN_DIR/bundles/<id>.bundle <base>..HEAD`.
4. Verifier/refuters/auditor/critic: read-only worktrees created from the bundle (`git -C $BUILD_REPO fetch <bundle> card/<id>-<nonce>` then `worktree add … <head_sha>`), removed by themselves in a `finally`.
5. Integrator: merges `card/<id>-<nonce>` into `integration/<runTag>` in `$BUILD_REPO` (the ONE writer of that branch); then `git -C $BUILD_REPO worktree remove` of the card's worktrees ONLY after `cherry_unmerged == []` (F-33); checkpoint bundle `$RUN_DIR/bundles/checkpoint-<n>.bundle <base>..integration/<runTag>` (size asserted ≤ 20 MB so the grill-folder sync stays sane; larger → `blocked:'bundle-too-large'` and the runbook tells the owner to push from the checkout).
6. Branch and worktree names carry `args.run_nonce`; a P0 cleanup step bundles then prunes stale worktrees of a previous run.

### 4.5 Integration order, conflict resolution, integration test
- Strictly topological order, ties by id, serial, single writer (T-10/T-11). `git merge --no-ff <head_sha>`; on ANY conflict `git merge --abort` and return `status:'conflict'` with the hunks; the conflict resolver (fresh worktree on the integration head) resolves only those hunks so that BOTH cards' acceptance still holds, runs `gate.sh`, bundles; the integrator fast-forwards and re-gates.
- After every merge: `gate.sh` on the merged tree (F-34) + deterministic `tools/no_lost_hunks.sh` (`git cherry` + `git patch-id` set difference) → `cherry_unmerged` and `patch_id_missing` must be empty (F-32). Red merged tree → one fix agent scoped to `integration` with both cards; unresolved after 2 rounds → `git revert -m 1` of the later card, card `blocked:'reverted-at-integration'`.
- After every wave: the integration tester clones the integration head into a fresh directory (`git clone --branch integration/<runTag> $BUILD_REPO $TMP/clone-<n>`), runs the full gate, the conformance suite parametrised over `{fake, recorded-hosted(skipped: needs owner recording), recorded-worker(skipped)}` and journeys J1–J6; its ledger digest is the wave's verdict (T-12). A red wave stops further waves; remaining cards are `blocked:'gate-red-upstream'`.

### 4.6 Held-out compositional seams (authored from the spec, hidden from implementers)
H1 tool loop × streaming × Continue (turn 2 contains turn 1's tool results; `finish_reason:'length'` → Continue resumes at token level); H2 `/v1` × identity (`x-ip-token` bound inside the generator body; 429 on the non-blocking semaphore); H3 MCP `ask → poll → status → preflight` with `chat` hidden; H4 `python_eval` × operator flag × every surface (UI checkbox alone cannot enable it; unreachable over `/v1` and MCP); H5 catalog admission × `models.yaml` schema × harness zero-call; H6 session isolation × TTL sweep × no rmtree on unload; H7 error taxonomy (quota/illegal-duration/abort) → titled notice in UI, `{"error":…}` event on `/v1`, partial text kept. Each is applied by the verifier and by the integration tester exactly like SWE-bench applies gold tests (checkout of the oracle paths from the held-out bundle before `pytest`).

---

## 5. Inner loop per card — exact counters and exit conditions

Constants (from `args`, with defaults): `MAX_FIX = 3` (verify→fix attempts), `MAX_AUDIT_FIX = 2`, `MAX_CRITIC_FIX = 1`, `MAX_NULL_RETRY = 1` (one narrower retry; then park), `MAX_REDECOMPOSE = 1` per card, `MAX_TAMPER = 1` (one tamper finding → fixer; a second → `blocked:'tamper'`). Every counter is per card and lives in the returned result object (replay-safe: derived from results, not closures).

```
S0  state probe          base sha exists; branch names free                                → else blocked:'stale-base'
S1  test author  ‖ heldout author        (parallel thunks under settle(); both fresh)
S2  red-confirmer        tests fail on base for the expected reason; collected>0          → else back to S1 once (fresh author), then blocked:'no-red'
S3  implementer          worktree, commits ≥1, gate.sh digest, dod[] with exit codes       → null ⇒ retry once (narrower, model per C-F) ⇒ blocked:'impl-null'
S4  verifier             re-run gate (digest equality), revert-proof, held-out, mutants,
                         tamper scan, locked-path diff, claim-vs-diff, acceptance re-run   → pass | fail(evidence) | unverifiable
S5  fix loop             attempt a=1..MAX_FIX; fingerprint fp(a) = fnv(sorted failing ids + first error line)
                           a==2 && fp(2)==fp(1)  → pivot agent → fixer with chosen alternative
                           a==3 && still failing → re-decomposer (once) → sub-cards into DAG, card closed as 'split'
                           P2P regression detected by verifier → fixer prompt begins with `git revert <fix_sha>`
                           tamper flagged → tamper judge → if confirmed: fixer (counts as a strike) / second time blocked:'tamper'
S6  refuter panel ×3     each must cite an executed command; majority refuted ⇒ back to S5 with the refutation as evidence
                         (a refuter-triggered fix consumes a MAX_FIX attempt; refuters re-run after every fix)
S7  auditor              deviations critical/high or claim_vs_diff non-empty or scope violation ⇒ fixer (a ≤ MAX_AUDIT_FIX) then verifier again
S8  critic               blocking (critical/high AND reproduced) ⇒ ONE fix pass ⇒ verifier again; residue → review round input
S9  postcondition probe  artifacts exist, sentinel, anchors; state probe of head_sha
S10 unitDone()           the ONLY exit to 'built'; else typed blocked with reason enum
```

Exit conditions (typed, never silent): `built` (all 12 predicate conditions true) · `blocked` with `reason ∈ {stale-base, no-red, impl-null, safeguard, oversize, fix-exhausted, tamper, audit-exhausted, critic-fix-failed, reverify-failed, unverifiable, budget, agent-cap, chain-threw}` · `split` (re-decomposed; sub-card ids listed). Each transition is `log()`ged with the reason and the attempt counters.

The 12-condition `unitDone()` predicate (D-12; one shared JS reducer, §13): (1) bundle artifact exists and is non-empty (postcondition probe); (2) `head_sha` resolvable and branch points at it (state probe); (3) every stage returned `repo_toplevel === args.build_repo`; (4) `impl.gate_digest === verify.gate_digest` — two independent executions of `gate.sh` on the same sha produced the same deterministic digest; (5) gate ledger `head_sha === impl.head_sha`, all step exit codes 0, `pytest.collected ≥ baseline − tests_removed`; (6) every acceptance id has `exit_code 0` in `impl.dod` AND in `verify.acceptance_reruns`; (7) `red_proof.failed_for_expected_reason && verify.revert_proof.failed_when_reverted`; (8) `verify.mutants.killed ≥ verify.mutants.total` (every scripted mutant killed) AND `tamper.signals == 0` (or tamper judge cleared) AND `locked_paths_diff == []`; (9) held-out tests `passed` (or the card declares no seams); (10) refuter majority `refuted:false`, each survivor citing an executed command; (11) audit: no open critical/high deviation, `claim_vs_diff == []`, `scope_violations == []`; (12) no open reproduced blocking critic finding; `outward_actions_taken` and `installed_packages` empty on every stage. The narrator line prints the 12 booleans (`1✓2✓…8✗`) so a partial predicate is visible.

---

## 6. Outer loop per wave and for the whole tree

Per wave (after serial integration): `integration tester` (fresh clone, full gate + conformance + journeys) → 5 reviewers (lenses: correctness · security-and-secrets · zerogpu-quota-and-cost · api-contract · tests-gate-and-claims) with `KNOWN` = sorted `seen` keys → dedup in JS (`fkey = file + '::' + normalised title`, vs `seen`, never vs `confirmed`; T/AP-5) → each fresh finding to 3 refuters (default refuted; executed evidence required) → survivors (≥2 of 3 not refuted) become `rf<round>-<id>` cards through the SAME inner loop and serial integration → judge panel ×3 (veto-only). Per-wave `MAX_WAVE_ROUNDS = 2`.

For the whole tree (after the last wave): the same round with `MAX_TREE_ROUNDS = 4`. Stop conditions, evaluated in this order and each logged: (a) `verdict === 'satisfied'` — requires 3/3 judges not vetoing (not a majority: reliability-first), zero blocked cards, fresh-clone gate green, zero open reproduced blocking findings, every DoD row with two mechanically independent signals; (b) `round ≥ MAX_TREE_ROUNDS`; (c) `dry ≥ 2` where a round is dry iff it confirmed 0 findings AND changed 0 fingerprints — then ONE inversion scout runs with the list of every probe already used (forbidden to reuse); only if it returns 0 reproduced findings does the loop close as `converged`; (d) budget reserve: `budget.total && budget.remaining() < Math.max(RESERVE, 0.15 * budget.total)`; (e) agent-count reserve: `agentCount > 800` (lifetime cap 1000). A judge verdict `blocked-needs-owner` ends the loop immediately with the owner list. Judge dissent is logged verbatim; a 2/3 "satisfied" is recorded as `not-satisfied` with the dissent as the next round's first item (D-24/C-2).

Overclaim termination (D-17): a finding of kind `overclaim` whose fixer disposition is `sentence_rewritten` with a scoped residual is closed, not re-opened; a `pushed_back` disposition goes to a resolver that reads both probes and names the winning probe (never averages); a finding id re-opened after a close goes to the arbiter (F-27).

---

## 7. Deterministic gates — `gate.sh` and where each runs

`gate.sh` lives at `$DURABLE/gate.sh` (installed by `setup`, copied into the repo by card `c01c` as `tools/gate.sh`, listed in `tests/protected.txt`). It runs ONLY under the 3.12 venv, records every step, never stops at the first failure (so the ledger is complete), writes `.gate/last_run.json` (with a UTC timestamp) and `.gate/last_run.digest` (sha256 over the timestamp-free canonical part — two independent runs on the same sha must produce the same digest, which is condition 4 of `unitDone()`), and exits non-zero if any blocking step failed. Warnings (idiom lint) are recorded and must be cleared by a named reviewer in the card's audit.

```bash
#!/usr/bin/env bash
# gate.sh — the only admissible evidence of verification (red-team §3, D-9, D-14, F-12, F-28).
# Usage: gate.sh --tree <path> --base <sha> --mode worktree|merged|clean [--oracle <ref>] [--baseline <n>]
set -u
TREE=""; BASE=""; MODE="worktree"; ORACLE=""; BASELINE=""
while [ $# -gt 0 ]; do case "$1" in
  --tree) TREE="$2"; shift 2;; --base) BASE="$2"; shift 2;; --mode) MODE="$2"; shift 2;;
  --oracle) ORACLE="$2"; shift 2;; --baseline) BASELINE="$2"; shift 2;; *) echo "unknown arg $1"; exit 64;; esac; done
VENV="${VENV:?VENV required}"; PY="$VENV/bin/python"
[ -d "$TREE/.git" ] || [ -f "$TREE/.git" ] || { echo "not a git tree: $TREE"; exit 65; }
case "$("$PY" -V 2>&1)" in "Python 3.12."*) ;; *) echo "REFUSED: gate requires the 3.12 venv, got $("$PY" -V)"; exit 66;; esac
HEAD_SHA="$(git -C "$TREE" rev-parse HEAD)"; mkdir -p "$TREE/.gate"; STEPS=(); FAIL=0; WARN=0
step() { # name, blocking(1|0), cmd...
  local name="$1" blocking="$2"; shift 2; local out rc
  out="$("$@" 2>&1)"; rc=$?
  printf '%s\n' "$out" > "$TREE/.gate/step-$name.log"
  STEPS+=("{\"name\":\"$name\",\"exit_code\":$rc,\"blocking\":$blocking,\"summary\":$(printf '%s' "$out" | tail -n 5 | "$PY" -c 'import json,sys;print(json.dumps(sys.stdin.read()))')}")
  if [ "$rc" -ne 0 ]; then if [ "$blocking" = 1 ]; then FAIL=1; else WARN=1; fi; fi
  echo "gate: $name exit=$rc"
}
# 0. pre-step: stray listeners from this build root, stale index.lock (F-26, F-42)
step prestep 1 bash -c '
  for p in $(ss -ltnp 2>/dev/null | grep -o "pid=[0-9]*" | cut -d= -f2 | sort -u); do
    if tr "\0" " " < /proc/$p/cmdline 2>/dev/null | grep -q "'"$(dirname "$TREE")"'"; then kill "$p" 2>/dev/null && echo "killed stray listener $p"; fi; done
  f="'"$TREE"'/.git/index.lock"; if [ -f "$f" ] && [ $(( $(date +%s) - $(stat -c %Y "$f") )) -gt 600 ]; then rm -f "$f"; echo "removed stale index.lock"; fi; true'
# 1. hygiene: line endings, LFS, blob cap, forbidden paths (F-21, F-22)
step eol 1 bash -c 'cd "'"$TREE"'" && ! git ls-files --eol | grep -E "w/crlf|w/mixed|i/crlf"'
step lfs 1 bash -c 'cd "'"$TREE"'" && [ -z "$(git lfs ls-files 2>/dev/null)" ]'
step blobcap 1 bash -c 'cd "'"$TREE"'" && ! git rev-list --objects "'"$BASE"'"..HEAD | git cat-file --batch-check="%(objecttype) %(objectsize) %(rest)" | awk "\$1==\"blob\" && \$2>5242880 {print; f=1} END {exit f}"'
step junk 1 bash -c 'cd "'"$TREE"'" && ! git ls-files | grep -E "(^|/)__pycache__/|\.pyc$|(^|/)\.venv/|\.whl$|\.log$|^idx\.json$|^runlog_tail\.txt$"'
# 2. undefined names, syntax, target version (F-19, F-23)
step ruff 1 "$VENV/bin/ruff" check --select F821,F811,F401,E9 --target-version py312 "$TREE"
step compileall 1 "$PY" -m compileall -q "$TREE"
# 3. locked oracle: reset protected/locked paths to the oracle ref, then any diff there is a violation (S-5, F-18, F-28)
if [ -n "$ORACLE" ]; then
  step locked-paths 1 bash -c 'cd "'"$TREE"'" && violations=$(git diff --name-only "'"$BASE"'"..HEAD -- $(cat tests/protected.txt 2>/dev/null) tests/acceptance conftest.py pytest.ini ruff.toml .github tools/gate.sh tools/claim_lint.py tools/tamper_scan.py 2>/dev/null); [ -z "$violations" ] || { echo "locked paths modified:"; echo "$violations"; exit 1; }; git checkout "'"$ORACLE"'" -- tests/acceptance 2>/dev/null || true'
fi
# 4. apicheck: every apis_used entry resolves in the pinned wheels with its kwargs (F-8)
step apicheck 1 "$PY" "$TREE/tools/apicheck.py" --tree "$TREE" --ledger "$TREE/plan/api-ledger.json"
# 5. tamper scan: assertion loss, skips, loosened matchers, swallowed errors, pytest-detection idioms, -k/--deselect in commands (S-6, F-18)
step tamper 1 "$PY" "$TREE/tools/tamper_scan.py" --tree "$TREE" --base "$BASE" --baseline "${BASELINE:-0}"
# 6. tests, twice, offline, only exit 0 is green; counts recorded (F-12, F-29)
run_pytest() { cd "$TREE" && "$PY" -m pytest -q -p no:cacheprovider --disable-socket --allow-hosts=127.0.0.1 -o junit_family=xunit2 --junitxml="$TREE/.gate/junit-$1.xml" 2>&1; }
step pytest-1 1 bash -c 'run_pytest 1'; step pytest-2 1 bash -c 'run_pytest 2'
step pytest-identical 1 bash -c 'cd "'"$TREE"'/.gate" && "'"$PY"'" - <<EOF
import xml.etree.ElementTree as E,json,sys
def counts(p):
    r=E.parse(p).getroot(); s=r if r.tag=="testsuite" else r[0]
    return {k:int(s.get(k,0)) for k in ("tests","failures","errors","skipped")}
a,b=counts("junit-1.xml"),counts("junit-2.xml"); json.dump({"run1":a,"run2":b},open("pytest-counts.json","w"))
sys.exit(0 if a==b and a["tests"]>0 and a["failures"]==0 and a["errors"]==0 else 1)
EOF'
step collected-floor 1 bash -c '"'"$PY"'" -c "
import json,subprocess,sys; c=json.load(open(\"'"$TREE"'/.gate/pytest-counts.json\"))[\"run1\"][\"tests\"]
base=int(\"'"${BASELINE:-0}"'\"); removed=subprocess.run([\"git\",\"-C\",\"'"$TREE"'\",\"log\",\"--format=%B\",\"'"$BASE"'..HEAD\"],capture_output=True,text=True).stdout.count(\"Tests-Removed:\")
sys.exit(0 if c >= base - removed else 1)"'
# 7. import smoke without the platform: CPU front must not load models; worker importable with stubs; import contract (LENS-4 §B rule)
step import-smoke 1 bash -c 'cd "'"$TREE"'" && env -u SPACES_ZERO_GPU QWEN_STUB=1 timeout 60 "'"$PY"'" -c "import app" && env -u SPACES_ZERO_GPU timeout 60 "'"$PY"'" -c "import worker.app" '
step import-contract 1 bash -c 'cd "'"$TREE"'" && "'"$PY"'" -m pytest -q -p no:cacheprovider tests/test_import_contract.py'
# 8. claims vs diff over every commit in the range (G-29, F-19, F-24)
step claim-lint 1 "$PY" "$TREE/tools/claim_lint.py" --tree "$TREE" --range "$BASE..HEAD"
# 9. idiom lint (warnings the named reviewer must clear) (F-10)
step idiom-lint 0 "$PY" "$TREE/tools/idiom_lint.py" --tree "$TREE" --range "$BASE..HEAD"
# 10. generated README, constants pin, persona absence, catalog schema + provenance files (F-17, F-24, F-25)
step readme-check 1 "$PY" "$TREE/tools/render_readme.py" --check
step protected-tests 1 bash -c 'cd "'"$TREE"'" && "'"$PY"'" -m pytest -q -p no:cacheprovider tests/test_constants_pin.py tests/test_personas_absence.py tests/test_catalog_schema.py'
# 11. secrets regex over the range (F-7); gitleaks if present
step secrets 1 bash -c 'cd "'"$TREE"'" && if command -v gitleaks >/dev/null; then gitleaks detect --no-banner --log-opts="'"$BASE"'..HEAD"; else ! git diff "'"$BASE"'"..HEAD | grep -E "ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,}"; fi'
# 12. red-proofs of the gate itself, only in merged/clean mode (D-14, F-28): RED on the f88b120 fixture and on the false-claim fixture, GREEN on the cleaned base
if [ "$MODE" != "worktree" ]; then step redproof 1 bash -c '"'"$TREE"'/tools/gate_redproof.sh" "'"$TREE"'"'; fi
# ledger + digest
PYV="$("$PY" -V 2>&1)"; NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; COUNTS="$(cat "$TREE/.gate/pytest-counts.json" 2>/dev/null || echo '{}')"
printf '{"head_sha":"%s","base_sha":"%s","mode":"%s","python":"%s","started_at":"%s","steps":[%s],"pytest":%s,"fail":%s,"warn":%s}\n' \
  "$HEAD_SHA" "$BASE" "$MODE" "$PYV" "$NOW" "$(IFS=,; echo "${STEPS[*]}")" "$COUNTS" "$FAIL" "$WARN" > "$TREE/.gate/last_run.json"
"$PY" - "$TREE/.gate/last_run.json" <<'EOF' > "$TREE/.gate/last_run.digest"
import json,sys,hashlib
d=json.load(open(sys.argv[1])); canon={k:d[k] for k in ("head_sha","base_sha","mode","python","pytest","fail","warn")}
canon["steps"]=[{"name":s["name"],"exit_code":s["exit_code"]} for s in d["steps"]]
print(hashlib.sha256(json.dumps(canon,sort_keys=True,separators=(",",":")).encode()).hexdigest())
EOF
echo "gate: head=$HEAD_SHA fail=$FAIL warn=$WARN digest=$(cat "$TREE/.gate/last_run.digest")"
exit $FAIL
```

Contracts of the tools the gate calls (all deliverables of card `c01c`, each shipped with a both-states fixture under `tests/gate_fixtures/{broken,fixed}/` and a self-test that fails if a detector is silent in both states, D-14): `tools/apicheck.py` (imports each `apis_used` symbol from the pinned wheels; every kwarg must be in `inspect.signature(...).parameters` or, for generate kwargs, in `GenerationConfig().__dict__`; unknown symbol → non-zero); `tools/tamper_scan.py` (per test file Δ assert count, new `skip|xfail|skipif`, `approx` widening, `is not None` replacing equality, `except Exception: pass|return`, `sys.exit(0)`, `PYTEST_CURRENT_TEST`/`sys.modules.get("pytest")` in non-test modules, `-k/--deselect/--ignore/-x` in any recorded command, `conftest.py` edits, deleted test files, collected-count drop without trailer → JSON report + non-zero); `tools/claim_lint.py` (every path/symbol/number/"N tests" in a commit message must appear in the whitespace-insensitive diff; `Renormalize-Only: yes` and one `Claim-Waiver: <reviewer>` trailer per card allowed; fails 5 of the 6 known over-claiming commits, the 6th via the constants pin); `tools/idiom_lint.py` (`preexec_fn=`, `__wrapped__`, `shutil.rmtree` inside an unload handler, `prefill_chunk_size` while `AutoModelForImageTextToText`, `lease_s - 30`, `max_retries` default in an `openai` client, `trust_remote_code=True`); `tools/render_readme.py --check` (model table from `models.yaml`, tool count from the registry, test count from `pytest --collect-only`); `tools/gate_redproof.sh` (worktree of the `f88b120` fixture must make `ruff` red; the false-claim fixture commit must make `claim-lint` red; the cleaned base must be green — results recorded into the ledger); `tools/no_lost_hunks.sh` (integration).

**Where each gate runs.**

| Location | Who | Mode | What is added |
|---|---|---|---|
| In-worktree, pre-merge | implementer (L0/L1 after each step; full before returning) then the **verifier** independently on a worktree built from the bundle | `--mode worktree --oracle tests/<id>-<nonce>` | verifier adds revert-proof, held-out tests (from the held-out bundle), `mutants.json` execution, acceptance re-runs; digest equality is asserted in JS |
| On the merged tree | integrator after every merge | `--mode merged` | `no_lost_hunks.sh`; a red merged tree → integration fixer (≤2) → revert |
| From a clean checkout | integration tester after every wave; the R1 final judge input | `--mode clean` (fresh `git clone`) | conformance suite (3 backends, skips counted), journeys J1–J6, red-proofs of the gate itself, `verification_level` aggregation |
| Pre-flight (P0) | setup agent | `--mode clean` on the cleaned base | proves the gate is RED on `f88b120` and GREEN on the base before any card is launched (D-9) |

---

## 8. Testability table and how staging/promotion requests are represented

| Level | Proven locally (3.12 venv, no GPU, no tokens, `--disable-socket`) | Requires the staging Space(s) | Requires the owner |
|---|---|---|---|
| Static | ruff F821/F811/F401/E9 (py312), compileall, claim-vs-diff, tamper scan, idiom lint, EOL/LFS/blob/junk, secrets regex, import contract, apicheck against pinned wheels, README render check, catalog schema + provenance file existence, persona absence test, constants pin | — | — |
| Unit / stub engine | the 73 baseline tests (persona-archive test made repo-local), 10 characterisation pins, `FakeEngine`/`backends/fake`, StreamParser golden + property tests (`hypothesis`, `derandomize=True`), tool_parse fixes, SSRF opener (recorder handlers, no sockets), regex/calculator timeouts, archive caps, `python_eval` red-proofs with a canary env var (allowlist, `/proc/<ppid>/environ` EACCES after `PR_SET_DUMPABLE=0`, rlimits trip, killpg leaves no orphan, flag off on every surface), session TTL sweep, harness `--dry-run` zero-call test, `models.yaml` schema, promotion scripts against fakes | — | — |
| Local integration (journeys J1–J6) | J1 `QWEN_STUB=1` boot serves UI + `/healthz{git_sha}` in < 10 s on a free port; J2 turn 2 contains turn 1's tool transcript; J3 two sessions → different benches; J4 `/v1` streams, `finish_reason:'length'` on truncation, `{"error":…}` event mid-stream, stops on disconnect (watcher), 429 when busy; J5 MCP schema lists only `ask/poll/status/preflight`; J6 `python_eval` unreachable over `/v1` and MCP and inert without the operator flag. Also `gradio_client==2.6.1` against a local server with `/healthz` sha equality (F-26); worker `encode`/`lease` pure modules (estimator rows, `max_time` arithmetic, resume encode with `continue_final_message="reasoning_content"`) | — | — |
| Platform behaviour (`staging-required`) | nothing (`spaces.GPU` is a no-op off-platform) | CPU Space boot + `/healthz` sha == pushed sha; worker import-time load under CUDA emulation; lease sizing, cold-start margin, measured tok/s and prefill rate; quota bucket of `gradio_client` calls with the scoped token (quota before/after one 16-token call); fla/Triton inside the forked worker; FP8 (with visual tensors, Q6) vs GPTQ on `large`; requirements resolution on rebuild; MCP over HTTP with a real client; canary pass^3; rollback rehearsal (redeploy last-known-good sha) | the owner creates the Spaces and the scoped token; CI (Trusted Publisher) deploys |
| Money / identity (`owner-required`) | nothing | — | ONE metered streamed router call (tool + thinking on) → fixture #1 and the parser-placement decision; the real 12-prompt harness under `--i-accept-cost`; the quantisation/export HF Job; GitHub repo + OIDC publishers + `production` environment; secrets; revoking the pasted token and the other agent's token; disabling its Windows scheduled tasks; Dev Mode off; production promotion |

**Representation.** Every acceptance criterion and every claim carries `level ∈ {local-mechanical, local-stub, staging-required, owner-required, unverified}` (F-37); a keyword list (lease, quota, ZeroGPU, worker fork, Triton, `x-ip-token`, MCP transport, Space rebuild, tok/s, cold start) forces ≥ `staging-required` in JS regardless of what an agent wrote. Staging and promotion needs are `checkpoint` objects (§9 `SYNTH.checkpoint`) rendered into `$RUN_DIR/RUNBOOK.md` (one numbered step per staging-required claim: the exact measurement, the number to record, the file CI must write) and `PROMOTION_REQUEST.md` (what/why/evidence/rollback). The owner's answers come back as `args.owner_approvals` fields (data) and as CI-written evidence files under `args.staging_evidence_dir`; the R2 evidence reader marks any missing file `unverified`.

---

## 9. Schemas for every stage (JSON Schema; root object; `required ⊆ properties`; enum verdicts; `sha` wherever code was read)

Design rules (T-18, D/AP-9, F-46): small objects (paths, shas, enums, counts, short strings ≤ 2 k chars), `minItems` on evidence arrays, no blobs (full artifacts go to disk, D-11), and the script re-validates semantics in JS (`done === every dod exit_code 0`, `pass` with empty evidence → `unverified`). A shared **envelope** is merged into every stage schema so the JS assertions are uniform (red-team §2 invariant 3).

```js
// ---- shared envelope (merged into every stage schema) ----
const VERIFICATION_LEVEL = ['local-mechanical', 'local-stub', 'staging-required', 'owner-required', 'unverified']
const SEV = ['critical', 'high', 'medium', 'low']
const CMD = { type: 'object', properties: { command: { type: 'string' }, cwd: { type: 'string' }, exit_code: { type: 'integer' }, output_tail: { type: 'string', description: '≤ 40 lines, verbatim' } }, required: ['command', 'exit_code', 'output_tail'] }
const ANCHOR = { type: 'string', pattern: '^[^:]+:[0-9]+@[0-9a-f]{7,40}$', description: 'path:line@sha' }
const ENVELOPE_PROPS = {
  status: { type: 'string', enum: ['SUCCESS', 'FAILED', 'BLOCKED_ON_OWNER'] },
  id: { type: 'string' }, reason: { type: 'string', description: 'required when status != SUCCESS (enforced in JS)' },
  repo_toplevel: { type: 'string', description: 'git rev-parse --show-toplevel of the tree you touched or read; "" if none' },
  outward_actions_taken: { type: 'array', items: { type: 'string' }, description: 'MUST be empty; any entry aborts the run' },
  installed_packages: { type: 'array', items: { type: 'string' }, description: 'MUST be empty' },
  commands_run: { type: 'array', items: CMD },
  artifacts: { type: 'array', items: { type: 'object', properties: { path: { type: 'string' }, bytes: { type: 'integer' }, sha256: { type: 'string' } }, required: ['path', 'bytes', 'sha256'] } },
  unverified_claims: { type: 'array', items: { type: 'string' } },
  terminal: { type: 'string', pattern: '^(SUCCESS|FAILED|BLOCKED_ON_OWNER):' },
}
const ENVELOPE_REQ = ['status', 'id', 'repo_toplevel', 'outward_actions_taken', 'installed_packages', 'commands_run', 'artifacts', 'terminal']
const env = (props, req) => ({ type: 'object', properties: Object.assign({}, ENVELOPE_PROPS, props), required: ENVELOPE_REQ.concat(req) })

// ---- P0 / plan ----
const SETUP = env({ venv: { type: 'string' }, python_version: { type: 'string', pattern: '^3\\.12\\.' }, gate_sh: { type: 'string' }, libsrc_durable: { type: 'string' },
  wheels_installed: { type: 'array', items: { type: 'string' } }, base_sha: { type: 'string', pattern: '^[0-9a-f]{40}$' }, baseline_collected: { type: 'integer' },
  redproof: { type: 'object', properties: { red_on_broken: { type: 'boolean' }, green_on_base: { type: 'boolean' }, ledger_digest: { type: 'string' } }, required: ['red_on_broken', 'green_on_base', 'ledger_digest'] } },
  ['venv', 'python_version', 'gate_sh', 'libsrc_durable', 'base_sha', 'baseline_collected', 'redproof'])
const GROUND = env({ base_sha: { type: 'string' }, facts: { type: 'array', items: { type: 'object', properties: { claim: { type: 'string' }, probe: { type: 'string' }, ts: { type: 'string' } }, required: ['claim', 'probe', 'ts'] } },
  assumptions: { type: 'array', items: { type: 'object', properties: { text: { type: 'string' }, confidence: { type: 'string', enum: ['high', 'medium', 'low'] }, load_bearing: { type: 'boolean' } }, required: ['text', 'confidence', 'load_bearing'] } },
  codex_rail_available: { type: 'boolean' }, toolchain_status_snapshot: { type: 'string' }, grounding_pack_path: { type: 'string' } },
  ['base_sha', 'facts', 'assumptions', 'codex_rail_available', 'toolchain_status_snapshot', 'grounding_pack_path'])
const DECISION_SHEET = env({ sheet_path: { type: 'string' }, rows: { type: 'array', minItems: 20, items: { type: 'object', properties: { id: { type: 'string' }, decided_value: { type: 'string' }, against_recommendation: { type: 'boolean' }, consequences: { type: 'string' }, dq_line: { type: 'integer' } }, required: ['id', 'decided_value', 'against_recommendation', 'consequences', 'dq_line'] } } }, ['sheet_path', 'rows'])
const API_LEDGER = env({ ledger_path: { type: 'string' }, symbols: { type: 'array', minItems: 30, items: { type: 'object', properties: { module: { type: 'string' }, symbol: { type: 'string' }, kwargs: { type: 'array', items: { type: 'string' } }, libsrc_anchor: { type: 'string' }, trap: { type: 'string' } }, required: ['module', 'symbol', 'kwargs', 'libsrc_anchor'] } } }, ['ledger_path', 'symbols'])
const SYMBOLS = env({ base_sha: { type: 'string' }, map: { type: 'array', items: { type: 'object', properties: { finding_id: { type: 'string' }, symbol: { type: 'string', description: 'file::function' }, anchor: ANCHOR, verdict_at_snapshot: { type: 'string', enum: ['confirmed', 'partially-confirmed', 'UNVERIFIED', 'refuted'] } }, required: ['finding_id', 'symbol', 'anchor', 'verdict_at_snapshot'] } } }, ['base_sha', 'map'])
const VERIFY_FINDING = env({ finding_id: { type: 'string' }, verdict: { type: 'string', enum: ['CONFIRMED', 'REFUTED', 'UNVERIFIED'] }, source_probe: { type: 'object', properties: { tool: { type: 'string' }, engine: { type: 'string' }, shell: { type: 'string' }, field: { type: 'string' } }, required: ['tool', 'engine', 'shell', 'field'] },
  verify_probe: { type: 'object', properties: { tool: { type: 'string' }, engine: { type: 'string' }, shell: { type: 'string' }, field: { type: 'string' }, command: { type: 'string' } }, required: ['tool', 'engine', 'shell', 'field', 'command'] }, evidence: { type: 'array', minItems: 1, items: CMD }, corrected_claim: { type: 'string' }, sha: { type: 'string' } },
  ['finding_id', 'verdict', 'source_probe', 'verify_probe', 'evidence', 'corrected_claim', 'sha'])
const CARD = { type: 'object', properties: {
  id: { type: 'string', pattern: '^(c[0-9]{2}[a-z]?|rf[0-9]+)-[a-z0-9-]+$' }, title: { type: 'string' }, area: { type: 'string', enum: ['platform', 'core', 'backends', 'api', 'ui', 'tools', 'worker', 'ci', 'docs', 'eval'] },
  tier: { type: 'string', enum: ['trivial', 'small', 'medium', 'large'] }, depends_on: { type: 'array', items: { type: 'string' } }, files_allowed: { type: 'array', minItems: 1, items: { type: 'string' } }, files_read: { type: 'array', items: { type: 'string' } },
  deps_allowed: { type: 'array', items: { type: 'string' } }, in_scope: { type: 'array', minItems: 1, items: { type: 'string' } }, out_of_scope: { type: 'array', items: { type: 'string' } },
  decision_ids: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, decided_value: { type: 'string' } }, required: ['id', 'decided_value'] } },
  finding_ids: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, corrected_text: { type: 'string' } }, required: ['id', 'corrected_text'] } },
  symbols: { type: 'array', items: { type: 'string' } },
  acceptance: { type: 'array', minItems: 1, items: { type: 'object', properties: { id: { type: 'string' }, check: { type: 'string' }, expect: { type: 'string' }, level: { type: 'string', enum: VERIFICATION_LEVEL } }, required: ['id', 'check', 'expect', 'level'] } },
  must_not_change: { type: 'array', items: { type: 'string' } }, journeys: { type: 'array', items: { type: 'string' } }, heldout_seams: { type: 'array', items: { type: 'string' } },
  protected_paths_touched: { type: 'array', items: { type: 'string' } }, outward_facing: { type: 'boolean' }, needs_gpu: { type: 'boolean' }, owner_approval_required: { type: 'boolean' },
  size_budget: { type: 'object', properties: { max_changed_lines: { type: 'integer' }, max_files: { type: 'integer' } }, required: ['max_changed_lines', 'max_files'] } },
  required: ['id', 'title', 'area', 'tier', 'depends_on', 'files_allowed', 'in_scope', 'decision_ids', 'finding_ids', 'acceptance', 'must_not_change', 'journeys', 'heldout_seams', 'protected_paths_touched', 'outward_facing', 'needs_gpu', 'owner_approval_required', 'size_budget'] }
const CARD_GRAPH = env({ cards: { type: 'array', minItems: 1, items: CARD }, coverage_notes: { type: 'string' }, unmapped_finding_ids: { type: 'array', items: { type: 'string' } } }, ['cards', 'coverage_notes', 'unmapped_finding_ids'])
const PLAN_JUDGE = env({ verdict: { type: 'string', enum: ['ready', 'not-ready', 'blocked-needs-owner'] }, must_fix: { type: 'array', items: { type: 'object', properties: { card_id: { type: 'string' }, what: { type: 'string' }, evidence: { type: 'string' }, severity: { type: 'string', enum: SEV } }, required: ['card_id', 'what', 'evidence', 'severity'] } }, plan_hash_seen: { type: 'string' } }, ['verdict', 'must_fix', 'plan_hash_seen'])

// ---- build: tests ----
const TESTS_WRITTEN = env({ card_id: { type: 'string' }, branch: { type: 'string' }, base_sha: { type: 'string' }, head_sha: { type: 'string' }, bundle_path: { type: 'string' },
  test_paths: { type: 'array', minItems: 1, items: { type: 'string' } }, command: { type: 'string' }, acceptance_ids_covered: { type: 'array', minItems: 1, items: { type: 'string' } },
  mutants_path: { type: 'string', description: 'mutants.json: ≥1 scripted one-line mutant per acceptance id' }, properties_written: { type: 'array', items: { type: 'string' } }, known_bads_xfail: { type: 'array', items: { type: 'string' } } },
  ['card_id', 'branch', 'base_sha', 'head_sha', 'bundle_path', 'test_paths', 'command', 'acceptance_ids_covered', 'mutants_path'])
const RED_PROOF = env({ card_id: { type: 'string' }, tests_head_sha: { type: 'string' }, base_sha: { type: 'string' }, collected: { type: 'integer' }, failed: { type: 'integer' }, errors: { type: 'integer' },
  failed_for_expected_reason: { type: 'boolean' }, reasons: { type: 'array', items: { type: 'string', enum: ['AssertionError', 'NotImplementedError', 'ImportError-new-symbol', 'AttributeError-new-symbol', 'other'] } }, evidence: { type: 'array', minItems: 1, items: CMD } },
  ['card_id', 'tests_head_sha', 'base_sha', 'collected', 'failed', 'errors', 'failed_for_expected_reason', 'reasons', 'evidence'])

// ---- build: implement / verify / refute / fix ----
const IMPL = env({ card_id: { type: 'string' }, impl_status: { type: 'string', enum: ['done', 'partial', 'failed', 'reused'] }, worktree: { type: 'string' }, branch: { type: 'string' }, base_sha: { type: 'string' }, head_sha: { type: 'string' },
  bundle_path: { type: 'string' }, commits_made: { type: 'integer' }, changed_files: { type: 'array', items: { type: 'string' } },
  dod: { type: 'array', minItems: 1, items: { type: 'object', properties: { acceptance_id: { type: 'string' }, command: { type: 'string' }, exit_code: { type: 'integer' }, evidence_path: { type: 'string' } }, required: ['acceptance_id', 'command', 'exit_code'] } },
  apis_used: { type: 'array', items: { type: 'object', properties: { module: { type: 'string' }, symbol: { type: 'string' }, kwargs_used: { type: 'array', items: { type: 'string' } }, ledger_anchor: { type: 'string' } }, required: ['module', 'symbol', 'kwargs_used', 'ledger_anchor'] } },
  claims: { type: 'array', items: { type: 'string' }, description: 'each must be visible in the diff' }, gate_digest: { type: 'string' }, gate_ledger_path: { type: 'string' },
  handoff: { type: 'object', properties: { decisions: { type: 'array', items: { type: 'object', properties: { what: { type: 'string' }, why: { type: 'string' }, alternatives_rejected: { type: 'string' } }, required: ['what', 'why'] } }, invariants: { type: 'array', items: { type: 'string' } }, open_problems: { type: 'array', items: { type: 'string' } }, next_step: { type: 'string' } }, required: ['decisions', 'invariants', 'open_problems', 'next_step'] },
  verification_level: { type: 'string', enum: VERIFICATION_LEVEL } },
  ['card_id', 'impl_status', 'worktree', 'branch', 'base_sha', 'head_sha', 'bundle_path', 'commits_made', 'changed_files', 'dod', 'apis_used', 'claims', 'gate_digest', 'gate_ledger_path', 'handoff', 'verification_level'])
const VERIFY = env({ card_id: { type: 'string' }, sha_tested: { type: 'string' }, verdict: { type: 'string', enum: ['pass', 'fail', 'unverifiable'] }, gate_digest: { type: 'string' }, gate_fail: { type: 'integer' },
  pytest: { type: 'object', properties: { collected: { type: 'integer' }, passed: { type: 'integer' }, failed: { type: 'integer' }, skipped: { type: 'integer' }, xfailed: { type: 'integer' } }, required: ['collected', 'passed', 'failed', 'skipped', 'xfailed'] },
  changed_lines: { type: 'integer' }, files_changed: { type: 'integer' },
  acceptance_reruns: { type: 'array', minItems: 1, items: { type: 'object', properties: { acceptance_id: { type: 'string' }, exit_code: { type: 'integer' }, evidence: CMD }, required: ['acceptance_id', 'exit_code', 'evidence'] } },
  revert_proof: { type: 'object', properties: { failed_when_reverted: { type: 'boolean' }, evidence: CMD }, required: ['failed_when_reverted', 'evidence'] },
  heldout: { type: 'object', properties: { applicable: { type: 'boolean' }, passed: { type: 'boolean' }, evidence: CMD }, required: ['applicable', 'passed'] },
  mutants: { type: 'object', properties: { total: { type: 'integer' }, killed: { type: 'integer' }, survivors: { type: 'array', items: { type: 'string' } } }, required: ['total', 'killed', 'survivors'] },
  tamper_signals: { type: 'integer' }, locked_paths_diff: { type: 'array', items: { type: 'string' } }, claim_vs_diff: { type: 'array', items: { type: 'string' } }, p2p_regression: { type: 'boolean' },
  failures: { type: 'array', items: { type: 'object', properties: { check: { type: 'string' }, first_error_line: { type: 'string' }, evidence: CMD }, required: ['check', 'first_error_line', 'evidence'] } },
  negative_control: { type: 'object', properties: { mutation: { type: 'string' }, expected: { type: 'string', enum: ['red'] }, observed: { type: 'string', enum: ['red', 'green', 'unrunnable'] } }, required: ['mutation', 'expected', 'observed'] } },
  ['card_id', 'sha_tested', 'verdict', 'gate_digest', 'gate_fail', 'pytest', 'changed_lines', 'files_changed', 'acceptance_reruns', 'revert_proof', 'heldout', 'mutants', 'tamper_signals', 'locked_paths_diff', 'claim_vs_diff', 'p2p_regression', 'failures', 'negative_control'])
const REFUTE = env({ target_id: { type: 'string' }, lens: { type: 'string', enum: ['correctness-reproduce', 'security-secrets', 'decision-fidelity'] }, refuted: { type: 'boolean', description: 'default true if uncertain' },
  evidence: { type: 'array', minItems: 1, items: CMD }, strongest_disagreement: { type: 'string' }, severity_after: { type: 'string', enum: ['critical', 'high', 'medium', 'low', 'none'] }, sha: { type: 'string' } },
  ['target_id', 'lens', 'refuted', 'evidence', 'strongest_disagreement', 'severity_after', 'sha'])
const FIX = env(Object.assign({}, IMPL.properties, {
  attempt: { type: 'integer' }, reproduced_first: { type: 'boolean' }, root_cause: { type: 'object', properties: { statement: { type: 'string' }, evidence_anchor: ANCHOR }, required: ['statement', 'evidence_anchor'] },
  hypothesis: { type: 'string' }, disposition: { type: 'string', enum: ['fixed', 'sentence_rewritten', 'pushed_back', 'needs_clarification', 'reverted_regression'] }, revised_text: { type: 'string' }, pushback_evidence: { type: 'array', items: CMD } }),
  IMPL.required.filter(k => !ENVELOPE_REQ.includes(k)).concat(['attempt', 'reproduced_first', 'root_cause', 'hypothesis', 'disposition']))
const PIVOT = env({ card_id: { type: 'string' }, fingerprint: { type: 'string' }, alternatives: { type: 'array', minItems: 2, items: { type: 'object', properties: { approach: { type: 'string' }, why_different: { type: 'string' } }, required: ['approach', 'why_different'] } }, chosen: { type: 'integer' }, reason: { type: 'string' } }, ['card_id', 'fingerprint', 'alternatives', 'chosen'])
const REDECOMPOSE = env({ card_id: { type: 'string' }, sub_cards: { type: 'array', minItems: 2, items: CARD }, why: { type: 'string' } }, ['card_id', 'sub_cards', 'why'])
const ARBITER = env({ finding_id: { type: 'string' }, decision: { type: 'string', enum: ['side_a', 'side_b', 'accepted_risk', 'needs_owner'] }, rationale: { type: 'string' }, evidence: { type: 'array', minItems: 1, items: CMD } }, ['finding_id', 'decision', 'rationale', 'evidence'])

// ---- build: audit / critic / tamper ----
const AUDIT = env({ card_id: { type: 'string' }, sha_audited: { type: 'string' }, verdict: { type: 'string', enum: ['compliant', 'deviations', 'reject'] },
  deviations: { type: 'array', items: { type: 'object', properties: { decision_or_finding: { type: 'string' }, what_the_diff_does: { type: 'string' }, what_it_should_do: { type: 'string' }, severity: { type: 'string', enum: SEV }, anchor: ANCHOR }, required: ['decision_or_finding', 'what_the_diff_does', 'what_it_should_do', 'severity', 'anchor'] } },
  claim_vs_diff: { type: 'array', items: { type: 'string' } }, scope_violations: { type: 'array', items: { type: 'string' } }, deps_violations: { type: 'array', items: { type: 'string' } },
  deletions_blast_radius: { type: 'array', items: { type: 'object', properties: { symbol: { type: 'string' }, consumers: { type: 'array', items: { type: 'string' } }, both_states_probe: { type: 'string' } }, required: ['symbol', 'consumers', 'both_states_probe'] } }, idiom_warnings_cleared_by: { type: 'string' } },
  ['card_id', 'sha_audited', 'verdict', 'deviations', 'claim_vs_diff', 'scope_violations', 'deps_violations', 'deletions_blast_radius'])
const CRITIC = env({ card_id: { type: 'string' }, sha: { type: 'string' }, hunks_cited: { type: 'array', items: ANCHOR },
  missing: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, title: { type: 'string' }, kind: { type: 'string', enum: ['untested-path', 'unhandled-error', 'decision-not-implemented', 'interaction', 'security', 'perf', 'modality-not-run', 'claim-unverified', 'source-unread', 'omitted-obligation', 'boundary'] }, severity: { type: 'string', enum: SEV }, reproduced: { type: 'boolean' }, evidence: CMD, anchor: ANCHOR }, required: ['id', 'title', 'kind', 'severity', 'reproduced', 'evidence', 'anchor'] } },
  coverage_notes: { type: 'string' } }, ['card_id', 'sha', 'hunks_cited', 'missing', 'coverage_notes'])
const TAMPER = env({ card_id: { type: 'string' }, sha: { type: 'string' }, signals: { type: 'array', minItems: 1, items: { type: 'object', properties: { signal: { type: 'string' }, hunk_anchor: ANCHOR, classification: { type: 'string', enum: ['tamper', 'legitimate', 'cannot-see-hunk'] }, reason: { type: 'string' } }, required: ['signal', 'hunk_anchor', 'classification', 'reason'] } } }, ['card_id', 'sha', 'signals'])

// ---- integrate / review / judge ----
const INTEGRATION = env({ card_id: { type: 'string' }, int_status: { type: 'string', enum: ['merged', 'conflict', 'gate-failed', 'skipped', 'reverted'] }, branch: { type: 'string' }, head_sha: { type: 'string' }, merged_sha: { type: 'string' },
  conflicts: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, ours: { type: 'string' }, theirs: { type: 'string' } }, required: ['file', 'ours', 'theirs'] } },
  cherry_unmerged: { type: 'array', items: { type: 'string' } }, patch_id_missing: { type: 'array', items: { type: 'string' } }, gate_digest: { type: 'string' }, gate_fail: { type: 'integer' }, checkpoint_bundle: { type: 'string' }, bundle_bytes: { type: 'integer' } },
  ['card_id', 'int_status', 'branch', 'head_sha', 'conflicts', 'cherry_unmerged', 'patch_id_missing', 'gate_digest', 'gate_fail'])
const REVIEW_FINDINGS = env({ lens: { type: 'string' }, sha_reviewed: { type: 'string' }, findings: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, title: { type: 'string' }, file: { type: 'string' }, anchor: ANCHOR, evidence: CMD, severity: { type: 'string', enum: SEV }, kind: { type: 'string', enum: ['bug', 'security', 'decision-deviation', 'overclaim', 'missing-test', 'perf', 'cost'] }, affects_correctness_or_requirement: { type: 'boolean' }, recommendation: { type: 'string' }, corrected_claim: { type: 'string' } }, required: ['id', 'title', 'file', 'anchor', 'evidence', 'severity', 'kind', 'affects_correctness_or_requirement', 'recommendation'] } }, probes_used: { type: 'array', items: { type: 'string' } }, coverage_notes: { type: 'string' } }, ['lens', 'sha_reviewed', 'findings', 'probes_used', 'coverage_notes'])
const JUDGE = env({ lens: { type: 'string', enum: ['spec-compliance', 'test-evidence', 'release-readiness'] }, sha_reviewed: { type: 'string' }, verdict: { type: 'string', enum: ['satisfied', 'not-satisfied', 'blocked-needs-owner'] },
  dod_items: { type: 'array', minItems: 1, items: { type: 'object', properties: { id: { type: 'string' }, type: { type: 'string', enum: ['deterministic', 'subjective'] }, opinion: { type: 'string', enum: ['YES', 'NO', 'UNBACKED'] }, citation: { type: 'string' }, receipt: { type: 'string', enum: ['reproduced', 'not-reproduced', 'unrunnable'] } }, required: ['id', 'type', 'opinion', 'citation', 'receipt'] } },
  vetoes: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, title: { type: 'string' }, anchor: ANCHOR, evidence: CMD, reproduced: { type: 'boolean' }, severity: { type: 'string', enum: SEV } }, required: ['id', 'title', 'anchor', 'evidence', 'reproduced', 'severity'] } }, dissent: { type: 'string' } },
  ['lens', 'sha_reviewed', 'verdict', 'dod_items', 'vetoes', 'dissent'])
const POSTCONDITION = env({ target_id: { type: 'string' }, checks: { type: 'array', minItems: 1, items: { type: 'object', properties: { name: { type: 'string', enum: ['exists', 'nonempty', 'parses', 'sentinel', 'anchors', 'bundle_verifies'] }, ok: { type: 'boolean' }, evidence: CMD }, required: ['name', 'ok', 'evidence'] } } }, ['target_id', 'checks'])
const STATE_PROBE = env({ sha: { type: 'string' }, branch: { type: 'string' }, sha_exists: { type: 'boolean' }, branch_points_at_sha: { type: 'boolean' }, worktree_clean: { type: 'boolean' }, evidence: { type: 'array', minItems: 1, items: CMD } }, ['sha', 'branch', 'sha_exists', 'branch_points_at_sha', 'worktree_clean', 'evidence'])
const STAGE_CLAIM = env({ claim_id: { type: 'string' }, level: { type: 'string', enum: VERIFICATION_LEVEL }, evidence_path: { type: 'string' }, evidence_present: { type: 'boolean' }, measured_value: { type: 'string' }, expected: { type: 'string' }, verdict: { type: 'string', enum: ['pass', 'fail', 'unverified'] }, deployed_sha: { type: 'string' } }, ['claim_id', 'level', 'evidence_path', 'evidence_present', 'measured_value', 'expected', 'verdict', 'deployed_sha'])

// ---- synthesis ----
const CHECKPOINT = { type: 'object', properties: { action: { type: 'string', enum: ['none', 'approve-smoke', 'approve-plan', 'create-github-repo-and-push', 'create-staging-spaces', 'set-secrets', 'record-fixture-1', 'run-hf-job', 'run-harness', 'approve-hf-job-and-promotion-rehearsal', 'promote-production', 'other'] },
  why: { type: 'string' }, exact_steps: { type: 'array', minItems: 1, items: { type: 'string' } }, blast_radius: { type: 'string' }, rollback: { type: 'string' }, cost_estimate: { type: 'string' }, evidence_paths: { type: 'array', items: { type: 'string' } }, required_owner_approvals_fields: { type: 'array', items: { type: 'string' } } },
  required: ['action', 'why', 'exact_steps', 'blast_radius', 'rollback', 'cost_estimate', 'evidence_paths', 'required_owner_approvals_fields'] }
const SYNTH = env({ stage: { type: 'string' }, head_sha: { type: 'string' }, stop_reason: { type: 'string' },
  rows: { type: 'array', minItems: 1, items: { type: 'object', properties: { card_id: { type: 'string' }, row_status: { type: 'string', enum: ['merged+gate-green', 'merged+gate-red', 'built-not-merged', 'parked', 'reverted', 'split', 'blocked_on_owner', 'dropped_null', 'not_attempted'] }, reason: { type: 'string' }, head_sha: { type: 'string' }, dod_done: { type: 'integer' }, dod_total: { type: 'integer' } }, required: ['card_id', 'row_status', 'reason', 'dod_done', 'dod_total'] } },
  dod_status: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, pass: { type: 'boolean' }, evidence_a: { type: 'string' }, evidence_b: { type: 'string' }, level: { type: 'string', enum: VERIFICATION_LEVEL } }, required: ['id', 'pass', 'evidence_a', 'evidence_b', 'level'] } },
  skipped_conformance_rows: { type: 'integer' }, owner_actions: { type: 'array', items: { type: 'string' } }, checkpoint: CHECKPOINT, report_path: { type: 'string' }, runbook_path: { type: 'string' } },
  ['stage', 'head_sha', 'stop_reason', 'rows', 'dod_status', 'skipped_conformance_rows', 'owner_actions', 'checkpoint', 'report_path', 'runbook_path'])
const SYNTH_VERIFY = env({ rows_checked: { type: 'integer' }, rows_rewritten: { type: 'array', items: { type: 'object', properties: { card_id: { type: 'string' }, was: { type: 'string' }, now: { type: 'string' }, evidence: CMD }, required: ['card_id', 'was', 'now', 'evidence'] } }, git_log_head: { type: 'string' }, ledger_entries: { type: 'integer' }, verdict: { type: 'string', enum: ['consistent', 'rewritten', 'inconsistent-unresolved'] } }, ['rows_checked', 'rows_rewritten', 'git_log_head', 'ledger_entries', 'verdict'])
```

JS-side semantic checks applied to every return (F-46): `status !== 'SUCCESS'` requires a non-empty `reason`; `outward_actions_taken.length > 0` aborts the run after logging; `installed_packages.length > 0` → the stage is `FAILED:installed`; `repo_toplevel` must equal `args.build_repo` or `''` (read-only agents); `pass` verdicts with empty evidence arrays are downgraded to `unverified`; any acceptance/claim whose text matches the staging keyword list has its `level` raised to `staging-required` regardless of the agent's value.

---

## 10. Replay/resume, null results, safeguard kills and concurrency

**Replay and resume (T-13..T-16, D-22, S-18, F-43).**
- `args` are computed by the orchestrator immediately before every invocation with `git rev-parse` and `sha256sum`, never inside the script: `{stage, runTag, run_nonce, launched_at, build_repo, wt_root, venv, gate_sh, durable, run_dir, libsrc, base_sha (40-hex), integration_sha_at_launch, plan_hash, toolchain_status_snapshot_sha, fleet, waveSize, maxFix, maxAuditFix, maxTreeRounds, reserveTokens, judge_perm, owner_approvals{…}, monitor_findings[], smoke}`. A moved repo changes `integration_sha_at_launch`, which appears in every code-reading prompt → the cache misses exactly where it must.
- Prompts are pure functions of `args` and prior typed results; arrays are sorted by id before `JSON.stringify(x, null, 1)`; no completion order, no `budget.spent()` value and no path that differs per session ever enters a prompt. Constants that may need tuning between runs live in `args`.
- Only completed `result` events replay; a kill mid-card re-runs the in-flight agents. Mitigations: PR-sized cards; commit-per-step; the implementer prompt's first instruction is "inspect `git -C $BUILD_REPO log card/<id>-<nonce>`; if the branch exists at a commit whose tree passes the card's acceptance, report `impl_status:'reused'`".
- Every cached result that carries a sha is consumed only after a **state probe** (`git cat-file -e <sha>`, `git rev-parse <branch>`); mismatch → the script logs `stale` and re-runs that stage live by appending a nonce-free but sha-bearing suffix to the prompt (`state:<live_sha>`), which is a deliberate cache miss.
- Resume from `resumeFromRunId` is allowed only if `args.integration_sha_at_launch` still equals the live integration head (checked by the first state probe); otherwise the orchestrator starts a fresh run with new args (the plan phase replays from cache because its prompts do not contain the integration sha).

**Null results and drop receipts (T-17, D-21, F-41).** Every `agent()` goes through `safeAgent()` (§13): it wraps the call in `withTimeout` (H6, pasted verbatim), converts `null`/timeout/throw into a typed `{status:'null'|'timeout'|'threw', reason}` object, appends `{card, stage, status, reason, label}` to `ledger[]`, and `log()`s it. Stage callbacks branch on `status`; nothing is `.filter(Boolean)`-ed without pushing the removed entries to `dropped[]`. Retry policy: implementer/critic/verifier null → ONE retry with a narrower reading list (and `model:'fable'` on hardening cards); a second null parks the card `blocked:'safeguard'` (F-42). Verifiers and refuters are never retried more than once; a null refuter counts as "did not refute" only if the other two ran and cited evidence, else the panel is `unverifiable` → fix loop input, not a pass. H6's honest scope is kept: a timed-out agent is dropped from the barrier but keeps running and its slot; the script logs the receipt and never counts it green.

**Safeguard kills (F-31, F-42).** Hardening cards are three small cards with narrow reading lists; their prompts are framed as "what the guard must refuse, with red-proof tests" and carry `model:'fable'`; a killed implementer's retry starts from the last commit (`git status`; discard only non-compiling partial edits); the gate pre-step removes stale `index.lock` and stray listeners. Two consecutive nulls on one card → park, and the synthesizer lists it under `needs_owner`.

**Concurrency (T-7, T-8, F-44).** `pipeline(wave, buildCard)` per wave (no barrier inside a card chain except the three-refuter `settle()` and the two test authors' `settle()`); a barrier exists only at the wave boundary (integration needs all of them), at the five-reviewer join and the three-judge join, all through `settle()` with typed drops. Wave size from `args.waveSize` (2 at cap 2; ≤6 at cap 14 — the DAG width, not the cap, limits it). Enqueue order = topological order with the spine first. At cap 2 the per-card chain is strictly sequential inside the two slots, so the script also `log()`s an estimated remaining wall-clock at each wave boundary from the agent-reported `date -u` durations (F-44). The Codespace resize (cap 14) must happen BEFORE the `build` run: `args.waveSize` changes the partition of `agent()` calls and therefore invalidates the cache for everything after the plan phase; resizing mid-run means a cache-cold resume (stated in §15 Q5).

**Budget and lifetime cap (T-20, F-45).** Loops are bounded by counters first, budget second: `budgetOk()` returns false when `budget.total && budget.remaining() < Math.max(RESERVE, 0.15 * budget.total)` or when `agentCount > 800`; the synthesizer + synthesis verifier always run (wrapped in try/catch so a throw still logs the ledger). With no `+Nk` directive `budget.total` is null and the counter caps are the backstop; the script logs this at start.

---

## 11. Budget and effort plan by role; agent counts and wall-clock at cap 2 and cap 14

**Effort by role.** `low`: setup, postcondition/state probes, bundle export. `medium`: test authors, red-confirmer, verifier, refuters, tamper judge, integration tester, staging evidence reader. `high`: ground, decision sheet, api ledger, card authors, implementer, fixer, pivot, re-decomposer, auditor, critic, integrator, reviewers, inversion scout, synthesizer, synthesis verifier. `xhigh`: card critic, plan judges, arbiter, conflict resolver, judge panel. `model` inherited everywhere except `model:'fable'` on the three hardening cards' implementer/fixer/verifier/critic (C-F).

**Agent count (derived; implementer durations are UNVERIFIED — no implementer has run under this tool yet; verifier/finder durations are the measured 4–5 min / 13–16 min from `wf_f47ecf9e-916`).**

| Phase | Agents per unit | Units | Subtotal |
|---|---|---|---|
| Smoke run | setup, ground, 1 trivial card through every stage (≈ 14), postcondition | 1 | ≈ 17 |
| Plan (R0) | setup (cached), ground, decision sheet, api ledger, symbolizer, 5 pre-verifiers (critic-1..5), 6 card authors, card critic, repair, 3 plan judges, plan-hash probe | 1 | ≈ 21 |
| Build per card (no fix) | state probe, test author, held-out author (≈ 40 % of cards), red-confirmer, implementer, verifier, 3 refuters, auditor, critic, postcondition probe | 24 cards | 11.4 × 24 ≈ 274 |
| Fix rounds | fixer + verifier + 3 refuters (+ pivot at strike 2) ≈ 5.3 per round; assume 1.2 rounds/card average (own history: 19 of 45 findings partially wrong on first pass) | 24 | ≈ 153 |
| Audit/critic fixes | fixer + verifier ≈ 2 per event; assume 0.5 events/card | 24 | ≈ 24 |
| Integration | integrator per card (+ conflict resolver 0.25 + ff) + integration tester per wave (≈ 12 waves at cap 2, 7 at cap 14) + postcondition | 24 | ≈ 45 (cap 2) / 40 (cap 14) |
| Review rounds | 5 reviewers + ≈ 6 fresh findings × 3 refuters + ≈ 3 fix cards × 16 + 3 judges (+ inversion scout once) | 3 rounds (cap MAX 4) | ≈ 225 |
| Synthesis | synthesizer + synthesis verifier + journal-export secrets scan | 1 | 3 |
| **Total R1** | | | **≈ 740 (cap 2) / ≈ 735 (cap 14)** — inside the 1000 lifetime cap; the `agentCount > 800` reserve stops scheduling new cards before P8 |
| R2 `stage` | 1 evidence reader per staging-required claim (≈ 12) + fix cards (≈ 3 × 16) + 3 judges + synth ×2 | 1 | ≈ 65 |
| R3 `promote` | evidence readers (≈ 6) + judges 3 + synth ×2 | 1 | ≈ 11 |

Token cost: with the measured 90–110 k tokens per verifier-class agent and 150–230 k per finder-class agent, and assuming implementers at the finder class, R1 lands around **90–120 M tokens** (≈ 3× a lean design's count; the extra is verification diversity, C-J). If a `+Nk` budget directive is set, `RESERVE` should be ≥ 15 % of it.

**Wall-clock.** Per-card critical chain: authors ‖ (8 min) → red 4 → impl 20 (UNVERIFIED) → verify 6 → refuters 5 ‖ → audit 6 → critic 5 → probes 2 ≈ 56 min with parallel legs, ≈ 70 min serialised at cap 2; one fix round adds ≈ 30 min. The spine `c01a…c05c` (≈ 11 cards) is serial by dependency at any cap.

| | Cap 2 (now) | Cap 14 (after resize) |
|---|---|---|
| Smoke + plan | ≈ 1.5 h | ≈ 0.7 h |
| Spine (11 serial cards, ≈ 1.2 fix rounds) | ≈ 11 × 1.6 h ≈ 17 h | ≈ 11 × 1.2 h ≈ 13 h (only intra-card parallelism helps) |
| Fan-out (13 cards) | 7 waves × ≈ 1.8 h ≈ 12.5 h | 2–3 waves × ≈ 1.4 h ≈ 3.5 h |
| Integration + wave gates | ≈ 3 h | ≈ 2 h |
| Review rounds (3) | ≈ 3 × 2.5 h ≈ 7.5 h | ≈ 3 × 1.2 h ≈ 3.5 h |
| **R1 total** | **≈ 41 h** (several resumes across Codespace sessions; bundles after every merge make that safe) | **≈ 22 h** |
| R2 / R3 | ≈ 4 h / ≈ 1 h | ≈ 2 h / ≈ 0.5 h |

Honest reading: the serial spine dominates; the cap-14 resize buys ≈ 2× on fan-out and panels but not on the spine. The price of the reliability angle is stated, not hidden: ≈ 740 agents and ≈ 22–41 h for R1 versus roughly a third of that for a lean design. The design accepts it because every one of the measured failure classes (verification theater, tampering, over-claiming, stale-sha replay, lost hunks) is guarded by a mechanism rather than a prompt.

<!-- CONTINUE -->
