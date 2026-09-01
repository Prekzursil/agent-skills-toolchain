# Long-Horizon Quality-Gate Closure Playbook

Date: 29.08.2026
Skill applied: `quality-gate-automation-architect` (all five references read)
Scope: governance + automation design for closing L1–L5 of `LONG-HORIZON-CLOSURE_2026-08-29.md`
Mode: design only. No code was edited, no commit was made, no file other than this one was written.
Authority: subordinate to `AGENTS.md` (estate locks, verification doctrine, NEVER-ROTATE) and to
`PROMPT-LONG-HORIZON-CLOSURE_2026-08-29.md` §3–§5. Where this playbook and those conflict, they win.

## Inputs read for this design

| Input | What it contributed |
|---|---|
| `LONG-HORIZON-CLOSURE_2026-08-29.md` | lane inventory L1–L5, completion contract, hard boundaries |
| `PROMPT-LONG-HORIZON-CLOSURE_2026-08-29.md` | ground truth, binding decisions, phase order, unit contract |
| `PERPLEXITY-BLUEPRINT-REVIEW-FEASIBILITY_2026-08-29.md` | 13 BLOCKERs, 15 IMPROVEMENTs, 7 new NOT-CHECKED |
| `PERPLEXITY-BLUEPRINT-REVIEW-COMPLETENESS_2026-08-29.md` | 12 blockers, 9 majors, census OK 24 / ENUM 9 / SKELETON 7 |
| `PERPLEXITY-BLUEPRINT-REVIEW-SCOPE_2026-08-29.md` | scope/alignment PASS (the only passing reviewer) |
| `RESEARCH-APPROVAL-GATES_2026-08-29.md` | R0–R3 tiers, 7-step protocol, `ReviewVerdict` schema |
| `AUTOMATION-SUITE-DECISIONS_2026-08-29.md` | G-1…G-11 resolved, G-12…G-21 open, provider probe failures |
| `.github/workflows/quality.yml` (SSOT repo) | live required-check producers (measured, see below) |
| `.github/workflows/codex-runner.yml` | live Codex worker with caps, forbidden paths, gitleaks, draft-PR-only |
| `.github/workflows/autofix-models.yml` | live `workflow_run` repair bot, currently DORMANT |
| `.github/workflows/dependabot-auto-merge.yml` | the only existing zero-touch merge path |
| `tools/editor/metaswarm/.coverage-thresholds.json` | 100/100/100/100, `pnpm test:coverage`, blocks PR creation |
| `D:\tools\mcp-manager\pyproject.toml` | pytest `testpaths=tests`; coverage omits `ui/app.py`, `ui/gui.py`; "all non-GUI logic must still hit 100% line+branch" |

### Measured control-plane facts (29.08.2026, read-only)

- Required-check producers in `agent-skills-toolchain` are one workflow, `quality`, with eight jobs:
  `gate-lint-format (ruff)`, `gate-types (basedpyright)`, `gate-tests-coverage (node workspaces)`,
  `gate-tests-coverage (python packages)`, `gate-tests-coverage (platform)`, `gate-sast (opengrep)`,
  `gate-secrets (gitleaks)`, `gate-deps (osv-scanner)`. Triggers: `push`, `pull_request`,
  `workflow_dispatch`; a `concurrency` block is present.
- `codex-runner.yml` is `workflow_dispatch`-only by deliberate design, pins `@openai/codex@0.144.1`,
  opens a **draft** PR, aborts with no PR above `max_changed_files` (default 40), greps a forbidden-path
  set (`.github/workflows/`, `.env`, `*.pem`, `id_*`, `.git/`), runs checksum-pinned gitleaks 8.21.2 on
  the staged diff, uses `concurrency: {group: codex-runner, cancel-in-progress: false}`, 45-minute timeout,
  and `rm -rf`s the reconstructed Codex home on `always()`.
- `autofix-models.yml` reacts to `workflow_run: [quality] completed` restricted to `failure` + `push` +
  `main`, and self-reports **DORMANT** (warning, clean exit) while `COPILOT_PAT` is absent — because
  GitHub Models was retired 2026-07-30.
- `dependabot-auto-merge.yml` is the only auto-merge in the estate: dependabot-actor-gated,
  `gh pr merge --auto --squash`, merge still blocked by the ruleset's required `quality` checks.
- No `sonar-project.properties`, no `.codacy.yaml`, no `codecov.yml`, no root `.deepsource.toml` was
  found in `agent-skills-toolchain`. **Sonar / Codacy / Codecov are NOT configured here.** Whether
  DeepSource is enabled server-side for the repo is **NOT-CHECKED** (L5 item 2 is exactly that probe).
- `.coverage-thresholds.json` exists at `tools/editor/metaswarm/` only. `D:\tools\mcp-manager` has
  **no** thresholds file → per the home contract its coverage status is `NOT-CHECKED`, not a pass.
- Provider baseline from the decision log: OpenRouter 402, Anthropic 401, OpenAI 401, Gemini 404.
  Basic Memory returns `Session not found`. Free RAM measured 2.49 GB of 31.63 GB during the
  feasibility review. All three are load-bearing for this design.

---

## 1. recommendation

**Adopt a split control plane with a Codex-first worker, and stop treating "closure" as one loop.**

1. **GitHub is the control plane for everything that can become a commit** in
   `source\agent-skills-toolchain` (the mcp-manager SSOT sync, the repaired blueprint if it is ever
   committed, browser/Playwright pins, Avante hardening notes). Truth about green/red is the `quality`
   workflow's eight check runs at the PR head SHA plus the `main` ruleset — not a dashboard, not an
   agent's summary, not a Cursor UI card.
2. **Codex is the primary repair worker**, not GitHub's native agent, because the estate already runs
   `codex-runner.yml` with the exact guardrails this playbook needs (diff cap, forbidden paths, secret
   scan, draft-only PR, pinned CLI) and because lane-specific prompts with explicit stop rules are the
   whole point here. GitHub Copilot coding agent stays as a **fallback worker** (it cannot approve or
   merge its own PRs, which suits us) and `autofix-models` stays as a dormant tier-2 draft bot.
3. **The local lane is primary only where the work is physically local** — Cursor MCP approval store
   (L1 steps 4–9), Daria Codeg container (L2), Windows diagnostics UI and Playwright profile (L4). No
   remote control plane can touch those. Those runs are **owner-present, receipt-producing, and never
   unattended**, and the local lane is explicitly *not* the backbone for repo repair.
4. **Four lanes stay separated forever**: PR repair, coverage ratchet, active-analyzer debt burn-down,
   consultation. The 25 blueprint blockers are **consultation-lane document defects** and must never
   enter the PR repair lane; the mcp-manager review findings are **coverage + PR repair**. DeepSource
   and Codacy are retired by owner direction and are not valid producers.
5. **Human-approved merge, always.** The single zero-touch exception already in place (Dependabot
   auto-merge behind full required checks) is the only allowlist; do not add a second one during
   closure. Agent PRs are draft PRs.
6. **Fail-closed accounting**: a lane is green only with a disk artifact re-read after writing, a
   passing deterministic receipt at the current head SHA, and a provenance tag. Budget abort, dormant
   provider, missing check, or stale context = `FAILED_TO_RUN` / `NOT-CHECKED`, never a pass.

What this buys: L1/L3 stop oscillating between "repair agent claims green" and "reviewer finds gaps",
because repair is bounded per classification and re-review is triggered by a receipt, not by a claim.

What it costs: the local lanes remain owner-gated, so L1 steps 4–9 and all of L2 cannot be finished
while the owner is away. That is a deliberate refusal to fake unattended capability, not a gap.

---

## 2. option_comparison

Three backbones compared even though one is favored, per the skill's required comparison.

### Option A — GitHub-native agent as both control plane and worker

| | |
|---|---|
| **Shape** | Assign work to GitHub Copilot coding agent; it runs in an Actions-powered environment and opens a PR; iterate by `@copilot` comments on the PR. |
| **Pros** | Most boring governance: branch protection, rulesets, required checks, review requirements are the contract. Agent PRs cannot self-approve or self-merge. One PR per task, repo-scoped. Nothing local to keep alive. Survives this machine's RAM pressure entirely. |
| **Cons** | Weak prompt control: no place to encode "tests-only preferred", "one rule family per batch", stale-SHA aborts, or the `UNIT-COMPLETE` contract. Draft PRs from the agent need a write-permission human to approve workflow runs, so unattended throughput is lower than it looks. Cannot touch any of L1 steps 4–9, L2, or L4 — the majority of remaining closure work. Copilot credential posture on this account is **NOT-CHECKED**. |
| **Verdict** | **Secondary / fallback worker.** Keep the control-plane half; reject it as the only worker. |

### Option B — OpenAI/Codex-first (GitHub still the control plane)

| | |
|---|---|
| **Shape** | `codex-runner.yml` (`openai/codex` CLI via `codex exec`, or `openai/codex-action@v1`) is the repair worker, dispatched per lane with a versioned prompt file; GitHub keeps required checks, rulesets, and merge authority. Codex app automations handle local recurring backlog jobs only. |
| **Pros** | Already built, already hardened, already pinned in this estate — the guardrails in §6 are mostly *documenting* what `codex-runner.yml` enforces today. Same worker model across CI, CLI, and app, which matches G-3/G-4. Full prompt control: lane separation, stop rules, output schema, scope caps are all expressible. Uses the ChatGPT subscription lane rather than the four failing API-key providers. `workflow_dispatch`-only means no fork or PR-body prompt-injection path to the `CODEX_AUTH_JSON` secret. |
| **Cons** | `workflow_dispatch`-only also means it is **not** self-triggering: someone or something must dispatch it, so "while I am away" needs a scheduled dispatcher, which is a new surface. `danger-full-access` + `--dangerously-bypass-approvals-and-sandbox` inside the job means the blast radius is bounded by the guard step, not by a sandbox — the diff cap, forbidden paths, and gitleaks step are load-bearing and must never be "simplified". Prompt-injection risk from repo content read during the run. Codex app automations need the app running and the project on disk — same fragility as the local lane. |
| **Verdict** | **PRIMARY worker.** Adopt, with the §6 guardrails made explicit and the trigger question answered in §7 P1. |

### Option C — Local-first hybrid

| | |
|---|---|
| **Shape** | Local `cursor-agent` / acpx queue drives everything; GitHub is just a mirror. |
| **Pros** | The only lane that can reach the surfaces that actually remain: Cursor approval store (37 non-core IDs), Codeg container, Windows policy/diagnostics UI, Playwright profile, `.agents` skill vault. Rich local context, owner-present approvals, no secret exfil surface. |
| **Cons** | Depends on this box: 2.49 GB free RAM measured, one-`cursor-agent` lock, `agent worker start` forbidden under 8 GB (G-26), subagents observed stalling and transcript-flush lag. Basic Memory currently `Session not found`, so its own memory of state is unreliable. State drift across `.agents` / `.claude` / `.codex` mirrors. As an unattended backbone it would produce exactly the failure mode this program exists to eliminate: silent abandonment with a stale UI card. |
| **Verdict** | **Secondary, and mandatory** — but only for local-only mutation and consultation, owner-present, with a receipt per action. Never the unattended backbone, never merge authority. |

**Chosen combination:** control plane = GitHub (A's half) · repair worker = Codex (B) · local-only
mutation + consultation = local lane (C), bounded. Copilot coding agent = declared fallback worker if
the Codex subscription lane fails preflight twice.

---

## 3. architecture

```
                     ┌──────────────────────────── OWNER ────────────────────────────┐
                     │ merges · approves R2/R3 · unlocks local mutation · overrides   │
                     └───────▲───────────────────────────────────────────▲───────────┘
                             │ human merge (mandatory)                   │ owner-present unlock
              ┌──────────────┴───────────────┐               ┌───────────┴────────────────┐
              │   CONTROL PLANE: GitHub      │               │  LOCAL PLANE (bounded)      │
              │   ruleset on main            │               │  serial queue, depth 1       │
              │   required checks = quality   │               │  one cursor-agent max        │
              │   (8 jobs, head-SHA scoped)  │               │  RAM guard per mode          │
              └──────┬───────────────┬───────┘               └───────┬─────────────────────┘
                     │               │                               │
        ┌────────────▼───┐   ┌───────▼────────────┐        ┌─────────▼──────────────────────┐
        │ LANE A         │   │ LANE C             │        │ LANE D (consultation)          │
        │ PR repair      │   │ analyzer debt      │        │ + LOCAL-ONLY MUTATION           │
        │ codex-runner   │   │ burn-down          │        │ classify · memo · escalate      │
        │ draft PR only  │   │ 1 tool×1 rule×1 dir│        │ Cursor approval store (L1 4-9)  │
        └────────┬───────┘   └───────┬────────────┘        │ Daria Codeg (L2)                │
                 │                   │                     │ diagnostics/Playwright (L4)     │
        ┌────────▼────────┐          │                     └─────────┬──────────────────────┘
        │ LANE B          │          │                               │
        │ coverage ratchet│          │                               │
        │ tests-first     │          │                               │
        └────────┬────────┘          │                               │
                 └───────────────┬───┴───────────────────────────────┘
                                 ▼
                   RECEIPT STORE (fail-closed evidence)
                   verify/<lane>/<run-id>/  ·  UNIT-COMPLETE record
                   provenance: disk-verified | agent-claimed
                                 ▼
                   LONG-HORIZON-CLOSURE_2026-08-29.md  (ledger, updated at every boundary)
```

### Lane definitions and their mapping onto L1–L5

| Lane | Contract | Owns from the closure ledger | Never touches |
|---|---|---|---|
| **A — PR repair** | Make the required checks on the *current head SHA* pass. | L1 step 2–3 (SSOT sync PRs, deployed↔SSOT parity), L4 commits (Playwright pin, Avante notes) once they become PRs | historical debt, coverage uplift beyond the ratchet, blueprint prose |
| **B — coverage ratchet** | Raise or preserve coverage with narrow, test-led changes against the project's own thresholds SSOT. | L1 (mcp-manager 322 tests → 100% non-GUI line+branch; deployed **and** SSOT suites) | lint, SAST, deps, analyzer backlog, GUI view layers (reasoned `omit`, not a threshold change) |
| **C — active-analyzer debt burn-down** | Reduce historical findings from currently configured producers in small reviewable batches, one tool × one rule family × one directory. | Residual opengrep/gitleaks/osv backlog and L1 review findings that are rule-shaped; explicitly excludes retired DeepSource/Codacy | anything the current PR needs to go green (that is Lane A), coverage, dependency bumps, retired analyzers |
| **D — consultation** | Classify, explain, escalate, design. Produces documents and verdicts, not merges. | L3 entirely (25 blueprint blockers), L5 items 1/3/4/5/6, plus all local-only mutation of L1 4–9, L2, L4 | merge authority, unattended repo mutation, "fix everything" runs |

**Why L3 is consultation and not repair:** the two failing reviews are not CI failures. They are
contract defects in a 6,994-line design document — dual `SourceRecord` schemas, two incompatible tier
taxonomies, three undefined safety controls, unreachable acceptance rows A4/A11, an undefined engine
interface with G-12 still Open, and a duplicate-prevention gate whose anchors do not exist. A repair
worker pointed at "make the reviewers pass" would rewrite prose until the reviewers stopped
complaining. Instead: split the 25 blockers by **file ownership** (Part 00 shared contract / Part 02 /
Part 05 / cross-part graph), settle the four owner decisions first (see §6 mutation authority), then
repair, reassemble, re-pin hashes, and re-run the three-reviewer gate. That is Phase C of the prompt,
run as a consultation loop with deterministic lints as the receipt.

### Evidence and state layout

- `verify/<lane>/<run-id>/` — command, args, exit code, stdout/stderr, artifact hash, head SHA,
  classification, decision. One directory per attempt, never overwritten.
- `UNIT-COMPLETE` record per unit, in the §5 format, with a provenance tag on every claim.
- The closure ledger is the single human-readable state file; it is updated **at every lane boundary**,
  and each line carries `disk-verified` or `agent-claimed`.
- Coverage thresholds are per-project files, never a home-level file. `D:\tools\mcp-manager` currently
  has none: Lane B's first act is to propose one (owner-approved) encoding 100% line+branch on non-GUI
  code plus the existing reasoned `omit` list, or to emit `NOT-CHECKED` on every coverage claim until it
  exists. Silence is not a pass.

---

## 4. workflow_outline

### Lane A — PR repair (GitHub control plane, Codex worker)

1. **Resolve truth, not dashboards.** Read the ruleset's required checks for `main`, then map each to
   its producer job in `quality.yml`. A required context with no check run at the current head SHA is
   `MISSING`, which blocks — it is not a pass and not a red to be "fixed".
2. **Pin the SHA.** Record `pr.head.sha` as `SHA_START`.
3. **Classify.** Exactly one classification per attempt, from: `lint`, `types`, `unit-test`,
   `coverage`, `sast`, `secrets`, `deps`, `infra/provider`, `flaky`, `stale-context`. Multiple failing
   classifications = multiple sequential attempts, never one blended fix.
4. **Route.** `coverage` → Lane B. Rule-shaped historical findings not required by this PR → Lane C.
   `infra/provider` and `stale-context` → no code change at all; re-run or escalate.
5. **Repair, bounded.** Dispatch `codex-runner` with the lane prompt (§5), the classification, the
   failing log tail, and the scope cap. Draft PR only.
6. **Re-verify at head.** Re-read `pr.head.sha`. If `≠ SHA_START`, abort without pushing → `STALE_HEAD`,
   re-queue once. Otherwise run the smallest relevant `quality` subset, then the full required set.
7. **Stop.** `success` (all required green at the new head SHA) / `partial` (classification resolved,
   others remain, next attempt queued) / `blocked` (same failing set + same first-error signature as the
   previous attempt, or cap tripped, or owner decision needed).
8. **Record + hand to human.** `UNIT-COMPLETE`, receipts, ledger line. Merge is the owner's.

### Lane B — coverage ratchet

1. Read the project's `.coverage-thresholds.json`. Absent → emit `NOT-CHECKED`, surface it, stop.
2. Run the file's `enforcement.command` — never a remembered command. For mcp-manager, run it in
   **both** places: the deployment (`D:\tools\mcp-manager`) and the SSOT copy
   (`source\agent-skills-toolchain\tools\mcp-manager`), and diff the results. Parity failure is a
   blocker, not a rounding difference.
3. Quantify before spending cycles: expected covered-line gain vs the denominator. If the required
   uplift needs new shared harnesses or production refactoring, stop `blocked` with the number.
4. Add targeted tests in already-touched code first. Production edits only as behavior-preserving seams,
   ≤ 20 changed lines, and only when no test-only path exists.
5. Stop the moment the threshold is met. Do not opportunistically raise other files.
6. Never change a threshold value, never widen `omit`, never add `# pragma: no cover` to satisfy a gate.

### Lane C — active-analyzer debt burn-down

1. Establish the backlog only from active producers: opengrep, gitleaks, osv-scanner, and current
   required-check artifacts. DeepSource and Codacy are retired and must not be installed or queried.
2. Batch by `tool → rule family → language → directory`. One batch per PR. ≤ 15 files.
3. Denylist (reviewer-only, never auto-fixed): auth, credentials, crypto, concurrency, migrations,
   public API signatures, transaction boundaries, authorization checks — i.e. exactly the categories the
   L1 security review already flagged.
4. Each batch PR carries the rule IDs it closes and the count delta. No mixed cleanup, no dependency
   bumps, no coverage work.
5. Stop when the batch would cross a behavioral boundary or needs judgment.

### Lane D — consultation and local-only mutation

1. **Triage** every blocked case into A/B/C/D with a one-line reason and a receipt reference.
2. **Blueprint repair (L3)**: split the 13 + 12 blockers by file ownership; settle the owner decisions
   (§6) *before* any prose is rewritten; repair in parallel per file owner; reassemble; re-pin the
   companion SHA-256 table; then re-run feasibility, completeness, and scope with **fresh** reviewers on
   the new revision hash. A reviewer must never re-review its own repair.
3. **Local mutation (L1 4–9, L2, L4)**: owner-present only, one action per step, receipt per step,
   rollback command recorded before the action. Order for L1 is fixed and non-negotiable: freeze
   sessions → pre-disable every non-core ID → prove the approval store is core-only → *then* guarded
   attach-all → restart one workspace → prove only the core six are active → preset + disable/enable
   refresh → LinkedIn stays default-off.
4. **Escalation memo** for anything blocked: what was tried, the receipt, the exact resume command.

---

## 5. prompt_patterns

All prompts are versioned files in the repo (auditable), passed as an argv element or `prompt-file`,
never spliced into a shell line. Repo content read during a run is untrusted input: a prompt may never
grant it authority.

### Shared preamble (prepended to every lane prompt)

```
You are a bounded repair worker. You do exactly one lane and one failure classification.
Ground truth is the check runs at the CURRENT head SHA and the files on disk — not summaries,
not dashboards, not a previous agent's claim. If an expected artifact or check is missing,
report MISSING; never infer a pass from silence.
Hard rules: never rotate or print credentials. Never force-push, hard-reset, or use --no-verify.
Never edit .github/workflows/**, AGENTS.md, CLAUDE.md, .agents/agents.json, .agents/local.json,
.agents/secrets/**, browser-profiles/**, or any .coverage-thresholds.json threshold value.
Never remove a feature or lower a threshold to make a gate pass. Never merge.
Stop and report rather than widening scope. Output the UNIT-COMPLETE block and nothing else after it.
```

### Lane A — PR repair

```
Read the failing required checks, their producer jobs, and the failing log tail for this PR at head
SHA <SHA_START>. Your assigned classification is <CLASS>. Goal: make the <CLASS> checks pass at the
latest head SHA. Make the smallest high-confidence change. Do not fix other classifications, do not
reduce historical analyzer findings, do not touch coverage beyond what <CLASS> requires.
Cap: <=10 files, <=400 changed lines. Re-run only the smallest relevant verification.
Before proposing a change, re-resolve the head SHA; if it differs from <SHA_START>, stop with
status BLOCKED and reason STALE_HEAD.
Stop if the next step would need broader refactoring, an owner decision, or a denylisted area
(auth, crypto, migrations, authorization, transactions, public API).
```

### Lane B — coverage ratchet

```
Read <project>/.coverage-thresholds.json and treat it as the only source of thresholds and of the
enforcement command. If the file is absent, output NOT-CHECKED and stop — do not invent a threshold.
Read the diff and the coverage report. Prefer targeted tests in already-touched code. Allow only
behavior-preserving seam changes, <=20 lines, and only when no test-only path exists.
Run the enforcement command in BOTH the deployment and the SSOT copy and report both results.
Never widen `omit`, never add coverage pragmas, never change a threshold.
Stop as soon as the target is met, or as soon as the next gain would require broader production
changes or a new shared harness — and in that case report the expected covered-line gain as a number.
```

### Lane C — analyzer debt burn-down

```
Fix one rule family, from one tool, in one directory. Cap: <=15 files. List the rule IDs you close
and the count delta. Do not mix coverage work, dependency updates, formatting sweeps, or unrelated
cleanup. Do not touch auth, credentials, crypto, concurrency, migrations, authorization checks,
transaction boundaries, or public API signatures — report those as reviewer-only.
Stop when the batch would change behavior or needs judgment.
```

### Lane D — consultation / classification

```
Do not modify code. Classify this failure into exactly one of: PR-repair, coverage, analyzer-debt,
owner-decision, provider-outage, flaky, stale-context. Cite the receipt that proves the
classification. If it is owner-decision, state the decision needed in one sentence, the options,
and what each option costs. Produce a remediation memo with the exact resume command.
```

### Lane D — blueprint repair unit (L3)

```
You own exactly these files: <file list>. Your assigned findings are <blocker IDs> from
PERPLEXITY-BLUEPRINT-REVIEW-{FEASIBILITY,COMPLETENESS}_2026-08-29.md. Apply the repair each finding
prescribes; do not redesign the seven-layer architecture and do not renegotiate a finding you were
not assigned. Where a finding requires an owner decision (engine G-12, single-owner R2 mode, RAM-guard
per-mode table, tier/data-class taxonomy choice), STOP and escalate — do not silently decide it;
the artifact's own §23 forbids that. Use exact patches or structural edits; never overwrite a whole
file with a generated fragment. Re-read every file you wrote and report its new hash.
```

### Unit return contract (unchanged from the closure prompt, with provenance added)

```text
UNIT-COMPLETE: <id>
status: SUCCESS|PARTIAL|BLOCKED|FAILED_TO_RUN
lane: A|B|C|D
classification: <one>
head_sha_start / head_sha_end:
files:
tests:            (command, exit code, receipt path)
reviews:
disk evidence:    (path + hash, each tagged disk-verified|agent-claimed)
remaining:
exact resume:
```

---

## 6. guardrails

Concrete decisions for every item the skill requires, plus the five this program specifically needs.

### Concurrency

| Scope | Limit | Mechanism |
|---|---|---|
| Per PR, per lane | 1 in-flight attempt | `concurrency: {group: repair-<lane>-pr-<number>, cancel-in-progress: true}` for Lane A; `cancel-in-progress: false` for Lane C so a batch is never half-pushed |
| Codex worker, globally | 1 | keep the existing `group: codex-runner, cancel-in-progress: false` |
| Lanes in flight per repo | 2 (A + C), and **never** A + B on the same PR | dispatcher refuses the second dispatch |
| Local plane | serial queue, depth 1; **one `cursor-agent` process maximum** (G-36) | queue admission check |
| Local background workers | forbidden while free RAM < 8 GB (G-26); browser-using runs ≥ 6 GB; interactive non-browser ≥ 2 GB | pre-run guard; a refusal is `DEFERRED_RESOURCE` (re-queueable), not a terminal failure |

### Retry budget

- **2 attempts per classification per head SHA.** Attempt 2 runs only if attempt 1 changed the failure
  signature; an unchanged signature means stop, not retry.
- **3 attempts per PR per rolling 24 h**, all classifications combined.
- **0 code-changing retries for `infra/provider`, `flaky`, or `stale-context`** — those are re-runs or
  escalations, never patches.
- Per-run wall clock: 45 min (matches `codex-runner`'s `timeout-minutes: 45`). Exceeded = `FAILED_TO_RUN`.
- Every attempt writes `verify/<lane>/<run-id>/` before exiting, including on failure.

### Stop-on-no-progress

Compute a progress key per attempt: `sorted(failing_check_ids) + sha256(first_error_line_normalized)`.
If attempt *N+1*'s key equals attempt *N*'s → **stop `blocked`** and escalate to Lane D. Two-strikes
rule from the estate floor applies: after the second failed attempt on the same hypothesis, stop and
enumerate alternatives instead of trying a third variant.

Terminal statuses are exactly: `success`, `partial`, `blocked`, `FAILED_TO_RUN`. There is no
"probably fine". A budget-aborted, cancelled, or dormant gate is `FAILED_TO_RUN` and is never green.

### Stale head SHA

- Record `SHA_START` at dispatch; re-resolve immediately before any push. Mismatch → abort with no
  push, status `blocked`, reason `STALE_HEAD`, re-queue **once**.
- A check run whose `head_sha` ≠ `pr.head.sha` is `MISSING`, not `PASS` and not `FAIL`. Obsolete
  required contexts are a governance problem to report, never something to satisfy with code.
- Local analogue: re-read the artifact and compare its hash before repairing it; for the blueprint,
  verify the companion SHA-256 table before and re-pin it after. A repair computed against a stale
  revision is discarded.
- Grace window: allow ~60 s and one re-check before drawing an adverse inference from an absent
  artifact (transcript-flush lag is measured on this box).

### Diff size / file scope caps

| Lane | Files | Lines | Hard backstop |
|---|---|---|---|
| A — PR repair | ≤ 10 | ≤ 400 changed | `codex-runner` `max_changed_files` (default 40) aborts with no PR |
| B — coverage | ≤ 6 | tests unbounded; production ≤ 20 | same |
| C — debt | ≤ 15, one rule family, one directory | ≤ 500 | same |
| D — blueprint repair | only the unit's declared file list | exact patches only | reassembly diff reviewed against pinned hashes |

**Forbidden paths for every automated worker** (superset of the live `codex-runner` grep):
`.github/workflows/**`, `AGENTS.md`, `CLAUDE.md`, `.agents/agents.json`, `.agents/local.json`,
`.agents/secrets/**`, `browser-profiles/**`, any `.coverage-thresholds.json` threshold value,
`*.pem`, `.env*`, `id_rsa|id_ed25519|id_ecdsa|id_dsa`, `.git/**`, the Cursor MCP approval store, and
anything outside `/workspace` for Daria. Also: **never modify an unrelated dirty file.**

### Production edits vs test-only preference

Order of preference: (1) add or fix a test; (2) fix the defect the test exposes, minimally;
(3) behavior-preserving seam change ≤ 20 lines; (4) stop and escalate. Never lower a threshold, widen
an `omit`, add a coverage pragma, delete a test, mark a test skipped, or disable a check to reach green.
Never silently remove a feature or downgrade a capability to buy reliability — if a real trade-off
exists, present it and let the owner decide.

### Mutation authority

| Actor | May mutate | May never |
|---|---|---|
| `codex-runner` (CI) | code + tests in the target repo, within caps; branch + **draft** PR | merge; touch forbidden paths; run on any fork-triggerable event; print or write a credential |
| Copilot coding agent (fallback) | same, via its own PR | approve or merge its own PR |
| `autofix-models` (tier 2) | draft patch PR from a failed `main` run | be a gate; turn red when its credential is absent (it reports DORMANT) |
| Local Cursor agent, owner-present | local config + local files in scope, one step at a time with a recorded rollback | expanded Cursor MCP definitions while any non-core approval remains; browser live profile without an explicit per-run choice; commits (background/headless agents never commit — G-68) |
| Reviewers (any lane) | their own review file only | self-certify; review their own repair; waive a failed or absent receipt |
| Owner | everything, including overrides | — |
| Anyone | — | rotate credentials (**NEVER-ROTATE**, no proposals either), force-push, hard-reset, `--no-verify`, `--yolo` without per-run approval, make `agent-skills-toolchain` public |

Four decisions are **owner-only** and block the lanes that depend on them: G-12 engine choice
(acpx-only / LangGraph layer / isolated leaf, restored verbatim), single-owner R2 mode, the per-mode
RAM-guard table, and the tier/data-class taxonomy pick (Part 00 vs RISK). Workers escalate; they do
not decide.

### Flaky and provider-failure handling

- **Preflight first.** Every lane run starts by proving its worker credential and its required
  providers. Measured baseline: OpenRouter 402, Anthropic 401, OpenAI 401, Gemini 404;
  `COPILOT_PAT` absent; Basic Memory `Session not found`.
- **A missing credential produces a loud DORMANT and a clean exit, never a second red beside a real
  one, and never a silent skip** — exactly the pattern `autofix-models` already implements. Record
  `FAILED_TO_RUN` for the lane, not a pass.
- **No silent fallback.** At most one different-vendor fallback per run, visible and logged, never
  mid-tool-call, never a silent family change (G-8).
- **Multi-voice panels:** fewer than 3 genuinely independent voices ⇒ `core_panel_complete: false` ⇒
  verdict `ESCALATE`, never `PASS`. An agent panel is never relabelled as human independence.
- **Flaky:** a check that passes on an unchanged re-run at the same SHA is `flaky`; record it, do not
  patch it. Two flakes on the same check within 24 h ⇒ quarantine proposal to Lane D. Never gate a
  merge on third-party availability; live smokes are owner-run receipts with an age limit, not CI gates.
- **Memory writes:** while Basic Memory returns `Session not found`, memory persistence is **deferred,
  not complete**, and must not be reported as captured. Do not disable semantic search to buy
  reliability — fix it off the request path.

### Zero-touch vs human-approved merge

- **Human-approved merge is mandatory** for every lane in this program. Agent PRs are draft PRs.
- The **only** zero-touch path is the existing Dependabot auto-merge, and it stays gated behind the
  full required `quality` set. Do not add a second allowlist during closure; revisit only after a
  measured low-risk rule allowlist exists with data behind it.
- R-tier mapping: R0 (docs, advisory research, reversible local analysis) may clear its internal loop
  automatically once receipts pass. R1 (standard code merge) needs an independent human covering the
  final revision. R2 (auth, crypto, personal data, policy/CI, security controls) needs a second
  independent human — unavailable in a single-owner estate, so record
  `human_approvals.two_party_certification: not_achieved` with the compensating deterministic controls
  named, and escalate. R3 (deploy, publication, irreversible external action) needs an accountable
  actor distinct from the author. Overrides are explicit, time-bounded, reasoned, audited, and never
  granted by the actor that failed the gate.

### Audit trail, status reporting, evidence refresh

- Every attempt: `verify/<lane>/<run-id>/` with command, exit code, output, artifact hash, head SHA,
  classification, decision. GitHub-native surfaces (job summary, check-run output, PR comment,
  artifact) carry the same summary so the audit survives without the local box.
- Every claim carries provenance: `disk-verified` (writer re-read the artifact it claims) or
  `agent-claimed` (asserted, not re-read). Resume flows re-verify `agent-claimed` entries before
  building on them.
- The closure ledger is updated at **every** lane boundary — status, receipt path, remaining, exact
  resume command. A lane may not advance while the previous boundary is unwritten.
- **Evidence refresh cadence:** at each phase exit, add one derived, tool-neutral lesson (date +
  source class + reusable lesson + guardrail consequence + scope) to the relevant
  `quality-gate-automation-architect/references/*.md`. Derived summaries only — never raw transcripts,
  never secrets. Promote a pattern from note to live reference once it has changed behavior twice.
  Durable decisions also go to Basic Memory when it is healthy; while it is not, they stay in the
  project receipt and are marked deferred.

---

## 7. rollout_phases

Each phase has a disk-verified exit. No phase starts before the previous exit is disk-verified.

### P0 — Observe only (no mutation)

Enumerate the ruleset's required checks and map each to its producer job. Confirm the eight `quality`
jobs are the true producers and that no obsolete required context exists. Confirm retired DeepSource
and Codacy contexts are not required checks. Run the mcp-manager enforcement path in both locations and record
the numbers **without changing anything**. Dispatch `codex-runner` once in a read-only diagnostic task
to confirm the worker still authenticates and that the guard steps fire.
**Exit:** a written check→producer map, a retired-analyzer absence receipt, deployed↔SSOT coverage numbers,
and one green diagnostic worker run. Every line tagged `disk-verified`.

### P1 — Lane A on one repo

Enable PR repair for `agent-skills-toolchain` only. Answer the trigger question: either the owner
dispatches `codex-runner` per lane, or a scheduled dispatcher does — and if scheduled, it re-checks the
RAM guard and the single-`cursor-agent` lock before admitting anything, and it never merges. Add the
stale-SHA re-resolve step and the progress-key stop rule. Keep draft-PR-only.
**Exit:** one PR taken from red to green by a bounded attempt, with receipts, merged by the owner; one
deliberately induced `STALE_HEAD` abort proven to push nothing.

### P2 — Lane B (coverage) on mcp-manager

Propose the missing `.coverage-thresholds.json` for mcp-manager (owner-approved) encoding 100%
line+branch on non-GUI code plus the existing reasoned `omit`; until it exists every coverage claim is
`NOT-CHECKED`. Then run the ratchet, deployed **and** SSOT, and reconcile parity. This closes L1
steps 2–3.
**Exit:** thresholds file on disk, both suites pass with identical numbers, parity diff empty, no
threshold or `omit` changed.

### P3 — Lane C (active-analyzer debt)

Turn active opengrep/gitleaks/osv findings into batches, one tool × one rule family × one directory.
Burn down the L1 review's rule-shaped minors here — not in Lane A. Denylist enforced. Do not restore
DeepSource or Codacy.
**Exit:** at least two batch PRs merged by the owner with rule IDs and count deltas recorded; zero
unresolved critical/high findings in the L1 surface; remaining minors either fixed or explicitly
disproven with a receipt.

### P4 — Lane D: local-only closure (owner-present)

L1 steps 4–9 in the fixed order (freeze → pre-disable non-core → prove core-only → guarded attach-all →
restart → prove six → preset + refresh → LinkedIn off). L2 Daria: install/auth/sandbox, terminal locked
by default, non-Cursor agents off, boundary and escape tests fail closed, handoff without token values.
L4: pin Playwright MCP, dedicated persistent headless profile, per-run 3-way profile choice preserved,
no-focus smoke without touching owner Chrome, diagnostics UI re-verified, Avante security re-review.
**Exit:** each step has a receipt and a rollback command; every escape/secret test fails closed.

### P5 — Lane D: L3 blueprint repair loop

Settle the four owner decisions. Split the 25 blockers by file ownership. Repair in parallel per owner,
reassemble, re-pin hashes, then re-run feasibility, completeness, and scope with fresh reviewers on the
new revision. Repeat until all three PASS. Do not sample — the completeness reviewer explicitly
requires all 40.
**Exit:** three PASS verdicts on the same revision hash, plus deterministic 40/320/source/citation/
reconciliation lints green.

### P6 — Final evidence and steady state

Formal uncommitted security review, active local/GitHub deterministic gates, this
architecture review, council only for genuinely unresolved trade-offs, self-reflect candidates
presented for owner approval, final completion audit across L1–L5 against the seven-point completion
contract. Then steady state: Lane A on demand, Lane C weekly batch, Lane B on threshold drift, Lane D
for everything blocked, evidence refresh at each boundary.
**Exit:** every lane `SUCCESS`, or a genuinely external blocker with exact evidence and a resume command.

---

## 8. risks

| # | Risk | Why it is live here | Mitigation | Residual |
|---|---|---|---|---|
| R1 | **False green from a missing or obsolete required context** | A strict gate can stay red while tools are green, and a context with no run at head SHA looks absent rather than failed | `MISSING ≠ PASS` rule; P0 check→producer map; head-SHA equality assertion on every check run | Ruleset drift between P0 and later phases — re-map at each phase exit |
| R2 | **Blast radius of `danger-full-access` in the Codex job** | The worker runs with approvals and sandbox bypassed; only the guard step bounds it | Diff cap, forbidden-path grep, checksum-pinned gitleaks on the staged diff, draft-PR-only, `workflow_dispatch`-only, PAT scrubbed from `.git/config`, target `.codex/` removed before exec, cleanup on `always()` — none of which may be "simplified" | Prompt injection from repo content read mid-run; egress is audited, not blocked |
| R3 | **Provider outage masquerading as a code failure** | Four API providers currently fail auth; `COPILOT_PAT` absent; Basic Memory session errors | Mandatory preflight; `infra/provider` classification gets zero code-changing retries; DORMANT + clean exit instead of a red; no silent vendor fallback | Subscription-lane auth can expire mid-window (the commented-out token write-back is the known fix, still off) |
| R4 | **Local plane collapses under RAM pressure** | 2.49 GB free measured; subagents observed stalling; transcript-flush lag | Per-mode RAM guard; `DEFERRED_RESOURCE` instead of terminal failure; serial queue depth 1; idempotent resumable units; 60 s grace before adverse absence inference | Long local sessions still die; mitigated only by resumability |
| R5 | **Blueprint repair turns into prose-until-the-reviewer-stops-complaining** | 25 blockers, four of them needing owner decisions the artifact's §23 says must not be silently decided | Consultation lane, file-ownership split, escalate-don't-decide rule, fresh reviewers on a new revision hash, deterministic lints as the receipt | Reviewer disagreement after one rebuttal round → escalate, don't accumulate debate |
| R6 | **Cursor MCP expansion executed before the approval store is core-only** | 37 non-core approved IDs measured; attach-all is unsafe today | Hard boundary: no expanded write while any non-core approval remains; fixed step order; prove core-only with a process check before attach | Ordering violation by a well-meaning agent — the boundary is repeated in every prompt preamble |
| R7 | **Coverage theatre** | mcp-manager has no thresholds file, so any percentage is unanchored | `NOT-CHECKED` until the file exists; no threshold/`omit`/pragma edits; deployed↔SSOT parity | GUI `omit` remains a judgment call — it is reasoned and greppable, and must stay that way |
| R8 | **Zero-touch creep** | An auto-merge already exists and works, which makes a second one tempting | One allowlist only (Dependabot behind full required checks); draft PRs for agents; human merge mandatory | Owner may override — explicitly, time-bounded, audited |
| R9 | **Deferred memory reported as captured** | Basic Memory returns `Session not found` | Memory writes marked deferred; project receipts carry the durable record; capability stays enabled | Knowledge loss until the session issue is fixed off the request path |
| R10 | **Lane bleed** — debt or coverage work smuggled into a PR rescue | Historically the fastest way to make a review unreviewable | Classification is single-valued per attempt; caps per lane; batch metadata in every debt PR | Reviewer must reject mixed PRs; make that an explicit review checklist item |

---

## 9. validation_plan

Each drill has a pass condition that a green run alone cannot fake. Detector silence counts **only
after a known-broken control fires**.

| # | Drill | Method | Pass condition |
|---|---|---|---|
| V1 | **Canary red** | Introduce a deliberate lint error and a deliberate failing test on a scratch branch | Both the corresponding `quality` jobs go red and the classifier assigns exactly `lint` and `unit-test`. Only after this may a green run be trusted |
| V2 | **Scope-cap abort** | Dispatch the worker with a task that touches 41+ files | Run aborts with an explicit cap error and **no PR is opened** |
| V3 | **Forbidden-path abort** | Task that edits `.github/workflows/x.yml` | Abort, no PR, path named in the error |
| V4 | **Secret canary** | Plant a synthetic (non-real) token pattern in the proposed diff | gitleaks fails the run, no PR opened, value redacted in logs |
| V5 | **Stale-SHA drill** | Push a new commit to the PR while an attempt is mid-flight | Attempt exits `blocked/STALE_HEAD`, pushes nothing, re-queues once |
| V6 | **No-progress stop** | Feed a failure the worker cannot fix (e.g. missing external credential) | Two attempts maximum, identical progress key detected, `blocked` + Lane D escalation memo with a resume command |
| V7 | **Provider-outage drill** | Remove the worker credential in a scratch config | Lane reports DORMANT / `FAILED_TO_RUN` loudly, exits clean, produces **no** second red and **no** silent pass |
| V8 | **Deployed↔SSOT parity** | Run mcp-manager's enforcement command in both trees | Identical pass/fail and identical coverage numbers; any diff is a blocker |
| V9 | **Thresholds-absent behavior** | Run Lane B against a project with no thresholds file | `NOT-CHECKED` emitted and surfaced; no invented threshold, no silent pass |
| V10 | **Resume drill** | Kill a local unit mid-run | Restart resumes from the disk artifact, does not start from zero, and does not double-apply; `agent-claimed` entries are re-verified |
| V11 | **Cursor MCP order drill** | Attempt a guarded attach-all while a non-core approval is still present | Refused with the boundary cited, nothing written |
| V12 | **Daria escape tests** | Attempt host-path read, secret read, MCP reach, and write outside `/workspace` from inside Codeg | All four fail closed, each with a receipt |
| V13 | **No-focus browser smoke** | Run the persistent headless agent profile task | Completes without focus and without touching the owner Chrome profile; per-run 3-way profile choice still enforced |
| V14 | **Blueprint lint gate** | Run the deterministic 40-workflow / 320-heading / anchor / capability / phase / risk-factor / owner-grammar lints on the repaired revision | All lints green **and** all three reviewers PASS on that same revision hash |
| V15 | **Merge-authority audit** | Review the run log for the phase | Zero merges by any non-owner actor; every agent PR was a draft; no `--no-verify`, no force-push, no rotation, no threshold edit |
| V16 | **Ledger completeness audit** | Diff lane boundaries against ledger entries | Every boundary has an entry with status, receipt path, provenance tag, remaining, and exact resume |

**Gate on the program itself:** P6 may not be declared complete unless V1–V16 have receipts, every
lane's seven-point completion contract is satisfied, and every remaining item is either `SUCCESS` or a
named external blocker with evidence and a resume command. A budget-aborted drill is `FAILED_TO_RUN`,
which is not a pass.

---

*Design produced read-only on 29.08.2026 by the `quality-gate-automation-architect` workflow. No code
was edited, no commit was made, and no file other than this one was created or modified. Measured facts
are labelled as measured; everything unproven is labelled `NOT-CHECKED`.*
