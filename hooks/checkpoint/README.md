---
title: README
type: note
permalink: dqverify-repo-20261013/hooks/checkpoint/readme
---

# hooks/checkpoint — compaction survival

A `PreCompact` writer and a `SessionStart` reader that let a long run survive a compaction with
**zero owner re-explanation**.

```
PreCompact    -> precompact.py -> .beads/context/execution-state.md
SessionStart  -> recover.py    -> hookSpecificOutput.additionalContext
```

## Why a second checkpoint pair exists

A PreCompact checkpoint writer was **already live** — `~/.agents/harness/modules.py:1802`
`SanitizedCheckpointModule` (registered `:3467`) — and had written **101 files** to
`D:/basic-memory/compaction-checkpoints/`. Nothing read them back:

* `~/.agents/harness/recall_index.py:46` — `_EXCLUDED_DIRS` contains `compaction-checkpoints`
* `~/.agents/harness/modules.py:2049-2058` — the recall module filters the same substring at
  query time

101 files written, 0 read paths. That open loop is why ~30 manual "resume" turns were needed
across 15+9 compactions. **This pair is designed reader-first**, and the reader is a dead-man
switch for the writer (below).

## Files

| File | Role |
|---|---|
| `checkpoint_state.py` | the whole implementation: capture, render, redact, read back, recover |
| `precompact.py` | PreCompact entry point (stdin JSON → state file, `{"suppressOutput": true}`) |
| `recover.py` | SessionStart entry point (stdin JSON → `additionalContext`) |
| `wire.py` | is it actually wired? `--check` / `--print-patch`. **No `--apply`, by design.** |
| `prove_recovery.py` | executable acceptance proof: 39 subprocess-isolated probes, both-states |
| `test_checkpoint_state.py` | 34 unit tests |
| `probe_s2_growth.py` | settling experiment for the watchdog design (S2 liveness) |
| `WATCHDOG-DESIGN.md` | idle-agent watchdog — **design only**, nothing implemented |

## Typed silence (P2-01)

Every call returns exactly one of `FINDING · CLEAN · NOT-CHECKED · RAISED · DEGRADED`, on stderr
as `CHECKPOINT-WRITE:` / `CHECKPOINT-RECOVER:` for **every** state including `CLEAN`.

`recover.py` emits into context for every state **except** `CLEAN` (a fresh start with nothing to
recover, where we proved we looked). The load-bearing one:

> **FINDING** — SessionStart with `source ∈ {compact, resume, clear}` and no checkpoint on disk.
> The writer is unwired or it died.

Without that state, "nothing to recover" and "the other half is broken" are byte-identical — and
that ambiguity is exactly how 101 files came to be written and never read.

## Safety properties (each has a test)

* **Session-id gated.** A checkpoint whose `session_id` differs is reported as a pointer and its
  content is **never** injected. `hooks/precompact-snapshot/snapshot.ps1:43-48` records the
  measured harm of not doing this: one session's context injected into a different session.
  `.beads/context/execution-state.md` is per-CWD and last-writer-wins across parallel sessions.
* **Redacted before disk.** Prefers `harness.redaction.redact_text`; falls back to a local
  pattern set covering bare tokens and the JSON `{"password": …}` shape. Which one ran is
  recorded in the front matter as `redaction:`.
* **Injected content is labelled UNTRUSTED historical content** (AGENTS.md §9).
* **O(tail), never O(session).** All transcript access goes through `_shared/transcript_tail.py`.
  Measured: **0.78 s wall on a 588 MB transcript**, 600 events mined, including interpreter
  startup — with a control asserting `events_mined > 100` and `status: OK`, because a file merely
  larger than 400 bytes is not evidence that anything was read.
* **Fail-open, always exit 0.** A checkpoint hook that can block a compaction is worse than none.
* **Does not litter.** `.beads/` is used when it already exists; otherwise the state goes to
  `~/.agents/state/harness/checkpoint/<project-key>/`. `.beads/` is only created with
  `CHECKPOINT_CREATE_BEADS=1`.
* **Writes only `execution-state.md`** inside `.beads/context/`. `active-plan.md` and
  `project-context.md` belong to the recall lane and are never touched.

## Wiring (OWNER ACTION — not applied)

```
python hooks/checkpoint/wire.py --check          # currently: FINDING, neither half wired
python hooks/checkpoint/wire.py --print-patch    # the exact JSON
```

The PreCompact half **must** be a `settings.json` entry: `_dispatch/dispatch.py:108-115`
`_EVENT_ALIASES` has no `precompact` key, so the dispatcher cannot route that event at all. The
SessionStart half is preferably one line in `_dispatch/manifest.json`
`events.SessionStart.checks`.

There is deliberately **no `--apply`**: seven lanes share this filesystem, and a read-modify-write
of a shared JSON from a lane that does not own it is how a sibling's edit gets silently reverted.

## Environment

| Var | Default | Effect |
|---|---|---|
| `CHECKPOINT_BEADS_ROOT` | – | force the state-file root (tests, owner override) |
| `CHECKPOINT_CREATE_BEADS` | off | allow creating `.beads/` where it does not exist |
| `CHECKPOINT_SKIP_GIT` | off | skip the (bounded, 3 s) git probes |
| `CHECKPOINT_MAX_CONTEXT` | 2600 | cap on injected characters |
| `CHECKPOINT_STALE_HOURS` | 72 | past this, a checkpoint is DEGRADED, not injected |
| `.disabled` file | – | both halves emit `NOT-CHECKED disabled` and do nothing |

## Verify

```
python prove_recovery.py --real-transcript <a real .jsonl>   # 39 probes, expect all pass
python -m pytest test_checkpoint_state.py -q                 # 34 tests
```