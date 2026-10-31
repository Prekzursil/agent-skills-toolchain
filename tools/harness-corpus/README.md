---
title: README
type: note
permalink: dqverify-repo-20261013/tools/harness-corpus/readme
---

# harness-corpus

Distils Claude Code session history (~10.6 GB of JSONL transcripts) into a bounded, structured
corpus that agents can reason over. Streaming, bounded-memory, fail-soft, read-only on the corpus.

## The hook-telemetry fix (PR3)

`mine.py` previously reported `hooks: {}` across the whole corpus and published
`DETECTOR_STATUS: BROKEN`. The conclusion drawn from that emptiness — "hooks write no durable
telemetry" — was **wrong**. Hook telemetry is the richest per-event data in the corpus.

The defect was a **nesting error, not a missing field**:

```python
# BEFORE (mine.py:309) — reads the ROOT of the record
hook = rec.get("hookName") or rec.get("hook_event_name")     # 0 matches in 1.56M lines
```

The key name `hookName` was already correct. It just lives one level down, on a record type
`scan()` never inspected:

```jsonc
{ "type": "attachment",                    // <- scan() branched on "assistant"/"user" only
  "attachment": {
    "type": "hook_success",                // 7 observed variants, see HOOK_ATTACHMENT_TYPES
    "hookName":  "PreToolUse:Bash",        // per-tool identity
    "hookEvent": "PreToolUse",             // bare lifecycle event
    "exitCode": 0, "durationMs": 469,
    "command": "Shared harness: PreToolUse",
    "stdout": "{\"hookSpecificOutput\":{...}}", "stderr": "",
    "toolUseID": "79d37b45-…" } }
```

`record_hook()` extracts it. Matching is on the **semantic role** (payload carries
`hookName`/`hookEvent`), never on the `type: "attachment"` envelope — `skill_listing`,
`task_reminder`, `deferred_tools_delta` and `file` records share that envelope and are not hooks.

### What the corpus now reports

`fires` · `by_event` · `by_outcome` · `blocks` · `block_reasons` · `errors` · `exit_codes` ·
`failing_commands` · `latency_ms` (p50/p95/max per hook).

`exit_codes` and `failing_commands` are the payoff: a hook that exits non-zero did not do its job,
and the command string identifies why (e.g. an unexpanded `${CLAUDE_PLUGIN_ROOT}`).
`latency_ms` matters because hooks sit on the critical path of every tool call.

## Tests

```bash
python -m pytest tools/harness-corpus/test_hook_telemetry.py -v
```

12 tests over **real** record shapes captured from `~/.claude/projects` — nothing invented.

`test_control_detector_finds_known_present_hooks_in_live_corpus` is a **mechanical
known-positive control**: it fails if the detector finds no hooks in the live corpus, where hooks
are known to fire. That turns "before reporting an absence, prove your detector finds a
known-present item" from a rule an agent must remember into a test that runs. It is the single
most important test here — it is the one that reproduces the original defect
(`scanned 11645 live transcripts and found 0 hook fires`).

Skips cleanly via `pytest.mark.skipif` when `~/.claude/projects` is absent (CI).

## Usage

```bash
python mine.py --out <dir>                 # full corpus
python mine.py --out <dir> --max-mb 40     # skip pathological files (a single one is 4.4 GB)
python mine.py --out <dir> --limit 50      # fast dry run
```

## Deploying

`mine.py` is deliberately **single-file and stdlib-only** so deployment is one copy with no
import graph:

```bash
cp tools/harness-corpus/mine.py ~/.claude/harness-sota-2026-07-18/mine.py
```

Re-run the miner afterwards to regenerate `corpus.json`; the `hooks` section changes from
`{}` / `DETECTOR_STATUS: BROKEN` to populated / `DETECTOR_STATUS: OK`.