---
title: round3-adoptions-2026-06-15
type: note
permalink: dqverify-repo-20261013/docs/round3-adoptions-2026-06-15
---

# Round-3 deep-research adoptions — 2026-06-15

Third scan over less-explored angles, ruthless default-reject vs the two prior
scans. 5 survivors; user chose to **implement all 5**. The first two scans were
on the modus-operandi / efficiency+memory axes; this round added security,
testing-strength, observability, and a frontier-agentic orchestration recipe.

## #1 — Dependency cooldown (temporal supply-chain quarantine)  *(security, A)*
Refuse any dependency version published in the last ~24h, so a zero-hour
malicious publish (Shai-Hulud / s1ngularity class) is held until the community
yanks it. Net-new vs trivy/sonar/deepsource (which only catch *disclosed* CVEs).
Set in ALL package managers present, or it's bypassable:

```
npm config set min-release-age 1440      # ~/.npmrc (npm 11.17) — REAL key is min-release-age,
                                          #   NOT "minimum-release-age" (that's a silent no-op)
pnpm config set minimumReleaseAge 1440   # pnpm 10.33 (NOT default until v11)
# yarn here is Classic 1.22 — NO cooldown feature (that's Yarn Berry 4.x: npmMinimalAgeGate: "1d")
```
**Caveat (lower than feared):** for `@latest`/range installs (incl. the `npx -y` MCP
launches) npm just resolves to the newest version ≥1 day old — it does NOT fail.
Only an exact pin to a <1-day version is blocked; override with `--before` per-command.
**Status:** APPLIED — npm `min-release-age=1440` + pnpm `minimumReleaseAge=1440`,
both verified by read-back. (Node migration to 24 LTS was aborted — hung on
~250 live node.exe locks; Node 25.2.1 left intact + working, npm 11.17.0.)

## #2 — Mutation-score gate (StrykerJS + mutmut)  *(testing, B)*
Grades assertion STRENGTH (kills injected mutants), not coverage — the
reward-hack EvilGenie/test-tamper-guard structurally cannot detect (a suite can
hit 100% coverage and kill 0 mutants). Runs ALONGSIDE `.coverage-thresholds.json`.
- TS/jest: `npx stryker run` with `tools/mutation-gate/stryker.config.template.json`
  dropped in as `stryker.config.json` (StrykerJS — MIT; do NOT use Mutahunter, AGPL).
- Python: **cosmic-ray** (`uv tool install cosmic-ray`) — verified Windows-native.
  NOTE: the research recommended `mutmut`, but mutmut is **WSL-only** (no native
  Windows support, issue #397) — do NOT use it here; cosmic-ray is the replacement.
- Calibrate `break` ~50-60 on critical modules, raise gradually; use `incremental`
  + scope to changed files so it stays fast. `/hypo` PBT folded in as an optional
  manual Python invariant pass — not a standing gate.
**Status:** cosmic-ray installed (Windows-native); Stryker runs via npx (no install,
verified invocable on Node 25); template + guide ready to drop into any jest/TS project.

## #3 — Test-time-compute scaling: RTV + PDR  *(frontier-agentic, A, high)*
Recursive Tournament Voting (N parallel rollouts → distill → recursive pairwise
tournament, judge is a non-contestant) + Parallel-Distill-Refine (sequential
refine conditioned on distilled prior summaries). arXiv:2604.16529: Opus 4.5
SWE-bench 70.9→77.6, Terminal-Bench 46.9→59.1. Built as a Workflow
(`workflows/rtv-pdr.js` + `skills/rtv-pdr/`), gated behind the ESE escalation
gate (expensive — fire only on hard units), using CLAUDE_CODE_FORK_SUBAGENT.

## #4 — MCP config-layer scanner  *(security, B)*
Audits the ~48-server MCP config for tool-poisoning + rug-pulls (a server
silently changing its tool defs post-install) — a surface nothing else covers.
NOTE: the OSS `mcp-scan` (Invariant Labs) was **acquired/renamed by Snyk** →
`snyk-agent-scan`. Verified it runs **locally**, masks secret env values (`***`),
and consent-gates starting each server (no auth/cloud upload on default `scan`;
the `evo` cloud-push and `guard` always-on proxy are separate — avoid `guard`).
- On-demand audit: `snyk-agent-scan scan` (approve servers interactively) or
  `snyk-agent-scan scan --dangerously-run-mcp-servers --json` (unattended; will
  start servers — heavy, some need their backend running). Run monthly / on new
  MCP installs. Do NOT wire as a hook (avoids the gateguard anti-pattern).
**Status:** installed + verified local-safe; documented as on-demand.

## #5 — Claude Code OpenTelemetry traces (beta)  *(observability, B)*
Latency-resolved span tree across tool/permission/hook/subagent/Bash boundaries —
the forensic view for a stalled orchestration run. On-demand only (beta; native
batching can lose the tail on a kill — prefer the cc-trace hook for long Ralph
loops). Enabler: `tools/otel-traces/enable-otel-traces.ps1` (starts a local
Jaeger via Docker + prints the launch env). Keep `OTEL_LOG_TOOL_CONTENT` off.
**Status:** enable-script + doc ready; turn on when diagnosing a stall.

## Honest nulls
- **dx-velocity: nothing net-new** — the `claude agents` cross-session TUI is a
  habit, not a mechanism; already covered by /agent-monitor.
- **TraceFix** (TLA+ protocol repair) — rejected on fit: the orchestration is
  single-dispatch over independent units, not the lock/channel/shared-state
  topology TraceFix verifies.
- **SCFW** (Datadog supply-chain firewall) — dominated by #1 at one-flag cost.
  **zizmor** already installed (~/.cargo/bin, v1.23.1).