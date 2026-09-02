# Read-Only Census — Harness / Config / Agentic-Workspace Docs Scattered Across Disk

Scope covered: `C:/Users/Prekzursil/.claude/**` (606 md files enumerated), `.agents/**`, `source/agent-skills-toolchain/**`, `source/ast-harness-reconcile/**` (the in-flight reconcile repo), `Documents/GitHub`, `Documents/**`, `Documents/codex` (empty), `D:/**` (basic-memory vault + gem-wave-b + pr-b-clone), plus basic-memory `search_notes`/`recent_activity`. NOTHING modified. SKILL.md operational files are counted only as a *duplication* signal, not itemized — the focus is analysis / plan / research / audit / decision docs.

Dates are LastWriteTime (may reflect a git checkout touch, not authorship — e.g. everything under `ast-harness-reconcile` shows `2026-07-13 03:17`, the clone time).

---

## AREA 1 — Harness SOTA recommendation / audit / remediation lineage (the core sprawl)
A ~2-month chain of "audit the harness → recommend fixes" docs, each superseding the prior, **all left loose with no supersede markers or index**.

| Path | Topic | ~Date | Status |
|---|---|---|---|
| `.claude/SOTA-HARNESS-RECOMMENDATIONS.md` | harness SOTA recs v1 | 06-20 | **superseded** (by V2, same day) |
| `.claude/SOTA-HARNESS-RECOMMENDATIONS-V2.md` | harness SOTA recs v2 | 06-20 | stale/superseded by later programs |
| `.claude/HARNESS-REMEDIATION-2026-06-21.md` | remediation actions | 06-21 | stale |
| `.claude/SELF-CALIBRATION-PLAN.md` | calibrated-silence/router tuning | 06-26 | partially-implemented (see `reference_harness_drift_fix`) |
| `.claude/AGENTIC-PERFECTION-PLAN.md` | agentic-perfection program | 06-29 | superseded by toolchain `docs/agentic-perfection/AGENTIC-PERFECTION-PLAN.md` (14KB, 07-07) — **two copies, divergent dates** |
| `.claude/RESEARCH-HARNESS-PLAN.md` | research harness | 06-28 | stale/partial |
| `.claude/MEM0-PILOT-PLAN.md` | mem0 pilot | 06-28 | **contradicted** — mem0 ruled NO-GO (`reference_prune_sweep_and_mem0_verdict`, `project_mcp_reduction`) yet plan still present |
| `.claude/harness-audit-2026-06-30/` (PLAN, harness-audit-check, mcp-consolidation, deep-research-upgrade, skill-consolidation, search-providers) | 6-file harness audit | 06-30 | stale (superseded by 07-03/07-05/07-12 sweeps) |
| `.claude/audit-2026-07-05/` (FORENSICS-full 89KB, FIX-PLAN 32KB, RED-TEAM 23KB) | forensic harness/security audit | 07-05 | partially-actioned |
| `.claude/harness-gemhunt-2026-07-03/` (DECISION-LOG 19KB, HYGIENE-AUDIT, MCP-PROGRAM-PLAN) | gem-hunt harness decisions | 07-03 | superseded by 07-12 gem-hunt |
| `.claude/gem-hunt-2026-07-12/ULTRACODE-HARNESS-SOTA-DECISION-QUEUE.md` (48KB) + `-GRILL-LOG.md` + `HARNESS-CRITICAL-STAGING-RESULTS.md` + `staging/**` | current SOTA harness sweep + staged bundles | 07-12/13 | **CURRENT / active** |
| `.claude/harness-audit-2026-06-30/` + `.claude/commands/harness-audit.md` + `.opencode/commands/harness-audit.md` | `/harness-audit` command (2 copies) | 06-30 | dup |
| `D:/basic-memory/harness/*.md` (Phase-3 SOTA Consolidation 07-13, Config-drift audit 07-13, Harness drift+memory-chain gap 07-13, Reconcile committed 07-13, + 10 older) | semantic harness decision chain | ongoing | **CURRENT** (the authoritative decision ledger) |

## AREA 2 — Agentic-workspace architecture / capability program
The "how should the whole workspace be shaped" question, split across ≥8 docs in 3 trees.

| Path | Topic | ~Date | Status |
|---|---|---|---|
| `.claude/AGENTIC-WORKSPACE-ARCHITECTURE.md` | final workspace architecture ("~90-95% already built, STOP building") | 06-11 | headline still cited in MEMORY.md; likely **still-valid but stale** |
| `.claude/WORKSPACE-CURATION.md` + `project_workspace_curation.md` | plugin/MCP de-bloat curation | 06-11 | active reference |
| `.claude/CAPABILITY-PROGRAM-PLANS.md` | capability assimilation program | 06-11 | superseded by basic-memory `capability-assimilation-program-2026-06-11` |
| `source/agent-skills-toolchain/docs/plans/2026-06-10-optimal-agentic-workspace-design.md` (15KB) | optimal workspace design | 06-10 | foundational, stale |
| `.../docs/plans/2026-06-11-workspace-design-v1.md` + `-workspace-knowledge-base.md` | workspace v1 + KB | 06-11 | foundational, stale |
| `memory/project_optimal_workspace.md`, `project_unified_mcp_gateway.md` | workspace/gateway notes | 06-10/11 | reference |
| `D:/gem-wave-b/docs/plans/*` (identical 2026-06-10/11 set) | **third copy** of the above plans | 07-13 (checkout) | duplicate tree |

## AREA 3 — MCP fleet / config audit + no-drift architecture
The single "what MCPs, consolidate them, keep config from drifting" topic fragmented across ≥12 docs + 9 memory notes.

| Path | Topic | Status |
|---|---|---|
| `.claude/mcp-audit-2026-07-03/` (9 files: PLAN 21KB, migration, updates, media-consolidation, sota-mgmt, duplications, social-consolidation, new-gems, HANDOFF) | biggest MCP audit | superseded-in-part |
| `.claude/MCP-SOTA-EXPANSION-PLAN.md`, `MCP-FLEET-IMPROVEMENT-DECISIONS.md` | MCP expansion/decisions | stale |
| `.claude/mcp-manager-ux-proposal-2026-07-06.md`, `compute-mcp-build-plan.md`, `cloud-hub-compute-research-2026-07-07.md` | mcp-manager + compute MCP | partial/built |
| `source/agent-skills-toolchain/docs/plans/2026-06-10-unified-cross-ai-mcp-architecture-design.md` (23KB) + `-implementation-plan.md` (26KB) | unified cross-AI MCP | foundational |
| `.claude/_config-backups/mcp-consolidate_2026-06-16.../REVERSAL-MANIFEST.md`, `.claude/mcp-servers/README.md` | consolidation backup | archive |
| memory notes: `reference_mcp_nodrift_architecture`, `reference_mcp_live_toggle_verdict`, `reference_mcp_stub_repair`, `reference_mcp_reap_parentaware_fix`, `ram_oom_mcp_diagnosis`, `mcp_fleet_state`, `project_mcp_fleet_expansion`, `project_mcp_reduction`, `feedback_mcp_enabled_state`, `feedback_mcp_state_preservation` | 10 MCP memory notes | mixed (some superseded) |
| `ast-harness-reconcile/tools/mcp/canonical-mcp-servers.json` (per RECONCILE-LOG) | **NEW canonical MCP inventory** | CURRENT source-of-truth |

## AREA 4 — Reconciliation repo `ast-harness-reconcile` (the in-flight enshrinement — THIS session's work)
Newly created 2026-07-13 to be the versioned source-of-truth for live `~/.agents` + `~/.claude` config. Sibling agents (harness-fix, harness-review, mcp-reconcile, skills-enshrine) are actively working it.

| Path | Topic | Status |
|---|---|---|
| `RECONCILE-LOG.md` | append-only drift-audit trail; documents the 07-13 centralization | **CURRENT / authoritative** |
| `README.md` (19KB), `AGENTS.md` (13KB), `QUALITY-CHARTER.md`, `LEADERBOARD.md`, `JOBMON_DESIGN_GRILL.md` | repo governance | current |
| `CLAUDE.md` (8.8KB) | **STALE/CONTRADICTORY** — still documents AgentBridge + `get_budget`/`check_budget` budget-pacing as the live multi-agent mechanism | see Problem #1 |
| `docs/claude-toolkit-gap-analysis-2026-05-28.md` (**293KB**) | foundational toolkit gap analysis | stale (~7 wks) but downstream-referenced |
| `docs/SESSION-RECONCILIATION-2026-06-06.md` + `-2026-06-10.md` | prior reconciliation sessions | historical |
| `docs/codex-*`, `guides/codex-invocation.md`, `codex-monitor-reconcile.md` | codex fan-out setup | current |
| `skills/SKILLS-MANIFEST.md` (30KB), `skills-claude-only/MANIFEST.md`, `skills/DEPLOYED-MANIFEST.json` | enshrined skill manifests | current |

## AREA 5 — Gem-hunt / self-improvement sweeps (parallel, unreconciled)
| Path | Topic | ~Date | Status |
|---|---|---|
| `.claude/gem-hunt-2026-07-12/**` | ultracode harness SOTA gem sweep + staging bundles | 07-12/13 | CURRENT |
| `Documents/Playground/biomedical-harness-audit/**` (BIO-MCP-HARNESS-AUDIT 60KB, HARNESS-IMPROVEMENT-QUEUE-STAGED 37KB, -DESIGN, -IMPLEMENTATION-PLAN, HARNESS-CONTRACTS, BENCHMARK-SPEC, batches/) | **SEPARATE** biomedical harness audit + improvement queue | 07-12 | CURRENT but **not cross-linked** to the gem-hunt queue → Problem #4 |
| `source/agent-skills-toolchain/docs/agentic-perfection/` (CHANGELOG 30KB, OPEN-THREADS 12KB, PROACTIVE-PARTNER-PROGRAM, AGENTIC-REPAIR-RELIABILITY 9.7KB) | agentic-perfection program | 06-29/07-07 | active-ish |
| `.claude/harness-gemhunt-2026-07-03/DECISION-LOG.md` | earlier gem-hunt decisions | 07-03 | superseded |
| skills: `gem-hunt`, `workspace-gem-hunt-2026-07-12`, `uiux-tooling-consolidation-2026-07-12` | sweep drivers | — | active |

## AREA 6 — Design-tooling research corpus
| Path | Topic | ~Date | Status |
|---|---|---|
| `.claude/design-research/` (16 docs: ai-design-tools, design-systems-sota, code-figma-roundtrip, figma-mcp-tools, claude-design-vs-figma, methodology, eval-rubric, wildcard, DESIGN-SKILLS-BUILT, DESIGN-SKILLS-AND-EVAL, DESIGN-WORKFLOW, FIGMA-SETUP, reframe-audit/) | design tooling deep-research | 06-30 | **superseded** by shipped design-studio/ui-audit skills + `uiux-tooling-consolidation-2026-07-12`; kept as loose research, no "implemented" marker |

## AREA 7 — Behavior contract / rules / governance
| Path | Topic | Status |
|---|---|---|
| `.claude/CLAUDE.md` + `AGENTS.md` + `rules/common/*` (agents, hooks, windows-shell, static-analyzer) | live behavior contract | **CURRENT / canonical** |
| `.claude/_harness-trim-backup-2026-06-05/` (full `rules/` tree ×12 langs + project-CLAUDE.md 17KB + global-CLAUDE.md) | **stale full backup of the rules tree** | archive-clutter |
| `.claude/skills-archived-2026-06-11/` (~40 SKILL.md) + `.claude/skills.pre-agents-20260401-062109/` (~90 files incl. 100KB+ AGENTS.md security packs) | two large stale skill snapshots | archive-clutter |
| `source/agent-skills-toolchain/agent-self/config/rules/` + `ast-harness-reconcile/agent-self/` | **more copies** of the same rules tree | duplicate |

## AREA 8 — App-plan/audit payloads polluting the workspace (not harness, but scattered & duplicated)
| Path | Topic | Status |
|---|---|---|
| `Documents/GitHub/momentstudio-fix/.claude/worktrees/**/UX_IA_AUDIT.md` + `ARCHITECTURE.md` | **~25 identical worktree copies** of one audit | orphaned worktree clutter |
| Reframe `PLAN-P1/P2/P4`, `WU-R0-EVAL-HARNESS`, `PHASE8-SOTA-MANIFEST` across `Documents/GitHub/Reframe`, `Reframe-wt-codeql`, `reframe-ui-redesign-1782065564`, `.claude/agent-worktrees/agent-1722514260/docs/` | Reframe plans replicated in ≥4 trees | duplicate |
| `.claude/reframe-audit-2026-07-13/` (findings_bundle 765KB, findings_high 163KB, REPORT) | Reframe Codex audit (app, not harness) | current, correctly scoped |

---

# Ranked reconciliation problems (worst first)

**1. CONTRADICTION — the newly-declared source-of-truth repo ships a stale governance doc.** `ast-harness-reconcile/CLAUDE.md` still describes **AgentBridge** + `get_budget`/`check_budget` budget-pacing as the live Claude↔Codex mechanism. Global `~/.claude/CLAUDE.md` and MEMORY.md state AgentBridge is **RETIRED (Windows-broken)**, replaced by `codex mcp-server` (fan-out) + `mcp_agent_mail` (live channel). The repo meant to END drift is itself carrying the single most out-of-date governance claim. High-confidence (~90%) this needs a rewrite before the repo is pushed.

**2. Superseded-but-present harness-recommendation lineage in `~/.claude/` root.** ≥10 loose top-level harness plan/audit/recommendation docs spanning 06-11 → 07-13 (SOTA-HARNESS-RECOMMENDATIONS + V2, HARNESS-REMEDIATION, SELF-CALIBRATION-PLAN, AGENTIC-PERFECTION-PLAN, MCP-SOTA-EXPANSION-PLAN, MCP-FLEET-IMPROVEMENT-DECISIONS, RESEARCH-HARNESS-PLAN, MEM0-PILOT-PLAN, CAPABILITY-PROGRAM-PLANS) with **no supersede markers, no index, no "done/superseded" status**. A fresh session re-reading any one would re-walk retired decisions. `MEM0-PILOT-PLAN` is actively *contradicted* (mem0 = NO-GO) yet still reads as a live plan.

**3. Quad+-forked skills/hooks/rules/plans trees — canonical is ambiguous.** The same skill/hook/rule/plan content lives in ≥5 live roots: `~/.claude/skills.daily`, `~/.claude/.agents/skills`, `~/.agents/skills`, `~/source/agent-skills-toolchain/skills`, `~/source/ast-harness-reconcile/skills`, `D:/gem-wave-b`, `D:/pr-b-clone`. Example: `ui-audit` SKILL.md + `critique_rubric.md` appears in ≥6 locations at 3 different sizes/dates (21.9KB `.agents` vs 30.8KB `skills.daily` — **divergent, not just copied**); `workspace-hooks/AGENTS.md` in ≥4. Memory says `~/source` toolchain is the historic canonical checkout, but RECONCILE-LOG now claims `ast-harness-reconcile` is source-of-truth — the two authorities are unreconciled.

**4. Two concurrent "harness audit → staged improvement queue" programs, not cross-linked.** `gem-hunt-2026-07-12/ULTRACODE-HARNESS-SOTA-DECISION-QUEUE` (+ D: Phase-3 SOTA Consolidation note) and `Documents/Playground/biomedical-harness-audit/HARNESS-IMPROVEMENT-QUEUE-STAGED` (37KB) + `-IMPLEMENTATION-PLAN` were both produced 07-12 in different trees with overlapping scope (harness contracts, benchmark spec, staged fixes). Risk of double-implementing or conflicting stages. No index ties them.

**5. MCP truth split across ≥12 docs + 10 memory notes with one just-created canonical.** The MCP inventory/consolidation/no-drift question is fragmented (mcp-audit-2026-07-03/9-files, harness-audit mcp-consolidation, unified-cross-ai-mcp plans ×2, MCP-SOTA-EXPANSION, MCP-FLEET-IMPROVEMENT-DECISIONS, mcp-manager-ux-proposal, + 10 memory notes several superseded). `ast-harness-reconcile/tools/mcp/canonical-mcp-servers.json` is now the intended single truth, but the dozen prose docs that predate it remain and still read as authoritative.

**6. Three large stale snapshot trees inflate `~/.claude` and every search.** `_harness-trim-backup-2026-06-05/` (full rules tree + project/global CLAUDE.md), `skills-archived-2026-06-11/` (~40 skills), `skills.pre-agents-20260401-062109/` (~90 files incl. two 100KB+ security AGENTS.md). These duplicate the entire live rules/skills hierarchy and are indistinguishable from live content without knowing the naming convention.

**7. Design-research corpus (16 docs) orphaned post-implementation.** The 06-30 design deep-research is superseded by the shipped design-studio/ui-audit skills and the 07-12 uiux-tooling-consolidation, but sits as loose research with no "implemented/superseded" pointer, so it competes with the shipped skills as apparent guidance.

**8. `claude-toolkit-gap-analysis-2026-05-28.md` (293KB) is a buried, ~7-week-stale keystone.** It's the foundational gap analysis many downstream plans reference, now deep in `ast-harness-reconcile/docs`, with no freshness note — unclear whether still authoritative or itself superseded by the later audits.

**9. Dual-truth: on-disk docs vs the basic-memory semantic vault.** `D:/basic-memory/harness/*` is the genuinely CURRENT decision ledger (Config-drift audit, Reconcile committed, Phase-3 SOTA, drift+memory-chain gap — all 07-13), yet the same facts also live in on-disk `.md` plans that lack the memory notes' supersede metadata. Recall surfaces current truth; a raw file-tree read surfaces stale truth. The two are not linked (files don't reference their memory permalink and vice-versa).

**10. Orphaned worktree/app-plan duplication.** ~25 identical `UX_IA_AUDIT.md`/`ARCHITECTURE.md` copies under `momentstudio-fix/.claude/worktrees/**` and Reframe plans in ≥4 trees are stale agent-worktree residue — not harness docs, but they dominate any recursive census and bury the real analysis docs.

---
## Notes / gaps
- `Documents/codex` exists but is **empty** (no md docs).
- Claude scratchpad/temp under `AppData/Local/Temp/claude/**` was NOT walked (ephemeral, session-scoped) — low value, excluded by design.
- `D:/gem-wave-b/` and `D:/pr-b-clone/` are full mirror-clones of the toolchain/hooks trees (Wave-B staging) — add another duplication layer if promoted.
- basic-memory `main` project is the healthiest reconciliation surface (supersede chains present); the on-disk `.md` sprawl is where the reconciliation debt actually lives.

