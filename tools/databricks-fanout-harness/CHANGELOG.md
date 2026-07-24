# Changelog — databricks-fanout-harness

## 2026-07-24

### Fixed
- **`run_E.submit_and_gate` no longer has a default wall-clock timeout.** `timeout_s` now defaults to
  `None` (poll until the Databricks job reaches a terminal state; cluster autotermination is the
  backstop). Pass an explicit `timeout_s` **only** to opt into a cap. The three internal callers
  (`node_preflight`, `runnability`, `run_coverage_fanout`) no longer pass a cap.
  - **Why:** a hard 45-min cap produced a FALSE-NEGATIVE `TIMEOUT` on the 2026-07-24 e2e prompt-synthesis
    run — the 3 artifacts were complete + gate-valid, but the cluster took just over 45 min end-to-end, so
    the driver gave up ~seconds before the job flipped `TERMINATED SUCCESS`. Large fan-out waves legitimately
    run for hours; a default cap silently discards good work.
  - **Validated:** re-gating the completed artifacts returns 3/3 `DONE`; a fresh no-cap run (the 4th
    "parallel-worktree orchestrator" prompt) polled 25m36s to a correct `DONE`.

### Changed
- **Node codex profile — fast + max-efficiency + full-permission, now passed via `-c`**
  (`contract.node_codex_flags()` + `preflight_units._CODEX`). Because the node runs
  `codex exec --ignore-user-config`, the owner's `~/.codex/config.toml` does NOT apply there, so the profile
  is passed explicitly: `-c model_reasoning_effort=ultra -c service_tier=priority -c approval_policy=never
  -c sandbox_mode=danger-full-access`. **"fast" maps to `service_tier=priority`** (priority serving) — codex
  0.145 has no `fast` config key (`fast-mode` is only a TUI/status-line state).
  - **TODO (node-side):** the Databricks `batch_runner` notebook must apply the same `-c` flags to its
    per-unit `codex exec` for the FAN-OUT to run under this profile (this change only covers the harness's
    preflight probe + the documented contract).

### Added
- `generated-prompts/` — 4 large paste-ready adoption prompts produced by the harness's own 21-agent
  coverage→synthesis fan-out (a full dogfood of the rail): one-shot dynamic e2e `/workflow` ·
  FULL CyberStrike adoption · FULL HackTricks skill+MCP adoption · parallel-worktree ultracode orchestrator.

### Known limitations (single-signal discipline)
- Reading an artifact via `databricks fs cat` **during** an active run returns racy partial snapshots; only
  POST-TERMINAL harvests are authoritative. The gate's `landed` count (filename exists) is an optimistic
  progress signal, **not** completion — completion is the full 5-clause AND-gate (terminal + artifact +
  ≥floor + `UNIT-COMPLETE:<id>` sentinel + schema).
