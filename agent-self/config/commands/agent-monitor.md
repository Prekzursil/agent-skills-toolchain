Launch a live view of Claude Code subagents. The former standalone Tkinter app has been
consolidated into the shared **`monitorcore`** package (stdlib-only, vendored inside the
`workflow-monitor` skill), split across two surviving surfaces:

Usage: /agent-monitor

## Whole-fleet Workflow cockpit (Task agents AND agents inside Workflows)

The **`workflow-monitor`** skill's live, read-only Textual cockpit — the whole-fleet board,
tagged by `[wf_id]`, with per-agent transcript-derived status and a live Feed pane:

```bash
python "$HOME/.agents/skills/workflow-monitor/workflow_monitor.py"
```

## Per-agent tail + flat Task-agent discovery

The **`run-agent-monitor`** skill drives `monitorcore.discovery` (discover every
`subagents/agent-*.jsonl`, flat or under a workflow) and `monitorcore.agent_tail` (a live,
colored per-agent tail):

```bash
# One-shot discovery table of the active session's subagents:
export PYTHONPATH="$HOME/.agents/skills/workflow-monitor"
python -c "import monitorcore.discovery as d; \
  [print(r['name'], r['running'], r['wf'] or '-', r['type']) \
   for r in d.scan(d.pick_active_dir(), 150, 120)]"

# Live-tail one agent (Ctrl-C to quit; -u when piping):
python -u -m monitorcore.agent_tail <path-to-agent-*.jsonl> --backfill 8
```

Both surfaces are **100% read-only** — they only read each subagent's own JSONL transcript, so
they never disturb the monitored session.

- Per-agent status: the discovery table's `running` flag is a recent-activity (mtime) signal,
  and the cockpit shows a coarse `running` / `done` / `error` / `idle` state. A finer
  transcript-derived deriver (`monitorcore.agent_state.agent_status` →
  `running` / `working` / `done` / `stalled`) is ported and unit-tested but not yet wired to a
  launchable surface — it feeds a live status display once the `AgentSource` monitor adapter
  lands (a later PR, which also adds `working` to the `Snapshot.state` enum).
- Freeze detection for long autonomous loops: `python -m monitorcore.watchdog` (alert-first;
  `--kill` optional).

Note: the cockpit opens a terminal UI — it cannot render inside the Claude chat interface.
Source: `tools/monitorcore/` (CI-gated), vendored into `skills/workflow-monitor/monitorcore/`.
