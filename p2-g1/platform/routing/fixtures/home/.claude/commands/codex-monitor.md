Launch the codex-monitor — a live dashboard of OpenAI Codex threads (the Codex-side counterpart to /agent-monitor, which shows Claude Code subagents).

Usage: /codex-monitor [--once] [--since-min N] [--idle N] [--max-threads N] [--width N]

Shows every recent Codex thread — from native `mcp__codex__codex` fan-out, `codex exec`, or an interactive TUI session — with its prompt, live tool-call / command-execution list, running elapsed + idle timers, token usage (+ context-window %), turn count, and typed status (running / idle / done / aborted). It merges two sources: Codex rollouts (`~/.codex/sessions/.../rollout-*.jsonl`) and Component-A relay stream files (`%TEMP%\codex-streams\*.jsonl`). Read-only — it never launches, steers, or kills Codex, so it is safe to leave running while a Workflow fans out Codex threads.

This is the **monitorcore** codex board (`mon codexmon`, PR-B3), fronted by a single-instance guard so repeated launches do not accumulate orphaned boards (a real incident on 2026-07-18: three orphaned monitors resident on a RAM-tight box). The guard also reaps strays, including the retired mingle-era monitor.
