# harness-bench - semantic-router regression net

Weekly Windows Scheduled Task (`ClaudeHarnessBench`) runs `bench.py` -> `../semantic-router/eval.py --json`, compares the shipped HYBRID router's skill/mcp recall to `baseline.json`, and on a DROP appends ONE `[date] [harness-bench] <what regressed> | PROPOSE: <cmd>` line to `~/.claude/BACKGROUND-DIGEST.md`.

It rides the EXISTING background-digest bus - NO new hook event / runtime / MCP; LOG + PROPOSE only (never auto-acts). The existing reader surfaces the line once at the next SessionStart.

- Register / unregister: `pwsh register-task.ps1` / `pwsh unregister-task.ps1` (no admin needed).
- Reset baseline: delete `baseline.json` - the next run re-seeds it silently. Baseline ratchets UP on improvement; a regression keeps the higher bar until fixed. Override paths in tests via `BENCH_BASELINE` / `BG_DIGEST_FILE`.
- Anti-overfit rationale: a green regression net is what LICENSES aggressive skill pruning - if HYBRID recall does not drop, pruning a skill did not hurt routing.
