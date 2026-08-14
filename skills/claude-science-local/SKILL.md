---
name: claude-science-local
description: Use to bring up, diagnose, or recover Anthropic's Claude Science local compchem / life-science workbench - a WSL2 daemon on 127.0.0.1:8000. Triggers - claude science, compchem or life-science workbench, :8000 down or unreachable, /claude-science, /cs, cs open, start claude science, open the science UI, science daemon wedged or off. Teaches the cs verbs (open, ensure, status, fix, doctor, backup, restore), why HTTP 401 means alive, the host-RAM SQLite wedge and that cs fix recovers it, and that NOT-CHECKED is not PASS. NOT for hosted or cloud compchem - scope is LOCAL only.
license: MIT
---

# Claude Science (local) — one-command control

> Anthropic's **Claude Science** compchem / life-science workbench has **no
> Windows build**. It runs as a **WSL2 Ubuntu daemon** serving a web UI on
> **`http://127.0.0.1:8000/`**. The `cs` dispatcher makes it always-on and
> one-command from any Windows shell. **LOCAL only** — no remote/Tailscale.

## When to use

- "Start / open Claude Science", "the science UI is down", "`:8000` won't load".
- Before another tool or agent calls `:8000` — run `cs ensure` first.
- The daemon is **wedged** (up but slow/timing out) or **off when needed**.
- You need a health readout, a recover, or a backup/restore of the science DB.

## Two facts that flip every diagnosis

1. **HTTP 401 on `/` = ALIVE.** `:8000` is behind an auth gate; a 401 (even a
   403) means the daemon is answering. Do **not** read 401 as "down".
2. **Slow / timeout = WEDGED, not down.** The daemon accepts the socket but
   answers slowly or never. Root cause: the WSL VM is frozen under **host-RAM
   pressure**, which stalls the SQLite `operon-cli.db` (lock contention — seen up
   to a 164 s `TxMutex` hold). A naive "any HTTP response = healthy" probe is
   blind to this. `cs` is **latency-aware**: a response `>= 4 s` reads as
   **WEDGED**, and `cs fix` recovers it.

## The `cs` verbs (run from PowerShell)

```
cs <verb>                                  # the shim on PATH
pwsh -File ~/.local/bin/cs.ps1 <verb>      # the same installed dispatcher, explicitly
```

Slash command: **`/claude-science <verb>`** (canonical) or **`/cs <verb>`** (short alias — the
rename kept it working; see `commands/claude-science.md` and `commands/cs.md`).

**Always the INSTALLED copy, never a source checkout.** Both slash commands used to name
`~/source/agent-skills-toolchain/scripts/claude-science/cs.ps1`, and that tree had drifted to a
detached HEAD holding the pre-fix tool — so `/claude-science doctor` ran an 11-row report with no
fail-closed states while `cs doctor` ran the 13-row one, on the same box, in the same minute.
`cs doctor`'s **Slash-command route** row now hashes whatever dispatcher the command files name and
fails unless it is byte-identical to the running code.

| Verb | What it does |
|---|---|
| **`cs open`** | Ensure up (start-if-down / recover-if-wedged), **wait for readiness** (not a blind sleep), then open the UI in the browser. The human one-click. |
| **`cs ensure`** | Headless ensure-up for **tools/agents** — emits `SUCCESS:cs-up` / `FAILED:cs-down` (exit 0/1). **Call this before any `:8000` request.** |
| **`cs status [-Json]`** | State + measured **latency** + a `wedged` flag (+ WSL daemon detail). `-Json` for machine parsing. |
| **`cs fix`** | Graceful force-recover: stop → clear stale locks (`daemon.sock`/`operon.lock`/`sbx-*`) → restart pinned. The wedge cure. (alias: `cs recover`.) |
| **`cs stop`** | Stop the daemon. |
| **`cs backup`** | Online SQLite snapshot to `D:\Backups\claude-science` (key stored separately; keeps last 7). Safe while the daemon is up. |
| **`cs restore <ts\|latest>`** | Roll back to a snapshot (keeps a pre-restore safety copy, drops stale WAL/SHM, restarts, verifies). |
| **`cs doctor`** | Full-stack **PASS/WARN/FAIL** report — the go-to when something is off. |

## Standard flow

- **Human wants the UI:** `cs open`. Done.
- **A tool/agent needs `:8000`:** `cs ensure`; proceed only on `SUCCESS:cs-up`.
- **"It's off / slow when I need it":** `cs status`. If `*** WEDGED ***` or DOWN →
  `cs fix` → re-`cs status`. If it won't come back → `cs doctor`.

## `cs doctor` — what it checks

A read-only report that operationalizes the reliability audit. Rows (each
PASS/WARN/FAIL/**NOT-CHECKED**/INFO): **WSL reachable** · **CS daemon** (state + latency,
flags `*** WEDGED ***`) · **daemon detail** (pid/version/uptime) · **DB** (integrity +
`journal_mode` + size) · **WSL disk free** · **Host RAM free** + top consumers
(the freeze root cause) · **Watchdog registered** · **Watchdog action path**
(does the task launch a script that exists, is durable, and matches this deploy? it was
launching out of a disposable git worktree) · **Watchdog re-launch trigger**
(a logon-only trigger cannot restart a watchdog that exited — that is how it stayed
dead for 3.3 days) · **Watchdog instances** (catches the duplicate-watchdog race) ·
**Watchdog heartbeat** · **Backup freshness** · **Backup restorable** (copies the newest
snapshot to a temp dir and integrity-checks the **copy**, so the backup root is never written) ·
**Slash-command route** (do `/claude-science` and `/cs` actually run this code?) ·
**PowerShell host** · **Tab-death regfix**. Ends with a `N FAIL, N WARN, N NOT-CHECKED, N PASS` summary and
**exits non-zero on FAIL or NOT-CHECKED**, so other tooling can gate on it.

### `NOT-CHECKED` is not `PASS` — read this row honestly

A health check that cannot reach its input **fails closed**. It was not always so: the DB row
used to print `WARN "sqlite3 or operon-cli.db not found"` when the real cause was a probe
timeout — a factual claim about a file it never looked at — while `Backup freshness` rendered
`PASS` green over the same unreachable VM. Now a timed-out or empty probe renders
`NOT-CHECKED` and says only that, a genuinely absent input renders `FAIL`, and the summary
counts NOT-CHECKED separately so `0 FAIL, 0 WARN` can no longer hide unmeasured rows.

Two heartbeat subtleties worth knowing, both measured:
- **A stale heartbeat alone does not mean the watchdog hung.** Under host-RAM pressure the
  watchdog *process* is descheduled and a single probe took 66 s against a nominal 8 s socket
  cap, so a healthy watchdog measuring a wedge looked hung. The row now AND-gates the stale
  beat against process liveness: stale + no process = FAIL, stale + live process = WARN.
- **The instance count used to count the probe itself.** Anything whose command line contained
  `cs-watchdog` matched, so asking the question could manufacture the "DUPLICATE" answer.

Two more, added 2026-08-12 after a verifier found the same defect class still live here:
- **A registered task is not a working task.** `Watchdog registered`, `re-launch trigger` and
  `instances` all read PASS while the action launched `cs-watchdog.ps1` out of a *linked git
  worktree* that a `git worktree remove` deletes — and Task Scheduler reports a missing
  `-File` target as a task that ran. If you ever register this by hand, point it at
  `~/.local/bin/cs-watchdog.ps1`, never at a checkout.
- **Run the doctor under `pwsh`, not Windows PowerShell 5.1.** 5.1 mangles native arguments
  containing embedded double quotes, so the quoted `sqlite3 -readonly "file:…"` inside the
  DB and backup probes reaches bash truncated and those rows go NOT-CHECKED. Measured on one
  box minutes apart: 5.1 `0 FAIL, 2 WARN, 4 NOT-CHECKED, 8 PASS` against pwsh `0 FAIL, 1 WARN,
  0 NOT-CHECKED, 13 PASS`. The `.cmd` shims now prefer `pwsh`; the **PowerShell host** row
  tells you when the 5.1 fallback fired. NOT-CHECKED here is the contract working, not a
  broken box — but it is also not a measurement.

### A run marked `[INJECTED]` is a SIMULATION, never health evidence

The harness below reaches the broken state through a `CS_FORCE_*` env seam. That seam once
obeyed those variables unarmed and unmarked, so `CS_FORCE_WSL_DB='ok|wal|999M'` produced a
fabricated `[+] DB PASS integrity=ok journal=wal size=999M`, `0 FAIL … 12 PASS`, exit 0 — a
health tool that could be ordered to print a green. Now: the seam is inert unless
`CS_FAULT_INJECTION=1` arms it; a `CS_FORCE_*` set without arming is **refused and reported**;
and an armed run gets a `Fault injection` **FAIL** row plus an `[INJECTED]` tag on every affected
detail, so it can never read clean and never exits 0. **Never quote a `[SIMULATED …]` run.**

Verify all of the above with the shipped both-states harness — it stubs every WSL probe, so it
is hermetic and safe to run *while* the box is wedged:

```
pwsh -NoProfile -File ~/.local/bin/test-cs-doctor-failclosed.ps1
```

One property it deliberately does **not** cover, because it needs the real filesystem: that the
doctor does not write into the backup root. That has its own probe, which snapshots every entry
in `D:\Backups\claude-science` around a doctor run —

```
python ~/.local/bin/test-cs-backup-readonly.py check ~/.local/bin/cs-doctor.ps1
```

Both of those measure **this box**. The third check measures the **wiring** — that the slash
command still routes to the installed dispatcher, that everything the docs tell you to run is
actually in `install.ps1`'s deploy list, that the config seam has no bypass, that `csmon` is still
registered. It is pure repo inspection (no WSL, no daemon, no scheduled task), so unlike the two
above it runs in **CI on every pull request** and is the only one of the three that cannot be
forgotten:

```
python scripts/claude-science/cs_wiring_check.py
```

Ten invariants, each with a paired mutation in `ci/tests/test_cs_wiring.py` that cuts exactly that
wire and asserts the gate goes red — run `python -m pytest ci/tests/test_cs_wiring.py -q` to watch
both directions. It exists because this toolset's recurring defect is not a bug in the code, it is
a reference left pointing at a stale, disposable or absent tree: the slash command ran a
detached-HEAD checkout, the watchdog was registered against a git worktree, `cs-deploy.sh`
installed from that same stale tree, and the read-only probe two paragraphs above was documented
for weeks while `install.ps1` never deployed it.

## Gotchas

- **Wedge ≠ crash.** The daemon rarely crashes; the usual failure is the RAM/
  SQLite **wedge**. If `:8000` is slow, don't restart WSL blindly — `cs fix`
  clears the locks and restarts cleanly.
- **Host-RAM pressure is the trigger.** If `cs doctor` shows low host RAM, the
  heavy neighbours (BOINC / LM Studio / Docker / a Claude fleet) are starving the
  VM. Free RAM, then `cs fix`.
- **A backup you can't restore is false safety.** `cs backup` and `cs restore`
  are matched — take a `cs backup` before risky changes; `cs restore latest`
  rolls back. `cs backup` now integrity-checks the snapshot it just wrote and exits
  non-zero if it does not open, and `cs doctor` has a **Backup restorable** row that opens
  the newest one rather than merely confirming a file exists.
- **One config file, env-overridable.** Port, distro, backup roots, wedge threshold, health
  floors and the freshness thresholds all live in `scripts/claude-science/cs.conf`. Both halves
  read it — `cs-lib.ps1` for PowerShell, `cs-lib.sh` for the shell scripts — and an environment
  variable of the same name overrides the file, so `$env:CS_PORT = 8123` needs no edit. The
  backup root is stored once in WSL form (`/mnt/d/...`); the Windows form is derived.
- **Scope is LOCAL.** Remote access / Tailscale (`cs-tailscale-serve.ps1`) is out
  of scope here — `cs` targets `127.0.0.1:8000` only.

## Adding data sources (brief)

MCP connectors are added **in the web UI only** (Customize → Connectors),
**URL/HTTP transport only** — the WSL daemon can't reach Windows stdio MCPs
directly. For the NVIDIA BioNeMo NIM compute connector and the full lifecycle
details, see `scripts/claude-science/README.md`.
