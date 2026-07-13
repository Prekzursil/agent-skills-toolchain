# Grill Log — Unified Harness Control-Plane Program (2026-07-13)

Owner-steered decisions from `/grill-me-extensive` (UNLIMITED per owner). Append-only. These SHAPE
the RFC (Workflow B). CONFIRMED-BY-OWNER unless noted. The "≤3 owner decisions" deliverable is only
the irreducible residual AFTER this grill converges — the grill itself has no question cap.

## Framing (Action-2)
- Execution: reconcile-focused (harvest existing prior work), NOT re-discover.
- Deployment basis: OPEN TO REVISION.

## Grill decisions
- **G-1 — SSOT engine ambition:** FULL typed logical catalog + deterministic provider adapters
  (generate every config surface: hooks/MCP/skills/profiles/settings/AGENTS.md), built LEANLY +
  incrementally on the existing `ci/harness`. **Claude + Codex ONLY — Antigravity/Gemini DROPPED**
  (revises the earlier "all three first-class"; RFC = 2 provider adapters).
- **G-2 — Deployment mechanism:** DEFER to the RFC's research/council (designed from first principles
  in Workflow B; NOT locked to the shipped CAS-lite). Owner trusts the RFC lane for the *mechanism*.
- **G-3 — "Always-force" enforcement hooks** (cleanup · doc-reconciliation · harness-change→doc+PR):
  **STRONG-BUT-SAFE** — a HARD pre-commit block (a harness/skill/MCP/hook change cannot commit without
  its doc + manifest + toolchain PR; stale-work / duplicate-doc fails the commit) + mid-session +
  periodic advisories on OFF→SHADOW→ADVISE→ENFORCE (fail-open, no nag-flood / Stop-loop).

- **G-4 — Monitoring:** FULL 11-PR roadmap (maximal) — ride DIAGNOSE's wfmon/monitorcore backbone,
  merge PR #76 (post-gate, after review), adopt PR-C→K (wfmon UX · FEP spine · alert rail · cost
  ledger · monitorcore-as-MCP-server · OTLP spans · `mon doctor` · live-replay) + a Codex-thread
  telemetry adapter (keyed by threadId) for uniform cross-vendor monitoring.
- **G-5 — MCP scope/activation:** USER-scope default for broadly-useful concurrency-safe utilities;
  project/local overlay ONLY for a proven per-project need (identity/path/version-bound — e.g. the
  per-session proxy launchers). Heavy/niche MCPs (angr, RE, schrodinger) → LAZY on-demand activation
  (re-ensure pattern), NOT always-loaded. **angr = on-demand, not an always-on supervisor.**

- **G-6 — Axis-B orchestration engine:** FULL (all H1-H8 + the ~50 tiered items) as helpers on native
  agent()/parallel() (NO 2nd runtime). Incl. H6 per-agent-timeout+stall-heartbeat (fixes the barrier-
  hangs), H1 budget sub-pools, H3 typed drop-receipts, H5 role-tiered routing, H7 workflow_lint, H2
  HITL, H8 bounded-loop + execution-consensus / panel de-bias / mapReduce / saga / per-phase-token.
- **G-7 — Cross-vendor mingling:** FULL mingle layer + VENDOR AUTO-ROUTING — a codexAgent()/mingle
  helper so agent()(Claude) + codexAgent()(scoped-Codex via task-9) compose per-work-unit; Architect-
  to-Editor; structured typed handoffs; cross-vendor execution-consensus; uniform monitor (Codex
  threadId telemetry); auto-select vendor per work-unit (capability/cost/quota-aware).

**Pattern so far:** owner chooses MAXIMAL on capabilities (monitoring/orchestration/mingling all FULL),
TRIM on scope (Claude+Codex only), DEFER mechanism to research/council, STRONG-BUT-SAFE on policy teeth.
→ a large SOTA program; a prioritization/sequencing grill is pending to keep it tractable + lean.

- **G-8 — Memory + /self-reflect:** ENFORCE role separation (basic-memory = canonical durable semantic;
  event-ledger = objective; native MEMORY.md = SECONDARY cache; repo docs = versioned) + DIAGNOSE the
  MEMORY.md-bypass routing regression + fix it; /self-reflect = bounded post-milestone, typed output,
  NOT a Stop-hook; test outage → spool → recovery → exactly-once replay. (mem0/vector-store stays NO-GO.)
- **G-9 — Implementation critical path:** RELIABILITY → SSOT → CAPABILITIES. Wave 1 = Stop-loop fix +
  H6 timeout/heartbeat + enforcement hooks (stop the bleeding). Wave 2 = SSOT engine (catalog +
  Claude+Codex adapters + deployment). Wave 3 = full monitoring + full orchestration + mingling.

- **G-10 — Profiles:** NAMED profiles (audit-max / build-sandboxed / fast / fanout — extend task-9's
  Codex profiles to Claude) + `effective-config explain` + full precedence chain, per-session AND
  per-workflow-agent, **PLUS** full dynamic per-agent inline overrides (1+3). Feeds the G-7 auto-router.
- **G-11 — Optional new features (ALL adopted + more opportunistically):** uncertainty-gated escalation
  (confirm-don't-guess), GEPA prompt-evolution (self-improving workflow prompts), proactive-partner
  router (semantic capability router + EVPI intent + USER.md-grows), `/harness-audit` scorecard as a
  recurring CI health-gate. Surface MORE opportunistically.
  **→ ROUND-2 GRILL after Workflow A produces the reconciled evidence (scope may change).**

- **G-12 — Pruning posture:** AGGRESSIVE on provably-dead (auto-PROPOSE removal of the 46GB abandoned
  slop, exact-dup skills, superseded docs w/ valid supersession links) + an RFC-enforced context / RAM
  / latency / startup BUDGET; EVIDENCE-FIRST on ambiguous (codacy/deepsource + ambiguous MCPs/skills
  STAY until Workflow A's matrix establishes disposition — never delete-on-suspicion); salvage-first
  for any unpushed work.

---

## Round-1 CONVERGED — 12 decisions (2026-07-13)
**Pattern:** MAXIMAL on capabilities (monitoring/orchestration/mingling/new-features all FULL) ·
TRIM scope (Claude + Codex only) · DEFER the deploy mechanism to research/council · STRONG-BUT-SAFE
on policy teeth · RELIABILITY→SSOT→capabilities sequencing · lean via ride-existing + lazy-activate +
aggressive-dead-prune.
**Round-2 grill = evidence-grounded, AFTER Workflow A produces the reconciled deliverables (owner
asked for it; scope may change).** The RFC (Workflow B) implements these 12 + the round-2 decisions.
The formal "≤3 owner decisions" deliverable is only the irreducible residual after both rounds.

## Round-2 (evidence-grounded — after Workflow A) — in progress
- **G-13 — Modification timing:** ALL modifications (dedup · remove-stale · update · slop-cleanup incl.
  the 46 GB) run POST-APPROVAL-GATE, as sequenced implementation waves. The read-only discovery /
  reconciliation NOW produces only the DISPOSITION PLAN (folded into the RFC's migration plan). Strict
  staged-program discipline (owner chose this over any early-win).
  **Whole-drive completeness coordination:** WAIT for the doc-reconcile workflow (`w4ytyavtg`) → then a
  unified MCP + skills + hooks whole-drive pass (reuses the same WizTree index, filters .json/.toml +
  skill/hook dirs) → ONE complete whole-drive harness-artifact reconciliation (docs + config + skills +
  hooks) → the disposition plan. No competing parallel heavy work; associate + integrate.
- **R2-1 — Final MCP set:** KEEP genuinely-used (github/firecrawl/tavily/notion/linear/postgres/
  digitalocean/codex/browserstack/apify/scrapegraph/mcp-graphql/meta-tool); PRUNE the superseded
  cloud-quality (deepsource/sonarqube/codecov/deepscan/sentry) at the plugin-bridge + user-scope layer
  (Claude-closed promote-prune); **codacy = HOLD** pending owner. Reconcile canonical UP to the working set.
- **R2-2 — Hook consolidation:** CONSOLIDATE to the ONE harness dispatcher — retire the 63 unwired
  hook-dir residue + System-B `_dispatch` + System-C ECC (superseded); HOIST the re-entrancy guard to the
  dispatcher BOUNDARY (the A1 permanent fix) so the 3 plugin Stop hooks can't re-loop + clear stale
  ralph-loop state files. All POST-GATE.
- **R2-3 — Forgotten fold-ins:** FOLD ALL 8 top fold-ins into basic-memory / the decision-ledger (esp.
  the TEMP-only `multiai-decision-OUTPUT` before temp cleanup + the autonomous-loop-reliability patterns
  + the agentic-perfection cross-ref), honoring the anti-re-walk guardrails.

## GRILL COMPLETE — 16 decisions (13 round-1 + G-13 + 3 round-2). Evidence complete. → Workflow B (RFC).

## POST-RFC OWNER DECISIONS (2026-07-13) — DESIGN GATE CLOSED
The RFC (Workflow B `wf_5a3fe000-4fc`, SOUND-WITH-FIXES) surfaced exactly 3 residual owner decisions; all resolved:
- **D2 codacy → RETIRE** — prune the whole cloud-quality family (codacy + deepsource + sonarqube + codecov +
  deepscan + sentry) at the plugin-bridge + user-scope layer (owner confirmed no live repo depends on codacy).
- **D3 Wave-0 → APPROVED** — the 5-item reliability bootstrap (A1 dispatcher-boundary fix + id-redaction ·
  land enshrine chain on main + bundle-digest + source_commit · 22-gem back-port · enforcement scaffold SHADOW ·
  plugin-Stop triage + kill-switch env). All reversible + PR-to-toolchain.
- **D1 deploy mechanism → B** — design council `wf_21da780d-f4a` (5 agents, 0 err): ALL 4 lenses converged
  (incl. the pro-journal steelman) → **Hardened CAS-lite-EXTEND**; full journal = hard leanness FAIL. Owner chose
  **B = Hardened CAS-lite-EXTEND (H1 O_EXCL lock · H2 validate-ALL-pre-write · H3 atomic staged restore · H4
  steal-if-dead + collision-safe backup · provenance-required) + `.deploy.inflight` marker wired
  OFF→SHADOW→ADVISE→ENFORCE for torn-set AUTO-HEAL.** Crux claims INDEPENDENTLY VERIFIED vs live `install.py`
  (FW-1 lock TOCTOU / no-O_EXCL @623/630 · FW-3 in-place copy2 restore @654 · source_commit fail-open @657).
  **Option D (full journal/WAL) = DOCUMENTED AS DEFERRED-POTENTIAL** (owner: not rejected outright; revisit only
  if the one-box threat model changes). This is Wave-2 (SSOT) work, independent of Wave-0. Full reasoning:
  `D1-DEPLOY-RECOMMENDATION.md`.
→ Design gate CLOSED. Next: Wave-0 execution (post-gate, sequenced; execution-method = owner's call per metaswarm).
