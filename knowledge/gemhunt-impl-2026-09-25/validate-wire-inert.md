# validate-wire-inert — ADVERSARIAL validation of the wire-inert lane

Completed 2026-09-25 23:45. Validator lane: `validate-wire-inert`.
Target report: `C:/Users/prekzursil/.agents/knowledge/gemhunt-impl-2026-09-25/wire-inert.md` (33,086 B).

**HEADLINE: 4 CONFIRMED · 1 CONFIRMED-with-OVERCLAIM · 1 REFUTED-DIAGNOSIS · 0 hard-rule
violations · 0 regressions.** The code is right everywhere I could test it. The one
genuine refutation is a *root-cause* claim, not a broken artifact — and it changes what
the orchestrator should fix.

## Verdicts

| # | Gem | Claimed | My verdict | Different instrument I used |
|---|-----|---------|-----------|------------------------------|
| a | recall-gate wired at UserPromptSubmit | VERIFIED ~95% | **CONFIRMED** | PowerShell `ConvertFrom-Json` hook walk + full `Compare-Object` line diff vs the backup + my own 4-state subprocess probe with different prompts and a cited-path-resolves assertion |
| b | ClaudeHarnessBench armed, digest produced | VERIFIED ~95% | **CONFIRMED** | `schtasks /query /xml` and `/query /v /fo LIST` (not `Get-ScheduledTask*`) + `baseline.json` mtime + proving `background-digest` is manifest-wired |
| b-res | 30s stall root cause = stdin/console invocation path | VERIFIED ~90% | **REFUTED (diagnosis)** — defect real, cause wrong | reproduced their exact shape 3/3 at 0.15s warm; cold build in an isolated copy >120s; per-glob timing isolates `plugins/**` at **189.82s** |
| c | observe.py wired + counters reset | VERIFIED ~95% | **CONFIRMED** | my own counter arithmetic (not `measure_success.py`) + a 6-state probe in a copied module dir, 4 states they never tested |
| d | completion.py binds the C16 constant | VERIFIED ~95% | **CONFIRMED (binding) / OVERCLAIM (consumer count)** | broke a temp COPY, not the live file; added the NEGATIVE CONTROL they lacked (pre-change module must ignore the break); grepped every importer estate-wide |
| e | 77 dirs, 42/20/5/10 four-way split | VERIFIED ~90% | **CONFIRMED — fully replicated** | my own classifier over every string in the parsed JSON + `schtasks /query /v /fo csv`, with my own fail-closed control |

## (b-residual) The refutation, in numbers

```
A) WARM index, subprocess + PIPE stdin  (their "30.02s TIMEOUT" shape)
   run1 0.147s rc=0 | run2 0.150s rc=0 | run3 0.170s rc=0
B) WARM index, subprocess + FILE stdin (no pipe at all)      0.158s rc=0
C) COLD index, isolated copy, no timeout cap          >120s  (never finished)

glob.glob(recursive=True) per pattern, measured separately:
   ~/.claude/skills/**/SKILL.md        0.18s   468 files
   ~/.claude/plugins/**/SKILL.md     189.82s  1743 files   <-- THE COST
   ~/.claude/agents/*.md               0.00s    20 files
   ~/.claude/commands/**/*.md          0.00s    75 files
   D:/basic-memory/**/*.md             0.03s   723 files
```

`route.py:206-216` caches `_index.json` for 86400s and writes it only **after**
`_build_index()` returns. eval.py's 30s `subprocess.run(timeout=30)` kills the build at
30s, so the cache is never written and the next call restarts a ~190s walk — 21 prompts
x 30s. Their "0.16s via shell pipe" was simply the run that landed on a warm cache
(live `_index.json` mtime 23:06:15).

Their line count (332) is correct. Their grep list
(`stdin|urlopen|requests|socket|subprocess|while True|Popen|sleep|11434`) omits
`glob`/`walk`/`rglob` — which is exactly why it could not see the cost. Same
detector-blind-spot class as the escaped-quote regex they already self-reported.

**Correctly-scoped claim:** *skill-router/route.py costs ~190s on a cold `_index.json`
because `_build_index()` recursively globs the 13 GB plugin cache; under eval.py's 30s
timeout the build dies before the cache is written, so every call re-times-out and the
LEXICAL arm records empty stdout. With a warm cache the identical invocation shape
returns in 0.15s.* The fix is pre-warm / narrow the glob / raise the first-call timeout
— **not** anything in the invocation path.

## (d) The overclaim

They wrote completion.py is live "via two downstream consumers", naming
`workflow-monitor/monitorcore/dbx_completion.py`. It is **not a consumer**: its own
docstring line 5 reads *"`hooks/_shared/completion.py` is the historical gate. It is
deliberately left alone"*, and its import block (51-58) has no `import completion` and
no `sys.path` work. Estate-wide grep for `import completion` / `from completion import`
(temp dirs excluded) = 5 hits: 3 test files + `codex-databricks-fanout/scripts/harness/
gate.py:56` in both the `.claude` and `.agents` copies.

- Correctly-scoped: **ONE** live non-test consumer, not two.
- Their RISK #1 (ImportError in the Databricks monitor path) is therefore refuted as a
  failure mode — that module cannot break.
- **New risk they missed, worse than the one they named:** gate.py:55-58 wraps the
  import in `except Exception: artifact_text_ok = None`, and :107 guards
  `if artifact_text_ok is not None:`. A broken completion.py import is **silently
  swallowed and the artifact check SKIPPED**, never raised. Measured: the `.agents`
  copy already resolves `_SHARED` to `None` (no `.agents/hooks/_shared` exists), so it
  already imports nothing and already skips that check. Pre-existing, but it is the real
  blast radius of adding an import-time sibling dependency.

## (a) Scope note, not a defect

1 of my 2 "should fire" prompts did not fire: nouns extracted were
`['router','harness','create','scratch']` — "bench" was never extracted. Recall is
partial, exactly as their own honest note about single-word stem matching says.

Live-session firing remains **UNVERIFIED**, as they stated: I searched all 4 live
transcripts for `recall-gate` hook records after 23:05 → **0 hits**; the 32 records in
`state/recall-gate-20260925.jsonl` carry **no `session_id` field** and their noun sets
match probe/test fixtures (`zqxjkv`, `plorbnax`, `frobnit`).

## (c) Precision nit

Live `success.json` now holds **309** keys, not 308 — one new key
`skill:game-find-anticheat` appeared after their measurement. "keys before=308
after=308" was true at reset; it has drifted +1. Backup totals reproduced exactly:
`keys=308 suggested_total=5800 used_total=5 max_suggested=1093 ratio=0.0009`.
Live: `suggested_total=6 used_total=1 ratio=0.1667`.

## Hard-rule scan — NO violations attributable to this lane

| Rule | Check | Result |
|---|---|---|
| 1 authored-vs-deployed | rules mtimes both trees | 3 rules changed 22:19-22:20 with **identical** mtimes in `~/.agents/rules/common` AND `~/.claude/rules/common` (correct order), **before** this lane's 22:25:36 backup, absent from its files_changed, matching the other lane's commit. `lint-rules-loading.ps1` → **PASS: every authored rule is cited AND deployed** |
| 2 `~/.claude.json` | python `json.load` | VALID, 95 top keys, **88 mcpServers**, 45 projects. mtime 23:31:29 == CreationTime = Claude Code's own atomic temp+rename, 26 min after the lane's last edit, 4 sessions live. Unattributable, not a finding |
| 3 no deletions | counts + diff | 88 mcpServers, 417 `.claude` skills, 416 `.agents` skills, 7 plugin dirs. settings.json diff is **additive-only: 17 `=>` lines, 0 `<=`** |
| 4 credentials | mtime sweep 22:00-23:10 over `.env`/`auth.json`/`credentials*`/`*token*`/`*.pem`/`*secret*` depth 3 | **NONE** modified; no value in the report |
| 5 no kills | process count | claude.exe=4, python=73, node=199 still live |
| 6 no commit | `git log` both trees | `~/.agents` HEAD `e04ffabc4` 22:21:20 (other lane), 18 dirty. `~/source/agent-skills-toolchain` → *fatal: not a git repository* — independently corroborates their "cannot reconcile" finding. No wire-inert commit |
| 7 both-states | my own break tests | independently proven for (a), (c), (d); (b) by receipt+artifact; (b-res) is a report, not a gate |
| 8 shell | n/a to validator | — |
| 9 write-as-you-go | artifact present | 33,086 B |
| 10 net-negative | retires named per item | present and specific |
| 11 labels | VERIFIED/INFERRED + bands | present throughout; the only mislabel is (b-res)'s cause |

## Regressions — NONE

`_dispatch`: **8 failed / 35 passed / 10 xfailed** — identical to their stated pre-work
baseline, and `test_settings_has_exactly_one_local_dispatch_for_event[PostToolUse]` (the
test most likely to break from a new PostToolUse entry) **PASSES**; only the PreToolUse
variant fails, on an event they never touched.

Green: harness-bench 37/37 · recall-gate 9/9 · observe 4/4 · failure_taxonomy 34/34 ·
completion 18/18 · completion_conformance 18/18 · taxonomy_binding 2/2 ·
lint-rules-loading PASS · settings.json parses (36 top keys, deniedMcpServers=6,
skillListingBudgetFraction=0.04, ENABLE_TOOL_SEARCH=true — all ground-truth values
preserved).

## Side findings (pre-existing, not theirs)

1. `test_completion_vendored.py` prints *"NOTHING CHECKED -- no vendored file present.
   Not a pass."* and returns 2. The C1 vendored-drift guard is currently **inert** on
   this box (the Databricks runners are absent). Honest by construction; still a gate
   measuring nothing here.
2. `.agents/skills/codex-databricks-fanout/scripts/harness/gate.py` cannot resolve
   `hooks/_shared` and therefore silently runs without the artifact-text check.
3. `~/source/agent-skills-toolchain/hooks` exists and is **empty (0 items recursive)**,
   and the tree's `.git` is not a repository — so the PreToolUse hook's prescribed
   remedy ("edit the repo copy") is unreachable. Their refutation stands.
