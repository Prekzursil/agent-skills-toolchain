# Claude Science — WSL2 launcher/recovery tooling

[Claude Science](https://claude.com/product/claude-science) (Anthropic's life-science / compchem workbench, launched 2026-06-30) has **no native Windows build**. It installs into **WSL2 Ubuntu** as a CLI daemon that serves a web UI on `127.0.0.1:8000`, which you open in the Windows browser (WSL2 auto-forwards localhost). It is **not** an Electron/GUI app.

These scripts wrap the daemon lifecycle so it's one command from any Windows or WSL shell.

## One-command control (`cs`)

`cs.ps1` is the single front door — everything else is plumbing it drives. **401 on
`/` = alive** (auth gate); a **slow/timeout** response = **WEDGED** (WSL frozen,
usually host-RAM pressure), which `cs fix` recovers. It targets `127.0.0.1:8000`
only — **LOCAL scope**.

```powershell
pwsh -File .\cs.ps1 <verb>     # or /cs <verb> from Claude Code
```

| Verb | What it does |
|---|---|
| **`cs open`** | Ensure up (start-if-down / recover-if-wedged), **wait for readiness** (not a blind sleep), then open the UI. The human one-click. |
| **`cs ensure`** | Headless ensure-up for **tools/agents** → `SUCCESS:cs-up` / `FAILED:cs-down` (exit 0/1). Call before any `:8000` request. |
| **`cs status [-Json]`** | State + measured **latency** + a `wedged` flag + WSL daemon detail. `-Json` for machine parsing. |
| **`cs fix`** | Graceful force-recover: stop → clear stale locks → restart pinned. The wedge cure. (alias `cs recover`.) |
| **`cs stop`** | Stop the daemon. |
| **`cs backup`** | Online SQLite snapshot to `D:\Backups\claude-science` (key stored separately, last 7 kept). Safe while up. |
| **`cs restore <ts\|latest>`** | Roll back to a snapshot (keeps a pre-restore safety copy, drops stale WAL/SHM, restarts, verifies). |
| **`cs doctor`** | Full-stack **PASS/WARN/FAIL** report (see below). |

### `cs doctor` output

A read-only, one-shot report that operationalizes the 2026-07-07 audit into a
repeatable table. Each row is PASS `[+]` / WARN `[!]` / FAIL `[X]` / INFO `[i]`:

- **WSL reachable** — distro answers (a timeout ⇒ VM wedged).
- **CS daemon** — `state=HEALTHY|SLOW|DOWN http=… latency=…ms`; a SLOW state is flagged `*** WEDGED ***`.
- **daemon detail** — pid / version / uptime.
- **DB** — `operon-cli.db` integrity + `journal_mode` + size.
- **WSL disk free** — ext4 headroom (disk-full mid-WAL risks DB corruption).
- **Host RAM free** + top 3 consumers — the freeze root cause.
- **Watchdog registered** / **Watchdog instances** — catches the duplicate-watchdog race.
- **Watchdog heartbeat** — age of the heartbeat file; catches a silently-hung watchdog.
- **Backup freshness** — newest snapshot age.
- **Tab-death regfix** — Chrome/Edge discard-exception policy applied.

Ends with a `N FAIL, N WARN, N PASS` summary; any FAIL prints `→ try: cs fix then re-run: cs doctor`.

## Reliability hardening (2026-07-07)

Following a live reliability audit (the recurring pain was **"off/wedged when
needed"**, not crashes), the suite was hardened:

- **Latency-aware wedge detection** (`cs-lib.ps1`, shared by `cs`, `cs-doctor`, and both supervisors so the signal never drifts). The old "any HTTP response = alive" probe was blind to the ~164 s SQLite/RAM freeze; now a response `≥ 4 s` reads as **WEDGED** and triggers recovery.
- **Single-instance watchdog + heartbeat** (`cs-watchdog.ps1`). A `Global\` mutex kills the dual-watchdog race (two instances were recovering each other's daemon); a heartbeat file makes a **hung** watchdog distinguishable from a **healthy-quiet** one. Plus timeout-wrapped WSL calls, immediate ensure-up on start, a host-RAM WARN guard, log rotation, and a crash-loop breaker (backs off after 3 recoveries / 15 min).
- **Graceful recover, backup-first.** `cs fix` clears stale locks then restarts pinned; `cs-restore.sh` keeps a pre-restore safety copy and verifies before declaring success.
- **In-WSL self-heal** (`cs-supervisor.sh`) as defense-in-depth alongside the Windows watchdog — launched by `/etc/wsl.conf [boot] command=`, it ensures CS up the instant the VM boots (closing the logon/boot gap) then latency-probes and self-recovers with its own heartbeat. **No systemd** — deliberately, to avoid the systemd-resolved/DNS blast-radius on this distro.
- **Fast-ensure, not resident.** `cs open` / `cs ensure` are one-shot (ensure-then-exit); nothing heavyweight stays resident, so the daemon idles out and **RAM frees when idle** — the supervisors, not the ensure path, keep it alive.
- **`cs-restore` added** — the missing inverse of `cs-backup` (a backup you can't restore is false safety).
- **Consolidated setup** — `install.ps1` lays the `cs*` launchers on PATH (Windows + WSL), `register-tasks.ps1` wires the logon watchdog + weekly maintenance, plus the tab-death regfix and a `cs open` shortcut.

> **Out of scope (local-only):** `schrodinger-bridge.ps1` (stdio→HTTP bridge attempt for the Schrödinger MCP — kept but not recommended) and `cs-tailscale-serve.ps1` (remote/Tailscale exposure) are **not** part of the local one-click flow.

## Install (one-time, no sudo)

```bash
# in WSL2 Ubuntu — user-space, sha256-verified, installs to ~/.local/bin
curl -fsSL https://claude.ai/install-claude-science.sh | bash
```

Dependencies: `bwrap` (bubblewrap ≥0.8 — Ubuntu 24.04 ships 0.9.0) and `socat`. WSL `sudo` needs a password, so `socat` is installed **without sudo** by extracting it from the `.deb`:

```bash
apt-get download socat && dpkg-deb -x socat_*.deb /tmp/socat-x && cp /tmp/socat-x/usr/bin/socat ~/.local/bin/
```

`cs-install.sh` automates the install + verify.

## Low-level scripts (`cs` drives these)

Prefer the `cs` dispatcher above. These are the primitives it calls; run them
directly only for scripting or debugging (put `~/.local/bin` on PATH; the
`.ps1`/`.cmd` go in a Windows PATH dir):

| Command | What it does |
|---|---|
| **`cs-start`** | Gentle: starts the daemon **only if down**, never kills a running one, then opens the UI. |
| **`cs-recover`** | Force-restart: `pkill -9`, clears stale `daemon.sock`/`operon.lock`/`sbx-bind-src/sock-*`, restarts, reopens UI. Use when the daemon **wedges** (`cs fix` wraps this). |
| **`cs-watchdog.ps1`** | Windows-side supervisor (logon task) — the outer net that recovers an idled-out distro / hung daemon / post-reboot state. |
| **`cs-supervisor.sh`** | In-WSL self-heal (defense-in-depth) launched at VM boot. |
| **`cs-backup` / `cs-restore`** | Online SQLite snapshot to D: / rollback. |
| **`cs-maintain`** | Weekly offline SQLite maintenance (registered task, Sun 04:00). |
| **`register-tasks.ps1`** | Installs the logon watchdog + weekly maintenance (no admin; falls back to a Startup-folder launcher). |

`cs-start`/`cs-recover` each exist in three flavors so they work from PowerShell
(`.ps1`), cmd (`.cmd`), and WSL bash (the extension-less script). Install with
`install.ps1` (copies to `~\.local\bin` + `~/.local/bin`), then `register-tasks.ps1`
for always-on supervision.

## Why `cs-recover` exists (beta gotcha)

The daemon can wedge on **SQLite lock contention** (`operon-cli.db`; server log shows `[perf] db_lock_hold TxMutex 500–1000ms`). That leaves a stale `daemon.sock`/`operon.lock`, which makes a naive `stop`→`serve` **hang**. `cs-recover` clears the locks first. Verify reachability with `Test-NetConnection localhost 8000` (NOT `Get-NetTCPConnection`, which doesn't see mirrored WSL ports); a healthy daemon returns **HTTP 401** on `/` (auth gate).

## Freeing host RAM (the real wedge lever)

The wedge is a **host-RAM** problem, not a Claude Science bug: when free RAM drops, Windows
freezes the WSL2 VM and the daemon stalls mid-SQLite. The durable fix is giving the VM RAM
headroom. The heaviest neighbours, each with a **config-only** knob (no uninstall needed):

- **LM Studio** — idle models pin GB of RAM. Enable **Just-in-Time model loading** + **auto-unload
  after idle** (Settings; e.g. 10 min) so an unused model releases its RAM. Highest-yield lever.
- **Docker Desktop (WSL2 backend)** — caps *all* WSL memory via `%USERPROFILE%\.wslconfig`, then
  `wsl --shutdown` to apply:
  ```ini
  [wsl2]
  memory=8GB      # hard ceiling for the WSL VM; leaves headroom for Windows + Claude Science
  ```
- **BOINC** — raise **"suspend when memory in use > N%"** (Options → Computing preferences), or
  suspend it while using Claude Science, so it yields RAM under pressure.
- **A large Claude Code / agent fleet** — many concurrent sessions each hold MCP children; close
  idle sessions when the VM is starved.

`cs doctor`'s **Host RAM free** row names the current top-3 consumers, so you can see which
neighbour to lean on. After freeing RAM, `cs fix` clears the wedge.

## Extensibility notes

- **Hooks:** unsupported — Claude Science has no Claude-Code-style hook system.
- **Skills:** 60+ built-in scientific skills + save-your-own in-app (`custom_skills` table).
- **MCP connectors:** added in the **web UI only** (Customize → Connectors), **URL-only** transport (verified: `custom_mcp_servers` sqlite schema has no "local command" column). It bundles **25 built-in bio/chem MCP servers** (mcp_chemistry, mcp_zinc, mcp_chembl, mcp_structures_interactions, mcp_drug_regulatory, mcp_pubmed, mcp_variants, mcp_human_genetics, …) + 27 one-click remote connectors.
- **Local Windows stdio MCPs** (Schrödinger, RDKit, etc.) can't be reached by the WSL daemon directly — they must be exposed over HTTP (stdio→HTTP bridge, e.g. supergateway) and added by URL. `schrodinger-bridge.ps1` is a kept-but-not-recommended attempt (the Schrödinger MCP is built for Claude Code's harness, not a plain gateway; it also duplicates the working Claude Code MCP).

## NVIDIA BioNeMo NIM compute connector

In **Compute → Connect NVIDIA BioNeMo NIM**, choose **Remote** (a 6 GB laptop GPU can't run any useful NIM locally — Boltz-2 needs ≥48 GB VRAM) and paste the host:

```
https://health.api.nvidia.com
```

Auth with `NVIDIA_API_KEY` (nvapi-… from build.nvidia.com/settings/api-keys). **Not** `build.nvidia.com/...` (that's the catalog/portal) and **not** `integrate.api.nvidia.com` (that's the LLM-chat host — won't resolve `/biology/`). Best models for small-molecule↔GPCR docking: **Boltz-2** (`mit/boltz2`, structure+affinity), **DiffDock** (`mit/diffdock`, poses), **OpenFold3** (`openfold/openfold3`, complexes).

## Browser tab-death fix

If the `localhost:8000` tab is discarded when you switch tabs, that's Chrome **Memory Saver** / Edge **Sleeping Tabs**. Exempt Claude sites (HKCU policy, no admin):

- Chrome: `HKCU\SOFTWARE\Policies\Google\Chrome\TabDiscardingExceptions` = `claude.ai`, `[*.]claude.ai`, `localhost`, `127.0.0.1`
- Edge: `HKCU\SOFTWARE\Policies\Microsoft\Edge\SleepingTabsBlockedForUrls` = same list

(Separately, the Claude-in-Chrome **extension** side-panel dying on tab-switch **in Edge** is the unfixable upstream bug anthropics/claude-code#30873 — use Google Chrome for that.)
