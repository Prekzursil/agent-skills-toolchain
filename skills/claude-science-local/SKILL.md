---
name: claude-science-local
description: Use to bring up, diagnose, or recover Anthropic's Claude Science local compchem / life-science workbench - a WSL2 daemon on 127.0.0.1:8000. Triggers - claude science, compchem or life-science workbench, :8000 down or unreachable, /claude-science, cs open, start claude science, open the science UI, science daemon wedged or off. Teaches the cs verbs (open, ensure, status, fix, doctor, backup, restore), why HTTP 401 means alive, the host-RAM SQLite wedge and that cs fix recovers it, and that NOT-CHECKED is not PASS. Also covers the env-build failure chart (missing socat egress proxy, logged-out daemon, wrong-account), the paste-code re-auth flow, and the GLM model bridge (cs-model glm/anthropic via the two-plane router). NOT for hosted or cloud compchem - scope is LOCAL only.
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

Slash command: **`/claude-science <verb>`** (see `commands/claude-science.md`).

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
**Slash-command route** (does `/claude-science` actually run this code?) ·
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

## Environment-build failures ("Couldn't reach the package server") — the full chart

Measured 2026-09-20; all three failure layers are INDEPENDENT and each hides the
next. Do not trust the UI's "check your internet" message — it is generic.

1. **Missing `socat` in the distro (the real killer).** Every env build spawns a
   sandbox egress proxy — literally `LD_PRELOAD=…/undumpable.so socat
   TCP-LISTEN:3128,fork,reuseaddr UNIX-CONNECT:…/sbx-bind-src/…/http.sock` — and
   micromamba downloads route through `localhost:3128`. No socat → the proxy
   exits **127** → every download fails "via localhost" in 0-20 ms, which the UI
   renders as a network outage. Probe: `wsl -- grep -a "Exit 127"
   ~/.claude-science/logs/server-*.log`. Fix: install socat. If `dpkg` is wedged
   (broken `install-info` postinst, same exit-127 class), bypass it:
   `apt-get download socat && dpkg-deb -x socat_*.deb /tmp/x && cp /tmp/x/usr/bin/socat /usr/local/bin/`
   — and also copy to `/usr/bin` (the sandbox spawns with a minimal PATH).
2. **Daemon logged out.** Env specs/registry credentials come from the ACCOUNT
   session (`claudeAiFetch`); logged-out = empty `~/.claude-science/conda/_netrc`
   and builds fail with the same "package server" text. Probe: the log floods
   `claudeAiFetch: 401 and refresh failed`. See the sign-in procedure below.
3. **Wrong account.** The Max subscription lives on
   **prekzursil1993@gmail.com** (`has_claude_max: true` — verify via
   `api.anthropic.com/api/oauth/profile` with the local Claude Code token).
   mariusvisalon70@gmail.com has **no** subscription; the OAuth authorize step
   rejects it with "requires a Pro or Max subscription". The UI's cached
   "Max 20x" badge survives logout and lies.

**Re-auth is the paste-code flow, and it is scriptable end-to-end**: `claude-science url`
mints a nonce → open it in the browser (the agent-persistent Playwright profile holds
the Google session; account chooser → "Andrei Visalon prekzursil1993") → the daemon
login page → "Paste code instead" → the authorize link auto-consents → copy the code
→ paste → Continue. Redirect sign-in is REFUSED by the daemon ("cannot trust the
localhost spelling"). A daemon restart DROPS the UI session — re-mint and re-login.

## The GLM model bridge (`cs-model`) — and why v1 failed

`cs-model glm` routes the daemon's **model calls** to the Z.AI GLM coding plan;
`cs-model anthropic` reverts to native Anthropic (stops the router, removes the
env). Restart with `cs fix` after either. State: `cs-model status`.

- **A blunt `ANTHROPIC_BASE_URL=https://api.z.ai/...` CANNOT work** (v1,
  measured): the daemon is not Claude Code — its session/OAuth validation, MCP
  directory fetch and token refresh all ride the same SDK base URL, and they die
  at z.ai ("claude.ai session expired … could not be refreshed"). Do not retry it.
- **v2 is a two-plane local router** (`cs_glm_router.py`, `:8231`):
  `/v1/messages*` → z.ai's **Anthropic-compat** endpoint
  (`https://api.z.ai/api/anthropic/v1/messages` — NOT the OpenAI-style
  `/api/coding/paas/v4` path), with claude-* model names mapped to `glm-4.6` and
  auth swapped to the probe-selected plan key; **everything else passes through
  to api.anthropic.com untouched**, so the session plane keeps working.
- The env file `~/.claude-science/daemon-env` must be **`export`-prefixed** — it
  is sourced by `~/.profile` AND by the patched `cs-start`/`cs-recover` before
  `claude-science serve`; without `export` the vars stay shell-local and never
  reach the daemon child. WSLENV bridges the ZAI keys into WSL
  (`ZAI_API_KEY_prekzursil1993/u:ZAI_API_KEY_realprekzursil/u`, user scope).
- **Verify the bridge end-to-end, not by env vars**: send a chat message in the
  UI and check `~/.claude-science/logs/glm-router.log` for
  `[router] POST /v1/messages -> 200 (glm)` — the UI reply text alone is NOT
  sufficient proof (your own prompt echoes the sentinel; count occurrences and
  check for a standalone reply "just now").
- Router lifecycle: `cs-model glm` starts it (nohup, log at
  `~/.claude-science/logs/glm-router.log`); `cs-model anthropic` kills it. If a
  stale router holds `:8231`, `cs-model status` shows the pid. `pkill -f
  cs_glm_router` self-matches your own shell — use `cs_glm_rout[e]r`.
- The bridge is what makes the app usable during a Max weekly-limit window —
  model calls ride the GLM plan while the quota resets.

## Adding data sources

Two routes, and the choice is forced by a server-side rule (measured 2026-09-20):

- **Remote URL connectors are https-only.** `POST /api/mcp-servers` rejects any
  `http://` URL ("must be reachable at a public https URL"), so a localhost
  HTTP MCP server (e.g. a FastMCP on `127.0.0.1:7870`) CANNOT be registered as
  a remote connector. Do not fight this — use the local route.
- **Local stdio connectors are the way to wire a same-machine MCP server.**
  Register from the logged-in UI page (browser-rail evaluate) with
  `POST /api/mcp-servers/local {name, command, args[], env, description}`,
  session-cookie auth **plus an `x-operon-csrf` header echoing the decoded
  `operon_csrf` cookie** (on `csrf_stale` hit `GET /csrf` first). Registrations
  persist in `~/.claude-science/mcp/local-mcp.json`.
- The daemon spawns local servers **inside its MCP sandbox**, which (a) hides
  `/home` unless you grant `~/.claude-science/config.toml`
  `[sandbox] user_read_paths = [...]` (+ `cs fix` restart), (b) **remaps HOME**
  to `~/.claude-science/orgs/<org>/workspaces/_mcp-<name>` — the server code
  must anchor paths to `__file__`, never `Path.home()` — and (c) routes egress
  through a SOCKS proxy (`pip install socksio` into the server env; FastMCP
  needs `show_banner=False`, its banner crashes there). Verify with
  `GET /api/mcp-servers/connectors` → `health.ok` + `connectionStatus`.
  Full worked example (Biomni): memory note `cs-local-stdio-connector-2026-09-20`.

For the NVIDIA BioNeMo NIM compute connector and the full lifecycle details, see
`scripts/claude-science/README.md`.
