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
