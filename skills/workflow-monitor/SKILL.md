---
name: workflow-monitor
description: Use when you want to LIVE-monitor a Claude Code Workflow ("ultracode") fan-out — watch every parallel agent's status, lens/task, model, tokens, tool activity, and final result across the WHOLE FLEET (all sessions/projects) in a read-only terminal cockpit, instead of the sparse native /workflows view or opening a terminal-tail per agent. Also for triaging errored/retrying/stalled agents mid-run, or reviewing a finished run's per-agent prompt/output.
---

# workflow-monitor

## Overview
A live, **read-only**, Windows-native **Textual cockpit** for Claude Code Workflow (ultracode) runs. It surfaces the one signal the native `/workflows` view and the old per-agent tailers under-use: the live-flushed telemetry **manifest** `~/.claude/projects/<proj>/<sess>/workflows/wf_<id>.json` (re-written ~0s after every agent progress event), which already carries per-agent `label` (the human lens name), phase, model, state, tokens, tool activity, and prompt/result previews — for the whole fan-out, across every session/project.

## Run it
```bash
pip install textual rich          # one-time (textual is the only non-stdlib dep)
python workflow_monitor.py        # the interactive whole-fleet cockpit
python workflow_run.py            # a plain-text one-shot fleet board (no TUI) — quick check / CI-friendly
```
Cockpit: left = filter + status chips + a **run → phase → agent** tree (glyph · lens · model · tokens · last-tool; `↻` retry, `STALL Ns` when idle); right = the selected agent's **Task** (its prompt), a live **Feed** (transcript tail), and **Result** (headline + clean output). Keys: `q` quit · `f` live-follow · `r` refresh. It **never writes** any `.claude` file and polls O(changed) so it stays snappy across hundreds of runs.

## How it works
`workflow_run.py` is the shared, dependency-light parser (manifest + journal + transcripts + `FleetPoller` O(changed) polling); the recall-workflow-agent skill shares this same core. Output/status come from the authoritative journal `result` / `started` events, not mtime guessing.

## Export a run (`e` / `wfmon export`)
Snapshot any run to a **self-contained, secret-redacted** Markdown / HTML / PDF report. Pure-render core (`wfmon_export`), stdlib-only at import; PDF engines are optional and feature-detected.
```bash
wfmon export <wf_id> [--scope run|subset|agent] [--agents L1,L2] \
             [--format md|html|pdf] [--pdf-engine ...] \
             [--tools full|summary|none] [--no-thinking] [--no-redact] \
             [--out DIR] [--projects DIR]
```
- **Cockpit keybind:** press `e` on a selected run/agent node to export it off the UI thread (defaults: md, full tools, thinking on, strict redaction, out = `<tempdir>/wfmon-exports/`).
- **Scope:** `run` = every agent; `subset`/`agent` = agents whose **label** is in `--agents` (case-insensitive, **label-set** — all matching agents export).
- **Fan-out DAG:** every report renders the run's phase→agent + phase→phase graph (Markdown as a `mermaid` flowchart plus an ASCII fallback; HTML inline) built purely from the phase list — there is no stored `fanout` field.
- **Redaction (strict by default, fail-closed):** API keys, GitHub PAT/oauth tokens, AWS keys, Slack tokens, JWTs, PEM private keys, `*.gitcrypt.key` paths are masked, then home paths (`C:\Users\<u>`, `/mnt/c/Users/<u>`, 8.3 `PREKZU~1`, …) collapse to `~`. An audit banner reports `N masked`; `--no-redact` opts out and is banner-flagged `redaction: off`.
- **PDF ladder (best-available, never raises):** `typst`(+pandoc) → `playwright` → `edge` → `chrome` → `pandoc` → `xhtml2pdf` → `fpdf2` → **`html`** (terminal). On any engine failure it descends and always ends by writing the self-contained interactive HTML (whose `onbeforeprint` expands all sections for browser print-to-PDF). `--pdf-engine` forces a rung but still degrades to HTML.
- **Read-only out-guard:** `--out` is resolved (realpath of the nearest existing ancestor + normalized tail + normcase, expanding 8.3 short names) and **refused** if it lands under `~/.claude/projects/**`. Export only ever READS `.claude`.
- **Exit codes:** `0` success · `1` render/engine error (PDF still degraded to HTML) · `2` bad args / out-guard violation / unknown `wf_id` / unknown label.

## Caveat (important)
The manifest + journal shapes are Claude Code **internal + undocumented** (verified on **v2.1.207**). Parsing is defensive, and `test_workflow_run.py` pins the schema against a real fixture — if a Claude Code update changes the shape, that test fails loudly. Re-verify the fixture after major CC upgrades.
