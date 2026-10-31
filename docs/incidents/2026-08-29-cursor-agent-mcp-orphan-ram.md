---
title: 2026-08-29-cursor-agent-mcp-orphan-ram
type: note
permalink: dqverify-repo-20261013/docs/incidents/2026-08-29-cursor-agent-mcp-orphan-ram
---

# Cursor Agent MCP process multiplication and orphan RAM incident

**Date:** 29.08.2026  
**Status:** root cause confirmed; immediate containment applied; automatic reap
intentionally disabled; old live sessions still require restart/closure  
**Secrets:** none recorded

## Executive finding

RAM pressure was not caused by one mysterious MCP invocation. Six concurrent
Cursor Agent sessions each loaded the global MCP configuration at session
startup. Four configured stdio MCPs each expanded through `cmd /c npx` into
multiple child processes. Two Cursor Agent roots had lost their parent process
and retained their complete MCP trees.

The recurrence chain was:

1. multiple local Cursor Agent sessions;
2. automatic per-session startup of configured stdio MCPs;
3. Windows parent exit without descendant lifecycle binding;
4. orphan root and MCP child survival;
5. repeated sessions multiplying the same process farms;
6. Resource Guard disabled and stale, so prior warnings produced no recovery.

## Initial measured state

- RAM: 31.63 GiB total, 30.45 GiB used, 1.18 GiB free.
- Commit: 65.52 GiB.
- Process count: approximately 670.
- Six Cursor Agent roots.
- Cursor Agent trees: approximately 5.9 GiB working set and 11.8 GiB private
  commit at peak measurement.
- Per-session configured stdio stacks:
  - Chrome DevTools
  - Context7
  - Firecrawl
  - Playwright
- Two parentless Cursor Agent roots: PIDs 57676 and 4596 at capture time.
- Windows Terminal: 7.58 GiB private commit.
- Edge tree: approximately 12.1 GiB private commit.
- WSL: approximately 5.73 GiB private commit; the `desktop-control-plane` kind
  node used approximately 1 GiB physical memory.
- Memory Compression: approximately 4.5 GiB working set. This was a symptom of
  pressure, not the originating allocator.
- `AC4BFSP` was absent.

## Controlled causal intervention

Before termination, both candidate roots were revalidated:

- exact Cursor Agent `node.exe` installation path;
- parent PID absent;
- CPU idle;
- metadata-only process-tree snapshot written.

Result:

- captured process-tree records: 36;
- total process-count reduction: 43;
- commit reduction: 1.579 GiB;
- no captured process survived;
- free physical RAM did not immediately rise because other live Cursor sessions
  continued allocating while Windows rebalanced compressed pages.

Snapshot:

`C:\Users\Prekzursil\.agents\secure-evidence\ram-incident-20260829T114336Z\snapshot.json`

## Transport history

Thirty backups plus the live config were parsed without exposing credentials.

| Date/state | Agent Mail | Basic Memory | Context7 | Firecrawl | Playwright | Chrome DevTools |
|---|---|---|---|---|---|---|
| First populated backup, 20.08 | HTTP | HTTP | stdio | stdio | stdio | stdio |
| 28.08 intermediate | HTTP | stdio then HTTP | stdio | stdio | stdio | stdio |
| 29.08 14:39 | HTTP | stdio HTTP-session proxy | stdio | stdio | stdio | stdio |
| Containment fix | HTTP | stdio HTTP-session proxy | **remote HTTP** | **remote HTTP** | stdio | stdio |

Context7, Firecrawl, Playwright, and Chrome DevTools did not spontaneously
change from HTTP in the retained history. The first two were canonical stdio
definitions imported from Codex configuration.

Basic Memory alone oscillated. Another active Cursor session implemented
`bm_cursor_http_session.py` and executed the Cursor merger at 14:39. The stated
reason was legitimate: Cursor retained a stale MCP session ID after the Basic
Memory HTTP daemon restarted. The proxy reinitializes the upstream HTTP MCP
session and does not bind/restart port 8765, but adds one small process per
Cursor session.

## Applied transport containment

Official endpoints were verified live:

- Context7 `https://mcp.context7.com/mcp`: 2 expected tools.
- Firecrawl `https://mcp.firecrawl.dev/v2/mcp`: 26 expected tools.

Canonical `agents.json` now uses those HTTPS transports with environment-backed
Bearer references. Cursor live config was regenerated and re-read from disk.

Registry defenses:

- `REMOTE_REQUIRED_SERVERS = {"context7", "firecrawl"}`;
- changing either name to stdio fails validation even if the policy tag is
  removed;
- HTTP entries cannot retain `command` or `args`;
- credential-bearing HTTP requires `https://`;
- `ctx7sk-` and `fc-` literal-key prefixes are rejected;
- no literal credential was written.

Verification:

- remote transport policy: 13 tests;
- MCP control-plane suite: 45 tests;
- combined final result: 58 passing;
- registry validator: `SUCCESS:mcp-control-plane-validate`.

Open Cursor Agent sessions retain their startup process trees. The reduction is
realized only after those sessions close/restart.

## Orphan guard outcome

A high-risk micro-guard was created and tested. It supports:

- exact Cursor Agent installation path;
- absent parent;
- minimum process age;
- three observations over at least 30 minutes;
- per-PID cumulative CPU and I/O stability across observations;
- membership-change reset;
- missing metric/time fail-closed;
- child creation-order validation;
- PID plus creation-time identity;
- immediate identity re-query before each exact PID kill;
- children-first exact `taskkill /PID /F`;
- no `/T` discovery and no kill-by-name;
- malformed-state fail-closed;
- metadata-only evidence.

PowerShell 5 tests include a real disposable sleeper process and pass.

Automatic reap is **not enabled**. Security review established that a task
running as the same interactive user cannot make its state/code fully
tamper-proof against every same-user agent without a separate privileged
execution boundary. The safe deployment is therefore:

- existing `Resource-Guard` Scheduled Task;
- least-privilege S4U principal;
- protected deployment copy and explicit paths;
- five-minute cadence;
- **report-only** orphan mode (`apply=0`);
- no automatic process termination.

Future confirmed orphans require the reviewed manual snapshot/kill/re-measure
procedure.

Latest protected log evidence:

- `ORPHAN-GUARD exit=0 apply=0`
- candidates 0
- `npx-cli.js` duplicates 30 from old still-open sessions

## Why the guard had not helped

Historical Resource Guard logs already showed:

- 14–30 duplicate `npx-cli.js` processes;
- 2.2–4.3 GiB MCP working set;
- free RAM as low as 1.6 GiB.

The task stopped after 26.08 because:

- Scheduled Task was disabled;
- deployed script differed from canonical;
- it only alerted and did not own safe orphan lifecycle handling.

The task-disable actor is not recoverable because Task Scheduler operational
history was unavailable.

## Independent corroboration

- Cursor documentation: configured MCP servers are automatically discovered by
  Agent CLI sessions and stdio entries spawn their configured commands:
  <https://cursor.com/docs/cli/mcp>
- Cursor issue #3786 reports MCP servers surviving Cursor close without a
  shutdown signal:
  <https://github.com/cursor/cursor/issues/3786>
- Cursor forum report describes accumulating MCP children across restarts:
  <https://forum.cursor.com/t/mcp-process-leak-orphaned-children-on-restart/156478>
- Windows requires explicit descendant lifecycle management; related Job Object
  analysis:
  <https://github.com/anthropics/claude-code/issues/57740>

## Remaining work

1. Close/restart old Cursor Agent sessions so the HTTP transport change takes
   effect.
2. Keep one local Cursor Agent process; use cloud workers only after explicit
   spend approval and scrubbed committed inputs.
3. Add a pre-launch one-agent guard without shadowing provider binaries.
4. Decide whether Playwright/Chrome DevTools should remain per-session stdio or
   move to reviewed shared/on-demand transport.
5. Reconcile Claude's still-stdio Context7/Firecrawl projection through the
   transactional control-plane plan; do not rewrite `.claude.json` ad hoc.
6. Preserve the Basic Memory session-refresh benefit while evaluating a shared
   singleton proxy only if it does not add an always-on service.
7. Investigate Windows Terminal, Edge, and the long-lived kind cluster
   separately; they are additional commit consumers, not MCP-orphan evidence.
8. Address C: pressure: protected Resource Guard measured 98% used with about
   15.5 GiB free.

## Completion classification

- `CONFIRMED`: process multiplication, per-session MCP stacks, two orphan roots,
  causal commit reduction, exact 14:39 Basic Memory writer, disabled/stale
  Resource Guard, Context7/Firecrawl remote capability.
- `CONTAINED`: two captured orphan trees removed; remote transport invariant
  installed; report-only Resource Guard enabled.
- `NOT COMPLETE`: old live sessions still retain old stacks; no hard
  one-local-agent launcher gate; no automatic orphan kill by deliberate safety
  decision.