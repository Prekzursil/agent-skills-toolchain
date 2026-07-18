# B — RFC Deliverables Index (Workflow B / design gate)

**Program:** Unified Harness Control-Plane (Claude + Codex). **Date:** 2026-07-13.
Maps the **18 required RFC deliverables** to their file + section. All files live in
`docs/audit-design-2026-07-13/`. Status legend: ✅ delivered · ⚠️ delivered-with-fix (see
`B4-CRITIC-VERDICT.md`).

| # | Required deliverable | Grill decision | File · section | Status |
|---|---|---|---|---|
| 1 | **Domain-separated authority model** + one-way deploy invariant + migration bootstrap | G-1, G-13 | `B1-RFC-core.md` §1 · `B1-interfaces.md` §1 | ✅ |
| 2 | **Typed logical capability catalog** (6 domains, live seed each) | G-1 | `B1-RFC-core.md` §2.2 · `B1-interfaces.md` §2.1–2.2 | ✅ |
| 3 | **Two deterministic provider adapters** (Claude + Codex; Antigravity dropped) + 3 hard invariants | G-1 | `B1-RFC-core.md` §2.1/§2.3 · `B1-interfaces.md` §2.3 | ✅ *(verified [EXTENDS build_hooks] is faithful)* |
| 4 | **Named profiles** + per-provider materialization + full precedence chain | G-10 | `B1-RFC-core.md` §3.1–3.3 · `B1-interfaces.md` §3.1–3.2 | ✅ |
| 5 | **`effective-config explain`** (per-key provenance, secret-redacted) | G-10 | `B1-RFC-core.md` §3.4 · `B1-interfaces.md` §3.2 | ✅ |
| 6 | **Deployment mechanism from first principles** (CAS-lite-extend vs journal; recommend) | G-2 | `B1-RFC-core.md` §4 · `B3-migration-verification.md` §2.1 | ✅ *(CAS-lite-EXTEND; deploy() verified live)* |
| 7 | **MCP scope / lifecycle matrix** (7 tiers · 5 classes · 6 policy rules) | G-5, R2-1 | `B1-RFC-core.md` §5 · `B1-interfaces.md` §5 | ✅ *(43 servers verified)* |
| 8 | **Typed interface signatures** (frozen dataclasses, [EXTENDS live symbol]) + traceability | G-1/2/5/10 | `B1-interfaces.md` §1–6 | ✅ |
| 9 | **Enforcement hooks** (cleanup · doc-reconciliation · harness-change→doc+PR; OFF→SHADOW→ADVISE→ENFORCE) | G-3 | `B2-RFC-operational.md` §1.1–1.4 | ✅ |
| 10 | **Stop-loop permanent fix** (boundary hoist, T1–T8, StopFailure, correlation IDs, 3 plugin Stop) | A1, R2-2 | `B2-RFC-operational.md` §1.5 | ✅ *(16-vs-17 event count: MF-2)* |
| 11 | **ONE-dispatcher consolidation** (retire 63 residue + `_dispatch` + ECC, reversible) | R2-2 | `B2-RFC-operational.md` §1.6 | ✅ |
| 12 | **Monitoring** (11-PR roadmap on wfmon/monitorcore + Codex-threadId adapter, observe-only) | G-4 | `B2-RFC-operational.md` §2 · `B3` W3.1 | ⚠️ *(PR-to-content cited, not re-verified: MF-5)* |
| 13 | **Memory + `/self-reflect`** (role separation, MEMORY.md-bypass fix, outage→spool→exactly-once) | G-8 | `B2-RFC-operational.md` §3 · `B3` W2.8 | ⚠️ *(bypass under-specified: MF-3)* |
| 14 | **Orchestration engine H1–H8 + ~50 tiered helpers** (native `agent()`/`parallel()`, H6 priority) | G-6 | `B2-RFC-operational.md` §4 · `B3` W1.5/W3.2 | ✅ |
| 15 | **Mingling** (`codexAgent()` + vendor auto-routing + Architect-to-Editor + cross-vendor consensus) | G-7 | `B2-RFC-operational.md` §5 · `B3` W3.3 | ✅ |
| 16 | **New features** (uncertainty-gate · GEPA · proactive-partner · `/harness-audit` scorecard) | G-11 | `B2-RFC-operational.md` §6 · `B3` W3.4 | ✅ |
| 17 | **Leanness / anti-bloat budgets** + cost/startup/context/daemon baseline | G-12 | `B2-RFC-operational.md` §7 · `B3-migration-verification.md` §3 (PART 3) | ✅ |
| 18 | **Staged migration + rollback plan** + **27-criterion failure-oriented verification matrix** | G-9, G-13 | `B3-migration-verification.md` PART 1 + PART 2 · `B3-migration.json` (twin) | ✅ |

**Gate-closing artifacts (beyond the 18):**
- **≤3 owner decisions + recommended Wave-0** — surfaced per-section (B1 §6–7; B2 §8–9; B3 §4) and
  **distilled to the actual ≤3** in `B4-CRITIC-VERDICT.md` §4–5 (see MF-1: the sections did not
  converge; the critic pass converges them).
- **Independent critic verdict** — `B4-CRITIC-VERDICT.md` (verdict: **SOUND-WITH-FIXES**; 6 must-fixes;
  load-bearing claims spot-verified against live source at HEAD `dd5366b`).
- **Machine-readable migration twin** — `B3-migration.json` (3 waves, 6 budgets, 27 criteria, 22-gem list).

**Evidence base the RFC rests on (A/C lanes, not RFC deliverables):** `A1`–`A6` (stop-loop · inventory ·
MCP matrix · skills-dup · decision-ledger · cleanup), `B-doc-*` (doc reconciliation + owner registry),
`C-config`/`C-mcp`/`C-hooks`/`C-skills` (per-domain reconciliations), `GRILL-LOG.md` (the 16 decisions).

`SUCCESS:B-DELIVERABLES-INDEX` — 18/18 required deliverables mapped; 16/16 grill decisions honored;
2 deliverables (12, 13) carry a tracked fix; nothing built/committed/deployed.
