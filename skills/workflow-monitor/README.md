---
title: README
type: note
permalink: dqverify-repo-20261013/skills/workflow-monitor/readme
---

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

## Export (`wfmon_export`) — snapshot a run to Markdown / HTML / PDF

`workflow_run.py` grows a small **add-only** timeline layer (`TimelineEvent`, `_flatten_content`,
`agent_timeline`, `agent_task`, `pair_tool_calls`) that walks a subagent's `agent-<id>.jsonl` in
file order into a typed event stream (`thinking` / `text` / `tool_use` / `tool_result`), pairs each
tool call with its result by `tool_use.id`, and recovers the spawn prompt (the first non-empty
`user` message — deliberately **not** the largest, so a huge later message can't shadow it). The
text-only `agent_transcript` / `agent_prompt` contract is untouched.

On top of that sits the **`wfmon_export`** package. It is stdlib-only at import time; the optional
PDF engines are feature-detected and imported *inside* functions, never at module top, so a missing
dependency can never break the cockpit or the CLI.

- **`model.py` is the only filesystem reader in the export path.** `collect_run(wf_id, *, projects,
  scope, agents)` locates the manifest, reads the journal + transcripts once, and fully
  materializes an immutable `ExportModel` (phases → agents, each with task / output / headline /
  timeline, plus a scoped `rollup` and a `provenance` dict carrying `CC_SCHEMA_VERSION`). Per-agent
  `state` is bucketed locally (`_state_bucket`) into `running` / `done` / `error` / `idle` with **no
  import of `workflow_monitor`**.
- **The renderers are pure functions of `ExportModel`** — no filesystem access in the render path.
  `render_markdown(model, *, tools, thinking, redact)` and `render_html(...)` both emit provenance
  (Markdown YAML front-matter / HTML `<header>`), a **redaction audit banner** (`N masked` or
  `redaction: off`), a **"run still active — snapshot"** banner when the run is non-terminal, status
  badges, a TOC, and a **fan-out DAG** built from `model.phases` (Markdown = a `mermaid` flowchart TD
  of phase→agent + phase→phase edges plus an indented ASCII fallback; HTML = the same DAG inline),
  then per-phase per-agent cards with collapsible tool blocks. `--tools full|summary|none` and
  `--no-thinking` are honored by **both** renderers. `render_html` is fully self-contained (inline
  `<style>` + `<script>`, no external/CDN refs), with a sticky TOC, a client-side text filter,
  collapse-all / expand-all, and `@media print` CSS + an `onbeforeprint` expand-all hook, and it
  doubles as the guaranteed PDF fallback.

### CLI

`wfmon export <wf_id> [options]` (via `wfmon.cmd`, `python -m wfmon_export`, or the cockpit `e`
keybind — all three share the one `run_export` core):

```
--scope run|subset|agent    default run; subset/agent REQUIRE --agents
--agents LABEL1,LABEL2       comma-separated agent LABELS (case-insensitive, label-set semantics:
                             ALL agents matching a label are included; unknown label lists the
                             available labels and exits 2)
--format md|html|pdf         default md
--pdf-engine ENGINE          force a PDF rung (typst|playwright|edge|chrome|pandoc|xhtml2pdf|fpdf2|
                             html); ignored unless --format pdf
--tools full|summary|none    default full (honored by md + html)
--no-thinking                drop thinking events (honored by md + html)
--no-redact                  opt out of STRICT redaction; prints an explicit 'redaction: off' banner
--out DIR                    output dir; default <tempfile.gettempdir()>/wfmon-exports/ (created on demand)
--projects DIR               fleet-root override (default ~/.claude/projects); used by tests + the keybind
```

Output: writes `<out>/<wf_id>[.<scope>].<ext>` and prints the absolute path, the PDF engine used
(pdf only), and `N masked` (or `redaction: off`). `wfmon.cmd` forwards the whole tail including the
leading `export` token; `main()` strips a single leading `export`, so `wfmon export <wf_id>`,
`python -m wfmon_export export <wf_id>`, and `python -m wfmon_export <wf_id>` all parse.

### Redaction (strict by default, fail-closed)

A pure `str → str` render-time filter, ON by default. Secrets are masked first, then home paths
collapse to `~`. Each substitution runs in its own try/except so a regex fault yields the partially
masked text — **never the raw string**. Masked classes: `sk-*` API keys (incl `sk-ant-*`), GitHub
PATs (`ghp_*`, `github_pat_*`) and oauth/user/server/refresh tokens (`gh[oure]_*`), AWS access-key
ids (`AKIA…`), Slack tokens (`xox[baprs]-…`), `Bearer` JWTs and standalone JWTs (tightened so both
leading segments must start `eyJ` — benign dotted base64 does **not** match), PEM `PRIVATE KEY`
blocks, and `*.gitcrypt.key` paths. Home-path forms collapsed: `C:\Users\<u>`, `C:/Users/<u>`,
`/c/Users/<u>`, `/mnt/c/Users/<u>`, and the 8.3 short name `PREKZU~1`. The count feeds the audit
banner; `--no-redact` is explicit and banner-flagged.

### PDF ladder (feature-detected; never imports a PDF lib at module top)

`detect_engines()` lists the available rungs in priority order — `html` is always present and last.
`render_pdf(html, md, out_path, *, engine=None, runner=subprocess.run)` auto-selects the first
available non-`html` rung (or a forced `--pdf-engine`), and on **any** failure walks down the ladder,
always ending by writing the self-contained HTML next to `out_path` and returning `("html", path)` —
it never raises to the user. Each library/binary is imported or spawned inside its own try/except;
detection uses `shutil.which` (typst / pandoc / msedge / chrome) and `importlib.util.find_spec`
(playwright / xhtml2pdf / fpdf) with **no PDF library imported at detection time**.

| # | engine | detect | how |
|---|---|---|---|
| 1 | `typst` | `which(typst)` **and** `which(pandoc)` | `pandoc <md> --pdf-engine=typst` |
| 2 | `playwright` | `find_spec(playwright)` | `page.set_content(html)` → `page.pdf(print_background=True)` |
| 3 | `edge` | `which(msedge)` / Edge install path | Edge headless `--print-to-pdf` (Edge-141 `--headless=new`→`old` ladder) |
| 4 | `chrome` | `which(chrome)` / Chrome install path | Chrome headless `--print-to-pdf` (same headless ladder) |
| 5 | `pandoc` | `which(pandoc)` (without typst) | `pandoc <md> -o <pdf>` |
| 6 | `xhtml2pdf` | `find_spec(xhtml2pdf)` | `pisa.CreatePDF(html, dest=...)` |
| 7 | `fpdf2` | `find_spec(fpdf)` | redacted, ansi-stripped plaintext → `FPDF.multi_cell` |
| 8 | `html` | always (terminal) | writes the self-contained interactive HTML; never fails |

### Read-only out-guard

Export **only ever reads** `~/.claude`. `--out` is resolved via `_resolve_for_guard` (realpath of
the nearest existing ancestor + normalized non-existent tail + `normcase`, which expands 8.3 short
names such as `PREKZU~1`) and **refused with exit 2** if it resolves to or under
`~/.claude/projects/**` — even when the target directory does not exist yet.