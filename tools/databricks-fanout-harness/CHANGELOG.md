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
- **Node per-unit `codex exec` timeout removed — opt-in, mirroring the driver fix** (owner: "no timeout").
  `batch_runner` previously capped each unit at `u.get("timeout_s", 2400)`; now a unit runs with NO node
  timeout unless it sets a positive `timeout_s`, and `Unit.timeout_s` defaults to `None`. Tradeoff: a hung
  unit is unbounded — opt into a per-unit cap for safety-critical lanes.

### Changed
- **Node codex profile — fast (priority serving), applied + verified on the live fan-out.** The node's
  `batch_runner` already bypassed approvals+sandbox (`--dangerously-bypass-approvals-and-sandbox`) and ran
  `model_reasoning_effort="ultra"`; the ONE missing piece for "fast" was **`service_tier="priority"`**, now
  added to the per-unit `codex exec` in the live Databricks `batch_runner` notebook (verified by re-export).
  `--ignore-user-config` drops `~/.codex/config.toml`, so it is passed explicitly via `-c`. **"fast" =
  `service_tier=priority`** — codex 0.145 has no `fast` config key (`fast-mode` is only a TUI/status-line
  state). Harness side: `contract.node_codex_flags()` + `preflight_units._CODEX` mirror this (perms via the
  `--dangerously-…` flag; `service_tier` + effort via `-c`). A reference copy of the node runner is now
  version-controlled at `node/batch_runner.py`.

### Added
- `generated-prompts/` — 4 large paste-ready adoption prompts produced by the harness's own 21-agent
  coverage→synthesis fan-out (a full dogfood of the rail): one-shot dynamic e2e `/workflow` ·
  FULL CyberStrike adoption · FULL HackTricks skill+MCP adoption · parallel-worktree ultracode orchestrator.

### Known limitations (single-signal discipline)
- Reading an artifact via `databricks fs cat` **during** an active run returns racy partial snapshots; only
  POST-TERMINAL harvests are authoritative. The gate's `landed` count (filename exists) is an optimistic
  progress signal, **not** completion — completion is the full 5-clause AND-gate (terminal + artifact +
  ≥floor + `UNIT-COMPLETE:<id>` sentinel + schema).
