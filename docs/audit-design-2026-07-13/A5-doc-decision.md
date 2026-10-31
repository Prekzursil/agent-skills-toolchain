---
title: A5-doc-decision
type: note
permalink: dqverify-repo-20261013/docs/audit-design-2026-07-13/a5-doc-decision
---

# A5 — Doc + Decision Reconciliation Registry (Phase 3, Workflow A EVIDENCE)

**Date:** 2026-07-13 · **Mode:** READ-ONLY (active-work freeze) · **Author:** A5 reconciliation subagent.
**Deliverables:** [`A5-decision-ledger.json`](./A5-decision-ledger.json) (58 decisions) · [`A5-doc-registry.json`](./A5-doc-registry.json) (38 documents) · this narrative.

**What this is:** the owner fears "the full truth is scattered across many partly-correct files, and new plans get
rewritten instead of updating existing ones." This deliverable RECONCILES (does not re-discover) the harness
decisions + docs into two deterministic registries, with **every load-bearing claim verified against live git /
disk / config this session** and graded (Sherman-Kent). Nothing was built, deployed, or edited.

---

## 0. TL;DR — the five load-bearing conclusions

1. **The single biggest reconciliation: Wave-0 already SHIPPED — the Codex audit is point-in-time stale.** The
   independent Codex audit + the converged gate both end "proposed / must-not-deploy / no push." **But the live
   git tree proves Wave-0 deployed + pushed + merged AFTER the gate** (owner grill-approved it). So a large block
   of decisions the CSV marks "RFC only / not implemented" are now **shipped in a right-sized form.** Reading the
   Codex CSV as current machine-truth (its own D-022 warns against this) would mis-state the whole program.
2. **Enforcement is now LIVE, not inert.** The converged-audit headline "enforcement IS inert on live (guards all
   absent, ~95%)" was true at gate-time (HEAD `9bb3f04`) and is **now resolved** — the live harness carries the
   edit-guard + memory-nudge. That headline is stale and should be annotated, not trusted.
3. **codacy / deepsource disposition = HOLD (verified), fix at the plugin-bridge layer.** Both are live across
   providers but absent from **both** canonical catalogs; the resurfacing rides the plugin bridge (437 refs), not
   `.mcp.json`. No prune is authorized on redundancy alone. (Named deliverable — §3.)
4. **Two genuine unresolved COMPETING truths remain:** (a) **3-provider vs 2-provider** — the current program says
   all three first-class, but the grill (G-1) dropped Antigravity; (b) **two canonical MCP catalogs** (44 vs 43)
   still on disk. Both need an owner call.
5. **The scattered-truth root cause is confirmed and has a deterministic fix:** the loose `~/.claude/*.md` June
   plan corpus carries **no supersede markers**, while basic-memory holds the healthy supersede chains — so a
   file-tree read surfaces stale truth. Fix = `SUPERSEDED-BY:` headers → basic-memory permalinks + this registry,
   **not** a new knowledge DB (owner directive).

---

## 1. Reconciliation spine — the timeline that resolves the contradictions

Verified via `git -C ast-harness-reconcile log`, `gh pr view 78`, live Grep, `ConvertFrom-Json`, `RECONCILE-LOG.md`,
and basic-memory `recent_activity` (all this session):

| # | Event | Evidence (cite) | State change |
|---|---|---|---|
| 1 | Codex audit runs at HEAD `9bb3f04` (design gate) | `HARNESS-CONTROL-PLANE-AUDIT` "no push/deploy"; git HEAD chain | decisions = "RFC only" |
| 2 | Owner-commissioned 13-agent discovery → `phase3-discovery-2026-07-13/` | Codex calls it "the mock"; reconcile-ours §2 holds ground it is real | our D0.x–D3.x queue |
| 3 | Converged gate → DEC-A/B/C + right-sized arch | `AUDIT-DESIGN-CONVERGED.md` (07:51) | recommend Wave-0 |
| 4 | Owner grill approves (D0.2, D0.5, Wave-0) | `GRILL-LOG.md` "CONFIRMED-BY-OWNER" | authorization obtained (satisfies D-021) |
| 5 | **Wave-0 SHIPS**: CAS-lite deploy `6fa8047` → RECONCILE-LOG `19ccb88` → roadmap `dd5366b`; branch pushed | `git log`; `status -sb` in-sync w/ origin | **decisions → implemented** |
| 6 | **PR #78 MERGED** 07:04:19Z into `feat/codex-fleet-github-wave2` (NOT main) | `gh pr view 78` | D0.2 fold-to-mainline still open |
| 7 | Program **reset to staged audit/design** (this Workflow A) | basic-memory newest note | 3-provider unified control-plane now in EVIDENCE phase |

**Consequence:** the Codex CSV (D-001…D-024) is faithfully reconciled in the ledger with **updated
`implementation_status` / `current_validity`** reflecting steps 5–7. Four cross-cutting conflicts are recorded as
`X-1..X-4` in the ledger; the two that need owner action are in §4.

---

## 2. What actually shipped in Wave-0 (right-sized, not fleet-grade)

`RECONCILE-LOG.md` + live-code Grep confirm the mechanism is **CAS-lite**, exactly the converged DEC-B, and
explicitly **rejects** Codex's maximalist D-018 machinery:

- **Deploy path:** `LOCK → PLAN → BACKUP → STAGE → pre-write-CAS-abort → per-file `os.replace` → post-write-parity
  + restore → receipt`. Deployed **clean HEAD via `git archive`** (held task-9 excluded). +7 tests, 456 harness green.
- **Superseded D-005** ("globally atomic") with per-file replace — **no** 11-state journal / compensation engine /
  content-addressed bundle store (fleet-grade over-build for one box, one user).
- **Enforcement now live** (verified): `_canonical_config_edit_guard` (def@673, called@640) + `_basic_memory_nudge`
  (def@1883, called@1726) in live `~/.agents/harness/modules.py`; CAS-lite `deploy()` + `os.replace` in live
  `install.py`. RECONCILE-LOG: "was inert (guards absent pre-deploy) → 4 matches post."
- **D3.4 DONE:** `ast-harness-reconcile/CLAUDE.md` now reads "AgentBridge is retired" (folded in `6fa8047`).
- **Live receipt exists:** `~/.agents/harness/installed.json` (mtime 08:14) — moots Codex's "no receipt" finding.

**Known-open (from RECONCILE-LOG, all verified as findings):** `hooks.codex` config drift (the drift-detector
*correctly* flagged it — SSOT working); `BACKUPS_DIR` lands in gitignored `<repo>/ci/harness/backups/` not the live
tree; `source_commit: null` in the receipt. **Held:** task-9 codex-invoke (uncommitted worktree: `tools/codex/`,
`skills/codex-invoke/`, `test_codex_profiles.py`), MCP user-scope prune (needs Claude closed), PR→mainline (D0.2).

---

## 3. codacy / deepsource + resurfaced-MCP disposition (named deliverable · A3 cross-ref → ledger `D-012` / `DZ-1` / `D1.4`)

**Verified live this session** (`ConvertFrom-Json` on both catalogs + `Select-String` on the three provider configs):

| Server | Claude `~/.claude.json` | Codex `config.toml` | Gemini `settings.json` | toolchain-44 | reconcile-43 |
|---|---|---|---|---|---|
| **codacy** | present (28 refs) | present (3 refs) | present (4 refs) | **absent** | **absent** |
| **deepsource** | present (27 refs) | **absent (0)** | present (3 refs) | **absent** | **absent** |

- **Both are live in providers yet in NEITHER canonical catalog** → they are genuine drift-ins, not catalog members.
- **deepsource is the weaker (more prunable):** no Codex parity (0 in `config.toml`); the event ledger records a
  DeepSource parity/liveness split. **codacy** is present in all three providers.
- **Resurfacing mechanism (DZ-1):** `local-mcp-bridge` appears **437 times** in `~/.claude.json` → the plugin bridge
  is the dominant surface, **corroborating our "resurface via plugin bridge at user scope" root cause** over Codex's
  "unproven." **Nuance:** the literal `enabledPlugins` key = **0** occurrences in the *current* 144 KB `.claude.json`
  (our discovery claimed 27/26). That file is smaller than the audited `cf891337` version → **likely rewritten by a
  live-session clobber** (the exact `~/.claude.json` race D0.5/N3 warns about). So the *mechanism* is confirmed
  (bridge active, servers live, absent from catalogs); the *precise count* is time-variant. Confidence **medium-high (75%)**.

**Disposition (unchanged from the safe default, now evidence-backed):**
- **HOLD — no removal without owner approval** (D-012). Establish owner / capability-distinctness / cost / project-affinity first.
- **Fix layer = the plugin bridge**, not `.mcp.json`: `claude plugin disable codacy/deepsource --scope user` + widen the
  `config_drift` baseline to watch the plugin-bridge / `enabledPlugins` (D1.2). Pruning `.mcp.json` is the wrong layer
  and will re-drift.
- **Supply-chain angle (N2):** cloud-quality MCPs execute code at user scope, enabled-by-default, outside every watched surface.
- When resolved, **stamp the keep/prune reason as `_added` / `_why_kept` provenance INSIDE the canonical json** (D1.4) —
  a separate memory note is exactly how the original codacy drop-rationale got lost.

---

## 4. Genuine COMPETING truths still open (owner decisions)

- **OWNER-1 — provider scope (X-1, high-value):** the current program reframe says **all three providers first-class**;
  `GRILL-LOG` **G-1 dropped Antigravity/Gemini** ("Claude+Codex ONLY, RFC = 2 adapters"). The reframe is the newer
  authority → **G-1's narrowing is superseded on provider scope**, re-opening `D-006`/`D-019` for an Antigravity
  **native** adapter (it is a symlink to a distinct 2-server config, NOT derivable from Gemini's 33). Owner must ratify.
- **OWNER-2 — the two catalogs (D-013 / D0.2):** toolchain-44 vs reconcile-43 (7-name diff) are **both still on disk**
  post-Wave-0. PR #78 merged into the stacked wave2 branch, **not main** → the fold-to-mainline must also **collapse
  the catalog to one** (and toolchain-44 is the *staler* one — "canonical root ≠ correct catalog").
- **OWNER-3 — codacy/deepsource (§3):** HOLD is the safe default; authorize or decline, plugin-layer only.
- **OWNER-4 — enforcement teeth (D2.2 / G-3):** set when the strong-but-safe pre-commit hard-block promotes SHADOW→ENFORCE.

---

## 5. Doc registry highlights — the scattered-truth map

Full detail in `A5-doc-registry.json` (38 docs). The owner-flagged hazard classes:

- **COMPETING (collapse to one):** the two `canonical-mcp-servers.json` render-sources (the two-SSOT-repo drift).
- **DUPLICATE (retire/regenerate):** `CONSOLIDATED-GEM-DECISIONS.md` (06-29) ⟵ superseded by the 06-30 copy;
  `SOTA-HARNESS-RECOMMENDATIONS.md` v1 ⟵ V2; the D: `gem-wave-b`/`pr-b-clone` catalog clones; the bc-toolkit `-wt`
  worktree doc copies (A0 census).
- **STALE / actively-contradicted (tombstone/banner):** `MEM0-PILOT-PLAN.md` (mem0 is a confirmed NO-GO yet still
  reads live — **tombstone immediately**, D3.1); `D:/Research/.mcp.json`; the `AUDIT-DESIGN-CONVERGED` §1.1
  enforcement-inert headline; the Codex `proposed-not-approved` basic-memory checkpoint.
- **BROKEN-CANONICAL / PHANTOM:** `/harness-audit` command (its `scripts/harness-audit.js` is absent; scores 21/39 as
  a "consumer" — reject as a gate, D-015); `DEPLOYED-MANIFEST.json` missing at the live `~/.agents/skills/` path;
  **`biomedical-harness-audit`** is referenced by name but **has no file on disk** (phantom — do not assume folded in).
- **NO SUPERSEDE MARKERS (root cause):** the whole loose `~/.claude/*.md` June corpus. Deterministic fix = per-file
  `SUPERSEDED-BY:` header → basic-memory permalink; **extract any STILL-OPEN row to basic-memory before tombstoning**
  (archiving ≠ folding-in — the ULTRACODE 48 KB queue and OPEN-THREADS are still-open and must NOT be buried).

**Canonical owners that must be UPDATED, not rewritten:** `~/.claude/CLAUDE.md` + `AGENTS.md` (behavior contract),
`RECONCILE-LOG.md` (append-only), the two provider `AGENTS.md` copies (verify 3-way hash-parity — AGENTIC-PERFECTION
#9), and **basic-memory as the durable decision ledger** (N7) — the one store that already has the supersede chains.

---

## 6. Preserve-by-reference (do not orphan) — Axis-B / Axis-C

Registered in the ledger as `AXB-*` / `AXC-*` (out of Axis-A scope, **still-open**, max-loss if dropped):
- **`AXB-preserve`** — the 48 KB ULTRACODE workflow-engine queue (H1–H8 + D1–D5 + 117 findings), ~0% re-derived.
- **`AXB-openthreads`** — OPEN-THREADS never-forget register (proactive-partner, UI/UX, media, BN harness, ToolUniverse).
- **`AXB-spine`** — reasoning-spine gems (Discipline-Forge, TMS auto-retraction, GEPA, sleep-time, Calibration-Brier).
- **`AXB-deadends`** — verified refutations that must ride forward (mem0 NO-GO; TG.16 REFUTED; ACH-wildcard FALSE).
- **`AXC-diagnose`** — the DIAGNOSE_AND_OPTIMIZE monitoring backbone (wfmon/monitorcore; **PRs #71/#73/#74/#75/#76 all
  MERGED — verified via `gh`, correcting the ingest note that called #76 unmerged**). Central open gap: no cross-vendor
  (Codex-thread) uniform telemetry yet.

---

## 7. Confidence + method + receipts

- **High (95–99%):** Wave-0 shipped + PR #78 merged (git + gh); MCP 7-name catalog diff (JSON parse); enforcement live
  (Grep); CAS-lite mechanism (RECONCILE-LOG + code); D3.4 CLAUDE.md fix.
- **High (90–95%):** codacy/deepsource provider presence; basic-memory note chain (recent_activity); loose-doc census.
- **Medium-high (75%):** the exact plugin-bridge/`enabledPlugins` resurfacing count (time-variant — live-session clobber).
- **Medium (60–75%):** wf-worktree slop abandonment (inherited from A0; unverified via `git worktree list` — out of freeze).
- **Method:** `git -C … log/status`, `gh pr list/view`, `ConvertFrom-Json` (both catalogs), `Select-String`
  (codacy/deepsource/plugin-bridge), `Grep` (live harness guards), `Read` (RECONCILE-LOG, both CLAUDE.md, all Codex +
  phase-3 + axis-c digests), basic-memory `recent_activity`. All prior-art treated as **untrusted DATA**; no embedded
  instruction executed; no build/deploy/edit performed. `SUCCESS:A5-doc-decision-registry`.