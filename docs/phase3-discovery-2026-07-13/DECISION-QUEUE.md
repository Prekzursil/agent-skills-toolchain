---
title: DECISION-QUEUE
type: note
permalink: dqverify-repo-20261013/docs/phase3-discovery-2026-07-13/decision-queue
---

# PHASE-3 GRILL GROUND TRUTH — Harness / MCP / Doc / Config SSOT Consolidation

*Synthesis of the read-only census (docs + MCP + branches), the SOTA research (dotfiles-SSOT, MCP-concurrency, enforcement-hooks), and the 5-voice council (Config-Architect · Pragmatist · Security · Maintainability · Owner-Workflow-Fit). The 9 "threads" are the owner's program items. Everything below is decision-ready for an extensive one-decision-at-a-time grill.*

---

## 1. CURRENT-STATE MAP (per thread — what the mess actually is)

**HEADLINE (reframes everything): the enforcement layer already exists but is INERT.** The whole task-8 enforcement layer (`canonical_config_edit_guard`, `basic_memory_nudge`, `install.py --deploy`, the config_drift shape-fix) is **committed to the repo but NOT deployed to live `~/.agents/harness`** — verified by file mtime + byte/grep counts. Every running session executes the *pre-task-8* tree, so the edit-guard, memory-nudge and deploy command are source-only in an **unpushed** branch (`chore/enshrine-runtime-config`). *This is itself the exact silent divergence the program exists to kill, and nothing in the harness detected it.* Worse, it's a **three-way split**: repo HEAD ≠ repo working-tree (uncommitted task-9 changes) ≠ live. "Single source of truth" is currently **three** sources.

- **Thread 1 — MCP SSOT (enforced?):** `tools/mcp/canonical-mcp-servers.json` exists as intended truth, but is a hand-reconciled snapshot, not enforced. Live user scope (63 servers in `~/.claude.json`) has drifted **+22 / −1** vs canonical (42). Root cause of the resurfacing codacy/deepsource is **VERIFIED**: they ride `plugin:local-mcp-bridge:*` at user scope via `enabledPlugins` (27/26 occurrences) — a layer the drop (which edited `.mcp.json`) never touched and the `config_drift` gate doesn't watch. The one runtime drift sentinel (`config_drift`) fires only on a native `ConfigChange` event the harness's own code documents as *possibly-never-emitted* — a LOW-confidence load-bearing assumption.
- **Thread 2 — user-scope + one-folder:** `promote-mcp-userscope.ps1` exists but is **additive-by-default** (prune off), **manual** (no hook), **no write-guard** (any `claude mcp add`/plugin install re-drifts), and **blocked-on-restart** (a live session clobbers `~/.claude.json` on exit). `angr` is in canonical but never promoted. Multi-drive walk-up gap spawned a stale `D:/Research/.mcp.json` (40 servers, pre-reconcile bugs) + two stale D: promote-script clones.
- **Thread 3 — config/skill/hook centralization:** Skills are **three-way drifted** (192 VCS / 278 runtime vault / 75 daily) because they're **copied, not symlinked** — 86 vault skills are un-enshrined. `~/.agents/harness` is canonical-but-**never-git** (being enshrined for the first time today). Same rules/hooks tree is forked across ≥5 live roots. Copy-not-symlink means silent divergence unless a parity check guards it.
- **Thread 4 — cleanup-after-work:** **Near-total gap.** No runtime hook forces cleanup; `no-runtime-junk.yml` is post-hoc and tracked-only. Concrete backlog: ~25 identical momentstudio worktree audit copies, 33 worktree branches, 3 large stale snapshot trees.
- **Thread 5 — stale-branch reconciliation:** **Zero tooling.** 49 repos scanned; the scatter is severe — Reframe **56 branches**, toolchain **30**, plus ~35 CI-cleanup litter branches. Critically, real **unpushed work** hides in the noise: battlecats-toolkit (+142/+29/+6), ToolUniverse (+34), Reframe uncommitted sidecar features (beatgrid, broll_index, smolvlm2), insta-mcp 2FA flow, agentchattr launchers, mcp-manager.
- **Thread 6 — doc-reconciliation enforcement:** `RECONCILE-LOG.md` is manual; `basic_memory_nudge` is capture-not-reconciliation and undeployed. **Dual-truth:** `D:/basic-memory/harness/*` is the genuinely-current decision ledger (has supersede chains) while on-disk `.md` plans carry no supersede metadata — a file-tree read surfaces stale truth, recall surfaces current.
- **Thread 7 — scattered-harness-doc reconciliation:** **Not performed.** ≥10 loose top-level harness plans in `~/.claude/` root with no supersede markers or index (SOTA-HARNESS-RECS v1+V2, HARNESS-REMEDIATION, SELF-CALIBRATION, AGENTIC-PERFECTION [two divergent copies], MCP-SOTA-EXPANSION, RESEARCH-HARNESS, CAPABILITY-PROGRAM, **MEM0-PILOT-PLAN which is actively contradicted — mem0 = NO-GO — yet still reads live**). 16-doc design-research corpus orphaned post-implementation. 293KB toolkit-gap-analysis buried and ~7wks stale. Two concurrent, un-cross-linked harness-audit programs (gem-hunt-2026-07-12 + biomedical-harness-audit).
- **Thread 8 — change-documented+committed gate:** **No gate fails on uncommitted/unsynced harness change** — proven live now. `no-runtime-junk.yml` runs only on push, and the branch is unpushed, so it has **never actually run**. The `#1 ranked contradiction`: the SSOT repo's own `ast-harness-reconcile/CLAUDE.md` still documents retired **AgentBridge**/`get_budget` as the live mechanism.
- **Thread 9 — harness-works-perfectly verification:** **The keystone gap.** `install.py --check` reconciles settings.json hooks but **never compares the live `~/.agents/harness` tree vs `ci/harness`** — so the active repo-vs-live divergence is invisible to it and **failing silently right now**. Coverage ≠ integration: a gate can be CI-green, shadow-inert in modules, AND absent-from-live simultaneously — all three true today.

---

## 2. CROSS-COUNCIL CONVERGENCE + DISAGREEMENTS

### High-confidence CONVERGENCE (all 5 voices agree — treat as settled priors, not grill questions)
1. **Deploy task-8 + build a live↔repo tree-parity check = THE keystone.** All five rank this #1. The mechanism mostly *exists*; the program is "deploy, delete, run the script," not "adopt a framework."
2. **Reject chezmoi as a tool; borrow its lessons** (allowlist-not-denylist, state/config split, gitignore-first, `.gitattributes` eol rules, copy-over-symlink). Adopting a new deploy engine on a multi-SSOT disease is counter-goal; `install.py --deploy` already copies. (Research recommended chezmoi; **all 5 council voices overrode the research.**)
3. **Collapse to ONE canonical repo.** Two declared SSOTs (`agent-skills-toolchain` historic + `ast-harness-reconcile` new) *is* the disease. Fold into one.
4. **Fix the MCP drop at the plugin-bridge / user-scope layer** (`claude plugin disable … --scope user`) + widen the `config_drift` baseline to watch `enabledPlugins`. Pruning `.mcp.json` is the wrong layer and won't stop re-drift.
5. **Cut the `doc_drift` AST/tree-sitter code↔doc binding gate.** Wrong tool — the debt is doc-supersedes-doc (prose plans), not doc-lags-code; it over-fires. Ship `kb_supersede` (reuse existing `recall_index.py`) instead.
6. **Defer MCP HTTP-gateway migration to a separate program.** Genuinely right for the N×M process explosion (kernel panic / RAM-OOM), but it doesn't serve the config-SSOT goal and bloats blast radius.
7. **Copy, never symlink, for repo→live deploy** (Windows Git `core.symlinks=false` degrades a committed symlink to a plaintext file). The `skills.daily` symlink stays a *local uncommitted* artifact.
8. **All new gates ship SHADOW-first, advisory, fail-open, never auto-delete.** Deletion (branches, artifacts) stays a human decision — the `mcp_doctor reap` + `New-Item -Force` + MSYS save-wipe scars govern.
9. **Delete `D:/Research/.mcp.json` + the two D: promote-script clones** (pure drift sources); keep `D:/Backups/config/*` read-only.
10. **The doc sprawl is a one-time librarian sweep, not a hook.** Hooks only fence *new* mess; the 606-file backlog must be manually tombstoned.
11. **Fix the `ast-harness-reconcile/CLAUDE.md` AgentBridge contradiction before any push** (+ blast-radius §9b sweep for other AgentBridge refs).
12. **Anchor drift checks to SessionStart (definitely fires), not the unverified `ConfigChange` event.**

### Genuine DISAGREEMENTS (owner must decide)
- **D-α — How aggressive the MCP user-scope migration:** Pragmatist/Config-Architect/Security say "just run `promote … -PruneExtraUserServers -Yes` once, Claude-closed." **Owner-Workflow-Fit dissents**: on a 25-session box "Claude fully closed" is nearly never true, so this *keeps getting deferred* — proposes a **structural fix: generate to a launch-read `.mcp.json` Claude ingests at startup**, sidestepping the `~/.claude.json` clobber-race for all *future* generation (one-time prune still needs a closed restart). → **Real fork.**
- **D-β — Where the enforcement teeth go:** Maintainability + Pragmatist argue the interactive shadow gates are weak ("68 hooks already failed to prevent this") and want the **hard block in a pre-commit hook** + a **frontmatter-status lint**. Config-Architect/Owner-Fit favor keeping *everything* advisory-inject per anti-nag ladder, hard block only much later per-gate. → Owner must set the enforcement posture.
- **D-γ — Secrets at rest:** Security floats age/SOPS **if** anything must be encrypted (over git-crypt). **Owner-Fit cuts age/SOPS entirely** (lockout risk on a no-babysit box; gitignore + gitleaks suffices). → Decide: gitignore-only vs encrypt-at-rest.
- **D-δ — Which repo becomes the ONE:** consensus is "fold into `agent-skills-toolchain`" (CI-backed, historic canonical) and retire `ast-harness-reconcile` to a staging clone — but the *merge direction* and whether the reconcile repo is fully retired vs kept-as-staging is an explicit owner call.
- **D-ε — config_drift's runtime future:** Security wants to **empirically verify** whether Claude Code emits `ConfigChange` before trusting it; others say don't bother, just replace with a SessionStart poll. → Verify-then-keep vs replace-outright.

*(Note: the research's two marquee recommendations — chezmoi and the gateway — were both overridden by unanimous council. That itself is a strong signal: don't let the grill re-open them as primary.)*

---

## 3. TIERED DECISION-QUEUE (ordered; each: decision · options · recommendation+why · trade-off)

### TIER 0 — FRAMING (decide these FIRST; everything downstream depends on them)

**D0.1 — SSOT deploy model: symlink vs copy vs dotfile-manager.**
Options: (a) **copy** via existing `install.py --deploy`; (b) symlink farm; (c) adopt chezmoi.
**Recommend (a) copy.** Why: already built, Windows-safe (symlinks degrade to text files), state/config split already handled. Trade-off: copy *drifts silently* → **mandates the D0.4 parity check as its guardrail** (a copy model without parity detection is exactly today's failure).

**D0.2 — ONE canonical repo (kill the second SSOT).**
Options: (a) fold `ast-harness-reconcile` content into `agent-skills-toolchain`, retire the sibling; (b) make `ast-harness-reconcile` the SSOT, retire toolchain's overlap; (c) keep both (status quo — rejected by all).
**Recommend (a).** Why: `agent-skills-toolchain` is the CI-backed, historically-canonical checkout with `no-runtime-junk.yml`; `ast-harness-reconcile` is a this-session reconcile staging area. Trade-off: migration effort now (move `ci/harness`, manifests, canonical MCP json) vs. permanently entrenched dual-truth. **Highest-leverage framing decision — dual-SSOT guarantees drift.**

**D0.3 — Big-bang vs incremental rollout.**
Options: (a) incremental, **deploy-first** (parity check → then gates → then sweeps); (b) big-bang (build all gates + sweep + prune together).
**Recommend (a) incremental, deploy-first.** Why: the committed enforcement layer sits inert while a build-fest is tempting; the active silent divergence must be closed before anything new lands. Trade-off: more discrete steps/restarts vs. lower blast radius and each step independently verifiable.

**D0.4 — Doc-reconciliation scope.**
Options: (a) **full librarian sweep** (tombstone ~10 loose plans + 3 snapshot trees + 16-doc design corpus + 293KB gap-analysis, with supersede pointers to basic-memory) + convention + `kb_supersede` nudge; (b) minimal (fix only the AgentBridge contradiction + MEM0-PILOT); (c) hook-only (build enforcement, defer the manual sweep).
**Recommend (a).** Why: basic-memory already holds the healthy supersede chains; the on-disk debt is what makes a fresh session re-walk retired decisions. Hooks only fence *new* mess — the backlog needs manual retirement. Trade-off: an afternoon of `git mv`/archive now vs. continued census-pollution and stale-guidance competition.

**D0.5 — How aggressive the MCP user-scope migration (the D-α fork).**
Options: (a) one-time `promote … -PruneExtraUserServers -Yes` Claude-closed (status-quo mechanism); (b) **restructure to a launch-read `.mcp.json`** so future generation sidesteps the `~/.claude.json` clobber-race, + one-time closed prune for the current cleanup; (c) leave additive, just delete D: copies.
**Recommend (b).** Why: on a high-concurrency box the closed-restart requirement is why the prune "keeps getting deferred"; a launch-read target makes it runnable-live going forward. Trade-off: one-time restructuring effort vs. permanently un-runnable-in-workflow prune. (The initial cleanup prune still needs one closed restart regardless.)

**D0.6 — Adopt chezmoi / age-SOPS?**
Options: (a) **no — borrow lessons, keep `install.py`**; (b) adopt chezmoi now; (c) defer chezmoi to a Phase-4 (post-consolidation, only if a 2nd machine materializes).
**Recommend (a)/(c).** Why: adopting a deploy engine mid-consolidation adds a *fourth* truth root; the pain is drift-enforcement + clobber-race + parity, none of which chezmoi solves. Trade-off: forgo multi-machine bootstrap (a problem this single box doesn't have) — revisit only on a real fleet.

**D0.7 — Secrets posture (the D-γ fork).**
Options: (a) **gitignore allowlist + gitleaks pre-commit backstop only**; (b) also age/SOPS encrypt-at-rest for `auth.json`/`.credentials.json`.
**Recommend (a).** Why: age adds a lockout failure mode on a no-babysit box; ciphertext-in-history is permanent if the key ever leaks. Trade-off: secrets never committed even encrypted (stronger) vs. losing at-rest portability. **Non-negotiable regardless: default-deny allowlist + first-time gitleaks scan of the never-git `~/.agents/harness` before its first commit.**

### TIER 1 — MECHANISM (the "make it real" work)

**D1.1 — Deploy task-8 to live + add the live↔repo tree-parity check (KEYSTONE).**
Options: (a) deploy + hash-diff `~/.agents/harness` vs `ci/harness`, wired to **SessionStart** (read-only, safe live) + `/harness-audit`; (b) deploy only; (c) defer.
**Recommend (a).** Why: closes the active silent divergence and is the only check that would have caught "committed-but-undeployed." Trade-off: must deploy **atomically (temp-dir + rename), session-aware**, never hot-swap harness code under running sessions (session-scoping scar). Verify gates are *deployed and firing*, not just CI-green.

**D1.2 — Fix the MCP drop at the right layer.**
Options: (a) `claude plugin disable codacy/deepsource/… --scope user` (the `mcp-fleet-curation` skill already does this) + widen `config_drift` baseline to `enabledPlugins`/plugin-bridge; (b) re-prune `.mcp.json` (wrong layer — rejected).
**Recommend (a).** Why: VERIFIED root cause is the plugin bridge at user scope; also a supply-chain concern (cloud-quality servers execute at user scope, enabled-by-default). Trade-off: touches plugin config, not just MCP json.

**D1.3 — config_drift runtime trigger (the D-ε fork).**
Options: (a) replace with SessionStart + scheduled diff(live user-scope, canonical); (b) verify `ConfigChange` empirically, keep if emitted, else fall back; (c) trust as-is (rejected — may be permanently inert).
**Recommend (a), with (b) as a cheap parallel check.** Why: a drift check that may never fire is theater; SessionStart definitely fires. Trade-off: SessionStart is periodic not real-time.

**D1.4 — The 13 "legit-but-un-canonicalized" MCP drift-ins (EVPI-gated, owner-only).**
For each of `codex`, `github`, `meta-tool`, `mcp-graphql`, `scrapegraph`, `sentry`, `postgres`, `linear`, `notion`, `digitalocean`, `browserstack`, `apify`, `claude-code-mcp`: **PROMOTE-to-canonical-then-keep** vs **prune**. Confirmed-prune set (no decision needed): codacy, deepsource, sonarqube, codecov, deepscan, firecrawl, tavily, figma-rest, semgrep. Confirmed-add: `angr`.
**Recommend:** clear keeps = `codex` (fan-out MCP, intentional), `github`, `meta-tool`, `mcp-graphql`, `scrapegraph`; the rest keep-only-if-actually-used. **Stamp the keep/prune reason as per-server provenance metadata INSIDE the canonical json** (`_added`,`_why_kept`) — not a separate memory note that desyncs (that separation is exactly how the codacy drop-rationale got lost). Trade-off: a few minutes of per-server owner judgment vs. a silent wrong bet.

### TIER 2 — GATES TO BUILD (all SHADOW-first, `GATE_CONTRACTS`-registered, ledger-reusing)

**D2.1 — Which advisory gates to ship.** Consensus KEEP (cheap, reuse existing state): `artifact_hygiene` (Stop; mutation-ledger ∩ untracked ∩ not-gitignored ∩ not-scratchpad → inject, never delete), `kb_supersede` (near-dup via `recall_index.py` → §8 supersede nudge), `uncommitted_change` (Stop; tracked edits + dirty tree + no commit → inject). Consensus CUT: `doc_drift` (AST binding). Owner-decide (lean-minimal): `stale_branch` (SessionStart advisory, `merge-base --is-ancestor`, 90d, **exclude concurrent-session/mtime-today branches**, never `-D`), `scattered_doc` (new `*.md` outside canonical roots → nudge), `doc_required` (fold into existing `claim_warning`).
**Recommend:** ship the 3 KEEP + `stale_branch` + fold `doc_required`; hold `scattered_doc` until the sweep defines canonical roots. Trade-off: each gate is catalogue-tax until it proves useful — `GATE_CONTRACTS` fitness must be able to sunset non-firing ones.

**D2.2 — Enforcement posture / promotion path (the D-β fork).**
Options: (a) SHADOW→burn-in→ADVISE, ENFORCE only per-gate after proven precision, hard block lives in **pre-commit** not mid-session; (b) promote to ENFORCE faster.
**Recommend (a).** Why: promoting shadow→enforce too fast triggers the N-agent nag-flood across 50-100 fan-outs and gets the harness distrusted/disabled. Trade-off: slower teeth vs. trust preservation. **Couple `basic_memory_nudge`↔ledger `canonical_tree` stamp — deploy the two lanes together or the nudge is dead-on-arrival.**

### TIER 3 — ONE-TIME SWEEPS (human-reviewed; mostly reversible)

**D3.1 — Doc archive sweep:** move ~10 loose harness plans to `~/.claude/_archive/` with `SUPERSEDED-BY:` header → basic-memory permalink; **tombstone MEM0-PILOT-PLAN immediately** (actively contradicted); mark the 16-doc design-research corpus "implemented"; banner the 293KB gap-analysis; cross-link the two concurrent harness-audit programs (gem-hunt + biomedical). Reversible (move, not delete).
**D3.2 — Delete drift sources:** 3 stale snapshot trees (`_harness-trim-backup`, `skills-archived`, `skills.pre-agents-*`), ~25 momentstudio worktree audit copies, `D:/Research/.mcp.json` + 2 D: promote clones. Verify-then-delete.
**D3.3 — Stale-branch triage: SALVAGE FIRST, then prune.** Before any mass `git branch -d` of the [gone]/worktree litter (~90% clears via `git branch -d` + GitHub auto-delete-head-branches), **salvage the unpushed work**: battlecats-toolkit (+142/+29/+6), ToolUniverse (+34), Reframe uncommitted sidecar features, insta-mcp 2FA flow, agentchattr launchers, mcp-manager. **Never touch concurrent-session/today-mtime branches.**
**D3.4 — Fix `ast-harness-reconcile/CLAUDE.md`** AgentBridge/`get_budget` contradiction + §9b blast-radius sweep for other AgentBridge refs. Do before any push.

### NEW valuable directions discovery uncovered (NOT in the owner's original ask — surface in the grill)
- **N1 — Salvageable unpushed WORK (not just cleanup):** the branch census found real feature bodies at risk (battlecats +142, ToolUniverse +34, Reframe beatgrid/broll_index/smolvlm2 sidecar, insta-mcp 2FA). This is *value to rescue*, reframing thread-5 from "prune" to "salvage-then-prune."
- **N2 — Plugin-bridge supply-chain surface:** cloud-quality MCPs (codacy/deepsource) execute code at user scope, enabled-by-default, outside every watched surface — a security direction beyond the drift cosmetics.
- **N3 — Launch-read `.mcp.json` architecture** (D0.5b): a structural fix to the clobber-race that makes MCP generation runnable-live — a genuinely new capability, not in the ask.
- **N4 — Reconciliation ritual on an existing cadence:** fold tree-parity + merged-branch triage + stale-doc scan into the recurring gem-hunt sweep, so the whole thing doesn't decay again.
- **N5 — MCP HTTP-gateway consolidation** (deferred but real): fixes the N×M process explosion the owner has actually hit (kernel panic, RAM-OOM) — schedule as a separate program.
- **N6 — first-time gitleaks scan of `~/.agents/harness`** before it *ever* touches git history (never-scanned canonical tree = classic leak vector).
- **N7 — frontmatter-status convention + basic-memory-as-decision-ledger** as the durable anti-decay control (vs. more shadow gates).

---

## 4. SEQUENCING + RISK

### Recommended build order (owner-fit, endorsed by all voices)
1. **Deploy task-8 to live (atomic, session-aware) + parity check wired to SessionStart** — *without this the entire enshrinement re-drifts; the three-way split is happening now.* Keystone.
2. **Pick ONE repo (D0.2) — fold `ast-harness-reconcile` → `agent-skills-toolchain`, retire sibling.** Fix the AgentBridge CLAUDE.md (D3.4) before push. gitleaks-scan the harness tree first (N6).
3. **Fix the MCP drop at plugin layer (D1.2) + SessionStart drift-audit (D1.3).**
4. **Ship the advisory gates SHADOW (D2.1).**
5. **One-time human sweeps: SALVAGE branches first, then prune (D3.3); doc archive (D3.1); delete drift sources (D3.2).**
6. **MCP prune, Claude fully closed (D0.5 / Tier-1 cleanup).**
7. **Later, decoupled: MCP HTTP-gateway migration (N5).**

### Needs a Claude RESTART / all-sessions-CLOSED
- **`promote-mcp-userscope.ps1 -PruneExtraUserServers -Yes`** — MUST run with **all Claude closed** (a live session rewrites `~/.claude.json` from memory on exit and clobbers the prune). This is the single unavoidable closed-restart step; it lands `angr`, evicts the dropped cloud-quality family + firecrawl/tavily/figma-rest/semgrep, and ships the pending playwright + Kaggle env fixes. Adding a **live-process guard** to the script (refuse to run if any `claude` is up) is a mandatory safety add.
- **The parity check + SessionStart drift-audit are READ-ONLY** and run live — no restart needed. This is the deliberate design that keeps the fix runnable on a 25-session box.
- **Large-window note:** the grill/synthesis and any big fan-out benefit from the 900k/1M window, but no *deploy* step requires it; keep the window for the decision work, not the mechanical steps.

### Reversible vs. irreversible (blast-radius map)
- **Reversible (safe to do):** repo→live deploy (copy — redeployable to prior tree), doc archive sweep (move, not delete), all gate shipping (SHADOW = observe-only), git branch operations (reflog-recoverable), repo merge (git history).
- **Irreversible / dangerous (human-gated, §6/§9):**
  - **Secret exposure on first enshrine** of the never-git harness / 34.7GB `.claude` → default-deny allowlist + gitleaks; if any secret ever staged, **rotate, don't just delete** (§9b — compromised regardless of exposure duration). *Highest-severity risk.*
  - **`git branch -D` of unpushed work** (battlecats +142, ToolUniverse +34, uncommitted Reframe features) → salvage-verify first; never bulk-prune.
  - **Auto-delete of artifacts/branches** → advisory only; deletion is human. (`mcp_doctor reap` + `New-Item -Force` + MSYS save-wipe scars.)
  - **MCP prune / harness hot-swap while sessions run** → clobbers siblings / intercalates sessions → live-process guard + atomic session-aware deploy.

### Top residual risks
1. **Program becomes a build-fest and never deploys** — the committed enforcement layer stays inert while new gates accrete. Mitigation: deploy-first, parity-check before any new gate.
2. **A THIRD/FOURTH SSOT gets added** (chezmoi, or keeping both repos) — every parallel store *is* the disease. Mitigation: D0.2 + D0.6 resolved before any build.
3. **Deploy-parity blindness persists** — SSOT worthless if live≠repo and nothing checks it (failing silently now). Mitigation: D1.1 is non-negotiable and first.
4. **Enforcement nag-flood across fan-outs** — subagent-aware, per-session dedup, shadow-first, fail-open, ENFORCE only after burn-in.
5. **Lane-coupling silent-dead gates** — `basic_memory_nudge`↔ledger `canonical_tree` must deploy together.
6. **config_drift permanently inert** — verify/replace the `ConfigChange` trigger (D1.3); don't trust it as thread-1's only sentinel.