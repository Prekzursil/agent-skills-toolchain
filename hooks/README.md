# hooks/ — agentic-perfection hook set (canonical copy)

This tree is the **canonical, version-controlled copy** of the session-built
*agentic-perfection* hook set that runs in `~/.claude/hooks`. It is the durable
home for the work so it is not lost if `~/.claude` is wiped, and so the program
can be revisited, diffed, and restored.

- **Deploy / restore:** `pwsh -File scripts/sync-hooks.ps1` copies this tree back
  into `~/.claude/hooks` (COPY, not symlink; idempotent; **non-destructive** — it
  never deletes live files, because the live dir is a superset). Dry-run with
  `-WhatIf`. See [`../scripts/sync-hooks.ps1`](../scripts/sync-hooks.ps1).
- **Program writeup / changelog:** [`../docs/agentic-perfection/`](../docs/agentic-perfection/)
  (CHANGELOG + plan + proactive-partner program + open-threads snapshot).
- **event-ledger lives HERE**, in [`event-ledger/`](event-ledger/). This line used
  to point at `../tools/event-ledger/` and call it "intentionally not duplicated
  here", which had become doubly false: the ledger *is* in this tree, and it *was*
  duplicated. `tools/event-ledger` was deleted on 2026-10-24 as a stale copy whose
  own README claimed to be "the versioned copy — keep in sync" while sitting two
  generations behind (233-line `ledger.py` against this tree's 441, and missing
  `oats.py`, `prune-report.py` and three test modules entirely).
- **Related, separately-versioned hooks:** a curated workspace-hooks subset
  (anti-degen, goal-reinject, inquisitiveness) lives in
  [`../tools/workspace-hooks/`](../tools/workspace-hooks/), and is intentionally
  not duplicated here.

## Design law

Grounded in the MAST failure taxonomy (arXiv 2503.13657) and the self-calibration
LAW (Huang ICLR'24: intrinsic same-context self-correction FAILS — every check
needs an **external signal**). The residual silent-failure surface lives **between
turns and between agents**, where in-context reasoning is blind; every fix writes a
durable **external ledger** (flat files / SQLite — never graph-memory, which blew
the latency budget before). Stay under the **~6-active-hook latency ceiling** by
CONSOLIDATING checks behind one dispatcher per event rather than one always-on hook
per check.

## Dispatcher architecture (`_dispatch/`)

`_dispatch/dispatch.py` + `_dispatch/manifest.json` are a **per-event dispatcher**.
For a given event, `dispatch.py` reads stdin once, then runs every check whose
`matcher` (regex on tool name; absent = always) matches — each in-process in its own
thread with a per-check timeout, **fail-open** — and aggregates every check's
`additionalContext` into ONE `hookSpecificOutput`. Adding a future check is one line
in `manifest.json`. This consolidated `Stop` 5→1 and `SessionStart` 3→1 (54/54
behavioural equivalence verified) to reclaim per-turn latency. `PostToolUse` and
`PreToolUse` checks are also routed through the manifest. Pre-existing B1/legacy
hooks stay as their own `settings.json` entries and are intentionally NOT listed in
the manifest.

| Event | Checks dispatched (this repo) |
|-------|-------------------------------|
| `SessionStart` | bg-registry/reconcile · memory-spool/flush_check · heartbeat · open-loops/resurface · background-digest/reader · wire-check · git-hygiene (both moved here from `Stop` on 2026-08-27; SessionStart ceiling raised 20 -> 35 in lockstep) |
| `Stop` | bg-registry/done_marker · heartbeat · honest-signal · stub-ledger/report · todo-surfacer · journey-coverage · dark-surface |
| `PostToolUse` | memory-spool/flush_check · tool-result-sentinel · stub-ledger/record |
| `PreToolUse` | bg-registry/register · memory-spool/spool · dup-guard |

`ulysses` and `tms` register their own `PreToolUse` exit-2 enforcement (a future
PreToolUse-dispatcher consolidation is queued in OPEN-THREADS).

## Hook catalog

### Durability spine (between-turns/agents — Tier 1 keystones)

| Hook | Event(s) | Trigger / what it does |
|------|----------|------------------------|
| `bg-registry/` | PreToolUse(Task) · SessionStart · Stop | Write-ahead NDJSON per `Task`/longrun spawn `{id,kind,cmd,pid,artifact,scope,ts,status}`; SessionStart reconciler checks pid-liveness + artifact and injects "ORPHANED BG WORK …". Fixes restart-killed-agent silent loss. |
| `memory-spool/` | PreToolUse + PostToolUse(`write_note`/`edit_note`) · SessionStart | Spools every intended basic-memory write to a local file FIRST; SessionStart read-back-verifies it flushed, re-flushes/alerts if not. The true fix for the 4h silent-memory-loss. |
| `wire-check/` | SessionStart (Stop until 2026-08-27) | Builds a static reference graph over the session diff; flags any session-added symbol/component/route/handler referenced 0× ("dead button / built-but-not-wired") and `*_v2/_new/_copy` with no live v1. The anti-slop keystone. |
| `_shared/` | (library) | `projid.py` resolves a **canonical project root** (not cwd drift) so every ledger is keyed consistently; `projid_migrate.py` migrates legacy cwd-keyed state. |

### Verification / anti-slop / boundary (Tier 2 just-do-its)

| Hook | Event(s) | Trigger / what it does |
|------|----------|------------------------|
| `tool-result-sentinel/` | PostToolUse(*) | Classifies every tool result → SUCCESS / FAILED / AMBIGUOUS (exit code + MCP error-envelope + empty-on-expected) and injects "TOOL X returned FAILURE — do not treat as success." |
| `honest-signal/` | Stop | The verbalized confidence band (VERIFIED / INFERRED / GUESSED) must match whether a verifying tool actually ran. Kills "I'm unsure" → then acts certain. |
| `stub-ledger/` | PostToolUse(Edit/Write) record · Stop report | Tracks every placeholder/stub/TODO introduced and reports unresolved ones at Stop. |
| `dup-guard/` | PreToolUse(Write) | Search-before-build: warns when a new file duplicates an existing capability. |

### Wildcard gems (cross-domain borrows)

| Gem | Origin | Event(s) | Trigger / what it does |
|-----|--------|----------|------------------------|
| `open-loops/` | Zeigarnik / GTD prospective memory | SessionStart resurface · `add.py` · `trigger_match.py` | Trigger-action notes `{condition,action,status}` ("when we touch BC, re-assert event_0") fired on **detection**, not request. Cures the forgotten-thread stress. |
| `ulysses/` | Ulysses self-binding / behavioral contracts | PreToolUse(arm/enforce) | Self-binding contracts; an exit-2 tripwire guards declared-dangerous ops (e.g. live-game writes). |
| `tms/` | Doyle-1979 Truth Maintenance System | PreToolUse stale-anchor | A SQLite justification graph behind every load-bearing RE value (offset/addr/pid/version). Retract a premise → cascade-flip downstream findings to OUT; `stale_anchor.py` BLOCKS a tool call resting on a retracted/changed-hash premise. Structural fix for the wrong-but-consistent anchor. See `tms/CONVENTIONS.md`. |
| `calibrated-silence/` | Signal Detection Theory / alarm-fatigue | (library used by proactive consumers) | Proactivity as an adaptive SDT operating-point: logs each interjection `{context,type,user-reaction}` and slides the threshold by rolling hit-rate + a fatigue proxy. Dissolves proactive-vs-don't-fatigue-me; governs all proactive consumers. |

> The **discipline-forge** capstone (the `/forge-discipline` skill that emits a
> hook + memory-schema + tripwire + skill for any named pattern and chaos-tests
> the tripwire before declaring it installed) lives as a **skill**, not a hook —
> see `skills/forge-discipline/`. The two disciplines it forged this session,
> **`no-force-push/`** and **`todo-surfacer/`**, are versioned here (each ships its
> `spec.json`, `fixtures.json`, a `chaos_*.py` GameDay self-test, and
> `SELFTEST-RESULT.txt` evidence).

### Anticipatory layer

| Hook | Event | Trigger / what it does |
|------|-------|------------------------|
| `background-digest/` | SessionStart | Reads the "while you were away" digest produced by the scheduled watchers (`scripts/agentic-perfection/world-watch.ps1`), surfaces it, then archives + truncates it. |

### Per-project identity & self-model

| Hook | Event | Trigger / what it does |
|------|-------|------------------------|
| `capability-catalog/project_card.py` | SessionStart | Injects a per-project card ("how I fail THIS user" / resume state) after the global capability catalog, keyed by the canonical project root from `_shared/projid`. Only `project_card.py` + its test are versioned here; the pre-existing `inject.py`/`catalog.json` stay live-only by design. |

### Infra / health (B1 + fixes)

| Hook | Event | Trigger / what it does |
|------|-------|------------------------|
| `mcp-liveness/` | (liveness) | Self-heals + alerts when a critical MCP (basic-memory) is down; `restart-basic-memory.ps1` invokes the hardened launcher. The basic-memory-4h fix. |
| `heartbeat/` | SessionStart · Stop | Health banner; accuracy fixed to a **live socket-probe** (no more stale mem:UP/DOWN). |
| `edit-checkpoints/` | (edit) | Snapshots edited files so `/rollback` can restore them. |
| `truth-verify/` | (verify) | Verification gate for load-bearing claims. |
| `persist-nudge/` | (nudge) | Nudges durable capture of decisions/findings. |

## Notes

- `_dispatch/manifest.json` hard-codes `hooks_root` to the live path — that is the
  deployment target and is correct after `sync-hooks.ps1`.
- `semantic-router/index/` (`meta.json` + `vecs.f32`) is a **generated** embedding
  index, committed so the router works immediately after a restore; rebuild with
  `python semantic-router/build_index.py`. `semantic-router/success.json` is mutable
  runtime state (rewritten on each routing success) and is **not** versioned
  (gitignored); `success.py` recreates it on demand.
- Every hook is fail-open (any error → exit 0). Most ship a `test_*.py`.
- Wiring (matchers/timeouts) lives in `~/.claude/settings.json`, which is personal
  and not versioned here; the manifest documents the per-event consolidation.
