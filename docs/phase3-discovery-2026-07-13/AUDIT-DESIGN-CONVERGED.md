# Converged Audit/Design Gate — Harness Config SSOT (2026-07-13)

Reconciles four independent inputs: our Claude-side discovery (`DECISION-QUEUE.md`) + the
independent **Codex** control-plane audit (8 artifacts in `Documents/Codex/2026-07-13/…/outputs/`)
+ prior forgotten decision-queues + **direct git/disk ground-truth verification** (this session).

**Status: AUDIT/DESIGN GATE.** No build / deploy / push performed. Ends with ≤3 owner decisions +
a recommended Wave-0. All proposals are PROPOSED. Cross-checked by two independent extraction
agents + owner-in-the-loop; a dedicated deploy-plan critic is folded into Wave-0 step 1.

---

## 1. Ground truth — directly verified this session (not either audit's prose)

### 1.1 The enforcement IS inert on live — CONFIRMED (~95%)
- `grep` of live `~/.agents/harness/*.py` for `_canonical_config_edit_guard`, `_basic_memory_nudge`,
  `_live_trees`, `_canonical_tree` → **all absent.** Only a defensive
  `getattr(self.ledger, "last_failed_fingerprint", None)` caller is present in live `modules.py`.
- ⇒ the anti-drift enforcement (commit `9bb3f04`) + task-8 tree-helpers are **NOT DEPLOYED to live.**
  The discovery's headline finding is confirmed by direct grep, not inference.
- **Drift direction: repo (working-tree ⊇ HEAD) is AHEAD of live.** Live = older baseline that HAS
  the Stop-loop fix (Agent-2 verified live `modules.py`/`adapters.py` + backup
  `modules.py.bak-loopfix-20260713-021353`) but LACKS: task-8 helpers, `config_drift` shape-fix
  (`f351403`), both enforcement gates (`9bb3f04`), task-9 codex (uncommitted).
- **NOT a hard fork** (no material live-ahead content; the loopfix is in both per `RECONCILE-LOG`).
  A safe deploy must still **back up live first + diff** in case of a sliver (~85%).
- `git diff HEAD -- ci/harness` = ONLY `modules.py` + `test_modules.py` (task-9, +88/−11). Confirmed.

### 1.2 Codex audit — real findings + 2 evidence gaps I disproved
- **CONFIRMED (Codex + me):** MCP split-brain (catalogs 44 vs 43, 7-name diff, `playwright.args`
  drift); Stop-loop root-cause is evidence-backed + sound; agent-mail `:8812` listener ABSENT.
- **Codex WRONG (disproved):** "no deployment receipt" — both `skills/DEPLOYED-MANIFEST.json` AND
  live `~/.agents/harness/installed.json` EXIST. Codex missed both.
- **Codex did NOT call our 3 commits a "mock"** (Agent-1 correction to my earlier caveat) — it labels
  the 13-agent discovery run "the mock." Do not over-rotate against Codex on state-modelling.
- **RFC verdict (Agent-1):** right-sized in DIRECTION (anti-sprawl, matches us), **over-engineered in
  MECHANISM** (CAS + 11-state durable journal + compensating transactions + content-addressed
  bundles to copy ~20–60 config files on one box). Some concurrency safety is defensible (the real
  `~/.claude.json` multi-session clobber-race); full journal/compensation is fleet-grade over-build.

### 1.3 agent-mail `:8812` DOWN — CONFIRMED breakage
- Direct probe: connection refused. The "always-on via `MCPAgentMailSupervisor`" claim is **false now**
  — the supervisor task itself may be dead. FLAG. Owner quick-action:
  `Start-ScheduledTask -TaskName MCPAgentMailSupervisor`. NOT restarted here (gate discipline).

---

## 2. Big scope finding — Axis A vs Axis B (don't lose prior work)
- **Axis A** = this phase-3 program: config / MCP / skill / doc single-source-of-truth.
- **Axis B** = the prior 48 KB `ULTRACODE-HARNESS-SOTA-DECISION-QUEUE` (2026-07-12): the
  `agent()/parallel()/budget()` **orchestration engine** — 117 findings / 8 gems (H1–H8) / 5
  decisions (D1–D5). **~0 % overlap with Axis A.**
- **This INVERTS the owner's fear:** we did NOT re-derive it — the risk is **LOSING** it (max-loss).
- Also still-open + at-risk: **OPEN-THREADS** backlog (proactive-partner, UI/UX overhaul, media
  consolidation, BN harness, ToolUniverse); reasoning-spine gems (GEPA, sleep-time,
  Calibration-Brier ledger, Discipline-Forge, TMS auto-retraction); verified dead-ends worth
  preserving (mem0 ≥7B NO-GO, TG.16 double-run REFUTED).
- **AGENTIC-PERFECTION #9 "AGENTS.md 3-divergent-files" is the ANCESTOR of Axis A** (continued +
  expanded — not a re-derivation). June `CONSOLIDATED-GEM-DECISIONS` mostly SUPERSEDED (built); thin
  duplicate slice (MCP-prune / skill-dedup / doc-GC) already echoed by our D1.2/D1.4/D3.1.
- `biomedical-harness-audit`: **NOT FOUND on disk** — the discovery likely mis-referenced it.

---

## 3. Cross-audit convergence (high-confidence — proceed without a fork)
Both independent audits (Codex + ours) + verification AGREE:
1. **Single source of truth = `agent-skills-toolchain`** (fold `ast-harness-reconcile` as frozen staging). *(Owner-confirmed D0.2.)*
2. **One-way deploy:** repo → validated candidate → copy to live + PRE-DEPLOY BACKUP → parity-hash check → receipt. No bidirectional sync; no silent live→repo writes.
3. **Anti-sprawl:** NO new daemon, NO 2nd memory store, NO fleet-ACID / 2nd orchestrator.
4. **Stop-loop:** FIXED + LIVE + backed-up (keep; optional refinement = a central-mixer invariant + host-integration test).
5. **Gate lifecycle = OFF→SHADOW→ADVISE→ENFORCE** (OUR ladder; Codex's RFC lacks it — fold ours in).
6. **MCP resurfacing root cause = the plugin-bridge at user scope (`enabledPlugins`)** — unique to our side; Codex inspects `.mcp.json` and misses it. Fix at the plugin layer, not `.mcp.json`.

---

## 4. Genuine conflicts → OWNER DECISIONS (≤3)

### DECISION A — Scope re Axis B + prior work
- **(a) RECOMMENDED — Preserve-by-reference.** Cross-link + register Axis B (48 KB ULTRACODE) +
  OPEN-THREADS + reasoning-spine as a SEPARATE still-open track with an explicit pointer index; keep
  THIS gate tight to Axis A. Don't lose them, don't absorb them (absorbing re-bloats + violates the
  tight-audit discipline).
- (b) Fold Axis B into this program (one mega-program) — massive scope expansion, re-bloat risk.
- (c) Axis A only, defer Axis-B preservation — risk: it stays scattered / at-risk.

### DECISION B — Architecture weight
- **(a) RECOMMENDED — Right-sized.** repo=SoT + copy-deploy + pre-deploy backup + parity-hash check +
  OFF→SHADOW→ADVISE→ENFORCE ladder + a LIGHT single-writer deploy-lock (covers the real clobber-race).
  Reject Codex's CAS / 11-state journal / compensating-transactions / content-addressed bundles as
  fleet-grade over-build for one box. *(= my held-caveat #3 + Agent-1's mechanism verdict.)*
- (b) Adopt Codex's full transactional RFC — stronger guarantees, far more to build + maintain.
- (c) Even lighter — copy-deploy + backup only; skip the parity gate + lock (weakest drift-detection).

### DECISION C — Wave-0 go/no-go (leaving the gate)
- **(a) RECOMMENDED — Approve Wave-0** = deploy repo→live (closes the confirmed inert-enforcement
  divergence) + wire the live↔repo parity check + fold the 5 `settings.json` hook hand-edits + fix the
  `CLAUDE.md` AgentBridge staleness (D3.4) — on `agent-skills-toolchain`, incrementally, each step
  verified, **branch pushed.** Codex build (task-9) held for a separate feature decision.
- (b) Smaller Wave-0 — just deploy + parity; defer the doc-fix + push.
- (c) Stay in gate — authorize no build yet; refine design/decisions first.

---

## 5. Disposition matrix
| Item | State | Disposition (proposed) |
|---|---|---|
| Anti-drift enforcement (`9bb3f04`) | committed, INERT on live | Deploy in Wave-0 (Decision C-a) |
| `config_drift` shape-fix (`f351403`) | committed, not live | Deploy in Wave-0 |
| task-9 codex-invoke build (`tools/codex/`, `skills/codex-invoke/`, `modules.py` +88/−11) | uncommitted, design-only spec + built files | **HOLD** — separate feature-commit decision; Axis-adjacent, not core SSOT |
| codacy / deepsource resurfaced MCPs | ride plugin-bridge at user scope | Wave item: fix at plugin layer; do NOT prune on redundancy alone (Codex caution) until capability/cost established |
| MCP split-brain (7-name diff, playwright.args) | live vs canonical drift | Wave item: reconcile to canonical + launch-read `.mcp.json` (D0.5, owner-confirmed) |
| `CLAUDE.md` AgentBridge budget-pacing block | stale (daemon retired) | Fix-before-push (Wave-0, Decision C-a) |
| agent-mail `:8812` down | confirmed breakage | FLAG — owner quick-action `Start-ScheduledTask`; not restarted here |
| Secrets (accounts.json, git-crypt) | out of scope; gitignore+gitleaks floor holds | No age/SOPS (council + reframe agree) |
| Axis B (48 KB ULTRACODE) + OPEN-THREADS + reasoning-spine | still-open, ~0% re-derived | Preserve-by-reference (Decision A-a) |

---

## 6. Wave-0 runbook (critic-hardened — deploy-plan critic verdict: PROCEED-WITH-FIXES ~85%)
Critic confirmed: design sound + right-sized, no irreversible-loss path (backups cover tree+settings;
the live "sliver" = 2 live-only lines of the OLD `_config_drift` form, superseded by `f351403`,
benign + backed-up). Push target correct (`agent-skills-toolchain`, fresh branch, `main` untouched).
Execution order revised to close 5 must-fixes:

1. **Build CAS-lite mechanism** (install.py) — atomic per-file `os.replace` (NOT dir-rename; Windows
   has no atomic dir-replace) + single-writer lock + pre-write re-hash (CAS abort-on-change) +
   post-write parity + restore-on-mismatch + receipt. *[builder]* Verify per-file `os.replace` in
   import-leaf order.
2. **Commit Wave-0 repo changes FIRST** (MUST-FIX #1/#3), **scoped** — install.py + test_install_deploy
   + CLAUDE.md fix + AXIS-B-PRESERVE-INDEX + audit docs. **Exclude HELD task-9** (modules.py delta,
   test_codex_profiles.py, tools/codex/, skills/codex-invoke/). NEVER `git add -A`.
3. **Deploy from the CLEAN committed state, NOT the dirty tree** (MUST-FIX #1): source via
   `git archive HEAD ci/harness` → temp → CAS-lite deploy → live. Back up live first.
4. **Post-deploy: run `python ~/.agents/harness/install.py --check` from the LIVE tree** (MUST-FIX #4;
   running install() from the repo would repoint hooks to the dev dispatcher). Parity must be clean.
   Only run full `install()` if live settings.json is missing the folded hooks (earlier check: it
   already matches — so `--check` only).
5. **Push ONLY if parity clean** (MUST-FIX #3): `git push -u origin chore/enshrine-runtime-config`.
   Never `HEAD:main` / `--force`.
6. Nice-to-haves: clear live `__pycache__` post-deploy (copy2 preserves mtime → stale-pyc); confirm no
   hook hard-depends on the DOWN agent-mail `:8812` before promoting gates.
7. Anchor a drift-audit to SessionStart (not `ConfigChange`). Promote the 2 enforcement gates
   SHADOW→ADVISE only after burn-in (no mid-session hard-block).

## 7. Right-sized architecture (reject fleet-grade)
Adopt: Git=authority · manifests+hashes=live-state receipts · basic-memory=semantic · event-ledger=
events · env/git-crypt=secret values · runtime dirs=mutable. One-way deploy path with pre-deploy
backup + parity-hash + a light single-writer lock + OFF→SHADOW→ADVISE→ENFORCE. **Reject:** typed
logical catalog, provider adapters, compare-and-swap, 11-state durable journal, compensating
transactions, content-addressed bundles, stale-lease recovery — fleet-grade for a single-user box
(anti-overfit; Agent-1 + council + my caveat #3 concur). Borrow their *lessons* (atomicity, backup,
verification), not their machinery.
