# Workflow Monitor (M2) — whole-fleet Workflow cockpit

A **live, read-only, Windows-native Textual TUI** that monitors Claude Code **Workflow
("ultracode") fan-outs across the whole fleet** — every session, every project, at once.

Status: the shared parser (`workflow_run.py`, M1) is built and verified against live data. The
Textual cockpit itself (layout, tree, live feed, triage) is the grounded build target described
below and in the top-level build-grounding doc; this README documents the module that exists and
the contract the UI is built on.

## What it is

Claude Code's Workflow feature ("ultracode") fans a task out into phases of parallel subagents.
Today the only ways to see that fan-out are the incumbent third-party monitor and the native
`/workflows` view — both under-use the richest data source available. This tool is a dedicated
cockpit: one screen showing every active (and recent) run across the *entire* fleet, drilling
down to a live-tailed feed of any single subagent's transcript.

It is **strictly read-only** — it only opens files under `~/.claude/projects/**` for reading, on a
poll cycle. It never writes to, mutates, or otherwise touches a live run.

## The key insight

Claude Code flushes a live telemetry **manifest** for every Workflow run to:

```
~/.claude/projects/<project>/<session>/workflows/wf_<id>.json
```

This file is rewritten almost immediately after every agent progress event and carries the
**entire fan-out state** in one place: per-agent label (the human-readable "lens" name), phase,
model, state, token count, tool-call count, last tool used, and prompt/result previews — plus
run-level status, phase list, and totals. The incumbent monitor and the native `/workflows` view
both under-use this manifest (they lean on other signals); this tool reads it directly as the
primary source of truth, cross-checking against `journal.jsonl` for authoritative per-agent status
and against the subagent transcripts for full drill-down. Reading the manifest instead of
reparsing raw transcripts is also what makes whole-fleet, near-real-time polling affordable.

## How to run

Requires Python 3.11+ (uses `from __future__ import annotations` / `X | None` syntax) and the
`textual` package (not yet a dependency of anything else in this environment — install it):

```
pip install textual rich
```

The TUI entry point (once built) will live alongside `workflow_run.py` in this directory. Until
then, `workflow_run.py` is runnable standalone as a smoke test / plain-text fleet board:

```
python workflow_run.py
```

This prints one rollup line (`N runs (M active) · running/done/error · total tokens`) followed by
the 8 most relevant runs (active first), each showing wf_id, name, status, per-agent counts, and
total tokens — a quick way to confirm the parser sees live data before trusting the full cockpit.

## The CC v2.1.207 internal-schema caveat

The manifest and journal formats are **internal, undocumented Claude Code implementation
details**, verified against `CC_SCHEMA_VERSION = "2.1.207"` (see the constant in
`workflow_run.py`). They are not a public API and can change without notice in a future Claude
Code release. `workflow_run.py` is written defensively against this:

- every field read goes through `_i()` / `_s()` helpers that coerce missing/wrong-typed values to
  a safe default (`0` / `""`) instead of raising
- `parse_manifest()` returns `None` on unreadable/malformed JSON rather than crashing the poller
- only fields observed on effectively every entry in real data are relied upon

Because of this, **a fixture test is mandatory**, not optional: capture one or more real
`wf_<id>.json` + `journal.jsonl` snapshots (e.g. from the verified `wf_2fcd91d3-c7b`
"multiai-orchestration-research" run, 13 agents / phases Search+Synthesize) as static test
fixtures, and assert `parse_manifest()` / `journal_states()` / `FleetPoller.poll()` produce the
expected `WFRun`/`WFAgent` shapes against them. That test is the tripwire that catches a future
Claude Code version silently changing the manifest schema, before the cockpit just goes quietly
blank or wrong.

## Data model (M1, in `workflow_run.py`)

- **`WFAgent`** — one subagent within one run: `agent_id, index, label, phase_index, phase_title,
  model, state, tokens, tool_calls, duration_ms, last_tool, last_summary, prompt_preview,
  result_preview, attempt, started_at, last_progress_at`, plus properties `.running`, `.errored`,
  `.retrying` (`attempt > 1`), and `.idle_ms(now_ms)`.
- **`WFRun`** — one Workflow run: `wf_id, name, status, phases, agent_count, total_tokens,
  total_tool_calls, duration_ms, started_at, manifest_path, session, mtime, agents[]`, plus
  `.active` (status not in a terminal set), `.counts()` (`{running, done, error, total}` derived
  from its agents), and `.subagents_dir()` (locates the sibling `subagents/workflows/<wf_id>/`
  directory holding `journal.jsonl` + per-agent transcripts).
- **`FleetPoller(projects=DEFAULT_PROJECTS)`** — the whole-fleet reader. `.poll()` globs
  `<projects>/*/*/workflows/wf_*.json`, and **only re-parses a manifest whose mtime has changed
  since the last poll** (O(changed), not O(all-manifests-every-tick)) — this is what makes
  1-second-cadence polling against hundreds of manifests affordable. `.active()` filters to
  non-terminal runs.
- **`fleet_rollup(runs)`** — aggregates a run list into `{runs, active_runs, running, done, error,
  tokens}` for the header/rollup bar.
- **`journal_states(wf_dir)`** — reads `journal.jsonl` to get the *authoritative* per-agent status
  (`'started'` vs `'result'`), since the manifest's own `state` field can lag.
- **`agent_prompt(agent_jsonl)`** / **`agent_output(agent_jsonl, wf_dir, agent_id)`** /
  **`report_headline(text)`** / **`agent_transcript(path)`** — transcript drill-down helpers: the
  agent's task (largest user message), its clean result (journal `result` if present, else the
  final assistant message), a one-line headline (first markdown heading), and the raw
  (users, assistants) message lists.

## Shared with the recall-workflow-agent skill

`workflow_run.py` is deliberately the **one shared parser** for both consumers: the
`recall-workflow-agent` CLI skill (prompt/output/headline/locate lookups for a single agent) and
this Textual monitor (the live whole-fleet board). Neither should reparse manifests or journals
independently — both import this module, so a schema fix or defensive tweak lands once and both
tools benefit, and the fixture test above protects both.
