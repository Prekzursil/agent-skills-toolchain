# Lane: wire-inert — Wire the built-but-inert

**Status:** COMPLETE — (a)(b)(c)(d) wired + both-states proven; (e) inventory delivered.
**Host:** OFFLOAD-W2025 (Windows Server 2025) · Python `C:\Python314\python.exe`
**Date:** 2026-09-25

> Every claim is labelled VERIFIED (exact command + output) or INFERRED, with a confidence band.
> If a section still reads "UNKNOWN - not yet measured", the unit died before measuring it and no
> verdict there may be cited.

---

## PREMISE CORRECTION (affects the whole lane) — VERIFIED, high confidence (95%)

The `PreToolUse` deployed-copy hook fires on every write under `~/.claude/hooks/...` saying
"Edit the REPO SOURCE instead → ~/source/agent-skills-toolchain/hooks/...". For **these three
hooks that premise is false**: the repo hooks dir is EMPTY.

```
Get-ChildItem -Force 'C:\Users\prekzursil\source\agent-skills-toolchain\hooks'
  -> (no output: directory exists, zero entries)
foreach($n in 'recall-gate','harness-bench','semantic-router'){ Test-Path "$tc\hooks\$n" }
  -> False / False / False
```

`~/.claude/hooks` is therefore the **authored** source for recall-gate, harness-bench and
semantic-router, exactly as `recall-gate/README.md:78-81` states (its step 3 asks someone to
*copy* the dir INTO the repo — i.e. it was never there). Edits below are made in the authored
location; the un-reconciled-to-git gap is an open loop, recorded under Risks.

`~/.agents/hooks` holds only `gap-check`, `no-force-push`, `scripts`, `hooks.json` and two
loose `semantic-router-*.py` files — it is not the hooks SSOT either. VERIFIED.

---

## (a) hooks/recall-gate — WIRED, BOTH STATES PROVEN ✅

| item | value | label |
|---|---|---|
| Location | `C:\Users\prekzursil\.claude\hooks\recall-gate\` (gate.py 14,527 B · tree_index.py 9,924 B · test_recall_gate.py 10,305 B) | VERIFIED |
| Intended event | `UserPromptSubmit` — `gate.py:349` emits `hookSpecificOutput.hookEventName = "UserPromptSubmit"` | VERIFIED |
| Never blocks | `gate.py:357` `return 0  # ALWAYS 0 — inject-only, never blocks`; both probe states observed `exit=0` | VERIFIED |
| Referenced in settings.json BEFORE | **NO** | VERIFIED |
| Referenced in manifest.json BEFORE | **NO** | VERIFIED |
| Existing test suite | **9/9 passed** before AND after the wiring | VERIFIED |
| Wired NOW | YES — `settings.json` `hooks.UserPromptSubmit`, group 1, after `semantic-router/route.py` | VERIFIED |

### The wiring (settings.json 27,209 B → 27,459 B, still valid JSON, 36 top-level keys)

```json
{
  "type": "command",
  "command": "python \"C:/Users/Prekzursil/.claude/hooks/recall-gate/gate.py\"",
  "timeout": 10,
  "statusMessage": "Recall gate: prior art over the harness tree"
}
```

Backup taken first: `settings.json.bak-wire-inert-20260925` (27,209 B).

### Evidence that it was inert BEFORE

```
Select-String -Path ~\.claude\settings.json -Pattern 'recall-gate' -SimpleMatch
  -> (no match; only line 233 semantic-router/route.py matched the sibling patterns)
Select-String -Path ~\.claude\hooks\_dispatch\manifest.json -Pattern 'recall-gate' -SimpleMatch
  -> (no match)
```

### BOTH-STATES PROOF — new instrument `recall-gate/wiring_probe.py`

The probe reads the command string **out of settings.json** and runs *that* (shell, stdin JSON),
so an unwired hook, a typo'd path or a `python` missing from PATH all fail it. It asserts:
WIRING present · FIRES on an absence claim · SILENT on a benign prompt · `exit 0` in both states ·
and every `~/`-path the digest cites resolves on disk (a "non-empty string" assertion would pass
on fabricated paths).

**FAILS on the broken state** (run against the pre-wiring backup — repeatable, touches nothing):

```
python wiring_probe.py C:\Users\prekzursil\.claude\settings.json.bak-wire-inert-20260925
UserPromptSubmit commands: 3; mentioning 'recall-gate': 0
FAILED:recall-gate-wiring WIRING=ABSENT -- the gate is not reachable from settings.json
exit 1
```

**PASSES on the good state** (live settings.json):

```
python wiring_probe.py
UserPromptSubmit commands: 4; mentioning 'recall-gate': 1
WIRED command: python "C:/Users/Prekzursil/.claude/hooks/recall-gate/gate.py"
STATE 1 FIRES   exit=0 injected=309B first-line='PRIOR ART (recall-gate — local harness tree; these files EXIST, read before asserting absence or rebuilding):'
STATE 1 PATHS   1 cited path(s), all resolve on disk
STATE 2 SILENT  exit=0 stdout=0B (expected 0B)
SUCCESS:recall-gate-wiring wired + fires on absence claim + silent on benign prompt
exit 0
```

The fire-state prompt is *"There is no observe hook for the semantic router, it does not exist,
I need to build observe from scratch."* → the gate answers with
`~/.claude/hooks/semantic-router/observe.py (matched 'observe')`. That is a self-referential
proof: the gate catches the exact false-absence claim this lane's item (c) is about.

Silent-state prompt: a weather question. `stdout=0B`.

### Honest note on the first probe draft — a REFUTED instrument, not a refuted gate

My first fire-prompt said *"there is no recall gate hook … no tree index either"* and the gate
returned `CLEAN / no-prior-art` with `nouns: ["recall","harness","either","scratch"]`. That is
correct gate behaviour: it matches single-word nouns against **indexed file stems**, and
"recall gate" (two words) is not a stem. The probe, not the gate, was the defect. Four
realistic absence-claim prompts naming real stems (`tree_index`, `observe`, `dispatch`,
`gate`) all FIRED, 4/4, each citing a file that exists. VERIFIED.

### Typed-state log confirms live execution

`state/recall-gate-20260925.jsonl` gained records during these runs, e.g.
`{"state":"CLEAN","reason":"no-prior-art","intent":"absence-claim","nouns":["recall","harness","either","scratch"],"vault":"OK","elapsed":0.172}`.

### Residual — UNVERIFIED, inline

- **Does the live Claude Code session pick this up without a restart?** Not measured. Hook
  registration is read from `settings.json`; whether an in-flight session re-reads it is
  UNVERIFIED. Settling experiment: start a new session, type an absence claim, look for a new
  `FINDING` record in `state/recall-gate-<today>.jsonl` with a real `session_id`. Confidence
  that a NEW session picks it up: high (~90%, the file is the documented registration surface);
  that THIS session does: unknown.
- **Precision against real prompt traffic remains UNVERIFIED** (the README already says so).
  My probe measures 1 fire / 1 silence, not a false-positive rate. Settling experiment
  unchanged: replay a day of real `UserPromptSubmit` payloads through `gate.run()` and count
  FINDING/CLEAN.

## (b) hooks/harness-bench

- Location: `C:\Users\prekzursil\.claude\hooks\harness-bench\` (bench.py 10,677 B, gate.py 6,043 B,
  test_bench.py 15,357 B, test_gate.py 5,021 B, register-task.ps1, baseline.json 118 B) — VERIFIED
- Intended invocation: weekly Windows Scheduled Task `ClaudeHarnessBench` → `bench.py`, via
  `register-task.ps1` (`schtasks /Create … /SC WEEKLY /D SUN /ST 03:00`), no admin needed — VERIFIED
- Task present BEFORE: **ABSENT** — `Get-ScheduledTask -TaskName ClaudeHarnessBench` →
  *"No MSFT_ScheduledTask objects found"* — VERIFIED
- Re-armed: **YES** — `pwsh register-task.ps1` →
  `Registering ClaudeHarnessBench -> "C:\Python314\python.exe" "…\harness-bench\bench.py"` /
  `SUCCESS: The scheduled task "ClaudeHarnessBench" has successfully been created.` exit 0.
  `Get-ScheduledTask` now returns `ClaudeHarnessBench  Ready`, trigger
  `StartBoundary 2026-09-25T03:00:00  DaysOfWeek 1` (Sunday) — VERIFIED
- **Output produced: YES, through the Windows scheduler.** `Start-ScheduledTask` → ran
  22:53:51→23:01:35 (7m44s), finished `State=Ready LastTaskResult=0`, and CREATED
  `~/.claude/BACKGROUND-DIGEST.md` (did not exist before: `Test-Path` false) containing:
  `[2026-09-25 23:01:35] [harness-bench] HYBRID router mcp recall 3/5 -> 2/5 | PROPOSE: python C:/Users/Prekzursil/.claude/hooks/semantic-router/eval.py`
  — VERIFIED. The re-armed net found a REAL regression on its first run.
- Own test suite: **37 passed** (`test_bench.py` + `test_gate.py`, pytest -q) — VERIFIED

### BOTH-STATES PROOF for (b) — the producer, not just the task

| state | baseline | result |
|---|---|---|
| **BROKEN** (baseline claims mcp 3/5, reality 2/5) | shipped `baseline.json` | digest line **WRITTEN** → regression reported. VERIFIED |
| **GOOD** (baseline matches reality, mcp 2/5) | scratch `baseline-pass.json` | `NO DIGEST LINE -> no regression detected`, exit 0, baseline unchanged (no spurious ratchet). VERIFIED |

Run with `BENCH_BASELINE` / `BG_DIGEST_FILE` overrides so the real baseline and real digest were
untouched by the PASS-state run.

### (b) residual — a REAL defect found underneath, disclosed inline

`hooks/skill-router/route.py` (the LEXICAL comparison arm of `eval.py`) **times out at 30 s on
every invocation** when called the way `eval.py:178` calls it. Measured, 3/3 consecutive, and
again in a second shell:

```
LEXICAL skill-router     form1 input+capture       30.02s TIMEOUT
LEXICAL skill-router     form2 Popen.communicate   30.01s TIMEOUT
HYBRID semantic-router   form1 input+capture        0.40s rc=0 out=379B
```

Yet the same script returns in **0.16 s, exit 0** when stdin is a shell pipe
(`'{...}' | python route.py`). Two independent signals that it is a stall and not a hang:
the child PID rotates on an exact 30 s cadence (52348 @22:57:52 → 23688 @22:58:22) and its CPU is
flat between spawns (0.109 s across an 8 s window, WS pinned at 15.1 MB). `sys.stdin.isatty()`
is **True** in this tool context, i.e. a console is attached exactly as under the scheduler —
so this is NOT a scheduler-only artifact.

Consequences, scoped honestly:
- The 7m44s weekly runtime is explained: ~21 prompts × 30 s on the LEXICAL arm.
- **The HYBRID arm that bench.py actually gates on WORKS** (0.40 s, 379 B) — so the gate signal
  is not obviously invalid. VERIFIED for the single-call case.
- **UNVERIFIED: whether the reported `mcp recall 3/5 -> 2/5` is a true regression.** A
  confounder exists: the semantic router has per-session suppression, and in my A/B the *second*
  consecutive call returned 0 B where the first returned 379 B. If `eval.py` reuses one session
  identity across its prompts, later prompts could be suppressed and recall under-counted.
  Settling experiment: run `eval.py --json` twice with distinct session ids per prompt and
  compare the HYBRID counters against a single-session run. Confidence that the regression is
  real: **low-to-moderate (~35-55%)** until that runs. It should NOT be actioned as a router
  regression yet.
- The root cause of the LEXICAL stall is NOT in `skill-router/route.py` itself (332 lines; one
  `sys.stdin.read()` at `:246`; no network, no subprocess, no loop, no sleep). It is in the
  interaction between that script and a piped-stdin child under a console. Not diagnosed
  further — out of lane. Filed as a finding, not fixed.

## (c) semantic-router/observe.py

- Location: `C:\Users\prekzursil\.claude\hooks\semantic-router\observe.py` (5,508 B) — VERIFIED
- Intended event: `PostToolUse`, matcher `Skill | Task | mcp__*` — its own docstring line 16 says
  *"Matched in settings.json for Skill / Task / mcp__\* tools"* — VERIFIED
- Referenced in settings.json / manifest.json: **NO** in both — VERIFIED
- `record_used` callers across `~/.claude`: **only observe.py itself** — VERIFIED
- Counter state BEFORE (new read-only instrument `measure_success.py`):
  `keys=308 suggested_total=5800 used_total=5 keys_with_used=5 max_suggested=1093` — VERIFIED
- Wired: **YES** — `settings.json` `hooks.PostToolUse`, new group, matcher
  `Skill|Task|SlashCommand|mcp__.*` (all four key-shapes `observe.py:_keys_for` can produce;
  its docstring asked for three and `:59-66` also handles `SlashCommand`) — VERIFIED
- Own test suite: **4 passed** (`test_observe_outcome.py`) — VERIFIED
- **Observation landed on disk: YES, on the LIVE `success.json`** — VERIFIED

```json
{
  "matcher": "Skill|Task|SlashCommand|mcp__.*",
  "hooks": [{ "type": "command",
              "command": "python \"C:/Users/Prekzursil/.claude/hooks/semantic-router/observe.py\"",
              "timeout": 5,
              "statusMessage": "Router success-alignment: credit an acted-on suggestion" }]
}
```

### BOTH-STATES PROOF for (c) — new instrument `observe_wiring_probe.py`

Reads the command out of settings.json, runs it in a redirected store (real `success.json`
never touched), and asserts: WIRING present · matcher covers Skill/Task/mcp__ · credits a
suggested successful call · **refuses** an `isError: true` call.

```
# BROKEN (pre-wiring backup) -> exit 1
PostToolUse commands: 4; mentioning 'observe.py': 0
FAILED:observe-wiring WIRING=ABSENT -- observe.py is not reachable from settings.json

# GOOD (live settings.json) -> exit 0
PostToolUse commands: 5; mentioning 'observe.py': 1
WIRED matcher: Skill|Task|SlashCommand|mcp__.*
STATE 1 CREDITS exit=0 used 0 -> 1 for a suggested, successful mcp call
STATE 2 REFUSES exit=0 used stayed 0 for an explicitly-failed call
SUCCESS:observe-wiring wired at PostToolUse + credits a real use + refuses a failed one
```

### End-to-end proof on the real store (no sandbox)

`route.py` → `observe.py`, one real session:

```
route.py exit=0 stdout=368B
suggested++ on 6 key(s): ['mcp:cheatengine','mcp:ida-pro-mcp','skill:game-re-binary',
                          'skill:reverse-engineering-toolkit','skill:swfoc-reverse-engineering',
                          'skill:game-find-anticheat']
crediting target=mcp:cheatengine via tool_name=mcp__cheatengine__some_tool
observe.py exit=0 stdout=0B (inject-nothing => 0B expected)
mcp:cheatengine: suggested 1 -> 1 | used 0 -> 1
SUCCESS:e2e-observe one observation landed on the live success.json
```

### Counter reset (the second half of the gem) — VERIFIED

`boost() = alpha * used/(suggested+2)` (`success.py:113-124`). With `max_suggested=1093` and
`used_total=5`, a key needed ~1000 real uses before its boost left the noise floor — the signal
was structurally unreadable, which is *why* it had to be reset alongside the wiring.

```
archived  -> success.json.pre-observe-wiring-20260925-230703.bak (16770B)   # archived, NOT deleted
keys before=308 after=308 (all counters zeroed)
suggested_total before=5800 after=0
used_total      before=5 after=0
```

Readability, before → after one real session:
`ratio 0.0009` (5/5800) → **`0.1667`** (1/6). `measure_success.py` now reports `SIGNAL=LIVE`.

**Provenance of the 5 pre-existing `used` credits: UNKNOWN.** `record_used` is called from
`observe.py` only (`grep -rn record_used ~/.claude` → 2 hits: the caller and the definition),
`observe.py` is referenced by no config, and `test_observe_outcome.py` redirects its store into
`tmp_path`. INFERRED (moderate, ~60%) they were hand-run during development. Not load-bearing:
they are archived and the post-reset store is attributable.

## (d) C16 failure-taxonomy module — WIRED to a live consumer, BOTH STATES PROVEN ✅

| item | value | label |
|---|---|---|
| Location | `C:\Users\prekzursil\.claude\hooks\_shared\failure_taxonomy.py` (9,859 B) + `test_failure_taxonomy.py` | VERIFIED |
| Live importers BEFORE | **ZERO.** `grep -rn failure_taxonomy ~/.claude ~/.agents` → 2 hits: its own docstring and `test_failure_taxonomy.py:17`. Premise **CONFIRMED** | VERIFIED |
| Own test suite | **34 passed** | VERIFIED |
| Verdict | **WIRED** (partially — see the split below) | — |

### The consumer chosen, and why

`hooks/_shared/completion.py` — the "ONE shared completion predicate (C1)", in the SAME package
dir, and genuinely live: imported by `codex-databricks-fanout/scripts/harness/gate.py:53-56` and
`workflow-monitor/monitorcore/dbx_completion.py`. It carried its own hardcoded copy of the
`severed-stream` class label at `:177` while the canonical constant sat unused one file away —
two spellings of one concept, free to drift, with nothing to notice.

Change: `completion.py` now imports `SEVERED_STREAM` from `failure_taxonomy` and interpolates it
at the call site. `sys.path` is prepared because consumers import this module by directory.

### BOTH-STATES PROOF — new instrument `_shared/test_taxonomy_binding.py`

A test asserting `reason.startswith("severed-stream")` would pass on the wired AND the hardcoded
version, proving nothing. These two tests can only pass if the value genuinely ORIGINATES in the
taxonomy: an IDENTITY check (`is` the same object) and a MUTATION check (rebind the constant, the
verdict reason must follow — a literal cannot follow).

**FAILS on the deliberately broken state** — `SEVERED_STREAM` changed **on disk** to
`"BROKEN-ON-PURPOSE"`:

```
FAIL test_identity_completion_reuses_the_taxonomy_constant
FAIL test_mutating_the_constant_changes_the_verdict_reason:
     BROKEN-ON-PURPOSE: exit 0 but artifact did not pass the gate
FAILED:taxonomy-binding 2 of 2 test(s) failed        exit 1
```

That second line is the load-bearing evidence: the break **propagated into a live module's
verdict text**. The taxonomy now drives real output.

**PASSES on the good state** (file restored):

```
OK  test_identity_completion_reuses_the_taxonomy_constant
OK  test_mutating_the_constant_changes_the_verdict_reason
SUCCESS:taxonomy-binding 2/2 -- C16 is load-bearing for completion.py   exit 0
```

Regression: `test_completion.py` **18/18 ALL PASS**, `test_failure_taxonomy.py` **34 passed**,
and the downstream import path still resolves (`from completion import artifact_text_ok, classify`
→ OK).

**A finding worth keeping:** during the deliberate break, `failure_taxonomy.py`'s OWN 34 tests
stayed **green**. A module's own suite cannot detect its own inertness — which is exactly how
9,859 B of tested code sat unused. Only a cross-module binding test can.

### The honest split — what was NOT wired, and the structural reason

Only the class-label constants are now live. The module's substance —
`classify_failure()`, `handler_for()`, `require_timeout_s()`, `TwoStrikesBreaker` — is still
unused, and its docstring names the intended consumer: the `parallel()` fan-out barrier.
**That barrier is JavaScript** (`~/.agents/workflows/` holds `rtv-pdr.js`, `mcp-tui-audit.mjs`,
`paper-hardening.js`), so a stdlib-Python module can never be imported by it. VERIFIED. That is
the structural reason C16 was inert, and it cannot be closed by wiring — it needs a port.

Two genuine Python consumers exist and each duplicates the taxonomy ad-hoc. **PROPOSED, not
performed** (both are live Databricks/monitor paths, outside this lane):

| candidate | the duplication | evidence |
|---|---|---|
| `.agents/skills/codex-databricks-fanout/scripts/batch_runner.py` | `state = f"FAILED:{uid} severed-stream"` and an ad-hoc `"429" in tail` count | `:173`, `:233` |
| `.claude/hooks/codex-monitor-autolaunch/check.py` | literal `` `severed-stream`, not SUCCESS `` | `:142` |

`RETIRED` is therefore the WRONG verdict — the module has real consumers. The correct residual is
**PORT the timeout/breaker half to the JS workflow runtime, and fold the two Python duplications
into the taxonomy.** Nothing was deleted.

## (e) Orphaned hook-dir inventory — DELIVERED ✅

### Detector correction first (this changes the briefed numbers)

My first detector regexed `"command"\s*:\s*"([^"]*)"` over raw settings.json. Every command value
contains **escaped quotes** (`python \"C:/...\"`), so `[^"]*` truncated at the first `\"` and
captured only `python \`. Result: it reported `recall-gate` and `semantic-router` as ORPHANS —
both of which I had just wired and could see in the file. A known-present control caught it
(`single-signal-verification.md` rule 3). Fixed by parsing the JSON and walking `hooks.<event>`,
with a `>= 10 commands parsed` sanity assert. **All numbers below are post-fix.**

### Counts (77 hook dirs, `~/.claude/hooks`)

| class | count | meaning |
|---|---|---|
| CONFIG-WIRED | **42** | in settings.json, `_dispatch/manifest.json`, or a scheduled task |
| LIBRARY | **20** | no config entry, but imported by PRODUCTION hook code — **not orphans** |
| TEST-ONLY | **5** | referenced ONLY by `test_*.py` — inert in production |
| ORPHAN | **10** | no config reference, no code reference anywhere |

**This REFUTES the briefed ground truth** that ">=20 are referenced by NO config … confirmed
orphans include recall-gate, event-ledger, calibrated-silence, anti-degen, beads,
capability-catalog." Five of those six are **libraries**, load-bearing via import, not orphans:

| briefed as orphan | actually | production importer |
|---|---|---|
| `event-ledger` | LIBRARY | `_shared/projid.py`, `capability-catalog/project_card.py` |
| `calibrated-silence` | LIBRARY | `contraindication/check.py`, `iatrogenics/gate.py`, `inquisitiveness/prompt-guard.py` |
| `anti-degen` | LIBRARY | `fresh-verify/trigger.py`, `loop-recovery/verdict.py`, `subagent-lifecycle/stop.py` |
| `beads` | LIBRARY | `capability-catalog/project_card.py`, `checkpoint/checkpoint_state.py` |
| `capability-catalog` | LIBRARY | `local-tui-reminder/check.py` |
| `recall-gate` | was a TRUE orphan; **now wired** (item a) | — |

Deleting any of those five on the "orphan" label would have broken working capability. The
distinction that matters is **config-wired vs import-wired**, and only the second needed a
different instrument.

### Classification of the 10 true ORPHANS

| dir | event it wants | verdict | reason |
|---|---|---|---|
| `notify-idle` | **Notification**, matcher `idle_prompt\|permission_prompt` | **WIRE** — highest-value remaining | Fully implemented desktop-balloon + BEL (`notify.py` 6,568 B + 8,844 B tests). `rules/common/hooks.md` already records that `Notification` is absent from the harness `EVENTS` tuple, and settings.json has no `Notification` event either — so an unattended session waiting on a permission prompt alerts nobody. Read-only, no writes. |
| `tool-preflight` | **SessionStart** | **WIRE** | "catches dead/missing MCP servers and project CLIs **before**" use. Read-only detection. Directly relevant: 30+ MCP servers failed to connect in this very session. |
| `memory-guard` *(TEST-ONLY, listed here for severity)* | **PostToolUse** | **WIRE** | "inbound tool-output injection guard" (`scan.py` 10,917 B + 14 KB tests + README). AGENTS §9 makes fetched content untrusted data; this is the enforcement and it is not running. |
| `compute-confidence-gate` *(TEST-ONLY)* | **PreToolUse** | **WIRE** | 17,255 B pre-flight assumption-ledger gate — the mechanism behind AGENTS-RUNTIME §1b. |
| `mvt-patch-leaving` | PostToolUse + Stop | **WIRE-CANDIDATE** | Substantial and tested (32,052 B check.py + 26,704 B tests). Needs an owner call on noise before arming. |
| `figma-mirror` | PostToolUse + Stop | **WIRE-CANDIDATE** | "always-mirror-to-Figma, inject-never-block (gem-hunt N.3)" — itself a built-but-inert gem-hunt artifact. Only worth arming if always-on Figma mirroring is wanted. |
| `mcp-userscope-sync` | SessionStart | **WIRE-CANDIDATE — owner call** | `heal.py` is CREATE-ONLY, fail-open, never overwrites. Safest of the three MCP hooks. NOT wired by me: it mutates MCP config surfaces and lane rule 3 makes MCP curation the owner's call. |
| `recall-inject` | UserPromptSubmit | **RETIRE (superseded)** | `build_index.py:2-4` scans the **basic-memory vault** (`D:\basic-memory`) — the same job the live `bounded_recall` (`~/.agents/harness/modules.py:1984`) already does on UserPromptSubmit. A third vault-recall implementation. It does NOT overlap recall-gate, which deliberately covers the complementary tree half (`test_does_not_index_the_vault` enforces that). File kept. |
| `mcp-canonical-sync` | SessionStart | **RETIRE (superseded)** | Its own docstring `:9`: *"Interim measure until the user-scope promote removes per-project files entirely."* User-scope promotion is the recorded current state, so the interim is over. File kept. |
| `mcp-defaults` | SessionStart | **UNKNOWN-QUARANTINE — do NOT wire** | `enforce-mcp-defaults.py:5-6, :22` **writes `~/.claude.json`** on every SessionStart. Lane rule 2 forbids touching that file at all (4 live sessions), and its job is *disabling MCP servers*, which rule 3 forbids. Wiring this would automate the exact disable-scope regression the estate has been bitten by. |
| `sonar-secrets` | none detectable | **UNKNOWN-QUARANTINE** | No top-level hook entry at all: only `build-scripts/pretool-secrets.ps1` (863 B) and `prompt-secrets.ps1` (1,025 B) plus an empty `.sonar/`. Credential-adjacent, so untouched per lane rule 4. Needs an owner decision on shape before any wiring. |
| `subagent-lifecycle` | SubagentStart / SubagentStop | **UNKNOWN-QUARANTINE** | 30 KB of tests and a 14,931 B `stop.py`, but settings.json already routes both events to the shared harness dispatcher. Whether this duplicates or extends that is unmeasured — the settling experiment is to diff `stop.py`'s behaviour against the shared harness's SubagentStop path. |
| `harness-trim` *(TEST-ONLY)* | none detectable | **UNKNOWN-QUARANTINE** | Two PowerShell scripts (`compact-restore.ps1`, `instructions-loaded-log.ps1`); no event named anywhere in the dir. |
| `compchem-preflight` *(TEST-ONLY)* | PreToolUse | **UNKNOWN-QUARANTINE** | 3,592 B probe, referenced only by `_dispatch/test_wiring.py`. Domain-specific; needs an owner call. |
| `_golden` *(TEST-ONLY)* | n/a | **KEEP — not an orphan** | It *is* a test harness (`test_hooks.py`, `test_import_safety.py`). Test-only is its correct state; the classifier flagged it mechanically. |

**Nothing was deleted, disabled or pruned.** Every row above is a proposal except items (a)-(d).

### Side finding: the dispatcher's own wiring suite is RED (pre-existing, NOT caused by me)

`_dispatch/test_wiring.py` + `test_manifest_presence.py` → **8 failed, 35 passed, 10 xfailed**.
Checked, not assumed: the failure text names `codex-monitor-autolaunch/check.py` duplicated on
PreToolUse, and the four `test_tracked_deploy_mirror_admits_every_dispatched_route` failures need
the repo mirror that is **empty** (the premise correction at the top). Neither `observe.py` nor
`recall-gate` appears in any failure message, and the one PreToolUse dispatch-count failure is on
an event I never touched. VERIFIED that my edits did not cause these.

---

## NET-NEGATIVE ledger

| Added | Retires |
|---|---|
| `recall-gate/wiring_probe.py` | README step 2's pointer to `~/.claude/harness-restore-20260806/_recall_bothstates.py`, which **does not exist** (`Test-Path` → False). The documented verification step was itself inert — a both-states probe that could never run. |
| `semantic-router/observe_wiring_probe.py` | Nothing directly. It is the mandatory both-states instrument for (c); without it the wiring is an unproven claim. |
| `semantic-router/measure_success.py` | Nothing. Justified: no existing script answers "is the suggested-vs-used signal readable", and it is not answerable by eye across 308 keys. Read-only, prints counts only (never a key dump), zero cost unless invoked. |
| `_shared/test_taxonomy_binding.py` | Nothing directly, but it is what makes `failure_taxonomy.py` **provably** non-inert — and it retires the assumption that a module's own green suite says anything about whether it is used (measured: 34/34 stayed green while the module was deliberately broken). |
| **Behavioural retirements (no file added)** | `recall-gate` wiring retires the *manual* README step 1 ("OWNER ACTION — not performed"). The counter reset retires 5,800 accumulated `suggested` with `used=5`, which made `boost()` unreadable. `completion.py`'s hardcoded `"severed-stream"` literal is retired in favour of the canonical constant. |
| **Proposed retirements (evidence given, NOT performed, nothing deleted)** | `recall-inject` (third vault-recall impl, superseded by live `bounded_recall`); `mcp-canonical-sync` (self-declared interim, superseded by user-scope promotion). |

Net: 4 files added, 4 durable duplications/dead-pointers retired, 2 further retirements proposed
with evidence. No file, MCP server, plugin, skill or branch was deleted or disabled.

## Files changed (uncommitted, per lane rule 6 — orchestrator commits)

MODIFIED:
- `C:\Users\prekzursil\.claude\settings.json` — 27,209 → 27,825 B. Two additions: one
  `UserPromptSubmit` entry (recall-gate) and one `PostToolUse` group (observe.py). Valid JSON,
  36 top-level keys, re-verified at the end.
- `C:\Users\prekzursil\.claude\hooks\_shared\completion.py` — imports `SEVERED_STREAM` from
  `failure_taxonomy` and uses it at `:177`.
- `C:\Users\prekzursil\.claude\hooks\semantic-router\success.json` — counters reset (keys kept).

NEW:
- `C:\Users\prekzursil\.claude\settings.json.bak-wire-inert-20260925` (pre-change backup, 27,209 B)
- `C:\Users\prekzursil\.claude\hooks\recall-gate\wiring_probe.py`
- `C:\Users\prekzursil\.claude\hooks\semantic-router\observe_wiring_probe.py`
- `C:\Users\prekzursil\.claude\hooks\semantic-router\measure_success.py`
- `C:\Users\prekzursil\.claude\hooks\_shared\test_taxonomy_binding.py`
- `C:\Users\prekzursil\.claude\hooks\semantic-router\success.json.pre-observe-wiring-20260925-230703.bak`
- `C:\Users\prekzursil\.claude\BACKGROUND-DIGEST.md` (created by the re-armed bench task)

SYSTEM STATE:
- Windows Scheduled Task `ClaudeHarnessBench` registered (weekly, Sun 03:00, current user).

NOT TOUCHED: `~/.claude.json` · any MCP server / plugin / skill / remote branch · any credential.
No commit was made. No process was killed.

## Re-run everything (one block)

```powershell
python ~\.claude\hooks\recall-gate\wiring_probe.py                     # SUCCESS:recall-gate-wiring
python ~\.claude\hooks\recall-gate\test_recall_gate.py                 # 9/9
python ~\.claude\hooks\semantic-router\observe_wiring_probe.py         # SUCCESS:observe-wiring
python ~\.claude\hooks\semantic-router\measure_success.py              # SIGNAL=LIVE
python ~\.claude\hooks\_shared\test_taxonomy_binding.py                # SUCCESS:taxonomy-binding
python ~\.claude\hooks\_shared\test_completion.py                      # ALL PASS (18)
Get-ScheduledTask -TaskName ClaudeHarnessBench                          # Ready
# broken-state halves (touch nothing live):
python ~\.claude\hooks\recall-gate\wiring_probe.py         ~\.claude\settings.json.bak-wire-inert-20260925   # exit 1
python ~\.claude\hooks\semantic-router\observe_wiring_probe.py ~\.claude\settings.json.bak-wire-inert-20260925   # exit 1
```

## Risks

- **Un-reconciled to git.** `~/source/agent-skills-toolchain/hooks/` is EMPTY, so recall-gate,
  harness-bench and semantic-router live only in `~/.claude/hooks` — drift per
  `rules/common/harness-vcs-hygiene.md`. Not fixed here (out of lane scope, and the lane bans
  committing). Open loop for the orchestrator.
- `settings.json` edited while 4 live sessions run. Mid-session `settings.json` edits invalidate
  the system prompt cache (`rules/common/context-reduction.md` §10). Accepted: the alternative is
  leaving the gates inert. `.claude.json` was NOT touched.
- **Three new hooks now run on hot paths.** Measured single-call costs: recall-gate
  `elapsed 0.0005-0.172 s` against a 2.5 s internal budget and a 10 s hook timeout; observe.py is
  a ~5 KB stdlib script with a 5 s timeout. Both are inject-only/inject-nothing and exit 0
  unconditionally, so the worst case is silence, never a blocked prompt or tool call. **UNVERIFIED:
  aggregate latency across a long session** — settling experiment: read `durationMs` from
  `hook_success` in a session transcript after a day of use.
- **`completion.py` now has an import-time dependency on a sibling module.** It prepares
  `sys.path` itself, and the one consumer that imports by directory
  (`codex-databricks-fanout/.../gate.py:53-56`) was re-verified to import cleanly. **UNVERIFIED:
  `workflow-monitor/monitorcore/dbx_completion.py`**, which imports `completion` by a mechanism I
  did not identify (a `test_completion_vendored.py` exists, suggesting a vendored copy). Settling
  experiment: run `monitorcore`'s own suite. Risk if wrong: an ImportError in the Databricks
  monitor path. Confidence it is fine: **moderate (~70%)**. This is the single riskiest change in
  the lane and the first thing to check if that monitor misbehaves.
- **A residual blocked-then-killed process chain exists from the bench run.** No process was
  killed by me (lane rule 5). The task itself completed (`State=Ready`, `LastTaskResult=0`).
- **Un-reconciled to git** — see the premise correction; `~/source/agent-skills-toolchain/hooks/`
  is empty, so all of this lives only in `~/.claude/hooks`. Open loop for the orchestrator, and
  the cause of 4 of the 8 pre-existing `_dispatch` test failures.
- The weekly bench now takes **~8 minutes** per run because of the LEXICAL 30 s stall. Harmless at
  Sunday 03:00, but it means the task will show `Running` for minutes — do not read that as hung.
