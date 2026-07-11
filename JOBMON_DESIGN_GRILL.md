# jobmon — general-purpose long-task monitor: design grill (decision queue)

Grounding: grill-me-extensive SCOUT+DIVERGE (wf_57443cdf, 4 lenses) over the FEP dashboard
(`~/.biomni-mcp/dbx_fep_dashboard.ps1`), `longrun`, `agent-monitor`, `mcp-gui/mcp-manager`.
Generalize the FEP dashboard into a permanent, source-agnostic monitor callable autonomously + explicitly.

## SETTLED (strong 4-lens consensus; confirm-only)
- **S1. No Fable/deep-research pass** — permanent-tool pattern + harness plumbing + reusable code fully in-repo. Engineering, not research.
- **S2. Generalize, not greenfield** — extract FEP `Bar/HMS/Spark/Grid` + pace-ETA + stage-idle into a source-agnostic core; the real gap = a generic job-descriptor (6 divergent monitor copies exist).
- **S3. Build ON the harness** — inherit `longrun` `SUCCESS:<id>`/`FAILED:<id>` §4 terminal contract, Monitor, PushNotification, event-ledger.
- **S4. Text/JSON primary** — GUIs "can't render in Claude chat"; agent needs machine-readable `status.json` (+ §4 markers) to watch its own monitor. GUI optional/local.
- **S5. Two-plane** — UNIVERSAL liveness plane (log mtime / byte-growth / line-rate / process-up — any task) + OPTIONAL progress plane (authored tasks emit `progress.json` heartbeat `{schema,done,total|null,phase,ts,seq}`); log-scrape = read-only 3rd-party fallback.
- **S6. Kill 2 shipped bug-classes** — (a) phantom-cap: ban hidden clamps; out-of-range WIDENS ETA uncertainty. (b) log-rolloff undercount: read the WHOLE progress record + monotonic `seq`, never a fixed tail.
- **S7. BLIND/UNKNOWN first-class** — tool-error keeps last-known verdict + age stamp; never render absence-of-signal as "done".
- **S8. ETA honesty** — p50/p90 range not a point; "total unknown ⇒ no %, show elapsed+rate"; measured-vs-prior provenance; never slide the finish clock on a stalled job.
- **S9. Config** — declarative registry (`task = {id, adapter, parser, eta_model, notify}`) + code escape-hatch for exotic sources.
- **S10. Detached, edge-triggered, deduped poller** — survives session-reap; agent reads flags edge-triggered (no identical-frame re-emit = no token waste / §4 compliant).

## OPEN DECISIONS (grill one at a time)
- **G-1 STACK** — Python+rich vs PowerShell-stdlib vs Python-stdlib. [REC: Python+rich core + thin PS launcher.] STATUS: asked.
- **G-2 FORM-FACTOR** — hybrid (core CLI + thin skill, MCP phase-2) vs script-only vs MCP-first. [REC: hybrid.]
- **G-3 PASSIVE vs WATCHDOG** — observe-default + opt-in `--watch`/remediate per task. [REC: two-tier.]
- **G-4 AUTONOMOUS-ATTACH** — explicit register-only first vs auto-attach every op >60s. [REC: register-only first; whitelist later.]
- **G-5 NOTIFICATIONS** — terminal + first-progress + stall vs %-milestone pushes. [REC: no %-spam.]
- **G-6 SCOPE/MIGRATION** — core + 2 live probes (FEP, BPMD) first vs migrate-all-now. [REC: core+live-first, commit early.]
- **G-7 NAME** — `jobmon`? [REC: jobmon.]

## PROCESS (user-specified)
grill (this doc) -> ultracode e2e build workflow -> branch/PR/merge green (agent-skills-toolchain) -> skill-vs-MCP settled by G-2.

## DECISION LOG (filled as answered)
- **G-1 STACK = Python + rich, COV-GATED PACKAGE** (mcp-manager pattern: `pyproject.toml`/uv, basedpyright standard, pytest `--cov-branch --cov-fail-under=100`, wired into `quality.yml` per-package `gate-types` + `gate-tests-coverage`). User chose max rigor over the lower-CI-burden tool option. Implication: 100%-branch coverage is a build requirement, so the engine must be structured for testability (pure core + injected clock/poller/notifier).
- **G-2 FORM-FACTOR = Package + MCP server (`jobmon-mcp`) from day 1 + CLI.** Agent calls structured MCP tools from any session (composes with cloud-hub); humans use the CLI (`--watch` rich TUI / `--json`). Most agent-native. Implication: design the MCP tool surface (e.g. `register_task`, `status`, `list`, `attach_watch`, `set_notify`) over the SAME core the CLI uses; the package now ships `core/`, `cli/`, `mcp/`, `ui/` (rich TUI) sub-packages, all under the 100%-cov gate.
- **G-3 REMEDIATION = Two-tier** — observe/read-only by default; per-task opt-in `--watch`/remediate (restart-on-death, auto-resubmit, auto-download, re-poll), mirroring the existing bpmd/rphe auto-recover watchers. Implication: remediation is a separate opt-in capability behind an explicit per-task flag; the core stays read-only + pure.
- **G-4 AUTONOMOUS-ATTACH = Auto-attach every op >60s from DAY 1** (PostToolUse/longrun hook auto-registers any background-Bash/workflow/longrun op crossing 60s). Max ambition. Implication: the auto-attach hook is a first-class day-1 deliverable — must be fail-open, deduped, whitelist/threshold-scoped (never over-attach trivial ops), carry a kill-switch, AND hit 100% branch cov. It is the riskiest, most harness-coupled component; design it with a pure decision-fn (attach? y/n) + a thin hook shell so the logic is fully testable.
- **G-5 NOTIFICATIONS = Terminal + first-progress + stall** (via PushNotification). No %-milestone spam. Push on done/failed/died, first real progress, and stall/anomaly (rate-drop / no-heartbeat).
- **G-6 BUILD ORDER = EVERYTHING in one PR** — engine + auto-attach hook + all probes + task-templates + rich TUI + MCP + `/command` + skill + deploy + CI wiring + tests-to-100%-cov, all in the first PR. Largest surface / slowest-to-green, but a single complete deliverable.
- **G-7 NAME = `taskwatch_monitor`** (package `taskwatch_monitor`, `/taskwatch_monitor` command, `taskwatch_monitor-mcp` server).

## CONVERGED SPEC (grill COMPLETE 2026-07-11 — this is the build input)
**Name** `taskwatch_monitor`. **Stack** Python + rich, cov-GATED package (mcp-manager pattern: pyproject/uv, basedpyright, pytest `--cov-branch --cov-fail-under=100`, wired into `quality.yml`). **Sub-packages:** `core/` (declarative registry, source-adapters, ETA-model library, universal-liveness + optional-progress planes, BLIND state, measured-vs-prior provenance, sqlite history/priors) · `cli/` (`--watch` rich TUI + `--json`) · `mcp/` (`register_task`/`status`/`list`/`attach_watch`/`set_notify`) · `hooks/` (auto-attach every op >60s: pure decision-fn + PostToolUse shell, fail-open, deduped, kill-switch) · `probes/` (FEP-Databricks, BPMD-Modal + templates: modal/gh-ci/rclone/build/git/llm/generic-logfile) · `ui/` (rich TUI). **Behavior:** two-plane (liveness + progress.json heartbeat), two-tier (observe default + opt-in remediate), notify terminal+first-progress+stall, ETA p50/p90 range (no fake %, provenance), kill phantom-cap + rolloff bug-classes, BLIND first-class, detached edge-triggered deduped poller, `SUCCESS:`/`FAILED:` §4 markers. **Artifacts** (mcp-gui pattern): `tools/taskwatch_monitor/` (pkg + launch.ps1 + install.ps1 + README + tests) · `~/.claude/commands/taskwatch_monitor.md` · skill `run-taskwatch_monitor/SKILL.md` + fixture + smoke.ps1 · `taskwatch_monitor-mcp` registered · D:\ deploy · sync-self snapshot. **Process:** branch -> build to green (ruff + basedpyright + pytest 100%) -> PR -> merge green.

**GRILL COMPLETE.** Next: ultracode e2e build -> branch/PR/merge green.
