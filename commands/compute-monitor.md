---
description: Served-generic monitor for ANY long computation. Shells to the mon dispatcher - list, watch, once, raw, logs, info - routed to the generic renderer scw_monitor.ps1. Read-only.
---

# compute-monitor — served-generic monitor for any long computation

One lean front door (`mon.ps1`) that points the generic renderer
(`scw_monitor.ps1`) at any registered computation: GPU/HPC jobs, MD/QM/FEP,
long sweeps — anything that emits the monitor protocol OR exposes discovery
signals. **No daemon** — nothing runs unless invoked. **READ-ONLY** w.r.t. the
computation (never kills/signals a process, never writes a compute dir).

## Usage

```
/compute-monitor [list | <id> | <id> once | <id> raw | <id> logs [-n N] | <id> info]
```

- `list` — monitorable computations (local registry + best-effort box descriptors). **Default when no argument.**
- `<id>` — live self-refreshing dashboard in a new window (add `-Inline` to run in this shell).
- `<id> once` — render ONE frame inline. **Use this for an agent/hook status check** (captured, non-blocking).
- `<id> raw` — dump the raw `key=value` protocol sample (a monitorcore `ComputeSource` sample) — parse `DONE=`, `OK_*=`, `JOB=…,<state>`.
- `<id> logs [-n N]` — tail the resolved compute driver log(s).
- `<id> info` — resolve + reachability + which collector tier is active (dry run; add `-Json`).

$ARGUMENTS

## What to Do

Shell to the dispatcher, passing `$ARGUMENTS` through verbatim (verb/id + any
sub-verb and flags). If `$ARGUMENTS` is empty, default to `list`:

```
pwsh -NoProfile -File C:/Users/Prekzursil/.biomni-mcp/mon.ps1 $ARGUMENTS
```

Then relay the dispatcher's output:

- **`list` / `info`** — surface the registered ids and, for `info`, the **active
  tier** (a `legacy`/`fallback` tier means the picture comes from a pre-fix
  collector; a `v2` tier means auto-discovery) and whether the box is reachable.
- **`once`** — this is a full rendered frame; report the headline (GPUs, per-job
  states, `n/total done`). Do **not** treat "All work terminal" as truth if the
  GPUs are still busy or the active tier is a legacy fallback — say so.
- **`raw`** — for programmatic checks, parse the protocol: a run is complete only
  when `DONE=n,total` has `n>=total`, no `JOB` is `running/pending`, and the
  `OK_*=1` sentinel is present (its absence = source not responding, **not**
  done).
- **`<id>` (watch)** — the Bash call returns immediately after opening a live
  window; tell the user the window is up (a terminal dashboard can't render in
  chat).

## Making YOUR computation monitorable

Register it in `mon_targets.json` (local) or drop `/root/.monitor.d/<id>.json`
(box, Tier-0 descriptor — see `mon.descriptor.schema.json`). A computation is
monitorable iff it exposes: (1) a **live enumeration** of its work units (a
process pattern or descriptor — never a static list), (2) a **countable
completion artifact** per unit, and optionally (3) a **log path**. Full contract:
`C:/Users/Prekzursil/.biomni-mcp/MON_CONTRACT.md`.

## Notes

- **Forward-compatible with `monitorcore`.** The `key=value` protocol is its
  `ComputeSource` wire format; the descriptor is its config; `mon <id>` is the
  local invocation of what monitorcore will later route. This command does not
  build monitorcore — it makes the compute lane speak the protocol.
- **Terminal dashboard**, not chat-renderable: `<id>` opens a new PowerShell
  window; `once`/`raw`/`logs`/`info` print inline (captured).

## Related

- Contract + protocol spec: `C:/Users/Prekzursil/.biomni-mcp/MON_CONTRACT.md`
- Tier-0 descriptor schema: `C:/Users/Prekzursil/.biomni-mcp/mon.descriptor.schema.json`
- Renderer (canonical, generic): `scw_monitor.ps1`
- Unattended snapshot (Layer C, optional): `mon_snapshot.ps1`
