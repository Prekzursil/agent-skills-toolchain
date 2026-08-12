# Claude Science — WSL2 launcher/recovery tooling

[Claude Science](https://claude.com/product/claude-science) (Anthropic's life-science / compchem workbench, launched 2026-06-30) has **no native Windows build**. It installs into **WSL2 Ubuntu** as a CLI daemon that serves a web UI on `127.0.0.1:8000`, which you open in the Windows browser (WSL2 auto-forwards localhost). It is **not** an Electron/GUI app.

These scripts wrap the daemon lifecycle so it's one command from any Windows or WSL shell.

## One-command control (`cs`)

`cs.ps1` is the single front door — everything else is plumbing it drives. **401 on
`/` = alive** (auth gate); a **slow/timeout** response = **WEDGED** (WSL frozen,
usually host-RAM pressure), which `cs fix` recovers. It targets `127.0.0.1:8000`
only — **LOCAL scope**.

```powershell
pwsh -File .\cs.ps1 <verb>     # or /claude-science <verb> from Claude Code (/cs still works)
```

The slash command is **`/claude-science`**; **`/cs`** is kept as a thin forwarding alias because
the dispatcher, the `cs.cmd` shim and every `cs <verb>` below still use the short name. (Claude
Code has no `alias:` frontmatter field, and `name:` only sets the display label of a personal or
project command — a forwarding file is the only mechanism.)

| Verb | What it does |
|---|---|
| **`cs open`** | Ensure up (start-if-down / recover-if-wedged), **wait for readiness** (not a blind sleep), then open the UI. The human one-click. |
| **`cs ensure`** | Headless ensure-up for **tools/agents** → `SUCCESS:cs-up` / `FAILED:cs-down` (exit 0/1). Call before any `:8000` request. |
| **`cs status [-Json]`** | State + measured **latency** + a `wedged` flag + WSL daemon detail. `-Json` for machine parsing. |
| **`cs fix`** | Graceful force-recover: stop → clear stale locks → restart pinned. The wedge cure. (alias `cs recover`.) |
| **`cs stop`** | Stop the daemon. |
| **`cs backup`** | Online SQLite snapshot to `D:\Backups\claude-science` (key stored separately, last 7 kept). Safe while up. |
| **`cs restore <ts\|latest>`** | Roll back to a snapshot (keeps a pre-restore safety copy, drops stale WAL/SHM, restarts, verifies). |
| **`cs doctor`** | Full-stack **PASS/WARN/FAIL/NOT-CHECKED** report (see below). Exits non-zero on FAIL or NOT-CHECKED. |

## Configuration — one file, env-overridable (`cs.conf`)

Port, distro, backup roots, the wedge threshold, the health floors and the backup-freshness
thresholds live in **`cs.conf`** and nowhere else. Both halves read it:

| Half | Reader | Consumers |
|---|---|---|
| PowerShell | `cs-lib.ps1` (~8-line parser) | `cs.ps1`, `cs-doctor.ps1`, `cs-watchdog.ps1`, `cs-start.ps1`, `cs-recover.ps1`, `cs-tailscale-serve.ps1`, `install.ps1`, `register-tasks.ps1` |
| Shell | `cs-lib.sh` | `cs-backup.sh`, `cs-maintain.sh`, `cs-restore.sh`, `cs-recover.sh`, `cs-supervisor.sh` |

Precedence is **environment > `cs.conf` > in-script default**, so `$env:CS_PORT = 8123` (or
`CS_PORT=8123` in the shell) changes the port with no edit, and a missing `cs.conf` degrades to
the values the scripts shipped with rather than to empty strings. The backup root is stored
**once**, in WSL form (`/mnt/d/...`); `cs-lib.ps1` derives the Windows form (`D:\...`).

Before this seam existed there were **25 hardcoded config sites across 12 files** (10 port, 9
distro, 6 backup-root); five PowerShell scripts never dot-sourced `cs-lib.ps1` at all and the
shell side had no lib whatsoever. There are now **0 outside the seam** — the only remaining
literals are the definitions in `cs.conf` and the matching fallback defaults in the two libs,
and `test-cs-doctor-failclosed.ps1` asserts all three agree so the fallback cannot drift from
the file it backs.

### `cs doctor` output

A read-only, one-shot report that operationalizes the 2026-07-07 audit into a
repeatable table. Each row is PASS `[+]` / WARN `[!]` / FAIL `[X]` / NOT-CHECKED `[?]` / INFO `[i]`:

- **WSL reachable** — distro answers (a timeout ⇒ VM wedged).
- **CS daemon** — `state=HEALTHY|SLOW|DOWN http=… latency=…ms`; a SLOW state is flagged `*** WEDGED ***`.
- **daemon detail** — pid / version / uptime.
- **DB** — `operon-cli.db` integrity + `journal_mode` + size.
- **WSL disk free** — ext4 headroom (disk-full mid-WAL risks DB corruption).
- **Host RAM free** + top 3 consumers — the freeze root cause.
- **Watchdog registered** / **Watchdog instances** — catches the duplicate-watchdog race.
- **Watchdog re-launch trigger** — the task must carry a *repeating* trigger, not only `-AtLogOn`.
- **Watchdog heartbeat** — age of the heartbeat file, AND-gated against process liveness.
- **Backup freshness** — newest snapshot age (WARN/FAIL thresholds from `cs.conf`).
- **Backup restorable** — *opens* the newest snapshot: SQLite magic header (Windows-side, works
  even when the VM is wedged) plus `PRAGMA integrity_check` (WSL-side, the real proof).
- **Tab-death regfix** — Chrome/Edge discard-exception policy applied.

Ends with a `N FAIL, N WARN, N NOT-CHECKED, N PASS` summary; any FAIL prints
`→ try: cs fix then re-run: cs doctor`. **Exit code is non-zero on FAIL or NOT-CHECKED**, so other
tooling can gate on `cs doctor` rather than parsing the table.

### Fail-closed contract (2026-08-12) — and how to falsify it

A health check that cannot reach its input **must not render green**. It used to. Measured: the
DB row printed `WARN "sqlite3 or operon-cli.db not found"` while both existed and the identical
probe returned `ok|wal|2.9M` in 1293 ms standalone — the real cause was an `Invoke-CSWsl` timeout
under host-RAM pressure, and one branch collapsed *three* causes (timeout / empty / genuinely
absent) into the message for only the third. Immediately below it, `Backup freshness` rendered
`PASS` over that same unreachable VM, and a third row (`daemon detail`) **silently vanished**
from the table instead of reporting that it was unmeasured.

Now: timeout or empty ⇒ `NOT-CHECKED` (and it says only that); genuinely absent ⇒ `FAIL`
(absence *is* a measurement); the summary counts NOT-CHECKED separately so `0 FAIL, 0 WARN`
cannot hide unmeasured rows.

Two detector bugs were fixed alongside, both measured live:

- **Watchdog instances counted the probe itself.** The filter was `CommandLine -like '*cs-watchdog*'`,
  which matches any shell whose command line contains that string — asking the question could
  manufacture the "DUPLICATE — dual-watchdog race" answer. Now `$PID` is excluded *and* the
  `-File …cs-watchdog.ps1` argument shape is required.
- **A stale heartbeat was read as a hung watchdog.** One probe took 66,396 ms against a nominal
  8,000 ms socket cap, because under RAM pressure the watchdog *process* is descheduled and no
  in-process timeout can bound that. So a healthy watchdog correctly measuring a wedge reported
  `STALE - watchdog hung?`. The row now AND-gates two independent signals: stale beat + **no**
  process ⇒ FAIL; stale beat + live process ⇒ WARN. The threshold is `CS_BEAT_STALE_S` (180 s,
  above the measured worst case) instead of a bare 90 s, and `cs-watchdog.ps1` writes the beat
  **before** the probe so a slow probe cannot age its own heartbeat.

Falsify all of it with the shipped both-states harness — 12 scenarios, 45 assertions, every WSL
probe stubbed, so it is hermetic and safe to run *while* the box is wedged:

```powershell
pwsh -NoProfile -File .\test-cs-doctor-failclosed.ps1
# SUCCESS:cs-doctor-failclosed all 45 assertions held
```

It asserts both directions — that each row goes FAIL/NOT-CHECKED when its input is broken, **and**
that the same row goes PASS in the paired healthy control. A test that only checked the broken
direction could not tell a fail-closed row from a row that is always red.

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

## Environments fail to create ("Package downloads blocked by network policy")

If the **Environments** panel shows `python` / `r` / `compute-provider-modal` /
`claude-science-mcp` **Failed** with conda/libmamba errors like
`Failed to connect to conda.anaconda.org port 443 via localhost after 0 ms`, this is a
**Claude Science-internal sandbox-networking bug** — NOT anything you can configure. Report it to
Anthropic; don't burn time on the fixes below that DON'T work.

**The signature:** the env-create sandbox cannot reach `conda.anaconda.org` through its localhost
egress proxy, while the AGENT's own tool sandboxes reach it fine (`HTTP 200`). Same host, same
network — only the env-create / MCP-catalog sandboxes are denied (`SOCKS5 error 2 = "connection not
allowed by ruleset"`). That asymmetry is inside CS's sandbox wiring.

**Six hypotheses, ALL refuted (2026-07-08 → 07-10) — do NOT re-chase any of these:**
1. **Account plan** — fails identically on **Free AND Max** accounts (verified via UI + `active-org.json`). Not the plan.
2. **Network egress** — the daemon's `socat` SOCKS5h proxy is up and reaches conda directly (`curl --socks5-hostname localhost:<port> conda.anaconda.org → 200`); host has internet.
3. **`Customize → Permissions` grant / `userAllowedDomains`** — empty but irrelevant; the UI "Package management" domain toggle shows **ON**, conda still denied.
4. **Package mirror** (`Settings → Network → Package mirror`) — set Conda=`https://conda.anaconda.org`, pip=`https://pypi.org/simple` (saved to `preferences.json`); error only changed to *"configured mirrors could not be reached."*
5. **WSL firewall** — `firewall=false` in `.wslconfig` + `wsl --shutdown`: no change.
6. **WSL networking mode** — `networkingMode=nat` vs `mirrored` + `wsl --shutdown`: fails identically (the "via localhost" signature *looked* like a mirrored-mode loopback bug — it isn't).

**There is NO user-side lever** (no CLI/env/config-file; the mirror is operon-DB + nonce-gated-UI
managed). **Fix = report to Anthropic:** `CS → Settings → Diagnostics → Download logs`, attach the
asymmetry evidence (env-create bridge `SOCKS5 error 2` vs agent bridge `HTTP 200`). Environments
can't be created on this setup until Anthropic fixes the env-create sandbox's egress.

**Meta-lesson:** when the *agent's* path works but the *feature's* path fails inside a vendor's
sealed component, escalate to "vendor bug" EARLY — don't cycle host-side hypotheses (this one
burned an account-switch that churned the user's session for nothing).

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
