---
title: B-doc-reconciliation-COMPLETE
type: note
permalink: dqverify-repo-20261013/docs/audit-design-2026-07-13/b-doc-reconciliation-complete
---

# B — Whole-Drive Harness/Agentic Doc Reconciliation (FINAL)

**Deliverable:** Workflow B FINAL — consolidated whole-drive doc reconciliation.
**Mode:** READ-ONLY (active-work freeze). Every "retire / tombstone / fold / delete" below is a
**finding**, never an applied change. Every source file was read as **UNTRUSTED DATA**; no embedded
instruction was executed.
**Date:** 2026-07-13. **Author:** B-consolidation subagent.
**Companion machine-readable registry:** `B-doc-registry-COMPLETE.json` (this file's evidence).
**Consolidates:** `B-doc-clustermap.md` (377 clusters) · `B-reconcile-0..5.json` (46 top clusters) ·
`A5-doc-registry.json` (loose `~/.claude` corpus + MCP + basic-memory ledger) · `A0-wholedrive-census`.

---

## 1. Coverage statement — proving this is exhaustive

**This is a whole-drive pass, not a sampled one.** WizTree indexed the **entire C: and D: MFT**;
both full CSVs were streamed row-by-row (**12,677,705 rows**: C 7,037,366 + D 5,640,339), corroborated
within **4 rows** of Codex's independent index (12,677,701). No sub-tree was skipped at scan time —
exclusions are applied as *filters*, not scan boundaries.

| Axis | Value |
|---|---|
| **Drives** | C: (898 GB used / 6.16 M files) · D: (3591 GB used / 5.15 M files), WizTree 4.31, 2026-07-13 05:56 / 06:04 |
| **Named roots** | `~/.claude` `~/.agents` `~/.codex` `~/.gemini` `~/source` `D:/Research` `D:/Tools` `D:/agent-monitor` (+ whole-MFT keyword net beyond them) |
| **Keyword net** | cond1 dir-contains `harness\|agent\|claude\|codex\|skill\|hook\|mcp\|workflow\|gem-hunt\|reconcile\|audit`; cond2 core `+agentic\|gemini\|monitor\|orchestrat\|ultracode\|grill\|council\|self-reflect\|dispatcher\|decision-queue`; cond2 wide `decision\|rfc\|gem\|research\|analysis\|plan\|design\|spec\|proposal\|roadmap\|memory` |
| **Exclusions (filters)** | `node_modules · .venv/venv · site-packages · __pycache__ · *cache* · dist/build/target · vendor/vendored/third_party · .git-internal(roots kept) · .cargo/.rustup/go-pkg-mod · .next/.nuxt/.svelte-kit/.pnpm/.yarn`. Model weights excluded by the md/txt/rst extension filter. **Secrets never opened.** |
| **Doc union (md+txt+rst)** | **59,250** (.md 51,610 · .txt 7,329 · .rst 311) |
| **Clusters** | **377** — top **46 explicitly reconciled** (all clusters ≥123 docs + the harness-relevant mid-tier); ~331 tail clusters (1–7 docs each) rolled up by class |
| **Excluded (vendored/cache/build)** | 83,704 |

### Delta vs the 8823 census

| | value |
|---|--:|
| Prior census `harness_md` | **8,823** |
| Delta (.md) | **+42,787** (union .md 51,610) |
| Delta (all docs) | **+50,427** (union 59,250) |

**The +50,427 delta is NOT newly-discovered harness research.** The prior 8,823 was a *narrow
harness-keyword `.md`* count; the union re-admits the whole-drive doc population. ~99% of the delta is
**non-harness bulk** the narrower count excluded and the union re-includes:

- vendored plugin/skill **marketplace caches** (cl-2 ~29k md, cl-16, cl-26, cl-9, cl-10),
- per-session **temp scratchpads + tool-result transcripts** (cl-0, cl-1, cl-8 session bulk, D:/claude-projects-archive tail),
- **OCR page-dumps** (cl-11 branica, cl-27 PhoneAudit) and license/README boilerplate,
- **full-repo clones + worktree graveyards** (cl-3 13.2 GB, cl-7, cl-52, cl-55, gem-wave-b/pr-b-clone).

A0 §0.4 refines it precisely: **~8,800 harness-keyword `.md` exist, of which 5,552 sit outside any
canonical repo** — and on verification those 5,552 resolve to the *same* project-graveyards, clones,
and vendored trees, **not** lost private research. **Net genuinely-forgotten harness value surfaced by
this exhaustive pass = a small, bounded set (~33 docs; §4).** That is the honest headline, consistent
with the standing verdicts (`harness_health_verdict`, `ultracode_sweep_queue`): the workspace is
**bloat-bound and ~90-95% built, not capability-starved**. *(Confidence: HIGH — row-count corroborated;
cluster classifications structural + disk-verified; "forgotten intent" MEDIUM per A0.)*

---

## 2. Canonical-owner registry (one owner per subject) + supersession links

The recurring pathology this reconcile fixes: **truth scattered across many partly-correct files with
no `SUPERSEDED-BY` markers**, so a fresh session re-walks retired decisions. Below, one owner per
subject; full rows in `B-doc-registry-COMPLETE.json` → `doc_owner_registry`.

### Governance (behavior contract + repo CLAUDE.md set)

| Subject | Canonical owner | Supersession / flag |
|---|---|---|
| Global harness guidance | `~/.claude/CLAUDE.md` | budget block DEPRECATED-in-place (OK, marked) |
| Cross-tool behavior contract §1-§11 | `~/.claude/AGENTS.md` | **3 physically-divergent copies** (`~/.codex` vs `~/.claude` vs `~/`) — AGENTIC-PERFECTION #9, the Axis-A ancestor; verify hash-parity |
| metaswarm workflow + gates | `~/CLAUDE.md` | correctly DEFERS multi-AI to global (good one-owner pattern) |
| Codex behavior contract | `~/.codex/AGENTS.md` | synced to parity 2026-07-11; verify drift |
| ast-reconcile repo gov | `source/ast-harness-reconcile/CLAUDE.md` | **FIXED** (Wave-0): now "AgentBridge is retired" |
| toolchain repo gov | `source/agent-skills-toolchain/CLAUDE.md` | ⚠️ **STALE-CONTRADICTION**: still prescribes retired AgentBridge; auto-loads in-repo (see §3/§4) |

### MCP configuration (the two-SSOT drift)

- **Live SSOT (one owner):** `~/.mcp.json` — the rendered config Claude ingests.
- **Two COMPETING render-sources:** `agent-skills-toolchain/tools/mcp/canonical-mcp-servers.json` (44,
  only-in: exa/figma-rest/firecrawl/tavily) **vs** `ast-harness-reconcile/tools/mcp/canonical-mcp-servers.json`
  (43, only-in: agent-mail/angr/biomni-hub). 7-name symmetric diff → **D0.2 must MERGE, not just pick.**
- **Stale drift:** `D:/Research/.mcp.json` (+5 bak siblings) + byte-identical `D:/gem-wave-b` /
  `D:/pr-b-clone` clones → retire/regenerate-read-only.
- **Canonical MCP architecture doc:** `agent-skills-toolchain/docs/plans/2026-06-10-unified-cross-ai-mcp-architecture-design.md`
  (updated 2026-07-06) — Axis-A MCP tasks should **UPDATE this in place**, not rewrite fresh.

### Program / trail (active)

`RECONCILE-LOG.md` (append-only drift trail) · `~/.agents/harness/installed.json` (live deploy receipt)
· `docs/phase3-discovery-2026-07-13/{DECISION-QUEUE, AUDIT-DESIGN-CONVERGED, AXIS-B-PRESERVE-INDEX,
NEXT-WAVES-ROADMAP}` · `A0-wholedrive-census`. One stale headline: AUDIT-DESIGN-CONVERGED §1.1
"enforcement-inert" is **RESOLVED** post-Wave-0 — annotate as gate-time.
⚠️ `skills/DEPLOYED-MANIFEST.json` is **broken-canonical** (missing at the live `~/.agents/skills/` path).

### Two memory systems (reconcile-awareness)

Two **persistent** stores coexist by design (AGENTS.md §8) and **both must be checked**:
- **basic-memory D: vault** (`D:/basic-memory/projects`, cl-34) — the semantic SSOT; **holds the healthy
  supersede chains the on-disk `.md` docs lack.** Prefer it as the durable decision ledger (N7).
- **Claude auto-memory** (`~/.claude/projects/C--Users-Prekzursil/memory/MEMORY.md` + archive, embedded
  in cl-8) — the cross-conversation index.

### Loose `~/.claude/*.md` June plan corpus — the supersession-marker debt

This is the root cause of "a fresh session re-walks retired decisions." Owner: A5 registry. Actions:

| Doc | Status | Action |
|---|---|---|
| `MEM0-PILOT-PLAN.md` | **stale, actively-refuted** | **tombstone NOW** → `SUPERSEDED-BY` mem0 NO-GO verdict |
| `CONSOLIDATED-GEM-DECISIONS.md` (06-29) | duplicate | tombstone → 06-30 |
| `SOTA-HARNESS-RECOMMENDATIONS.md` (V1) | superseded | banner → V2 |
| `{HARNESS-REMEDIATION, MCP-SOTA-EXPANSION, RESEARCH-HARNESS, CAPABILITY-PROGRAM-PLANS, MCP-FLEET-IMPROVEMENT, PRUNE-RECOMMENDATIONS}.md` | superseded (mostly BUILT) | banner each `SUPERSEDED-BY` → basic-memory permalink; **extract still-open rows first** |
| `OPEN-THREADS.md` | **still-open — DO NOT tombstone** | migrate to basic-memory (owner's #1 stress = losing this) |
| `AGENTIC-PERFECTION-PLAN.md`, `PROACTIVE-PARTNER-PROGRAM.md`, `AUTODREAM-H6-DESIGN.md` | still-open residual | extract ROUND-2/3 rows before any tombstone |

---

## 3. The DUPLICATE + STALE + SLOP sets

### DUPLICATE (byte/tree copies of a canonical source)

- **agent-skills-toolchain repo × 3 physical copies** — canonical `source/agent-skills-toolchain`;
  `tmp/ds-agent-skills-toolchain` (cl-7) + `work/agent-skills-toolchain-re` (cl-29, frozen 04-01) +
  `D:/pr-b-clone` (cl-17, deleted). No loss (all in git).
- **Skill deploy fan-out** — SOURCE `skills/` → `.agents/library` (installed domain packs) →
  `.claude/skills.daily` (curated *processed* active) → `.agents/skills` (full vault). Each is a distinct
  **role**; edit SOURCE + redeploy, never hand-edit a deployed copy.
- **metaswarm plugin** — canonical = marketplace/`~/.claude/plugins/metaswarm`; copies in `.codex/metaswarm`
  (cl-47), `.gemini/extensions` (cl-30), `antigravity-cli` (cl-37), `tmp/ds-qzp` (cl-52), `GitHub/qzp` (cl-55).
- **ToolUniverse skills** (cl-24/25), **QZP design docs** (cl-52/55 vs live repo),
  **momentstudio worktree graveyard** (cl-3, 13.2 GB), **bc-toolkit worktrees** (cl-14),
  **CONSOLIDATED-GEM 06-29→06-30**, **SOTA-HARNESS V1→V2**, **basic-memory DR mirror** (cl-21, intentional).

### STALE (contradicted by current truth / abandoned approach)

`MEM0-PILOT-PLAN.md` (mem0 NO-GO) · `agent-skills-toolchain/CLAUDE.md` (retired AgentBridge, **auto-loads
in-repo — CVE-2026-47751-class hazard**) · `SESSION-RECONCILIATION-2026-06-10.md` (mcp-funnel abandoned) ·
`D:/Research/.mcp.json` (+5) · `.codex/metaswarm` + `.codex/superpowers` (orphaned April parity, 0 config
refs) · `.gemini/extensions` (~3mo behind) · the no-supersede-marker loose June corpus · stale QZP
checkouts (cl-52/55/58) · `work/…-re` (cl-29) · deleted gem-wave-b / pr-b-clone index rows.

### SLOP (ephemeral / vendored / rollback noise — not real harness docs)

`AppData/Local/Temp` cl-0 (14,922) · `.codex/.tmp` cl-1 (5,351) · `Roaming/Claude` cl-10 (1,359) ·
`.codex/plugins` staging cl-16 (883) · `.serena/logs` cl-19 (676) · `.vscode/extensions` cl-26 (326,
**exclude from harness scope**) · `.claude/checkpoints` cl-35 (181, rollback snapshots) · `.claude/projects`
session bulk (cl-8 minus the canonical `memory/` subdir) · D:/claude-projects-archive tool-result `.txt`
tail. **Total slop ≈ 20,949 docs across the 3 largest slop clusters alone.**

---

## 4. FORGOTTEN-HIGH-VALUE list (owner priority — fold / corroborate / contradict)

**33 items** consolidated across all 6 slices. Grouped by fragility + relation. Full rows (with fold
actions) in `B-doc-registry-COMPLETE.json` → `forgotten_high_value`. **Honest split: only ~9 are truly
at-risk of loss** (temp-only / phone-only / non-harness-project-buried); the rest are **live-in-canonical
corroboration** the program must cross-reference so it doesn't re-derive, or **basic-memory guardrails**
a FILE-only audit would miss.

### 4a. TRULY AT-RISK of loss (fragile location) — fold before it's gone

1. **`…/scratchpad/multiai-decision-OUTPUT.md`** (TEMP-ONLY) — 18 KB synthesis that PRODUCED the
   multi-AI-mingle design; its **10-tool maturity table + kill-list + Q5/Q6 resolutions are richer than
   memory and live only in temp.** → fold into basic-memory before cleanup.
2. **`…/scratchpad/multiai-decision-PROMPT.md`** (TEMP-ONLY) — 122 KB ~13-lens research corpus behind it;
   discardable once the OUTPUT is preserved.
3-6. **BC `ralph-loop-hardening-plan.md` (80 KB) + `bc-unlock-master.yml` + `ralph-loop-hardening-design.md`
   + `ralph-fsm-redesign-plan.md`** — battle-tested autonomous-loop reliability architecture buried in a
   non-harness RE project: supervisor-outside-failure-domain, 3-watchdog taxonomy, durable idempotent
   broker, layered PreToolUse bypass-block, **deterministic-FSM-not-LLM-judgment**, single-actor-per-phase.
   → **FOLD a distilled "autonomous-loop reliability patterns" note into basic-memory citing the source.**
7. **Founding `Quality_Gate_Hooks` chat** (PHONE-BACKUP-ONLY) — the 2026-04-05 origin request for
   "strict 0 issues before any push" across Sonar/Codacy/Semgrep/Qlty/Sentry/DeepSource/Codecov. →
   preserve as the program's north-star origin record.
8. **`QZP-V2-DESIGN.md`** (STALE local checkout) — reference the live QZP repo, don't re-derive.
9. **`D:/ToolUniverse/plugin`** (unused 118-skill plugin) — FLAG, do not blind-fold (intentional gap).

### 4b. LIVE-in-canonical — CORROBORATES; cross-reference so the program doesn't re-derive

- **`docs/agentic-perfection/OPEN-THREADS.md`** — #9 "AGENTS.md 3-divergent" is the **direct Axis-A
  ancestor**; cross-ref every ACTIVE/QUEUED item into the A5 ledger.
- **`AGENTIC-PERFECTION-PLAN.md`** (source doctrine: TIER-1 keystones + 6-hook ceiling) ·
  **`PROACTIVE-PARTNER-PROGRAM.md`** (the vision — verify shipped-vs-aspirational) ·
  **`claude-toolkit-gap-analysis-2026-05-28.md`** (300 KB seed: context-rot diagnosis, keep §5 catalog) ·
  **`unified-cross-ai-mcp-{architecture,implementation}` plans** (Axis-A MCP owners — update in place) ·
  **`2026-06-11-fanout-corpus.md`** (research provenance) · **`workspace-knowledge-base.md` +
  `SESSION-RECONCILIATION-2026-06-06.md`** (prior-art for this audit's deterministic-registry directive) ·
  **`docs/incubating/skills`** (28 stubs; codex-config-canonicalizer / store-auditor / cli-session-convergence
  map onto Axis-A).

### 4c. basic-memory GUARDRAILS — CONTRADICT a naive audit (MUST-HONOR; a FILE-only pass misses these)

- **`gem-hunt … execution status (2026-07-13)`** — **DO-NOT-RE-APPLY**: all 11 gem items already deployed
  byte-identical; re-applying overwrites the only rollback `.bak` (`~/.claude` is not git) = **harmful**.
- **`harness-gemhunt … state (2026-07-03)`** — CARVE-OUTS: do NOT fold benchmark-optimization-loop (235×
  traffic); do NOT delete the unwired `no-force-push/` §9 guard (wire-or-park); baseline `eval.py` before
  ANY skill-description edit.
- **`Archived improvement candidates … do not re-suggest`** — 4 hooks explicitly ARCHIVED (autonomy
  Stop-DoD evaluator, input secret guard, parallel file-ownership, dangerous-command guard).
- **`microVM-OS-sandbox … DEFERRED`** — do NOT re-suggest unprompted.
- **`Capability Assimilation Program`** — SECURITY: **ROTATE `HACKTRICKS_API_KEY`** (pasted in chat) +
  never call `mcp__sci-hub__*` (quarantined).
- **`beads requires Dolt`** — TEMPORAL: decision **reversed same day** (Dolt 2.1.7 + bd installed);
  recall the current truth.

### 4d. CONTRADICTS the current program — stale drift to banner/tombstone (owner action)

- **`agent-skills-toolchain/CLAUDE.md`** — retired AgentBridge, auto-loads in-repo.
- **`MEM0-PILOT-PLAN.md`** — reads live despite mem0 NO-GO.
- **`SESSION-RECONCILIATION-2026-06-10.md`** — mcp-funnel abandoned.

### 4e. CORROBORATES (already-wired; do NOT re-propose)

`Modus-operandi upgrades #1-7 IMPLEMENTED` · `Friction-mining items IMPLEMENTED` · `Anticipatory layer
BUILT` (scheduled-tasks, off the hook-ceiling — **do not orphan**) · `Per-project intelligence` (projid.py) ·
`Workspace Curation de-bloated` (config-SSOT; do not wipe curated MCP state) · `ultracode Workflow-harness
SOTA queue` (Axis-B, max-loss-risk — preserve) · this program's own DR-backed control-note.

---

## 5. Doc-reconciliation-hook — design implications

The evidence points at a **specific, bounded hook** — not a new subsystem. It must obey the standing
design law (`AGENTIC-WORKSPACE-ARCHITECTURE` / `SELF-CALIBRATION-PLAN`): **every check anchors to an
EXTERNAL signal; hooks TRIGGER, a separate model or a deterministic registry JUDGES; LOG+SURFACE+PROPOSE
only, never auto-edit; fail-open; stay under the ~6-active-hook ceiling** (fold into an existing
SessionStart/PreToolUse slot — **no new hook event**).

**Root causes it must attack (all evidenced above):**
1. **No supersession markers** on the loose `~/.claude` plan corpus → fresh sessions re-walk retired
   decisions (MEM0, funnel, AgentBridge).
2. **Fork-not-fold** — new plans get written fresh instead of updating the canonical owner (the two-SSOT
   MCP catalogs; competing gem consolidations).
3. **Two memory systems** (auto-memory + basic-memory) checked inconsistently.
4. **Auto-loading stale config** — an in-repo `CLAUDE.md`/`AGENTS.md` prescribing a retired mechanism
   (AgentBridge) is a live drift *and* a CVE-2026-47751-class hazard.
5. **Fragile forgotten value** — the richest syntheses live in temp/phone/deleted-clones, invisible to a
   FILE-only or memory-only audit.

**Design:**

- **A. Fold-not-fork owner check (PreToolUse on Write/Edit of a `*.md` plan/design in `~/.claude` or a
  repo root).** Read the deterministic **canonical-owner registry** (`B-doc-registry-COMPLETE.json` /
  A5) for an existing owner of the subject; if found, **inject** "an owner exists at `<path>` — UPDATE it
  (add `SUPERSEDED-BY`) instead of writing fresh." Registry + link-validation, **NOT a new knowledge DB**
  (owner directive). This is the deterministic JUDGE.
- **B. Anti-re-walk gate (advisory).** Before a plan proposes a candidate, check the basic-memory
  **anti-re-walk ledger** (archived-candidates, microVM-deferred, gem-hunt DO-NOT-RE-APPLY, carve-outs);
  surface "this was closed/deferred on `<date>` — see `<permalink>`." §4c is the seed corpus.
- **C. Stale-config tripwire (SessionStart, fold into the existing tool-preflight/config-drift slot).**
  Keyword-scan auto-loading `CLAUDE.md`/`AGENTS.md`/`.mcp.json` for retired-mechanism strings
  (`AgentBridge`, `get_budget`, `mcp-funnel`, `mem0`) and for the **3-way AGENTS.md hash-divergence**;
  surface a banner-this finding. Deterministic, no LLM.
- **D. Both-memory-store rule.** Any recall/registry read consults **both** the basic-memory D: vault
  and the `~/.claude/projects/…/memory/MEMORY.md` auto-memory — never one.
- **E. Fragile-forgotten sweep (SCHEDULED TASK, not a hook — mirrors the Anticipatory layer, off the
  hook-ceiling).** Periodically scan temp scratchpads for deliverable-shaped `*-OUTPUT.md`/synthesis docs
  and phone/DR backups for origin artifacts **before cleanup**, surface-once for folding into basic-memory.
- **F. Preserve `OPEN-THREADS`.** The hook must treat `still-open-prior-art` as **KEEP** — never propose
  tombstoning the never-forget backlog (owner's #1 stress).

**Non-goals (explicitly out — anti-re-walk):** no OS-sandbox, no secret-guard hook, no parallel
file-ownership hook, no dangerous-command hook (all ARCHIVED, §4c). No new always-on hook event. No new
knowledge DB. The output is advisory findings + banners the owner applies — consistent with this whole
reconcile being READ-ONLY.

---

*End B-doc-reconciliation-COMPLETE.md — evidence in `B-doc-registry-COMPLETE.json`.*