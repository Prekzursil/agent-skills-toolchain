---
title: README
type: note
permalink: dqverify-repo-20261013/tools/mcp/mcp-host-supervisor/readme
---

# mcp-host-supervisor — always-on launcher for the shared MCP hosts

Keeps exactly ONE `mcp_http_host.py` per enabled server alive on its loopback port, so every
Claude Code / Codex session dials the same shared instance instead of spawning its own stdio
child. Companion to `../mcp-http-host/` (PR #159, the host itself) and to
`docs/mcp-consolidation-plan.md` (which server to migrate, in what order, and why).

## Why a supervisor and not just the host

Measured on this box 2026-07-24: `basic-memory` and `rdkit-mcp-server` are **already**
shared-HTTP services — and each was running in **duplicate**, costing 599 MB of commit
between them. A shared endpoint without supervision double-launches. The health gate here
adopts a healthy endpoint rather than binding over it.

## What it adds over `MCPAgentMailSupervisor`

That supervisor is the proven pattern (named mutex, health gate, backoff, rotating log,
logon Scheduled Task) and this mirrors it. Grepping it for `orphan|reap|TotalProcessorTime`
returns nothing, so two things are added:

**CPU-progress wedge detection (AND-gate).** Its own comment records the failure a
single-signal recycle causes: a 90 s grace *"killed near-ready children 2-60s before they
bound → a non-converging crash loop"*. A kill here needs three agreeing signals — unhealthy
**AND** CPU flat **AND** `requests_served` flat. Unhealthy-but-still-burning-CPU is `BUSY`,
and is left alone.

**Ownership-scoped orphan reaping.** A machine-wide pattern reap once killed sibling
sessions' MCP children. A process is killed only if it is our untracked leftover or its
parent is gone; a process parented by another live process always survives.

## Layout

| file | purpose |
|---|---|
| `fleet.py` | ALL decision logic — manifest validation, wedge verdict, orphan selection — plus a JSON CLI. 100% covered by 48 tests. |
| `mcp_host_supervisor.ps1` | the actuator. Shells to `fleet.py` for every decision. |
| `install_task.ps1` | registers/removes the `MCPHostSupervisor` logon task (backs up any prior registration). |
| `fleet.example.json` | manifest template — every entry ships `"enabled": false`. |
| `tests/` | 48 tests; 5 mutation probes prove they catch the weakened safety rules. |

## Verdicts

| verdict | condition | action |
|---|---|---|
| `HEALTHY` | health probe answered | — |
| `STARTING` | inside the startup grace (default 240 s) | never kill |
| `DEGRADED` | unhealthy, streak < 3, or no previous sample | wait |
| `BUSY` | unhealthy but CPU or requests advancing | wait |
| `WEDGED` | unhealthy **and** CPU flat **and** requests flat | recycle |

## Guardrails

* Ports **8765** (basic-memory) and **8812** (agent-mail) are rejected — they are live.
* Non-loopback binds are rejected.
* A duplicate port or name in the manifest is a hard error; the supervisor starts nothing.
* An empty reap signature raises rather than matching every process.
* `-DryRun` reports every start/kill without doing it.
* Never touches `~/.claude.json`. Registration is apply-when-closed via
  `../mcp-http-host/apply_registration.py`.

## Usage

```powershell
Copy-Item fleet.example.json fleet.json      # then enable ONE server
C:/Python314/python.exe fleet.py validate --manifest fleet.json
./mcp_host_supervisor.ps1 -Manifest fleet.json -Once -DryRun
./install_task.ps1
Start-ScheduledTask -TaskName MCPHostSupervisor

./install_task.ps1 -Uninstall                # full removal
./mcp_host_supervisor.ps1 -StopExisting      # stop hosts, keep the task
```

## CLI (what PowerShell calls)

```bash
python fleet.py validate --manifest fleet.json   # exit 1 + errors if unsafe
python fleet.py plan     --manifest fleet.json   # enabled servers + health URLs
python fleet.py verdict  --state  state.json     # HEALTHY|STARTING|DEGRADED|BUSY|WEDGED
python fleet.py orphans  --input  procs.json     # pids safe to reap
```

All four read **UTF-8 with or without a BOM**: the supervisor runs under `powershell.exe`
(Windows PowerShell 5.1), whose `Set-Content -Encoding utf8` emits a BOM that plain
`json.load` rejects. That broke the reap step end-to-end before it was fixed; a regression
test pins it.

## Dev

```bash
python -m pytest tests/ --cov=fleet --cov-report=term-missing   # 48 passed, 100%
python tests/mutation_probe.py fleet.py                        # both-states proof
uvx ruff@0.15.17 format --check . && uvx ruff@0.15.17 check .   # CI-pinned gate
```

## Dependency

Launches `../mcp-http-host/mcp_http_host.py`, which lands with **PR #159**. Until that
merges, validation / planning / reaping / dry-run all work; starting a real host does not.