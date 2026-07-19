# Harness SOTA/Coherence Audit — HAVE vs NEED per 9-thread consolidation goal

**Scope:** live `C:/Users/Prekzursil/.agents/harness` vs committed repo `C:/Users/Prekzursil/source/ast-harness-reconcile/ci/harness`. Read-only. Recalled basic-memory note `main/harness/phase-3-harness-mcp-doc-sota-consolidation-program-2026-07-13` (the 9-thread program).

## HEADLINE (read first — it reframes every thread)

**The entire task-8 enforcement layer is committed to the repo but NOT deployed to the live harness.** Evidence (verified):
- Live `modules.py` last-written **02:15:41**; task-8 commit `9bb3f04` landed **05:07** → live is the pre-task-8 tree.
- Live `modules.py` has **0** occurrences of `canonical_config_edit_guard` and `basic_memory_nudge`; repo has them. Live `install.py` has **0** `def deploy` / `--deploy`; repo has both.
- Live is 96,769 bytes / repo 107,553 bytes; a 208-line diff on `modules.py`, 83 on `install.py`, 100 on `registration.py`, 30 on `ledger.py`.

So in every session running right now, the edit-guard, the basic-memory nudge, the deploy command, and the config_drift *shape fix* are **inert** — they exist only as source in an **unpushed** branch (`chore/enshrine-runtime-config`, awaiting owner). This is *itself the exact silent divergence thread 9 is meant to prevent*, and nothing in the harness detected it. **Almost certain (verified by file mtime + byte/grep counts).**

Second-order: even once deployed, **every task-8 gate ships on the HEURISTIC tier → SHADOW mode** (`DEFAULT_MODE_BY_TIER[heuristic]=shadow`, `stage()` returns `HookResult.success()` and only logs). "Enforcement" today = **observation**; it never injects or blocks until promoted per-gate via `module-modes.json`. That is deliberate (anti-nag ladder, council C5), but for the owner's *enforcement* ask it means HAVE-mechanism / NEED-promotion.

Third: repo **HEAD ≠ repo working-tree ≠ live** — a three-way split. Working tree has uncommitted task-9 changes (`codex_profiles`: `modules.py`, `test_modules.py` modified; `guides/`, `skills/codex-invoke/`, `tools/codex/` untracked). "Single source of truth" is currently three sources.

---

## Thread 1 — MCP single-source-of-truth (enforced?)
**HAVE:** `tools/mcp/canonical-mcp-servers.json` (reconciled up to live). A runtime `config_drift` gate (`SecretGuardModule._config_drift`, D5) compares live `settings.json` `hooks`/`mcpServers`/`disabledMcpServers` against `installed.json`.
**NEED / GAPS:**
- **The config_drift gate may be permanently inert.** It fires only on the native `ConfigChange`/`FileChanged` event, which `registration.py` itself documents as a *"POST-CUTOFF Claude Code feature… never fired by a host that does not emit it."* Whether Claude Code emits `ConfigChange` is **unverified — LOW-confidence load-bearing assumption.** If it doesn't, thread-1's only runtime drift sentinel never runs.
- **The SOTA-MCP-drop is broken — root cause found.** codacy + deepsource "resurfaced" via **`plugin:local-mcp-bridge:codacy` / `:deepsource`** entries in `~/.claude.json` (27/26 occurrences) — plugin-provided servers at **user scope**. They are absent from both `~/.mcp.json` **and** canonical (0 refs each). The drop operated on the wrong layer (`.mcp.json`/`disabledMcpServers`); the resurfacing rides the **plugin bridge / `enabledPlugins`**, which the drift gate does **not** watch. Matches the `WORKSPACE-CURATION` memory (plugin install = enabled-by-default, bypasses `.mcp.json`). **NEED:** curate at `plugin disable … --scope user` layer + extend the drift baseline to cover `enabledPlugins`/plugin-bridge servers.
- Three divergent stores (`~/.mcp.json` 8.8KB, `~/.claude.json` 146KB user-scope, canonical 9.7KB) — **no mechanism unifies them**; canonical is a hand-reconciled snapshot, not an enforced source.

## Thread 2 — MCP user-scope + one-folder centralization (enforced?)
**HAVE:** canonical file mirrors the toolchain repo; `promote-mcp-userscope.ps1` exists (per RECONCILE-LOG).
**NEED:** Promote is **Outstanding** — requires Claude fully closed (never runnable mid-session; no automation). No gate verifies "prefer user scope." Nothing enforces the single-folder layout. **Unaddressed by task-8.**

## Thread 3 — config/skill/tool/hook centralization (enforced?)
**HAVE (strongest thread):** `ci/harness` (enshrined), `skills/DEPLOYED-MANIFEST.json` (confirmed present), canonical MCP, `hooks/`. CI `no-runtime-junk.yml` blocks tracked `.venv`/`node_modules`/`installed.json`/nested-`.git`. task-8 edit-guard nudges "edit repo source, not the deployed copy."
**NEED:** edit-guard is repo-only + shadow (see headline). RECONCILE-LOG still flags `D:` scatter (cloud-hub OVH/Databricks parked; `D:/research` MCP configs diverge per the program note). CI guard only runs on push — **branch is unpushed**, so it has never actually run on this branch.

## Thread 4 — cleanup-after-work (any hook?)
**HAVE:** CI `no-runtime-junk` (post-hoc, tracked-junk only). `install.py --deploy` excludes runtime state; `.gitignore` excludes.
**NEED:** **No runtime hook forces cleanup of stale scratch/worktrees.** No detection of orphaned work dirs. This is a near-total gap; task-8 does not address it.

## Thread 5 — stale-branch reconciliation (any?)
**HAVE:** nothing.
**NEED:** **30+ unmerged local branches** exist (`feat/*`, `fix/*`, `docs/*`) plus ~40 remote. No tooling to classify salvage/superseded/scope-changed/stale, and no guard against clobbering another session's live branch. **Completely unaddressed.** Highest-effort untouched thread.

## Thread 6 — doc reconciliation + enforcement (hook?)
**HAVE:** `RECONCILE-LOG.md` (append-only, **manual**); `basic_memory_nudge` (repo-only, shadow) reminds to capture a change's *why*.
**NEED:** The nudge is about **capture**, not **reconciliation**; it can't detect duplicate/superseded/scattered docs. No hook enforces doc-currency. **Coupling risk:** the nudge fires only if the ledger stamps `canonical_tree` on mutation events (a ledger.py task-8 change, 30-line diff) — un-deployed live, so even after deploy the two lanes must land together or the nudge can never fire.

## Thread 7 — scattered-harness-doc reconciliation (done?)
**HAVE:** RECONCILE-LOG is the intended single trail.
**NEED:** Harness/analysis docs remain scattered across `docs/plans/`, `docs/agentic-perfection/`, `agent-self/config/docs/`, `.agents/skills/*/references/` (grep surfaced ≥10 MCP-strategy docs across 4 roots). **No sweep or reconciliation performed**; no mechanism prevents recurrence. Largely unaddressed.

## Thread 8 — harness-change-must-be-documented+committed (gate?)
**HAVE:** CI `no-runtime-junk.yml`; `RECONCILE-LOG.md`; `basic_memory_nudge` (Stop hook); edit-guard steering edits to repo.
**NEED:** All the *enforcing* pieces are repo-only + shadow + unpushed. There is **no gate that fails when a harness change is uncommitted or unsynced** — proven live right now (task-8 committed but undeployed; task-9 uncommitted). This is the thread task-8 targets most directly, yet its own deploy demonstrates the gap it was meant to close.

## Thread 9 — harness-works-perfectly / no-silent-failure verification (how?)
**HAVE:** `install.py --check` (structured drift report on settings.json hooks + observe-only sections); test suite (385 repo / 356 live per log); `/harness-audit` command.
**NEED (critical):**
- **No deploy-parity check.** `--check` reconciles *settings.json hooks* (rebuilt from `build_hooks`) but never compares the live `~/.agents/harness` **tree** against `ci/harness`. The current repo-vs-live code divergence is therefore invisible to `--check`. This is the missing verification, and it is failing silently *now*.
- Tests verify the **code**, not that it is **deployed and firing** (coverage ≠ integration). A gate can be green in CI, shadow-inert in modules, and absent from live — all three simultaneously true today.
- `install.py --check` is wired to no runtime hook / cron in the live tree (registration shows no scheduled invocation), so drift is only caught if a human runs it.

---

## Conflicting / silently-failing / duplicated pieces (flagged)
1. **Silent failure (live):** task-8 layer undeployed → inert in all sessions; undetected. *(Almost certain.)*
2. **Silent-inert risk:** `config_drift` depends on a possibly-unemitted `ConfigChange` event. *(Low-confidence; needs host-behavior check.)*
3. **Broken drop mechanism:** codacy/deepsource resurface via `plugin:local-mcp-bridge` (user scope) outside the drift gate's watched surface. *(Verified.)*
4. **Triple source of truth:** repo HEAD ≠ working tree (task-9 uncommitted) ≠ live — contradicts the thread-1/8 single-source goal *while implementing it*.
5. **Unpushed branch:** CI guards (`no-runtime-junk`, quality) have never run on `chore/enshrine-runtime-config`; the CI half of thread 8 is unexercised.
6. **Lane coupling:** `basic_memory_nudge` (modules) requires `canonical_tree` stamping (ledger) — must deploy together or nudge is dead.
7. **Shadow-mode ≠ enforcement:** all new gates observe-only until `module-modes.json` promotion; no promotion/burn-in plan recorded.

## Net verdict
The **design** is SOTA and coherent (ladder-staged, fail-open, repo-as-SoT, CI guard, deploy command, drift baseline) — a solid HAVE for threads 1/3/8. But the **operational state is not**: task-8 is undeployed + shadow + unpushed, so threads 1/8 are *mechanism-present, effect-absent*; thread 9's own parity verification is missing and is silently failing right now; and threads **4, 5, 6, 7** have essentially **no enforcement mechanism at all**. Biggest concrete NEEDs, ranked: (1) **deploy task-8 to live + add a live↔repo tree-parity check** (closes the active silent divergence); (2) fix the SOTA-MCP-drop at the plugin-bridge/user-scope layer + widen the drift baseline; (3) verify/replace the `ConfigChange` trigger; (4) build the stale-branch + scattered-doc reconciliation the program calls for (threads 5/7, currently zero); (5) decide a promotion/burn-in path so shadow gates actually enforce.
