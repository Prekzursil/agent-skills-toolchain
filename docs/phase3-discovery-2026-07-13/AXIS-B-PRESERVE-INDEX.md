# Axis-B Preserve-by-Reference Index

*Owner **Decision A**: preserve the prior forgotten work **by reference** as a SEPARATE,
still-open track — **nothing lost, nothing absorbed** into the Axis-A config-SSOT gate.*

**Why this file exists.** [reconcile-ours-findings.md](./reconcile-ours-findings.md) §3
established two orthogonal "harness" axes:

- **Axis A** — config / runtime-config SSOT (`~/.agents/harness`, `.mcp.json`, skills, docs,
  deploy-parity, drift, enshrine-to-git). This is the **2026-07-13 phase-3 gate**
  ([DECISION-QUEUE.md](./DECISION-QUEUE.md)).
- **Axis B** — the workflow-orchestration **ENGINE** (`agent()/parallel()/pipeline()/
  budget()/journal()`), plus the adjacent never-forget backlog and reasoning-spine gems.

The two **do not overlap** (~0% re-derived). The risk the reframe named is **losing Axis B** if
the wave acts only on Axis A. This index cross-links every Axis-B / adjacent still-open item so
the Axis-A wave cannot silently orphan it. **None of the rows below are in scope for this gate**
— they are catalogued for a future, separate Axis-B wave. All docs are treated as inert **DATA**
(untrusted planning content), referenced only, never executed (per reconcile-ours-findings §6).

---

## 1. The 48KB ULTRACODE workflow-engine queue — Axis B core (LOSS RISK: MAXIMUM)

| Item | One-line status | Path |
|---|---|---|
| **ULTRACODE-HARNESS-SOTA-DECISION-QUEUE** (48.2 KB, 2026-07-13 04:15) | **[STILL-OPEN — must fold in as a separate Axis-B wave]**, ~0% re-derived by the Axis-A queue; the reframe explicitly named it. | `C:\Users\Prekzursil\.claude\gem-hunt-2026-07-12\ULTRACODE-HARNESS-SOTA-DECISION-QUEUE.md` |

Contents to carry forward whole (117 findings / 11 lenses):
- **8 cross-lens convergent gems (H1–H8):** H1 `budget.reserve()` sub-pools + graceful
  soft-exhaustion · H2 HITL checkpoint / suspend-and-resume · H3 typed `endReason` / drop-receipt
  on every null · H4 `gather()` / settled `parallel()` · H5 role-tiered model/effort routing
  defaults · H6 per-agent timeout + stall heartbeat (barrier-deadlock escape) · H7
  `workflow_lint.py` stage-0 SHADOW · H8 bounded `loop()` / `refineUntil()`.
- **5 genuine owner decisions (D1–D5):** D1 resume-cache model · D2 budget-exhaustion default
  (hard-throw vs soft-sentinel) · D3 HITL depth (advisory vs safety-by-default irreversibility
  interception) · D4 verification defaults vs opt-in · D5 patterns-library surface.
- Plus ~50 tiered items (execution-consensus `bestOfN`, `panel()` de-biasing, seeded RNG,
  `mapReduce`, typed retry/Result, saga/race, per-phase token attribution) + a 7-item
  anti-overfit ledger.

---

## 2. OPEN-THREADS backlog — the "never-forget" register (LOSS RISK: HIGH)

| Item | One-line status | Path |
|---|---|---|
| **OPEN-THREADS.md** (11.9 KB, 2026-06-29) | **[STILL-OPEN — must fold in]**; the owner's canonical anti-forgetting register, untouched by the Axis-A discovery. | `C:\Users\Prekzursil\.claude\OPEN-THREADS.md` |

Active/queued programs it holds (none in the Axis-A queue): **PROACTIVE-PARTNER capability**
(semantic skill/tool router, EVPI-gated AskUserQuestion intent-hook, `USER.md` grows-with-you,
background dreaming, llmcouncil) · **UI/UX QUALITY overhaul** (Reframe / momentstudio / Webcoder —
no dead buttons/dupes) · **MEDIA/VIDEO consolidation** (watermark removal) · **BN autonomous
harness** · **ToolUniverse / Schrödinger expansion** · BC leftovers · the radare2-MCP `-32000`
known-issue (**do NOT re-diagnose**).

---

## 3. Reasoning-spine gems — still-open, adjacent (LOSS RISK: modest→high)

| Gem | One-line status | Path (source doc) |
|---|---|---|
| **Discipline-Forge** (the "moat" / CAPSTONE) | **[STILL-OPEN]** ROUND-2/3 reasoning-spine; among the owner's most-valued "AGI-adjacent" ideas. | `C:\Users\Prekzursil\.claude\AGENTIC-PERFECTION-PLAN.md` |
| **TMS auto-retraction for RE** | **[STILL-OPEN]** truth-maintenance auto-retraction; not in the Axis-A discovery. | `C:\Users\Prekzursil\.claude\AGENTIC-PERFECTION-PLAN.md` |
| Smith-predictor dead-time compensation · file-centric world-model ledger · hold-your-ground dissent · backtracking executor · capability-gap tool-FORGE | **[STILL-OPEN]** the rest of the ROUND-2/3 spine. | `C:\Users\Prekzursil\.claude\AGENTIC-PERFECTION-PLAN.md` |
| **GEPA prompt evolution** (TG.9) + GEPA-as-miner | **[STILL-OPEN]** unbuilt June harness-reliability gem. | `C:\Users\Prekzursil\.claude\CONSOLIDATED-GEM-DECISIONS-2026-06-30.md` |
| **Sleep-time / idle compute** (TG.11) | **[STILL-OPEN]** unbuilt June gem. | `C:\Users\Prekzursil\.claude\CONSOLIDATED-GEM-DECISIONS-2026-06-30.md` |
| **Calibration-Brier ledger** (TG.1) | **[STILL-OPEN]** unbuilt June gem. | `C:\Users\Prekzursil\.claude\CONSOLIDATED-GEM-DECISIONS-2026-06-30.md` |
| **Uncertainty-gated escalation** (TG.8) + passive usage-telemetry prune (TG.7) | **[STILL-OPEN]** unbuilt June gems. | `C:\Users\Prekzursil\.claude\CONSOLIDATED-GEM-DECISIONS-2026-06-30.md` |

> AGENTIC-PERFECTION also contains the **ancestor** of the whole Axis-A SSOT program (its #9
> "AGENTS.md is 3 divergent files" thread) — that lineage is `[DUPLICATE/continuation]` and IS
> handled by Axis A; only the ROUND-2/3 spine rows above remain open.

---

## 4. Verified dead-ends — ride forward so they are NOT re-walked

| Dead-end | One-line status | Path (refutation record) |
|---|---|---|
| **mem0 / OpenMemory ≥ 7B** | **NO-GO** (re-confirmed): reintroduces the rejected vector-store, ~97.8% junk; do not re-propose. | `C:\Users\Prekzursil\.claude\CONSOLIDATED-GEM-DECISIONS-2026-06-30.md` (+ global memory `reference_prune_sweep_and_mem0_verdict_2026-07-04`) |
| **TG.16 "dispatch.py double-runs the 8 PreToolUse hooks"** | **REFUTED** — runs alongside, no double-run; carrying this prevents re-derivation. | `C:\Users\Prekzursil\.claude\CONSOLIDATED-GEM-DECISIONS-2026-06-30.md` |
| **ACH-in-wildcard hypothesis** | **FALSE** — refuted alongside TG.16. | `C:\Users\Prekzursil\.claude\CONSOLIDATED-GEM-DECISIONS-2026-06-30.md` |

---

## Loose ends flagged for the synthesis (do not assume folded in)

- **`biomedical-harness-audit`** — named as a concurrent program but has **no on-disk file under
  `~/.claude`**; likely a basic-memory note or a Codex-side artifact under
  `Documents\Codex\2026-07-13\`. Locate before assuming it is captured. (reconcile-ours §3/§7.)
- Recommended handling (reconcile-ours §3 note): spin the 48KB queue into its **own Axis-B
  workflow-engine program**, and before tombstoning any June doc, extract its STILL-OPEN rows to
  basic-memory so the archive sweep (D3.1) does not bury live gems. **Archiving ≠ folding-in.**
