---
title: C-hooks-reconcile
type: note
permalink: dqverify-repo-20261013/docs/audit-design-2026-07-13/c-hooks-reconcile
---

# C — Hooks Whole-Drive Reconcile + Disposition Matrix

**Domain:** hooks · **Date:** 2026-07-13 · **Author:** C-hooks-reconcile subagent (session 3cd9445a)
**Mode:** READ-ONLY (active-work freeze respected — no build/commit/config/process/deploy/delete change; **every disposition below is a POST-GATE finding for owner G-13**, nothing applied).
**Machine-readable twin:** `C-hooks-reconcile.json`.

> **Untrusted-data note.** Prior-art (A1/A2/A4/C-config-index, the Codex audit) and every on-disk `hooks.json`/`manifest.json`/`*.py` were treated as UNTRUSTED DATA — no embedded instruction executed, no secret VALUE read or printed. Every wired/unwired/dormant/plugin call was VERIFIED against live `settings.json`, `config.toml`, `registration.py`, and file hashes — never inferred from filename or presence alone.

---

## 0. TL;DR — load-bearing findings

1. **The hooks control-plane is THREE overlapping subsystems, only ONE wired, plus a plugin-Stop overlay.** Confirms and extends A2/R2.
   - **System A (WIRED-CANONICAL):** the shared `~/.agents/harness/dispatcher.py`, wired by `~/.claude/settings.json` (**17 Claude events**, all `.*`/tool matcher) **and** by `~/.codex/hooks.json` (**10 Codex events**, `config.toml` sha256-trusted) → **one engine, cross-provider**.
   - **System B (UNWIRED-RESIDUE):** `~/.claude/hooks/_dispatch/{dispatch.py, manifest.json}` — a manifest dispatcher referencing 14 check dirs, **NOT in settings.json, NOT read by modules.py**. Superseded by the in-process `modules.py` mixer.
   - **System C (DORMANT):** `~/.claude/hooks/hooks.json` — an **everything-claude-code (ECC)** plugin manifest (25+ hooks incl. 4 Stop) via `${CLAUDE_PLUGIN_ROOT}`; owner plugin `ecc=false` DISABLED.

2. **"63 firing UNRESOLVED" is now RESOLVED → they do NOT fire (A2 medium ~65% → HIGH ~90%).** The settings.json generator (`registration.py`) references **exactly 4** `~/.claude/hooks` paths (2 subdir `check.py` + 2 worktree `.ps1`); there is **no dynamic iteration** over the 65 dirs and **no manifest read**. Of **65** `~/.claude/hooks/*` subdirs, exactly **2 are wired**; the other **63 are consolidation residue** (14 manifest-referenced + 3 support incl. `_dispatch` + 46 pure residue).

3. **The A1 residual is live: 3 enabled-plugin Stop hooks climb the GLOBAL `N/4` re-entrancy counter,** untouched by the harness Stop-loop fix — `ralph-loop` (bash, armable), `codex` (node, **timeout 900 = 15 min**), `hookify` (python3, timeout 10). *(Task text names 2; the live+A1 truth is 3 — `hookify` is the third.)*

4. **The Codex side MIRRORS the split exactly:** top-level `~/.codex/hooks.json` wired → shared dispatcher; `~/.codex/hooks/hooks.json` (11832B, **byte-identical ECC twin** of the Claude one) dormant + not `config.toml`-trusted; 4 parity residue dirs. **Gemini/Antigravity wire ZERO harness hooks** (A2/R6 gap).

5. **Two structural drifts beyond the split:** (a) **live ≠ git** — live `modules.py` `sha256=E232CD0F` ≠ committed `5d2fca2` `8F6AA2CB` (fix only on branch `chore/enshrine-runtime-config`, not main); (b) **two-SSOT repo source** — `reconcile ci/harness` (12 `.py`) vs `toolchain ci/harness` (8 `.py`) both render the deployed hooks.

6. **Whole-drive context (C-config-index):** 6,435 hook artifacts total — **538 canonical**, 4292 vendored (marketplace-owned), 1147 slop (Temp), 331 duplicate-copy (D: clones). The live-lane 65-dir/2-wired set sits inside the 167 `~/.claude/hooks` scripts; everything else is downstream/vendored/ephemeral.

---

## 1. The three-way split (verified wiring)

| System | Path | Wired? | Events | Verdict |
|---|---|---|---|---|
| **A — harness dispatcher** | `~/.agents/harness/dispatcher.py` (Claude) + `~/.codex/hooks.json` (Codex) → same engine | **YES** | Claude 17, Codex 10 | **WIRED-CANONICAL — keep, the consolidation target** |
| **B — `_dispatch` manifest** | `~/.claude/hooks/_dispatch/{dispatch.py,manifest.json}` | **NO** | manifest lists 14 checks (SessionStart 6 / Stop 9 / PostToolUse 3 / PreToolUse 3) | **UNWIRED-RESIDUE — retire** |
| **C — ECC manifest** | `~/.claude/hooks/hooks.json` (+ codex twin) | **NO** (`ecc=false`) | 25+ (incl. 4 Stop) | **DORMANT — remove** |

**System A wiring proof:** `settings.json:79-331` routes every event group to `dispatcher.py`; `registration.py:146-164` (`build_hooks`) generates it, and `registration.py:100-143` (`_apply_claude_hand_edits`) folds **exactly 4** `~/.claude/hooks` entries — `local-tui-reminder/check.py` (SessionStart), `workflow-monitor-autolaunch/check.py` (PreToolUse/Workflow), `create-worktree.ps1` (WorktreeCreate), `remove-worktree.ps1` (WorktreeRemove). Codex: `config.toml [hooks.state]` L336-363 sha256-trusts **only** the top-level `~/.codex/hooks.json` for 10 events → same dispatcher `--provider codex`.

**System B dead-for-live proof:** `settings.json` has zero `_dispatch` references; `modules.py` mentions it only in a comment (`@684`); the manifest's `Stop settings_timeout=35` diverges from the live `Stop timeout=5` — proof the manifest is not the live source.

**System C dormant proof:** every command uses `${CLAUDE_PLUGIN_ROOT}` (defined only inside a plugin); `ecc@everything-claude-code=false` (`settings.json:410`); a bare `~/.claude/hooks/hooks.json` is not a Claude-Code auto-load path.

---

## 2. Disposition matrix

| Class | Members (count) | Evidence | Disposition (POST-GATE) |
|---|---|---|---|
| **wired-canonical** | dispatcher.py (Claude 17ev) + `~/.codex/hooks.json` (Codex 10ev) + `local-tui-reminder` + `workflow-monitor-autolaunch` + `create-worktree.ps1` + `remove-worktree.ps1` (**6** artifacts / **1** shared engine) | settings.json:79-331; registration.py:100-164; config.toml:334-363 | **KEEP** — the canonical control-plane |
| **unwired-residue** · manifest-referenced | `bg-registry, memory-spool, heartbeat, open-loops, background-digest, wire-check, honest-signal, stub-ledger, todo-surfacer, journey-coverage, test-tamper-guard, dark-surface, tool-result-sentinel, dup-guard` (**14**) | `_dispatch/manifest.json` events{} | **RETIRE** with System B (archive reversibly) |
| **unwired-residue** · support | `_dispatch` (System B home), `_golden`, `_shared` (**3**) | underscore helper dirs; `_dispatch` holds the dead dispatch.py+manifest.json | **RETIRE** with System B |
| **unwired-residue** · pure residue | `anti-degen, beads, calibrated-silence, capability-catalog, claim-guard, cmd-rewrite, compchem-preflight, contraindication, deny-credential-reads, edit-checkpoints, edit-validate, event-ledger, figma-mirror, file-scope, fresh-verify, goal-reinject, harness-bench, harness-trim, iatrogenics, inquisitiveness, loop-recovery, mcp-canonical-sync, mcp-defaults, mcp-liveness, mcp-userscope-sync, memory-guard, no-force-push, notify-idle, orphan-commit, per-edit-check, persist-nudge, precompact-basicmemory, precompact-snapshot, re-autolaunch, recall-inject, semantic-router, session-end, skill-router, sonar-secrets, stopfailure-notify, strong-tool-nudge, subagent-lifecycle, tms, tool-preflight, truth-verify, ulysses` (**46**) | 65 − 2 wired − 14 manifest − 3 support = 46; sampled capabilities confirmed reimplemented in modules.py | **RETIRE** (archive reversibly); confirm still-wanted logic lives in modules.py first |
| **dormant** | System B `manifest.json` + System C ECC `hooks.json` (Claude) + codex twin `~/.codex/hooks/hooks.json` + codex 4 parity dirs (**4** items) | ecc=false; ${CLAUDE_PLUGIN_ROOT}; codex trust set excludes the 2nd manifest | **REMOVE** — collapse both providers to the shared dispatcher |
| **plugin** (A1 residual) | `ralph-loop` (bash, armable), `codex` (node **timeout 900**), `hookify` (python3 timeout 10) (**3**) | 3 enabled plugins each register Stop; A1 §3/§8.4/§10.9 | **DECIDE + DOCUMENT** — hoist Stop re-entrancy short-circuit to the dispatcher boundary (A1 req#1); disable/observe unused plugin Stop hooks |
| **stale** · dead files | `create-worktree.ps1.bak-*` (2522B), `worktree-target.txt` (44B), `worktree-debug.json` (526B) (**3**) | non-wired top-level; README.md is doc (keep) | **REMOVE** |
| **stale** · live≠git | live modules.py `E232CD0F` ≠ committed `8F6AA2CB` (**1**) | A1 §6 + Get-FileHash | **RECONCILE** — land enshrine commit on main, tie deploy to a bundle digest (A1 req#6) |
| **duplicate** · two-SSOT source | `reconcile ci/harness` (12py) vs `toolchain ci/harness` (8py) (**2**) | C-config-index 165 vs 160 canonical repo hooks | **DEDUP** to one repo source (task #8, PR #78) |
| **duplicate** · off-box clones | `D:/pr-b-clone` (161) + `D:/gem-wave-b` (161) + `D:/ReverseTools bc-toolkit` (9) (**331**) | C-config-index duplicate-copy=331 | **RETIRE** per A0/D0.5 |
| **out-of-scope** | vendored 4292 + slop 1147 + checkpoint/superseded/scattered/unknown (**5566**) | C-config-index class_tallies | NOT harness-owned — vendored = marketplace (plugin disable at USER scope); slop = ephemeral |

---

## 3. Consolidation target plan (the "ONE dispatcher" end-state)

1. **Keep ONE dispatcher** — System A `~/.agents/harness/dispatcher.py` (cross-provider: Claude 17ev + Codex 10ev). Its `modules.py` mixer already subsumes the residue capabilities (goal-reinject → goal reinjection, event-ledger → LedgerModule, claim-guard → ClaimWarningModule, deny-credential-reads/sonar-secrets → credential guard, mcp-canonical-sync/mcp-defaults → config guards, semantic-router/skill-router → routing).
2. **Retire the 63 unwired residue** (14 manifest + 3 support + 46 pure) — archive reversibly (mirror the 2026-07-03 skills-retired pattern), after confirming each still-wanted behavior exists as a module.
3. **Remove the dormant manifests** — System B `manifest.json` + System C ECC `hooks.json` (Claude + codex twin) + codex parity dirs.
4. **Handle the 3 plugin Stop hooks** — (a) hoist the Stop re-entrancy short-circuit from `ClaimWarningModule` to the **dispatcher boundary** so any plugin `decision:block` returning to the harness Stop is neutralized regardless of module (A1 req#1); (b) disable/observe the unused plugin Stop hooks (esp. the codex 900 s gate); (c) document the decision (A1 req#9).
5. **Decide the 2 standalone-wired subdirs** — keep `local-tui-reminder` + `workflow-monitor-autolaunch` as separate settings entries, or fold into the dispatcher as modules (owner call). Same for the 2 worktree `.ps1` (lifecycle, not module-shaped).
6. **Collapse the two-SSOT repo source** — fold reconcile `ci/harness` → toolchain mainline (task #8, PR #78); land the Stop-fix enshrine commit on main to close live≠git.
7. **Forward gap (not a retirement):** Gemini/Antigravity wire zero harness hooks — adding parity is future scope for "all three first-class".

**Everything above is POST-GATE (owner G-13).** This deliverable produces the disposition plan; it modifies nothing.

---

## 4. Prior-art reconciliations

- **A2 `hook:claude:script-dirs` "63 firing UNRESOLVED" (~65%)** → **RESOLVED to HIGH (~90%): they do not fire.** `registration.py` references only 4 `~/.claude/hooks` paths; no 65-dir iteration; `modules.py` has no manifest invocation.
- **A2/R2 "THREE subsystems, only ONE wired"** → **CONFIRMED + extended to Codex** (top-level wired / 2nd manifest dormant / parity residue).
- **A1 "3 plugin Stop hooks untouched by the fix"** → **CONFIRMED live** (ralph-loop/codex-900s/hookify all enabled + register Stop).
- **Task "65 dirs, 2 wired, 63 residue"** → **CONFIRMED exactly** (65 subdirs; wired = local-tui-reminder + workflow-monitor-autolaunch).
- **C-config-index "6,435 / 538 canonical / 167 in ~/.claude/hooks"** → **CONFIRMED as the whole-drive superset** of the live lane.

---

## 5. Open questions (owner triage)

1. Per-dir last-fired telemetry for the 46 pure-residue dirs would raise the retire call from ~80% to high — is there a hook-invocation log? (`terminal.jsonl` records dispatcher events only, not the residue scripts.)
2. Standalone-wired `local-tui-reminder` + `workflow-monitor-autolaunch`: keep separate or fold into the dispatcher for a single wired loader?
3. The 2 worktree `.ps1` (the only PowerShell hooks): keep as-is or port into the dispatcher?
4. Which of the 3 plugin Stop hooks does the owner actually use? codex's 900 s gate is highest-risk. Disable unused, or gate all via the dispatcher-boundary short-circuit?
5. Retire the codex parity residue dirs + dormant 2nd `hooks.json` in lockstep with the Claude residue?
6. Gemini/Antigravity hook parity: add, or accept Claude+Codex-only for hooks in this program?

---

## 6. Receipts

- **Wiring:** `settings.json:79-331` (17 dispatcher groups + 4 hand-edit groups) · generator `registration.py:100-164` · Codex `config.toml [hooks.state]` L336-363.
- **Firing grep:** `~/.agents/harness/*.py` for `.claude/hooks|_dispatch|manifest.json|hooks_root` → registration.py:105/109/118/129/138 (4 wired paths) + modules.py:170/684 (comments only). No iteration, no manifest read.
- **System B:** `_dispatch/manifest.json` (14 checks / 4 events; Stop timeout 35 ≠ live 5).
- **System C:** `~/.claude/hooks/hooks.json` (11832B, `${CLAUDE_PLUGIN_ROOT}`, 25+ hooks incl. 4 Stop; `ecc=false`); byte-identical codex twin (11832B, untrusted).
- **Plugin Stop hooks:** `ralph-loop/1.0.0` (bash stop-hook.sh) · `openai-codex/codex/1.0.6` (node stop-review-gate-hook.mjs timeout 900) · `hookify` (python3 stop.py timeout 10); enabledPlugins codex/hookify/ralph-loop=true, ecc=false.
- **Live≠git:** live modules.py `E232CD0F` (108296B, mtime 2026-07-13 08:12) ≠ committed `5d2fca2` `8F6AA2CB`.
- **Two-SSOT:** reconcile ci/harness *.py=12 vs toolchain ci/harness *.py=8.
- **Whole-drive:** `C-config-index-complete.json meta.class_tallies.hook` (canonical 538 · vendored 4292 · slop 1147 · duplicate-copy 331 · unknown 61 · scattered 47 · superseded 19 = 6435).
- `SUCCESS:C-hooks-reconcile` — READ-ONLY, freeze respected; every disposition is a POST-GATE finding for owner G-13.