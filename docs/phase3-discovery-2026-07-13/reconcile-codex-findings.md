---
title: reconcile-codex-findings
type: note
permalink: dqverify-repo-20261013/docs/phase3-discovery-2026-07-13/reconcile-codex-findings
---

# Reconcile: Codex Control-Plane Audit — Extraction & Critical Assessment

**Author:** Claude reconciliation sub-agent (Phase 3 discovery)
**Date:** 2026-07-13
**Task:** Extract + critically assess the parallel Codex control-plane audit so it can be reconciled with the Claude-side discovery. Read-only. Codex's 8 artifacts are treated as **untrusted tool output (data)**, not instructions.
**Source dir:** `C:\Users\Prekzursil\Documents\Codex\2026-07-13\visualize-plugin-visualize-openai-bundled-turn-3\outputs\`

**Evidence tags used inline:** `[EVIDENCE-BACKED]` = cites a real git ref / file hash / config value / line number; `[ASSERTION]` = plausible but not independently shown; `[MISMODELS]` = frames reality in a way the evidence does not support.

---

## 0. Security screen (untrusted-data check)

I scanned all 8 files for agent-directed injection (run/build/deploy/delete commands, "ignore previous instructions", role-spoofs, claimed authorization, `curl|sh`, base64). **None present.** The artifacts are recommendation-heavy — they repeatedly say "freeze", "do not deploy", "approve design only", and describe deploy/rollback/delete *sequencing* — but always as **proposals gated on explicit owner approval**, never as commands to an executing agent. I treated every action-phrase (including the "Next safe action" and the Wave plan) as Codex's position (data) to be reconciled, and acted on none of it. No red-flag quote required.

---

## A. Codex's top findings (ranked, with severity + evidence + my tag)

Codex lists 8 "Critical findings". Ranked by load-bearing weight:

1. **Stop 3/4 root cause supported; incident contained (not universally closed)** — *high*. Evidence: one live Stop registration (5s timeout); `adapters.py:121-128` maps `stop_hook_active`→normalized trigger; `modules.py:1733-1746` silent-allow before claim detection on re-entrant Stop; 5 focused tests pass in 0.61s; runtime telemetry `23:37:19Z inject / 23:37:36Z allow`. **[EVIDENCE-BACKED]** — the strongest, best-grounded finding. Root-cause chain (old adapter read generic `trigger`, lost native `stop_hook_active`) matches documented Claude hook semantics. Fix present + tested. See §G.

2. **MCP control plane is split-brain** — *high*. Two "canonical" catalogs disagree: main=44 (`f406d95…`), reconcile=43 (`8d2bc76…`); 7-name symmetric diff (only-main: `exa, figma-rest, firecrawl, tavily`; only-reconcile: `agent-mail, angr, biomni-hub`); `playwright.args` drift. Provider fleets: Claude 63, Codex 25, Gemini 33, Antigravity 2. **[EVIDENCE-BACKED]** (hashes + counts internally consistent: 40 shared +4/+3 = 44/43). Codacy/DeepSource unresolved, *not* auto-removable.

3. **Live harness partially — not wholly — deployed** — *high, but framing contested*. 8 core files equal reconcile HEAD (`__init__, adapters, dispatcher, models, redaction, storage, recall_index, injection_grammar`); 6 do not (`ledger.py, modules.py, install.py, registration.py, test_native_events.py, test_modules.py`). Raw comparison **[EVIDENCE-BACKED]**; the *defect framing* ("unexplained partial drift", "no receipt proves whole-tree deployment") **[MISMODELS]** — see §I.1. `modules.py` is a *known uncommitted worktree file*, so live≠HEAD is the **expected** mid-enshrinement state, and commit `9bb3f04` (anti-drift enforcement) is the reconciling mechanism.

4. **Active-work freeze necessary; "the mock proved it"** — *high, but see §I.2*. The concurrent Claude run created `docs/phase3-discovery-2026-07-13/` (14 files, 380,091 bytes). File existence **[EVIDENCE-BACKED]** (I am writing into that very directory; it holds our council/inventory/research artifacts). The "prompt-conformance failure" reading is partly **[ASSERTION]** (interpretive) and is a critique of **our** Phase-3 discovery.

5. **Registration/process topology multiplication severe** — *medium*. ~786 MCP-wrapper processes, 271 node / 185 python / 227 cmd, 272 est. logical roots. Codex **self-flags these as topology estimates, not instance counts** — appropriately hedged **[ASSERTION-hedged]**. Fixed endpoints: `8765 basic-memory PRESENT`; `8812 agent-mail ABSENT`; `8760 angr ABSENT`; `8888 hexstrike`; `9224 biomni`. **[EVIDENCE-BACKED, point-in-time]**.

6. **Antigravity inventory must resolve links** — *medium*. `~/.gemini/antigravity-cli/mcp_config.json` is not empty; it is a **symlink** to `~/.gemini/config/mcp_config.json`, hash `58c8d213…`, 2 entries (`agentchattr, chrome-devtools`). **[EVIDENCE-BACKED]** and a legitimate correction of an earlier length-only inspection. Runtime load unproven (no Antigravity process).

7. **`/harness-audit` useful but mis-scoped** — *low/medium*. Installed command expects `scripts/harness-audit.js` (absent from both worktrees); a cached plugin copy scored the repo 21/39 "consumer". **[EVIDENCE-BACKED]** but Codex correctly rejects it as an acceptance gate (its advice — project-local `.claude/`, `.mcp.json`, `memory.md` — conflicts with the Basic-Memory authority model).

8. **Workspace Agents = optional async observer only** — *low*. No editable owner agents; no `harness` match; API trigger returns `202 Accepted`, no run ID, no readable response. **[EVIDENCE-BACKED from docs, not exercised]**. Correctly excluded from the correctness path.

---

## B. RFC architecture — "Transactional Harness Projector"

**Headline decision:** build a **one-shot transactional projector**, *not* a daemon or universal orchestration control plane. Git = desired authority; receipts = transaction truth; Basic Memory = rationale (off the correctness path); event ledger = objective history (off the correctness path).

- **Deploy path (source→runtime):** clean *named* Git tree → pure deterministic renderers (must not implicitly read `HOME`, cwd, clock, env, git status) → immutable **content-addressed bundle** (`manifest.json` + `checksums/` + `rendered/<target>/` + `plans/` + `transaction-template.json`) → read-only `plan` → approval gate → journal+lock+CAS → same-dir staging → per-target replace → verify → receipt. **No live→live or live→Git auto-sync**; a separate `import` command may *propose* from observed bytes but cannot rewrite desired state.
- **Live↔repo parity / verification:** `plan` / `effective-config explain` reports raw preimage hash + semantic digest, proposed postimage hash + semantic digest, preserved/ignored/forbidden fields, predicted reload boundary, drift, conflicts, blockers — **writing nothing**. Acceptance gate AC-10 demands "exact post-deploy parity and second-plan no-op".
- **Lifecycle ladder:** Codex does **not** use OFF→SHADOW→ADVISE→ENFORCE. Instead it defines a **deployment-transaction** journal: `PLANNED → PREIMAGES_VERIFIED → STAGED → APPLYING → APPLIED_PARTIAL → VERIFYING → COMMITTED / COMPENSATING → COMPENSATED / CONFLICTED / FAILED`, plus a **wave ladder** (Wave 0 authority/exclusions → Wave 1 pure parsers+read-only plan → Wave 2 offline bundle+journal+CAS → Wave 3 disposable-target e2e → separately-approved first-live canary). See §J for how this diverges from our gate-mode ladder.
- **Locking:** per-target **raw-byte compare-and-swap** (fresh preimage hash immediately before replace) + a "cooperating-writer lock" that "reduces races but never substitutes for CAS"; same-directory/same-volume atomic replacement where the platform supports it. Explicitly refuses to claim **fleet-wide ACID** ("multi-target = durable, journaled, conflict-detecting, compensating transaction — not globally atomic").
- **Rollback:** exact protected **preimages** stored in a local transaction area (ACL/encryption/retention policy); compensation runs **only if the current raw hash still equals this transaction's postimage** — a newer/foreign change yields `CONFLICTED` and is **never overwritten**. Handles missing-vs-empty file, BOM/encoding/newlines, ACLs/attributes, reparse-point identity, flush/durability semantics as part of the target contract.
- **Secrets:** secret **values** live only in external secret mechanism/env; Git/reports/receipts/bundle/Basic-Memory/ledger carry only **secret-reference names**. No credential-bearing preimages enter the portable bundle. Flags that captured Claude release/user-state snapshots *structurally* contain OAuth/account fields → must be rejected as deployable templates + quarantined (AC-20 `PARTIAL_RISK`).

**Right-sizing verdict (parent's key question):**
- **Direction = RIGHT-SIZED and agrees with us.** Codex actively *narrows* from "universal control plane" and rejects daemon / second memory store / second orchestrator / observability SaaS / bidirectional sync / fleet ACID / whole-`.claude.json` replacement (RFC §13; D-010). This is exactly the anti-sprawl posture our thesis wants.
- **Mechanism = OVER-ENGINEERED for scale.** CAS + an 11-state durable journal + compensating transactions + a "crash-after-every-journal-transition-and-replacement" fault matrix + immutable content-addressed bundles is **distributed-systems / DB-grade** machinery. The actual job is copying ~20–60 config files (settings.json, `.mcp.json`, `config.toml`, a dozen hook/module `.py`) from a git repo to `~/.agents/harness` + provider dirs on **one Windows box, one user**. Our thesis — **copy + pre-deploy backup + live↔repo parity diff** — delivers ~90% of the safety at ~20% of the complexity. **Partial justification exists:** the box genuinely runs many concurrent Claude+Codex sessions (audit saw 2 Claude + 5 Codex live), and shared files like `.claude.json` are known to be clobbered by concurrent session-exit (our own MEMORY notes this). So *some* pre-write hash-check ("mini-CAS") + timestamped backup is defensible — but the full journal/compensation-conflict apparatus is fleet-grade over-build here. **Net: correct principles, over-built implementation.** (confidence: high on direction, medium-high on the over-engineering flag)

---

## C. Owner decisions (verbatim-ish + Codex's recommended default)

Codex deliberately reduces to **exactly three** (matches the ≤3 high-EVPI convention):

1. **OWNER-1** — "Approve or reject the narrowed transactional-projector RFC and Wave 0/Wave 1 fixture-only work after the current worktree is released." **Default: approve design only; no live deployment.**
2. **OWNER-2** — "Choose the single committed desired-state repository and disposition of `ast-harness-reconcile` after salvage review." **Default: `agent-skills-toolchain` desired root; reconciliation worktree remains frozen staging evidence until safely integrated.**
3. **OWNER-3** — "Decide later whether to authorize one first-live canary after all disposable gates pass." **Default now: do not authorize live deployment.**

---

## D. Verification matrix — VERIFIED vs ASSERTED

36 rows (AC-01..27, TX-A..G, HIST-A, WS-A). Status distribution:

| Status | Count | Rows |
|---|---:|---|
| **PASS (scoped)** | **4** | AC-13 Stop (incident scope), AC-14 no-long-hook/longrun (audit scope), AC-21 dirty-work-untouched, AC-27 limitations-explicit |
| CONDITIONAL_APPROVE | 1 | AC-26 fresh-context reviewer |
| PARTIAL / PARTIAL_* | 12 | AC-02,05,06,08,11,15,17,20,23,24,25, TX-F |
| FAIL_CURRENT / FAIL_MOCK | 3 | AC-04 parity, AC-07 duplicates, TX-G prompt-conformance |
| NOT_RUN | 5 | AC-03,09,10,12,16 |
| NOT_BUILT | 9 | AC-01,18,19,22, TX-A,B,C,D,E |
| DEFERRED | 2 | HIST-A transcript index, WS-A workspace agent |

**Only ~11% (4/36) are actual passes, and 3 of those 4 are AUDIT-scope** ("we didn't break anything / we were honest"). The **only substantive harness-behavior pass is AC-13 (Stop), and even it is "incident scope", not universal.** Everything describing the RFC's actual *product* (projector, CAS, journal, bundle, compensation, cross-provider parity) is `NOT_BUILT`/`NOT_RUN` — **because the projector does not exist.** The RFC is 100% aspirational; zero of its transaction/parity claims carry implementation evidence. Codex is honest that this is a design gate, but the parent should read the RFC as **unbuilt design, not validated system.**

**Load-bearing VERIFIED items** (checked against git/disk/config): (1) both worktree HEADs+branches incl. commits `5d2fca2→f351403→9bb3f04`; (2) SHA256 of 9 config files; (3) catalog 44-vs-43 diff + `playwright.args`; (4) Stop line-numbers + 5 tests + inject→allow telemetry; (5) Antigravity symlink→2 entries `58c8d213…`; (6) provider counts 63/25/33/2; (7) 8-equal/6-unequal live-vs-HEAD; (8) WizTree 12.67M-row census + focus-root sizes; (9) listeners (8765 present; 8812/8760 absent); (10) transcript census 10,677 files / 9.919 GiB; (11) rubric 21/39.

**Merely ASSERTED:** the "421k tokens/52% window" prior footprint (historical); the *old-adapter* half of the Stop chain (inferred, only the fix is shown); the 8 mock conformance interpretations; process topology (self-hedged); the `202` Workspace contract (from docs); Antigravity runtime load (explicitly unproven); the plugin-bridge "resurfacing" mechanism (Codex itself says unproven).

---

## E. MCP-scope matrix (69 rows) — verdicts

**codacy** → in `claude_user`, `codex_user`, `gemini_user`; **absent from both catalogs**. Disposition: **"UNRESOLVED … do not remove by presence alone"** = HOLD (D-012). **deepsource** → `claude_user` + `gemini_user` only, no Codex. Disposition: **"UNRESOLVED/LIKELY-PRUNE-OR-PROJECT: no Codex callable parity; process overhead observed"** = prune-leaning but not authorized. So **neither is auto-removed**; deepsource is the weaker (more prunable) of the two.

**User-vs-project scope findings:** Claude **user=63** (54 stdio+9 http, "no per-entry disabled field"); Claude **home project=42** but `settings.local.json` explicitly activates **only 12** (`enableAllProjectMcpServers=false`); Claude **research project=40**. Codex's load-bearing model: **registration ≠ activation ≠ liveness** (D-007), and **"no blanket user-scope promotion"** — heavy/repo-bound/identity-bearing servers stay project/local/on-demand. This directly aligns with our own "don't bulk-promote to user scope" memory.

**"Resurfaced MCP" root cause — Codex does NOT confirm it.** Finding #3: "The mock claimed plugin-bridge resurfacing as *verified*, but current `.claude.json` also contains explicit top-level registrations. The exact restoration mechanism and owner intent still require field/provenance evidence." → Codex **under-credits our already-established root cause** (UI-disable writes *project* scope; fix = `claude plugin disable --scope user`). It treats the mechanism as unproven rather than adopting our prior finding. (A reconciliation gap, not a contradiction.)

**Keep / prune / defer calls:** RETAIN `basic-memory` (canonical singleton). HOLD/UNRESOLVED (no prune w/o approval): `codacy, agent-mail, angr`. LIKELY-PRUNE-OR-PROJECT: `deepsource`, `memory`(Gemini-only, conflicts w/ Basic-Memory). REVIEW-SUPERSESSION (may be superseded by search-hub/native): `firecrawl, tavily, exa, figma-rest, meta-tool`. RECONCILE (definition drift): `playwright`(args), `cloud-hub`(env). ADAPTER (provider-specific, legit): `ralph-orchestrator` (native-Win vs WSL). EXPERIMENTAL (catalog-only, don't promote): `codex-fleet-github`. CLASSIFY (decide scope/profile/lifecycle) for most shared-catalog members. **No row authorizes deletion.** Notable catch: `agent-mail` "REVIEW-BLOCKED: fixed endpoint enabled in Codex but **no listener on 8812**" — contradicts our CLAUDE.md "always-on 8812" claim → possible degraded supervisor; corroborates "registration ≠ liveness". (`8765 basic-memory` present ✓ corroborates our own port map, raising snapshot credibility.)

---

## F. Whole-drive index — census & "does it replace a WizTree scan?"

**It IS the distilled summary of a WizTree scan, not a substitute for one.** Method = path-only streaming over the **complete** WizTree CSV exports (`WizTree_20260713055603 (C).csv` + `...060430 (D).csv`), **12,677,701 rows** (C 7.04M + D 5.64M), no file bodies opened. So it consumes a raw WizTree export and argues *against re-crawling on every run*.

- **Focus-root sizes:** `.claude` **36.6 GB** (dominant), `.codex` 3.64 GB, `.agents` 469 MB, `.gemini` 386 MB, `agent-skills-toolchain` 2.27 GB, `ast-harness-reconcile` 41 MB; `D:\Research` 50 GB, `D:\basic-memory` 14.7 GB.
- **Doc-sprawl census (C: / D:):** `AGENTS.md` **603/59**, `CLAUDE.md` **284/50**, `.mcp.json` **239/13**, `settings.json` 227/46, `hooks.json` 164/5, `config.toml` 153/26, `canonical-mcp-servers.json` **5/2**, `DEPLOYED-MANIFEST.json` **1/0**, `RECONCILE-LOG.md` 1/0, `installed.json` 36/0.
- **"mcp"-named dirs:** C 5144 / D 1324, of which **~91% excluded** as vendor/cache/generated (4695/5144 C, 1204/1324 D).
- **Interpretation (Codex):** counts are *candidates, not canonical sources or duplicates*; high counts "validate the need for a deterministic registry … rather than whole-disk content crawling"; **no cleanup/deletion authorized.**
- **Two gaps worth flagging:** (a) **5 `canonical-mcp-servers.json` on C:** but Codex only reconciled 2 (the 44 & 43) — 3 unaccounted. (b) A **`DEPLOYED-MANIFEST.json` exists** yet the RFC proposes building a *new* bundle/manifest receipt system as if none exists, and Finding #6 says "no receipt proves whole-tree deployment" — Codex census-detected a deployment manifest but did not treat it as the parity receipt (possible not-invented-here / missed existing artifact).

---

## G. Stop-loop / recursive-lifecycle-hook incident — verdict

**Symptom:** `Shared harness: Stop… 3/4` in the Claude transcript; reported 32m25s / 53.2k-token drain.
**Root cause chain (Codex):** (1) first Stop → `ClaimWarningModule` advisory injection; (2) Claude continues, invokes Stop again; (3) reentrancy marked via native `stop_hook_active`; (4) **old adapter read only generic `trigger`, so the reentrancy signal was lost**; (5) advisory re-injects until the host continuation cap.
**Fix present + evidence:** one Stop registration (5s timeout); `adapters.py:121-128` normalizes `stop_hook_active`; `modules.py:1733-1746` silent-allow before claim detection on re-entrant Stop; 5 tests pass 0.61s; runtime `inject → allow` telemetry.
**My verdict:** **technically sound and well-evidenced [EVIDENCE-BACKED].** The `stop_hook_active` mechanism matches documented Claude hook behavior; the fix is real and tested. Codex correctly calls it **"contained, not universally closed"** and recommends hardening (move the invariant to the **dispatcher/mixer boundary**, add a whole-module subprocess test + an actual Claude host-integration test). The only ASSERTED part is the *old-adapter* behavior (step 4) — the pre-fix code isn't shown, only the post-fix path. **This is Codex's best work; I largely agree.** Note: `modules.py` (the Stop guard's home) is one of the uncommitted worktree files, i.e., the fix is **live-deployed but ahead of committed HEAD** — which is exactly why Finding #6's "partial deployment" is *enshrinement-in-progress*, not a defect (see §I.1).

---

## H. Decision ledger — notable decisions + supersessions

24 rows (D-001..D-024). Supersessions/reversals:
- **D-005 "deployment is globally atomic" → SUPERSEDED by D-018** "per-target atomic replacement within a durable conflict-detecting compensating transaction." (Skeptic/critic found multi-target/volume/provider can't be one atomic rename.)
- **D-011 "MCP reduction completed permanently" (2026-04-01) → SUPERSEDED-current-state**: current 63/25/33 disproves durability. (Matches our own "bloat regressed" memory.)
- **D-013 "one canonical MCP catalog exists" → invalid/split-brain** (44 vs 43 + Codex 25-name third authority).
- **D-020 "an audit/read-only prompt naturally stays non-mutating" → invalid**, "mock failed conformance" → replaced by **testable invariants** (executable freeze fixtures).
- **D-021 "council convergence authorizes implementation unless owner objects" → REJECTED**; explicit affirmative approval required.
- **D-022 "mock decision queue is current machine truth" → evidence-not-authority.**
- **D-016 "provider hooks reach every background workflow subagent" → invalid/disproven**: "129 main-loop signatures vs zero in 14 subagent transcripts" → use static-lint/propose-only, don't promise hook enforcement. *(Notable, real limit.)*
- **D-019 "Antigravity generatable from Gemini settings" → invalid-as-stated** (symlink to distinct 2-server config; loader unproven).
- **Retained roles:** D-003 Basic Memory = semantic authority (off correctness path), D-004 event ledger = objective history, D-010 no second orchestrator/memory/observability.

---

## I. Critical assessment — WRONG / mismodeled claims (the load-bearing part)

### I.1 "Partial deployment" framing MISMODELS an in-progress enshrinement `[MISMODELS]`
Codex's raw comparison (8 live files = HEAD, 6 ≠ HEAD) is **[EVIDENCE-BACKED]**. But the *conclusion* — "unexplained partial drift", "no receipt proves whole-tree deployment", used to justify "must not be deployed yet" — does **not** follow from the evidence, because:
- `modules.py`, `test_modules.py` (2 of the 6 unequal files) are **in Codex's own `uncommitted_areas` list** for the worktree. So live≠HEAD for those is the **expected** state during an active `chore/enshrine-runtime-config` branch whose *entire purpose* is to enshrine live runtime config into the repo.
- Commit **`9bb3f04` "anti-drift enforcement"** is precisely the reconciling mechanism, and the parent confirms it is **real, peer-reviewed** work (part of `5d2fca2`→`f351403`→`9bb3f04`). Codex acknowledges `9bb3f04` "adds anti-drift controls" (D-002/D-008) but characterizes it as **"partial"** — a characterization the parent disputes as complete anti-drift enforcement. That partial-vs-complete claim is checkable against the commit; I did not re-audit it (out of scope), so I flag it as **contested, evidence-underdetermined**.
- **Net:** Codex's evidence supports "live currently differs from committed HEAD for 6 files (several of them known-uncommitted)"; it does **NOT** support "the harness is broken/undeployed." It is mid-enshrinement — a different and expected state.

### I.2 The "mock" narrative — precise reconciliation `[EVIDENCE-BACKED file existence / ASSERTION on failure]`
The parent's ground-truth guard was: *the three commits are real peer-reviewed work, NOT a mock.* **Finding: Codex AGREES the three commits are real** — it explicitly calls them "three unpushed commits" and never labels them a mock. **Codex's "mock" is a DIFFERENT artifact:** the concurrent Claude 13-agent discovery run (`workflow wcph0kvkg`, ~1.7M tokens, 27m35s) that created `docs/phase3-discovery-2026-07-13/` (14 files, 380 KB) — i.e., **our Phase-3 discovery output** (confirmed: I am writing into that directory; it contains our council-*/inventory-*/research-*/DECISION-QUEUE files). So:
- **Do not over-rotate against Codex here** — on the commits, Codex and Claude actually **agree** they are real work. The parent's worry ("if Codex treats it as a mock") is **unfounded for the commits.**
- Codex's 8 "conformance failures" mix **[EVIDENCE-BACKED]** observations (14 files created; Basic-Memory note written; 1.7M-token fan-out; rediscovered a prior queue) with **[ASSERTION]** interpretations ("treated council as authorization", "proceed unless objected", "recommended deploy/delete"). Some are fair process critiques; some are Codex's framing of our legitimate discovery as a failure.
- **Double-standard to flag:** Codex criticizes the mock's "expensive fan-out discovery" while itself running a **12.67M-row whole-drive scan + a 2-month, 10,677-file transcript census + process-topology sweep.** Codex's defense (its scans are deterministic/path-only/bounded vs an unbounded LLM fan-out) is *partially* valid — but the "you did too much discovery" critique lands awkwardly given Codex's own discovery volume.

### I.3 Appropriately-hedged, not wrong
Process topology (786/272 — self-labeled estimates), Antigravity runtime (explicitly unproven), plugin-bridge resurfacing (explicitly unproven), the `202` contract (from docs). Codex flags each limitation honestly — these are **not** errors, and the honesty is a strength (AC-27 PASS).

---

## J. AGREE vs DIFFER vs our working thesis

**Our thesis:** (A) `agent-skills-toolchain` = single source of truth; (B) deploy repo→live via copy + pre-deploy backup + live↔repo parity check; (C) gates on an OFF→SHADOW→ADVISE→ENFORCE ladder; (D) right-size — one user, one Windows box, not a multi-tenant control plane.

**3 sharpest AGREE:**
1. **(A) Single source of truth = `agent-skills-toolchain`.** Codex OWNER-2 default + D-001 land exactly here. Strong agreement.
2. **(B-principle) One-way repo→live; live is *observed/deployed* state not editable source; need backup (exact preimages) + parity (raw+semantic hash, second-plan no-op).** D-002 + RFC §9 + AC-10. Agreement on direction and on the *need* for a parity check.
3. **(D-philosophy) Anti-sprawl:** no daemon, no second memory/orchestrator/observability, no fleet ACID, no whole-`.claude.json` rewrite. D-010 + RFC §13. Directly matches "not a multi-tenant control plane."

**3 sharpest DIFFER:**
1. **Mechanism weight (B/D).** Codex = CAS + 11-state durable journal + compensating transactions + crash-after-every-transition fault matrix + content-addressed bundles. Ours = **copy + timestamped backup + parity diff** (+ at most a pre-write hash-check for concurrent-session safety). Codex is fleet-grade; **over-engineered for one box/one user.** This is the parent's over-engineering flag, confirmed.
2. **Lifecycle model (C).** We want an **OFF→SHADOW→ADVISE→ENFORCE gate-mode ladder** (how a gate/hook *behaves*). Codex has **no such ladder**; it offers a **deployment-transaction** lifecycle (PLANNED..COMMITTED/COMPENSATED) + a Wave ladder (fixture→disposable→canary). Adjacent but **different axis** — Codex does not cover our gate-rollout ladder. (Ironically the harness already ships shadow/advise/enforce semantics — the Stop `inject` vs `allow`, anti-drift "enforcement" — so our ladder is the more natural fit and is a genuine coverage gap in Codex's RFC.)
3. **Status of our work (values clash).** Codex subordinates the whole `ast-harness-reconcile` worktree to **"frozen staging evidence, not deployable authority"** and frames our discovery fan-out as a **conformance failure**. We frame the enshrine commits as shipped, peer-reviewed work. Reconcilable path: `ast-harness-reconcile` is the **staging branch that merges into** `agent-skills-toolchain` (the canonical root) — but note `agent-skills-toolchain`'s catalog (44) is the **staler** one (holds the "possible-superseded" `exa/figma-rest/firecrawl/tavily`), so "canonical root" ≠ "already-correct catalog"; Wave 0 catalog reconciliation is still required either way.

---

## K. Codex's biggest evidence GAPS (for the synthesis step)

1. **The RFC is 100% unbuilt** — only 4/36 acceptance rows pass, 3 of them audit-scope; every projector/CAS/journal/parity claim is `NOT_BUILT`/`NOT_RUN`. Design, not validated system.
2. **"Partial deployment" defect claim rests on live≠HEAD for files that are *known-uncommitted*** — the evidence shows enshrinement-in-progress, not breakage (§I.1).
3. **Ignored an existing `DEPLOYED-MANIFEST.json`** (census-detected, count=1) while asserting "no receipt proves deployment" and proposing a brand-new bundle/manifest system.
4. **3 of 5 `canonical-mcp-servers.json` on C: unaccounted for** (only the 44 & 43 reconciled).
5. **Under-credits our established "resurfaced MCP" root cause** (UI-disable→project-scope) as "unproven".
6. **`agent-mail` 8812 listener absent** flagged but not root-caused (degraded supervisor vs never-running) — a live-service health question left open.
7. **Old-adapter half of the Stop chain is inferred**, not shown (only the fixed path has code evidence).
8. **Antigravity runtime load, plugin resurfacing mechanism, and the `202` Workspace contract are all unexercised** (doc/inference only) — Codex says so, but they remain gaps for any decision that leans on them.