---
title: codex-monitor-reconcile
type: note
permalink: dqverify-repo-20261013/guides/codex-monitor-reconcile
---

# Codex Monitor Reconcile — the ONE way to watch both rails live

> **Definitory rule:** *To watch a Codex run live, register the run's `codex exec --json` JSONL with
> `run-taskwatch_monitor` for a single detached run, or use the `workflow-monitor` Codex lane to watch
> the whole fan-out (Claude + Codex) in one read-only cockpit. There is no third tool and no
> hand-rolled tailer.*

Codex reaches the model two ways — a **detached `codex exec`** process and an in-session
**`mcp__codex__codex`** call ([`codex-invocation.md`](codex-invocation.md) §1). Historically each had
its own ad-hoc tail. This doc reconciles them onto **one event stream and two existing monitors** —
no new monitor tool is built. Grounded on `codex-cli 0.144.1` (`codex exec --json` verified).

---

## 1. The single load-bearing fact: one event stream

Both rails emit the **same** structured event stream when run with `--json`:

```
codex exec --json …    → prints session/startup + turn events to stdout as JSONL
```

`--json` is verified present on `codex-cli 0.144.1`. The startup/session-configured events carry the
loaded MCP-server + tool inventory and the session id; turn events carry token/tool activity and the
final result. **This is the same shape the scope proof parses** ([`codex-invocation.md`](codex-invocation.md)
§3) — one shape, pinned once by a **shared fixture test**. If codex changes the event schema, that
fixture fails loudly rather than a monitor silently mis-parsing a stale shape.

Because both rails resolve to this one stream, watching them is not two problems — it is one stream
read by two surfaces sized to the job.

---

## 2. Watch a detached `codex exec` run → `run-taskwatch_monitor`

Use this when you launched (or the invoke skill launched) a **single** long-running `codex exec` in the
background and want an honest, BLIND-aware status with p50/p90 ETA and no fabricated percentage.

**Wire it (no new monitor — register the JSONL as a generic logfile):**

```powershell
# 1. Launch detached, teeing the JSONL event stream to a log (the invoke skill does this via longrun).
#    -o records the last-message path; the JSONL is the live progress surface.
codex exec --json -o "$out\last.txt" "…prompt…"  > "$log\codex-<id>.jsonl" 2>&1   # detached / longrun

# 2. Register that log with taskwatch — the generic-logfile adapter handles any N/M or NN% stream.
taskwatch register generic-logfile codex-<id> --config path="$log\codex-<id>.jsonl"

# 3. Status in chat (JSON — the live TUI cannot render inside chat):
taskwatch status --json
# …or the live terminal cockpit in its own window / current console:
.\launch.ps1 -Inline
```

**Why taskwatch and not a tail:** it is BLIND-aware (a poll error holds the last verdict with an age
stamp, never relabels it `DONE`), it never fabricates a percentage when the total is unknown (`--%` +
elapsed/rate instead), and it reads whole records (monotonic `seq`, no tail-undercount after log
rolloff). These are exactly the failure modes a naive `Get-Content -Wait` hides.

**Recovery ties in:** the invoke error contract records the session id + `-o` path; on a fast-exit or
`CODEX_HOME`-drift, `codex-runtime-recovery` re-reads the same JSONL and `codex resume`s — the monitor
and the recovery path read one artifact.

---

## 3. Watch an in-session `mcp__codex__codex` call → `workflow-monitor` Codex lane

Use this when Codex is running as an **in-session MCP call** (a `mcp__codex__codex` /
`mcp__codex__codex-reply` thread), typically fanned out from a Claude Workflow — and you want one board
across the whole fleet rather than a per-thread tail.

`workflow-monitor` already renders Claude Workflow fan-outs from the live-flushed telemetry manifest.
The reconciliation **extends** it with a **Codex source adapter** in `workflow_run.py`: an O(changed)
poller that reads the `codex exec --json` rollout/startup events and folds each Codex thread into the
same **run → phase → agent** tree beside the Claude agents. One read-only cockpit, both vendors, one
key set (`q` quit · `f` follow · `r` refresh). It never writes any `.claude` file.

The Codex event shape it consumes is pinned by the **same shared fixture** as §1 and the scope proof —
so all three consumers (monitor lane, scope proof, taskwatch) stay in lockstep across codex releases,
and a schema change surfaces as a loud fixture failure in one place.

---

## 4. Disambiguation — three names, three scopes

| Tool | Scope | When |
|---|---|---|
| **`run-taskwatch_monitor`** | ONE detached `codex exec` run | You launched a single background exec and want honest ETA/status |
| **`workflow-monitor`** (Codex lane) | the WHOLE fan-out, both vendors | Watching a Workflow that mixes Claude agents and `mcp__codex__codex` threads |
| **`/codex-monitor`** | Codex-thread dashboard | A quick standalone view of Codex threads (counterpart to `/agent-monitor`) |

Rule of thumb: **one run → taskwatch; a fleet → workflow-monitor; a quick Codex-only glance →
`/codex-monitor`.** All three are read-only; none fabricates progress; all read the one `--json` stream.

---

## 5. What is NOT the way (anti-patterns)

- **A hand-rolled `Get-Content -Wait` / `tail -f` on the JSONL.** No BLIND-awareness, fabricates or
  omits progress, undercounts after rolloff. Register with taskwatch instead.
- **Polling `mcp__codex__codex` by re-calling it.** The MCP rail is in-session and single-shot per
  call; you watch it via the event stream in `workflow-monitor`, not by re-invoking the tool.
- **A second bespoke monitor.** The reconciliation is explicitly *no new tool* — one event stream, two
  existing monitors (taskwatch for one run, workflow-monitor for the fleet), one shared fixture.
- **Expecting a live TUI inside chat.** Both cockpits are terminal surfaces. In chat, use
  `taskwatch status --json` or the workflow-monitor plain-text one-shot board (`workflow_run.py`).

---

## 6. Summary — the ONE way, both rails

1. Every Codex run, both rails, emits the **same `codex exec --json` JSONL** — one shape, one shared
   fixture.
2. **One detached exec run** → `run-taskwatch_monitor` (`taskwatch register generic-logfile …`).
3. **In-session `mcp__codex__codex` / the whole fan-out** → the `workflow-monitor` Codex lane.
4. No new monitor, no hand-rolled tailer, no fabricated percentages, no chat-rendered TUI.