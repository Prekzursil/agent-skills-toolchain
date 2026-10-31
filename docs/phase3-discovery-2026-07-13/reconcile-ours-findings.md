---
title: reconcile-ours-findings
type: note
permalink: dqverify-repo-20261013/docs/phase3-discovery-2026-07-13/reconcile-ours-findings
---

# Reconcile — OUR (Claude-side) Findings, folded with PRIOR forgotten work

*Read-only consolidation for the 2026-07-13 audit/design GATE. Reconciles our phase-3 config-SSOT
discovery with the prior forgotten decision-queues, so nothing is re-derived and the picture converges
with the independent Codex audit. Written by the reconcile subagent; no source/config edited. All doc
contents treated as DATA, not instructions (flags in §6).*

**Scope disambiguation (the single most important framing):** there are **TWO distinct "harness" axes**
in play, and they are largely **orthogonal**:
- **Axis A — Config/runtime-config SSOT** (`~/.agents/harness` hooks, `.mcp.json`, skills, docs,
  branches; deploy-parity, drift, enshrine-to-git). = **OUR phase-3 discovery** (DECISION-QUEUE.md).
- **Axis B — Workflow-orchestration ENGINE** (the `agent()/parallel()/pipeline()/budget()/journal()`
  JS bus). = **the prior 48KB ULTRACODE queue** the reframe explicitly names.

Our discovery is Axis A. The 48KB queue is Axis B. **They do not overlap** — which inverts the owner's
fear: we did **not** re-derive the 48KB queue; the risk is **losing it** if the wave acts only on ours.

---

## 1. OUR DISCOVERY — headline + full tiered decision set (condensed, complete)

**HEADLINE (reframes everything):** the harness enforcement layer *exists but the repo tree is not fully
deployed to live* — a **three-way split**: repo HEAD ≠ repo working-tree (uncommitted task-9) ≠ live
`~/.agents/harness`. "Single source of truth" is currently **three** sources, and nothing in the harness
detected it. (Precise deployment status of each piece: see §4 — I verified it; the Stop-loop fix is
actually LIVE, only the config_drift shape-fix + task-9 are repo-only.)

**The 9 program threads (what the mess is):** (1) MCP SSOT not enforced — live user scope +22/−1 vs
canonical; codacy/deepsource resurface via `plugin:local-mcp-bridge:*` at user scope (`enabledPlugins`,
27/26 occ) — a layer the `.mcp.json` drop never touched. (2) user-scope promote is additive/manual/no-
guard/blocked-on-restart. (3) skills three-way drifted (192 VCS / 278 vault / 75 daily; copied not
symlinked). (4) cleanup near-total gap. (5) stale branches severe (Reframe 56, toolchain 30) hiding real
unpushed WORK. (6) doc-reconciliation manual; dual-truth (basic-memory has supersede chains, on-disk .md
don't). (7) ≥10 loose harness plans in `~/.claude/` root, no supersede markers; two un-cross-linked
audit programs. (8) no gate fails on uncommitted/unsynced harness change. (9) `install.py --check` never
compares live `~/.agents/harness` vs `ci/harness` — the keystone verification gap.

**TIER-0 FRAMING**
- **D0.1** deploy model → **copy** via `install.py --deploy` (Windows-safe; mandates D1.1 parity guard).
- **D0.2** ONE canonical repo → **fold `ast-harness-reconcile` → `agent-skills-toolchain`** (highest-leverage). *(CONFIRMED — §2)*
- **D0.3** rollout → **incremental, deploy-first** (close the active divergence before building).
- **D0.4** doc-reconciliation → **full librarian sweep** + `kb_supersede` nudge.
- **D0.5** MCP migration → **restructure to a launch-read `.mcp.json`** (sidestep the `~/.claude.json` clobber-race) + one-time closed prune. *(CONFIRMED — §2)*
- **D0.6** chezmoi/age-SOPS → **no** (borrow lessons, keep `install.py`; revisit only on a real fleet).
- **D0.7** secrets → **gitignore allowlist + gitleaks backstop only** (no age/SOPS lockout risk).

**TIER-1 MECHANISM**
- **D1.1 (KEYSTONE)** deploy task-8 to live + live↔repo hash-parity check wired to **SessionStart** (read-only, safe live) + `/harness-audit`; atomic temp-dir+rename, session-aware.
- **D1.2** fix the MCP drop at the **plugin-bridge layer** (`claude plugin disable … --scope user`) + widen `config_drift` baseline to watch `enabledPlugins`. (Pruning `.mcp.json` = wrong layer.)
- **D1.3** `config_drift` trigger → replace with **SessionStart poll** (the native `ConfigChange` event is documented *possibly-never-emitted* — a LOW-confidence load-bearing assumption); optionally verify-then-keep.
- **D1.4** the 13 legit-but-uncanonicalized MCP drift-ins (EVPI-gated owner call): clear keeps = `codex`,`github`,`meta-tool`,`mcp-graphql`,`scrapegraph`; confirmed-prune = codacy/deepsource/sonarqube/codecov/deepscan/firecrawl/tavily/figma-rest/semgrep; confirmed-add = `angr`. Stamp keep/prune reason as per-server provenance metadata INSIDE the canonical json.

**TIER-2 GATES (all SHADOW-first, GATE_CONTRACTS-registered, ledger-reusing)**
- **D2.1** ship: `artifact_hygiene` (Stop), `kb_supersede` (recall_index near-dup), `uncommitted_change` (Stop), `stale_branch` (SessionStart advisory, exclude concurrent/today-mtime, never `-D`); fold `doc_required` into `claim_warning`; CUT `doc_drift` (AST binding, wrong tool); hold `scattered_doc`.
- **D2.2** enforcement posture → **SHADOW→burn-in→ADVISE, ENFORCE per-gate only after proven precision; hard block in pre-commit not mid-session** (else N-agent nag-flood across 50-100 fan-outs). *(DEFERRED as build-wave — §2)*

**TIER-3 ONE-TIME SWEEPS (human-reviewed, mostly reversible)**
- **D3.1** doc archive sweep → `~/.claude/_archive/` with `SUPERSEDED-BY:` → basic-memory permalink; **tombstone MEM0-PILOT-PLAN immediately** (actively contradicted); cross-link the two audit programs.
- **D3.2** delete drift sources (3 stale snapshot trees, ~25 momentstudio worktree copies, `D:/Research/.mcp.json` + 2 D: promote clones). Verify-then-delete.
- **D3.3** stale-branch triage → **SALVAGE FIRST then prune**; never touch concurrent-session/today-mtime.
- **D3.4** fix the `ast-harness-reconcile/CLAUDE.md` AgentBridge contradiction + §9b blast-radius sweep (before any push).

**NEW directions surfaced (N1–N7, not in the original ask):** N1 salvageable unpushed WORK (battlecats
+142/+29/+6, ToolUniverse +34, Reframe sidecar beatgrid/broll_index/smolvlm2, insta-mcp 2FA); N2
plugin-bridge supply-chain surface (cloud-quality MCPs execute code at user scope, enabled-by-default);
N3 launch-read `.mcp.json` architecture; N4 fold reconciliation ritual into the recurring gem-hunt
cadence; N5 MCP HTTP-gateway consolidation (deferred, real — fixes N×M process explosion / RAM-OOM);
N6 first-time gitleaks scan of `~/.agents/harness` before it ever touches git; N7 frontmatter-status
convention + basic-memory-as-decision-ledger (durable anti-decay control vs more shadow gates).

**5 owner-disagreements (D-α..D-ε):** α how aggressive MCP user-scope migration (→ resolved by D0.5
launch-read); β where enforcement teeth go (pre-commit hard block vs all-advisory — → DEFERRED as
build-wave); γ secrets at rest (gitignore-only vs age/SOPS — → D0.7 gitignore-only); δ which repo becomes
the ONE + merge direction/retire-vs-staging (→ D0.2 fold into toolchain); ε config_drift's runtime
future (verify ConfigChange vs replace with SessionStart — → D1.3 replace).

---

## 2. GRILL-LOG owner-confirmed decisions (state as CONFIRMED)

- **D0.2 CONFIRMED-BY-OWNER** — fold `ast-harness-reconcile` → `agent-skills-toolchain` (owner: "do 1").
- **D0.5 CONFIRMED-BY-OWNER** — restructure to a **launch-read `.mcp.json`** (+ one-time closed prune for the current cleanup) (owner: "picked 1").
- **Q2 (rollout order) + Q3 (enforcement posture) DEFERRED** — these are BUILD-WAVE decisions the gate defers; they become recommendations in the migration plan, decided at wave-approval.
- **NO new discovery swarm** — reconcile existing work instead (owner-aligned, matches the reframe's anti-duplication). The 13-agent discovery was OWNER-COMMISSIONED, not rogue recursion.
- **The audit-gate REFRAME is ADOPTED (~85%)** — treat this as an audit/design GATE, not a build; converge to ≤3 owner decisions + a recommended wave, STOP before implementation. **3 caveats HELD (§7 hold-ground):** (1) not a "mock/smoke run" — 3 real peer-reviewed commits, reconcile ACTUAL state; (2) "started-a-swarm" self-criticism is a partial FALSE-POSITIVE (owner-commissioned); (3) the full typed-catalog/CAS/single-writer-lock RFC is likely GOLD-PLATING for a single-user harness — take the lessons (atomic deploy + pre-deploy backup + live↔repo parity + OFF→SHADOW→ADVISE→ENFORCE), right-size the machinery.

---

## 3. PRIOR-WORK OVERLAP VERDICT (the key deliverable)

Prior queues located on disk (paths absolute):

| Prior doc | Path | KB / date | Axis |
|---|---|---|---|
| **ULTRACODE-HARNESS-SOTA-DECISION-QUEUE** | `C:\Users\Prekzursil\.claude\gem-hunt-2026-07-12\ULTRACODE-HARNESS-SOTA-DECISION-QUEUE.md` | 48.2 / 2026-07-13 04:15 | **B (workflow engine)** |
| **CONSOLIDATED-GEM-DECISIONS-2026-06-30** | `C:\Users\Prekzursil\.claude\CONSOLIDATED-GEM-DECISIONS-2026-06-30.md` | 33.7 / 06-30 | A+domain |
| CONSOLIDATED-GEM-DECISIONS (older) | `C:\Users\Prekzursil\.claude\CONSOLIDATED-GEM-DECISIONS.md` | 16.5 / 06-29 | A+domain |
| **OPEN-THREADS** | `C:\Users\Prekzursil\.claude\OPEN-THREADS.md` | 11.9 / 06-29 | A/behaviors |
| **AGENTIC-PERFECTION-PLAN** | `C:\Users\Prekzursil\.claude\AGENTIC-PERFECTION-PLAN.md` | 13.6 / 06-29 | A/behaviors |
| Loose plans (already in D3.1 archive list) | `~/.claude/` root: SOTA-HARNESS-RECOMMENDATIONS(.+V2), HARNESS-REMEDIATION-2026-06-21, SELF-CALIBRATION-PLAN, MCP-SOTA-EXPANSION-PLAN, RESEARCH-HARNESS-PLAN, CAPABILITY-PROGRAM-PLANS, MEM0-PILOT-PLAN, PROACTIVE-PARTNER-PROGRAM, PRUNE-RECOMMENDATIONS-2026-06-30 | — | A/mixed |
| `biomedical-harness-audit` | **NOT FOUND on disk under `~/.claude`** | — | — |

> `biomedical-harness-audit` (named in our DECISION-QUEUE thread-7 as a concurrent program) has **no file
> under `~/.claude`**. Likely a basic-memory note or a Codex-side artifact (cf. the 8 Codex audit files
> under `Documents/Codex/2026-07-13/…` incl. `HARNESS-CONTROL-PLANE-AUDIT`). **Gap for the synthesis to
> close** — do not assume it's captured.

### 3A. ULTRACODE 48KB queue (Axis B) — VERDICT: **[STILL-OPEN — must fold in], ~0% re-derived**
The reframe explicitly names "prior 48KB queue" — this is it (48.2KB, dated 2026-07-13 04:15, ~hours
before our discovery). It is a **workflow-engine** roadmap: **117 findings, 11 lenses, 8 cross-lens
convergent gems, 5 genuine decisions.** Its content:
- **8 convergent gems (H1–H8):** H1 `budget.reserve()` sub-pools + graceful soft-exhaustion (9/11 lenses);
  H2 HITL checkpoint/suspend-and-resume (the "harness can't AskUserQuestion mid-workflow" fix); H3 typed
  `endReason`/drop-receipt on every null; H4 `gather()`/settled `parallel()`; H5 role-tiered model/effort
  routing defaults (largest avoidable cost); H6 per-agent timeout + stall heartbeat (barrier-deadlock
  escape); H7 `workflow_lint.py` stage-0 SHADOW; H8 bounded `loop()`/`refineUntil()`.
- **5 genuine owner decisions (D1–D5):** D1 resume cache model (opt-in cacheKey vs full content-addressed);
  D2 budget-exhaustion default (hard-throw vs soft-sentinel); D3 HITL depth (advisory queue vs safety-by-
  default irreversibility interception — an autonomous workflow can push to main *today*); D4 verification
  defaults vs opt-in patterns+lint; D5 patterns library surface (injected namespace vs cookbook).
- Plus ~50 tiered items (execution-consensus `bestOfN`, `panel()` de-biasing, seeded RNG, `mapReduce`,
  typed retry/Result, saga/race, per-phase token attribution, `patterns` namespace, `workflow_fitness.py`)
  and a 7-item anti-overfit ledger.

**Tag:** every ULTRACODE decision is **[STILL-OPEN — must fold in]** as a **separate Axis-B wave**. Our
Axis-A config-SSOT DECISION-QUEUE mentions **none** of it. Only faint philosophical kinship exists (both
use SHADOW-first / anti-overfit / cross-vendor independence), so ~0% is a genuine [DUPLICATE].
**LOSS RISK: MAXIMUM** — if the wave executes only our config-SSOT queue, the entire 48KB workflow-engine
program is orphaned despite the reframe naming it.

### 3B. CONSOLIDATED-GEM-DECISIONS (June gem-hunt, ~120 gems) — VERDICT: mostly **[ALREADY-SUPERSEDED]**, thin **[DUPLICATE]** slice
- **[ALREADY-SUPERSEDED — APPLIED]:** the TIER-0 native flips were executed 2026-06-30 (doc's own
  "TIER-0 applied" §): `permissions.deny` secret-reads, `honest` output-style, statusLine already-satisfied,
  effort xhigh. Do **not** re-proposal these.
- **[ALREADY-SUPERSEDED — BUILT as skills]:** a large fraction of the TOP-GEMS/domain items are now live
  skills (visible in the roster): capa-triage (TG.19), ghidriff (TG.20, via bc-update-survival), Vina/
  PoseBusters/Boltz-2 (compchem-validators/structure-based-screening), WhisperX/tracked-reframe (transcribe/
  reframe), execution-grounded-bon (TG.13), agent-as-judge (TG.12), diff-blind-test-synth, ui-audit +
  axe-core/odiff/Lighthouse (ST.46/47/50), design-studio. These are DONE, not open.
- **[DUPLICATE — we partially re-derived]:** the **MCP-prune / skill-dedup / doc-GC** slice —
  our D1.2/D1.4 echo PR.2 (PARK-COLD-MCPs) + PR.5 (UNINSTALL-DISABLED-PLUGINS); our D3.1 echoes PR.8
  (GC-SUPERSEDED-PLANNING-DOCS) + PR.3 (CUT-MEM0-PILOT); our D2.1 SHADOW-gates echo TG.6 (shadow-hook A/B).
  Our versions ADD the plugin-bridge root cause + launch-read target, so it's partial re-derivation of the
  *action*, not the *mechanism*.
- **[STILL-OPEN]:** unbuilt harness-reliability gems — **GEPA prompt evolution (TG.9), sleep-time/idle
  compute (TG.11), Calibration-Brier ledger (TG.1), uncertainty-gated escalation (TG.8), GEPA-as-miner,
  passive usage-telemetry prune (TG.7)**. Not in our discovery. Modest loss risk.
- **Dead-ends to NOT re-walk (verified refutations):** TG.16 "dispatch.py double-runs the 8 PreToolUse
  hooks" is **REFUTED** (runs alongside, no double-run); ACH-in-wildcard hypothesis **FALSE**; mem0/OpenMemory
  **NO-GO**. Carrying these forward prevents re-derivation.

### 3C. OPEN-THREADS.md — VERDICT: **[STILL-OPEN — must fold in], the "never-forget" register**
This is literally the owner's anti-forgetting doc ("the user's #1 stress is discussed-then-postponed ideas
vanishing"). Contains active/queued programs our config-SSOT discovery does **not** touch:
**PROACTIVE-PARTNER capability** (semantic body-level skill/tool router, EVPI-gated AskUserQuestion intent-
hook, USER.md grows-with-you, background dreaming, adopt llmcouncil); **UI/UX QUALITY overhaul** (Reframe/
momentstudio/Webcoder — no dead buttons/dupes); **MEDIA/VIDEO consolidation** (watermark removal); **BN
autonomous harness**; **ToolUniverse/Schrödinger expansion**; plus BC leftovers and the radare2-MCP -32000
known-issue (do NOT re-diagnose). **LOSS RISK: HIGH** — none of this is in our queue; it is the canonical
backlog the owner most fears losing.

### 3D. AGENTIC-PERFECTION-PLAN.md — VERDICT: mixed; contains our program's **ANCESTOR** + **[STILL-OPEN]** reasoning-spine
- **The direct ancestor of our whole SSOT program:** item **#9 "AGENTS.md is physically 3 DIVERGENT files
  (~/.codex vs ~/.claude vs ~/, stale) — single-canonical + hash-drift tripwire (NOT symlinks)"** and the
  **project-identity resolver** (5-Reframe-shard / 3-momentstudio-shard fragmentation). Our Thread-3 (config/
  hooks forked across ≥5 live roots) + D0.1 copy-not-symlink + D1.1 parity check are the **generalized,
  expanded continuation** of this 2026-06-29 open thread → **[DUPLICATE/continuation]** at the concept level,
  but our deploy-parity keystone + enshrine-to-git are new.
- **[ALREADY-SUPERSEDED — BUILT]:** TIER-1 durability spine (bg-registry, memory-spool, wire-check),
  tool-result-sentinel, honest-signaling — largely shipped (the harness modules exist).
- **[STILL-OPEN]:** the ROUND-2/ROUND-3 **reasoning-spine gems** — **Discipline-Forge (the "moat"/CAPSTONE),
  TMS auto-retraction for RE, Smith-predictor dead-time compensation, file-centric world-model ledger,
  hold-your-ground dissent, backtracking executor, capability-gap tool-FORGE**. Not in our discovery.
  Modest-to-high loss risk (some are the owner's most-valued "AGI-adjacent" ideas).

### 3D-summary — how much of OUR discovery re-derived prior work
**Calibrated estimate (~25–30% conceptual overlap, ~0% with the 48KB queue):** of our ~24 config-SSOT
decisions, roughly **5–7 substantially echo prior work** — SHADOW-first gates (TG.6), MCP-disable-at-user-
scope (PR.2/PR.5 + mcp-fleet-curation skill), doc-GC + tombstone-MEM0 (PR.8/PR.3), single-canonical-config
(AGENTIC-PERFECTION #9), consolidation-GC. The **keystones are genuinely NEW**: deploy/live↔repo parity
(D1.1), the plugin-bridge root cause (N2/D1.2), launch-read `.mcp.json` (N3/D0.5), salvage-first branch
framing (N1/D3.3), and the three-way-split diagnosis. **So our discovery is NOT a wholesale re-derivation
of any single prior queue** — it continues+expands the June "3-divergent-files" thread and re-derives a
minority of the June harness-reliability slices; it is fully orthogonal to the 48KB ULTRACODE queue.

**Prior decisions we are at risk of LOSING if the wave acts only on our new queue (ranked):**
1. **The ENTIRE 48KB ULTRACODE workflow-engine queue** (H1–H8 + D1–D5 + ~117 findings) — MAXIMUM risk; the reframe named it, our queue ignores it. **Must be carried as a separate Axis-B wave.**
2. **OPEN-THREADS backlog** (proactive-partner, UI/UX overhaul, media consolidation, BN harness, ToolUniverse) — HIGH risk; it is the never-forget register.
3. **AGENTIC-PERFECTION ROUND-2/3 reasoning-spine** (Discipline-Forge, TMS auto-retraction, Smith-predictor, world-model, hold-your-ground) — modest/high risk.
4. **June unbuilt harness gems** (GEPA, sleep-time compute, Calibration-Brier ledger, uncertainty-gated escalation) — modest risk.
5. **Verified dead-ends** (TG.16 double-run REFUTED; ACH-wildcard FALSE; mem0 NO-GO) — must ride forward so they aren't re-walked.

> **Reconciliation note:** our D3.1 plans to *archive* the loose `~/.claude/` plans with supersede pointers —
> but **archiving ≠ folding-in open decisions.** The ULTRACODE queue is NOT even in D3.1's archive list
> (it's newer, under `gem-hunt-2026-07-12/`, dated 07-13). Recommend the wave explicitly (a) spin the 48KB
> queue into its own Axis-B workflow-engine program, and (b) before tombstoning any June doc, extract its
> STILL-OPEN rows into basic-memory so the sweep doesn't bury live gems.

---

## 4. Stop-loop fix status — VERIFIED (refines the task's "may be inert" framing)

**Claim under test:** our commits carry a Stop-loop fix (populate `event.trigger` from `stop_hook_active`
+ a `ClaimWarning` re-entrancy guard); discovery found "enforcement committed-but-NOT-deployed-to-live,"
so the fix *may be inert on live*.

**Fresh-context filesystem verification (read-only grep + mtime; §1b/§7 hold-ground with evidence):**

| Evidence | Finding |
|---|---|
| `~/.agents/harness/modules.py` (LIVE) | `ClaimWarningModule` @1563; **re-entrant Stop guard @1591–1598** reads `event.trigger ∈ {stop_hook_active,true,1}`; opt-in one-shot Stop-block @1639–1644. mtime **2026-07-13 02:15:41**, 1838 lines / 96,769 B. |
| `~/.agents/harness/adapters.py` (LIVE) | @124–125 maps host `stop_hook_active` → `event.trigger`. |
| **`~/.agents/harness/backups/modules.py.bak-loopfix-20260713-021353`** | a **"loopfix" backup dated 2026-07-13 02:13:53**, immediately before the live modules.py mtime (02:15) — a smoking gun that the loopfix WAS applied to live at ~02:15. |
| `ci/harness/modules.py` (REPO) | same fix present, @1708/@1736 — but 2025 lines / 107,553 B, mtime **05:28:58** (≈3h newer, **+187 lines** vs live). |
| `config_drift`-family refs | LIVE modules.py = **6**; REPO modules.py = **14** (+ `install.py` reconciler + tests 34 vs live 6). |

**Verdict (confidence ~90%, evidence = file grep + mtime + the loopfix backup):**
- **The Stop-loop fix is DEPLOYED and ACTIVE on live — it is NOT inert.** The re-entrancy guard + the
  `stop_hook_active`→`event.trigger` mapping are physically present in live `modules.py`/`adapters.py`,
  with a dedicated `loopfix` backup taken minutes before the live mtime.
- **What IS committed-but-not-deployed** (validating the DECISION-QUEUE headline, which named it precisely)
  is the **broader delta**: the **config_drift SHAPE-FIX** (`f351403`, 14 vs 6 refs), the **task-9 codex
  build** (uncommitted), and the full enforcement additions (`install.py --deploy` reconciler + expanded
  tests) — the repo tree is +187 lines / ~3h ahead of live.
- **Therefore, refine the parent framing:** "the fix may be inert" is **too pessimistic for the Stop-loop
  fix specifically** — that fix is live. The live tree is an **intermediate** state (task-8-partial +
  loopfix), NOT a pristine "pre-task-8" tree; the true undeployed delta is the config_drift shape-fix +
  task-9. **This is the exact point to reconcile against Codex's Stop-loop analysis** — if Codex reports
  the loopfix inert, that conflicts with the live filesystem here (loopfix backup + present in live).
- **Residual uncertainty (~10%):** I verified *presence + structural identity* of the guard via grep, not
  a full byte-diff of the ClaimWarning logic block; a subtle behavioral drift between the live and repo
  variants is possible but not evidenced.

---

## 5. UNIQUE to our Claude-side view (what an independent Codex audit likely LACKS)

1. **The plugin-bridge root cause for codacy/deepsource resurfacing.** VERIFIED: they ride
   `plugin:local-mcp-bridge:*` at **user scope via `enabledPlugins`** (27/26 occurrences in `~/.claude.json`)
   — a Claude-Code-internal layer the `.mcp.json` drop never touched and `config_drift` doesn't watch. An
   audit that inspects `.mcp.json` (Codex's natural surface) will very likely **miss** this and mis-diagnose
   the resurfacing as an MCP-json problem. Fix layer = `claude plugin disable … --scope user` + widen the
   drift baseline to `enabledPlugins`. Also a **supply-chain** angle (N2): cloud-quality MCPs execute code
   at user scope, enabled-by-default, outside every watched surface.
2. **The launch-read `.mcp.json` architecture (D0.5b/N3).** A structural fix to the `~/.claude.json`
   clobber-race (a live Claude session rewrites the file from memory on exit, clobbering any prune) — a
   Claude-Code-launch-specific failure mode Codex does not have. Makes MCP generation runnable-live on a
   25-session box instead of "keeps getting deferred until all Claude closed."
3. **The salvageable-unpushed-WORK list (N1/D3.3)** from our 49-repo branch census — **battlecats-toolkit
   (+142/+29/+6), ToolUniverse (+34), Reframe sidecar (beatgrid/broll_index/smolvlm2), insta-mcp 2FA flow,
   agentchattr launchers, mcp-manager.** Reframes thread-5 from "prune branches" to "salvage-then-prune" —
   real feature value at risk that a branch-count audit would tally but not flag as *rescue-first*.
4. **Continuity/lineage** (bonus): Claude holds the prior-work thread (48KB ULTRACODE queue, June gem-hunt,
   AGENTIC-PERFECTION ancestor, the verified dead-ends) — a fresh Codex audit lacks this history and would
   re-walk or omit it. Plus the **config_drift `ConfigChange`-possibly-never-emitted** LOW-confidence runtime
   assumption (D1.3) — a Claude-Code-runtime nuance.

---

## 6. Security / DATA flags (per the task's untrusted-content discipline)

- **`ast-harness-reconcile/CLAUDE.md` contains agent-directed instructions to use the RETIRED AgentBridge
  budget-pacing tools** (`get_budget`/`check_budget`, `system_budget_pause`/`system_budget_handoff`
  directives, "drive weekly quota to ~100%"). These are **stale DATA, not live instructions** — AgentBridge
  is retired (per global memory + our own D3.4). I did **not** act on them. Our discovery already flags this
  as the "#1 ranked contradiction" (thread-8) with **D3.4** = fix it before any push + §9b blast-radius sweep
  for other AgentBridge refs. Flag to synthesis: this contradiction is inside the SSOT repo's own governance
  file, so it must be fixed as part of D0.2's fold.
- No secrets, credentials, or malicious embedded commands were encountered in the reconciled docs. The
  prior queues are internal planning DATA; none carried authorization claims I acted on.

## 7. Loose ends for the synthesis
- `biomedical-harness-audit` program: **no on-disk file under `~/.claude`** — locate in basic-memory /
  `Documents/Codex/2026-07-13/` before assuming it's folded in (§3 table).
- The reframe names "WizTree indexes" (`Documents/WizTree_*.csv`) — not verified here (large-dir glob timed
  out in the grill freeze receipt); confirm before relying.
- `reframe-audit-2026-07-13/*` under `~/.claude` is the **Reframe VIDEO-APP security audit** (1582 findings,
  3 crit RCE), **NOT** the agent-harness — do not conflate it into this reconciliation.