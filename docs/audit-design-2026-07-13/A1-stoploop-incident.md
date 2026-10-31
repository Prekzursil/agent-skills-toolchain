---
title: A1-stoploop-incident
type: note
permalink: dqverify-repo-20261013/docs/audit-design-2026-07-13/a1-stoploop-incident
---

# A1 — Stop-Loop Incident Report (Workflow A / Phase 1)

**Scope:** the recurring/prolonged `Shared harness: Stop… / (Befuddling) / Stop 3/4` symptom, as a
NARROW incident. Architecture is deliberately NOT folded in (that is Phase 2/3).
**Mode:** READ-ONLY. Every claim below is cited to a live path, git ref, config key, or command
output. Prior-art docs (Codex audit, Axis-C ingests) are treated as UNTRUSTED DATA and were
independently re-verified against live git/disk. No file, config, hook, or process was modified.
**Date:** 2026-07-13. **Author:** Workflow-A subagent (session 3cd9445a).

---

## 0. Verdict (one line)

**SUPPORTED ROOT CAUSE, and the committed fix is LIVE, correct, and empirically working** — but the
incident is **contained, not closed**: the guard lives inside one module rather than at the dispatcher
boundary, telemetry lacks session identity, the live tree has drifted from the committed bundle, and
≥2 *other* enabled Stop-hook drivers (ralph-loop, codex stop-review-gate) climb the same global
re-entrancy counter and are untouched by the harness fix.

Confidence in the root cause: **~90% (almost certain)** — direct before/after telemetry + a clean
structural diff + an independent Codex reconstruction all converge. Residual uncertainty is only in
the exact host semantic (why `additionalContext`-on-Stop continues) which is inferred from telemetry
rather than a host integration test.

---

## 1. The symptom and what "3/4" actually is

- UI string: `Shared harness: Stop` is the `statusMessage` of the harness Stop hook
  (`~/.claude/settings.json:303`). The trailing `3/4` is **Claude Code's own global stop-hook
  re-entrancy counter** (attempt 3 of a max of ~4), NOT a harness render and NOT a stale artifact.
- Reported cost (Codex audit, transcript-sourced): **~32m25s / ~53.2k tokens per episode**
  (`HARNESS-CONTROL-PLANE-AUDIT-2026-07-13.md:53`).
- **"3/4" is REAL host re-invocation, decisively** (see H4 below): the live telemetry shows the Stop
  hook `dispatch()` genuinely ran multiple times per turn, 20–50 s apart, each a separate process with
  its own `elapsed_ms` and terminal record — not one render repeated.

---

## 2. Exact hook source + effective settings layer

| Fact | Evidence |
|---|---|
| Live Stop hook command | `python "C:/Users/Prekzursil/.agents/harness/dispatcher.py" --provider claude --event Stop`, `timeout: 5`, no matcher, `statusMessage: "Shared harness: Stop"` |
| Settings layer | **User scope** `~/.claude/settings.json` lines **296–307**. `cwd` = `C:\Users\Prekzursil`, so the "project" `.claude/settings.json` **is** the user file (same path). |
| Number of Stop groups in that file | **1** (`$s.hooks.Stop.Count == 1`, one hook command). |
| The live tree is not git | `~/.agents/harness` is **NOT a git repo** (`fatal: not a git repository`). It is the canonical *deployed* copy; the git source-of-truth is `~/source/agent-skills-toolchain/ci/harness/`. |
| The `_dispatch/manifest.json` indirection is DEAD for live | Per Axis-C DIAGNOSE §4.1 (`ingest-diagnose-and-optimize.md:143-147`): live hooks route through `~/.agents/harness/dispatcher.py` (matcher `.*`) and do **NOT** read `hooks/_dispatch/manifest.json`. Verified: that manifest exists and even lists a Stop entry **with `settings_timeout=35`**, but it is not wired live (the live Stop timeout is **5**). Editing the manifest changes nothing live. |

## 3. Duplicate registrations across layers

**No duplicate harness Stop registration.** Scan of every layer:

| Layer | Present | Stop hook? |
|---|---|---|
| `~/.claude/settings.json` (user = project, cwd is home) | yes | **1** (the harness) |
| `~/.claude/settings.local.json` | yes | **none** |
| worktree `…/ast-harness-reconcile/.claude/settings.json` + `.local.json` | **absent** | — |
| managed policy `C:\ProgramData\ClaudeCode\managed-settings.json` | **absent** | — |

**BUT three *enabled plugins* register their own Stop hooks** (a second class of Stop-capable path the
harness does not own; the `N/4` counter and `stop_hook_active` are GLOBAL, so any of these returning
`decision:block` re-invokes ALL Stop hooks, including the harness — which then shows `Stop 3/4`):

| Plugin (enabled) | Stop command | Timeout | Armed? |
|---|---|---|---|
| `ralph-loop@claude-plugins-official` | `bash …/hooks/stop-hook.sh` | (default) | **Inert unless `./.claude/ralph-loop.local.md` exists in cwd**; returns `{"decision":"block","reason":<prompt>}` when armed (`stop-hook.sh:185`). Session-isolated (`:31-35`). Stale state files exist in `Documents/GitHub/event-link` and `…/pbinfo-scrape` — NOT the harness cwd. |
| `codex@openai-codex` | `node …/scripts/stop-review-gate-hook.mjs` | **900 (15 min)** | "Optional stop-time review gate." Arming condition **not verified** in this pass → residual risk (a Stop hook that can run 15 min synchronously). |
| `hookify@claude-plugins-official` | `python3 …/hooks/stop.py` | 10 | Only fires if user configured a Stop rule in a `.local.md`. |

## 4. Invocation chain, I/O, exit codes, decision:block, correlation IDs, timing

- **Chain:** host fires Stop → `dispatcher.main()` reads stdin JSON → `normalize_event()`
  (`adapters.py:73`) → `HarnessDispatcher.dispatch()` runs every module → `render_output()`
  (`adapters.py:145`) → `main()` writes native JSON. **For Stop it ALWAYS writes** (`dispatcher.py:530`:
  `if native or args.event in {"Stop","SubagentStop"}`).
- **Inputs that matter:** `last_assistant_message` (claim detection) and `stop_hook_active`
  (re-entrancy). `normalize_event` maps `stop_hook_active` → `event.trigger="stop_hook_active"`
  (`adapters.py:121-128`, the loop-fix half).
- **Output on Stop:** `action="inject"` → `{"hookSpecificOutput":{"hookEventName":"Stop",
  "additionalContext":<text>}}` (`adapters.py:184-190`); `action="continue"`/`"block"` →
  `{"decision":"block","reason":…}` (`adapters.py:171-174`). Empty result → `{}` (still written for Stop).
- **Exit code:** always **0** (fail-open; `main()` returns 0 on any exception, `dispatcher.py:512-536`).
- **decision:block on Stop:** the harness path to it is `render_output` for `action in {block,continue}`.
  Telemetry shows the harness **never** used it (see §5) — the loop was `inject`-driven.
- **Correlation IDs: ABSENT.** `_record_terminal` writes only
  `ts, terminal, provider, event, action, reason_code, elapsed_ms, failed_modules` (`dispatcher.py:486-497`)
  — **no session_id, no invocation_id.** A loop cannot be tied to a session from telemetry. (Confirms
  audit "telemetry lacks session identity.")
- **Timing signature (the smoking gun):** inject-on-Stop records carry `elapsed_ms ≈ 56–145 ms` (full
  claim detection + basic-memory nudge); the guarded re-entrant `allow` records carry
  `elapsed_ms ≈ 7–10 ms` (short-circuits before the expensive path). Example healthy pair:
  `08:03:17 inject/102.8ms` → `08:03:52 allow/7.5ms`.

## 5. The specific determinations requested

1. **Is `stop_hook_active` checked BEFORE any continuation?** **YES (post-fix).** `ClaimWarningModule.run`
   short-circuits to `HookResult.success()` (allow, empty) at `modules.py:1707-1712` — the very first
   thing after the event-type gate, *before* `last_assistant_message` is even read (`:1713`). Verified by Read.
2. **Does a Stop path invoke a lifecycle path that re-triggers Stop (internal recursion)?** **NO internal
   recursion.** The only harness modules that branch on Stop are `LedgerModule` (`:792` — writes the turn
   record via `_append_turn`, then returns allow; I/O only, never inject/block) and `ClaimWarningModule`.
   The re-trigger is **external**: the *host* re-invokes Stop after the harness emits `additionalContext`
   on the prior Stop. It is a host-level loop, not a Python call-stack recursion.
3. **API-error termination mis-handled as normal Stop vs StopFailure?** **No `StopFailure` hook is
   registered** (settings.json has `Stop` only) and the harness has no `StopFailure` branch. API-error
   terminations are therefore not *distinguished*, but they do **not** drive this loop (an error Stop with
   no completion language fails `ClaimWarningModule._CLAIM` → no inject). Residual: StopFailure path is
   unhandled (audit `:75` notes the host distinguishes them).
4. **Long research/memory/monitor/agent work synchronously inside the hook?** **Not in the harness Stop
   path.** Timeout is 5 s; on Stop it runs `_append_turn` (bounded file append) + `_basic_memory_nudge`
   (ledger replay capped at 120 entries, `modules.py:1906`) — no network, no agent spawn. **However the
   *codex* plugin's Stop hook has `timeout: 900`** — a genuine "15-min synchronous work in a Stop hook"
   risk, but it is a plugin, not the harness.
5. **Is "3/4" real progress, stale rendering, or recursion?** **REAL host re-invocation counter**
   (see H4). Not stale, not a render artifact.

## 6. Fix verification — LIVE + committed + correct

**The loop-fix has two halves, both verified present in the LIVE tree** (`~/.agents/harness`):

- **adapters half (populate `trigger` from `stop_hook_active`):** diff of live vs the pre-fix backup
  `backups/adapters.py.bak-loopfix-20260713-021353` shows exactly one change —
  pre-fix `trigger=str(data.get("trigger") or "")` → post-fix the `stop_hook_active`-populating
  expression (`adapters.py:121-128`). **CONFIRMED live.**
- **modules half (re-entrancy short-circuit):** `modules.py:1707-1712` returns allow on a re-entrant
  Stop; the guard block is present in live and absent from the pre-fix backup
  `backups/modules.py.bak-loopfix-20260713-021353`. **CONFIRMED live.** The comment at `:1703-1706`
  explicitly names *"the 'Stop 3/4' / 53k-token drain."*

**Committed:** commit **`5d2fca2`** ("chore(harness): enshrine drifted runtime config into version
control", **2026-07-13 04:04:57 +0300**) on branch **`chore/enshrine-runtime-config`** contains both
halves in `ci/harness/adapters.py` + `ci/harness/modules.py` (grep-confirmed `stop_hook_active` +
`Stop 3/4`). **Caveats:** (a) the commit is on a **feature branch, not main**; (b) **live `modules.py`
is NOT byte-identical to the committed one** — SHA256 live `E232CD0F…` vs `5d2fca2:ci/harness/modules.py`
`8F6AA2CB…` — validating Codex audit `:137` ("modules.py … does not [equal reconciliation HEAD]"). So
the fix *logic* is in both trees, but the git commit is **not a faithful snapshot of live**.

**Correct + working (empirical before/after, live `terminal.jsonl`, 921 Stop records, 07-11 00:07 →
07-13 09:44):**

- Distribution: **538 `allow|ok`, 383 `inject|unverified_completion_claim`, 0 `block`, 0 `continue`.**
- **Pre-fix loop signature:** **38 runs of ≥3 consecutive `inject` with no intervening `allow`, up to
  8 consecutive**, many in tight 20–50 s bursts (e.g. `11-Jul 05:49:39→05:50:00` = **4 injects in 21 s**;
  `13-Jul 00:16:05→00:23:52` = **8 injects**). **Every run ends before the 02:13:53 fix** (last run ends
  `13-Jul 01:01:00`).
- **Post-fix:** **zero** consecutive-inject runs across the remaining ~7.5 h (02:13→09:44); the pattern
  is clean `inject → allow` (re-entrant Stop returns allow in ~7 ms). This is direct evidence the guard
  broke the loop.
- Independent corroboration: Codex audit observed the same `inject → allow` pair (`:70-71`).

---

## 7. Ranked hypothesis table (kept for auditability; H1 is the supported cause)

| # | Hypothesis | Evidence FOR | Evidence AGAINST | Verdict |
|---|---|---|---|---|
| **H1** | **Pre-fix, `ClaimWarningModule` re-injected `unverified_completion_claim` (additionalContext) on every Stop with completion language + no ledger evidence; the harness's own `additionalContext` emission caused the host to re-invoke Stop; with `trigger` un-populated and no re-entrancy guard, each re-invocation re-injected → looped to the host cap (`Stop 3/4`).** | 38 pre-fix consecutive-inject runs (≤8), tight 20–50 s bursts, all pre-02:13; clean post-fix; `modules.py:1703` names the exact symptom; adapters diff shows the missing `trigger`; Codex reconstruction `:57-71`; 0 block records ⇒ inject-driven. | Exact host semantic of `additionalContext`-on-Stop is inferred from telemetry, not a host test; pre-fix window 01:01–02:13 was quiet (soft fix-moment boundary). | **CONFIRMED (~90%)** |
| H2 | A plugin (ralph-loop / codex gate) drove the continuation; harness inject was a passenger. | Harness telemetry can't see plugin decisions; codex gate `timeout 900`; ralph-loop *is* a Stop-block loop. | ralph-loop inert without cwd `.claude/ralph-loop.local.md` (none in harness cwd; the 2 that exist are elsewhere + session-isolated); **post-fix the harness allows and the loop STOPS** — a plugin driver would keep the counter climbing while the harness allows. | **Co-driver LOW (~10%)**; not the primary cause |
| H3 | `HARNESS_CLAIM_GATE=block` forced `decision:block` on Stop. | Block path exists (`modules.py:1757-1764`). | **0 block records in 921 Stop entries**; no `HARNESS_*` env set. | **REFUTED** |
| H4 | "3/4" is stale rendering / render recursion, not real progress. | — | Separate `dispatch()` runs 20–50 s apart, each its own record + `elapsed_ms`; host `stop_hook_active` is documented re-entrancy (audit `:75`). | **REFUTED — it is the REAL host counter** |
| H5 | API-error termination mis-handled as normal Stop drove the loop. | No StopFailure handling. | Error Stop lacks completion language → no inject; guard caps re-entry anyway. | **REFUTED as driver** (StopFailure-undistinguished is a residual) |

---

## 8. Why "contained, not closed" — residuals (evidence-cited)

1. **Module-local guard (the core gap).** `ClaimWarningModule` is currently the *only* harness module
   that returns non-allow on Stop AND the only one carrying the guard. The invariant is **not enforced
   at the dispatcher boundary** — any future Stop-capable module added without its own guard re-opens the
   loop. (Audit central point; Deliverable-1 req #2.)
2. **No correlation IDs.** `terminal.jsonl` has no session/invocation id (`dispatcher.py:486-497`) — a
   recurrence cannot be attributed.
3. **Live ≠ git.** Live `modules.py` SHA ≠ committed `5d2fca2`; fix committed only on branch
   `chore/enshrine-runtime-config`, not main; the manifest dispatcher (`hooks/_dispatch/manifest.json`,
   Stop `timeout 35`) is dead-for-live and diverges from the live `timeout 5`.
4. **Second Stop-continuation drivers untouched:** ralph-loop (armable) + codex stop-review-gate
   (`timeout 900`) climb the same global counter and re-invoke the harness Stop hook. Stale
   `ralph-loop.local.md` files exist in `event-link` / `pbinfo-scrape`.
5. **`StopFailure` unhandled** (API-error termination not distinguished).
6. **Host semantic unproven by test** (`additionalContext`-on-Stop-continues is inferred).

## 9. Minimal containment (findings only — NOT applied, per the active-work freeze)

- **No emergency change is warranted** — the fix is live and the last ~7.5 h of telemetry is loop-free
  (matches audit "no emergency mutation warranted").
- If a recurrence appears, the fastest read-only checks are: (a) confirm no `HARNESS_CLAIM_GATE=block`
  in the *host* env (default is inject; telemetry already shows 0 blocks); (b) confirm no
  `./.claude/ralph-loop.local.md` in the active cwd; (c) grep the last N `terminal.jsonl` rows for a
  consecutive-`inject` run (the §6 signature). **There is currently NO env kill-switch** to disable the
  ClaimWarning Stop nudge without editing code — a `HARNESS_STOP_GUARD=off` escape hatch is a
  recommended (deferred) add.

## 10. Permanent-fix requirements (adopt the audit's 8, made concrete)

1. **Hoist the re-entrancy short-circuit to the DISPATCHER boundary.** In `dispatch()`, when
   `event.event=="Stop"` and `event.trigger` indicates re-entrancy, suppress ALL continuation-capable
   output (force `action=allow`, drop `additionalContext`) regardless of which module fired. Closes the
   module-local hole.
2. Preserve native re-entrancy losslessly (record raw `stop_hook_active` **and** normalized `trigger`).
3. Re-entrant Stop must emit **exit 0 + exactly `{}` + newline + empty stderr** (assert; `main()` already
   writes `{}` when native is empty).
4. First Stop may inject once; immediate re-entrant Stop must allow — as a **dispatcher** invariant + test.
5. Exactly one owned Stop registration (true today; add a config-drift assertion).
6. Every deployed file tied to a clean bundle digest (close live≠git drift; land the fix on main).
7. Telemetry: add redacted `session_id` + `invocation_id` + raw/normalized re-entrancy to `terminal.jsonl`.
8. Whole-mixer + **host integration** regression required for every new Stop-capable module.
9. (Incident-specific) Decide + document the plugin Stop drivers (ralph-loop, codex gate); observe/handle
   `StopFailure`.

## 11. Regression-test spec (concrete, minimal-first)

| ID | Level | Setup | Assert |
|---|---|---|---|
| T1 | unit (exists) | Stop, `last_assistant_message="all tests pass"`, no ledger receipt, `trigger=""` | `action=inject`, `reason=unverified_completion_claim` |
| **T2** | unit (the guard) | same event but `stop_hook_active=true` | `action=allow`, `reason=ok`, `additional_context=[]`, and `render_output → {}` |
| T3 | adapters unit | `normalize_event` with `stop_hook_active` ∈ {true,"true",1} vs absent/false | `trigger=="stop_hook_active"` vs `""` |
| **T4** | dispatcher boundary (NEW — would have caught the gap) | inject a synthetic module that unconditionally returns `action=inject` on Stop; fire a re-entrant Stop | native output is empty `{}` (proves the guard is at the boundary, not per-module) |
| T5 | whole-process subprocess | run `dispatcher.py --event Stop` with stdin `{"stop_hook_active":true,…}` | exit 0, stdout `"{}\n"`, stderr empty (req #3) |
| T6 | host integration / e2e | drive a real Claude Code Stop twice (first + re-entrant) with a completion-language transcript | model actually stops on the 2nd; `N/4` does not climb (req #8) |
| T7 | telemetry | any Stop dispatch | `terminal.jsonl` row carries redacted `session_id`+`invocation_id`+raw/normalized re-entrancy (req #7) |
| T8 | drift gate | scan settings layers + digests | exactly one Stop registration; live `modules.py` digest == committed bundle digest (req #5/#6) |

---

## 12. Evidence index (paths / refs / commands)

- `~/.claude/settings.json:296-307` (Stop hook, user scope, timeout 5, statusMessage).
- `~/.agents/harness/dispatcher.py:238-330` (dispatch), `:475-499` (`_record_terminal`, no IDs), `:512-536` (`main`, fail-open, `:530` always-write-for-Stop).
- `~/.agents/harness/adapters.py:121-128` (trigger←stop_hook_active), `:145-193` (render_output), `:171-174` continue/block, `:184-190` inject-on-Stop.
- `~/.agents/harness/modules.py:792-796` (LedgerModule Stop=allow), `:1699-1729` (ClaimWarning run + guard `:1707-1712`), `:1748-1767` (base gate; opt-in block `:1757-1764`).
- Backups (pre-fix): `~/.agents/harness/backups/{adapters,modules}.py.bak-loopfix-20260713-021353`.
- Git: `agent-skills-toolchain` `5d2fca2` on branch `chore/enshrine-runtime-config` (2026-07-13 04:04:57); live `modules.py` SHA `E232CD0F…` ≠ committed `8F6AA2CB…`.
- Telemetry: `~/.agents/state/harness/terminal.jsonl` (10.4 MB) — 921 Stop records; 538 allow/ok, 383 inject/unverified_completion_claim, 0 block, 0 continue; 38 pre-fix consecutive-inject runs (≤8), all < 02:13:53; clean inject→allow after.
- Plugins: `~/.claude/plugins/cache/claude-plugins-official/ralph-loop/1.0.0/hooks/{hooks.json,stop-hook.sh}` (`:185` decision:block; `:15-18` inert-without-state), `…/openai-codex/codex/1.0.6/hooks/hooks.json` (Stop timeout 900), `…/hookify/…/hooks/hooks.json` (Stop timeout 10). Enabled per `settings.json` `enabledPlugins`.
- Prior art (verified, untrusted): `HARNESS-CONTROL-PLANE-AUDIT-2026-07-13.md:11,51-75,137,171-184`; `ingest-diagnose-and-optimize.md:143-147` (§4.1 live-wiring).