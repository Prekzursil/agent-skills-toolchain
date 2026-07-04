# Claude Science — WSL2 launcher/recovery tooling

[Claude Science](https://claude.com/product/claude-science) (Anthropic's life-science / compchem workbench, launched 2026-06-30) has **no native Windows build**. It installs into **WSL2 Ubuntu** as a CLI daemon that serves a web UI on `127.0.0.1:8000`, which you open in the Windows browser (WSL2 auto-forwards localhost). It is **not** an Electron/GUI app.

These scripts wrap the daemon lifecycle so it's one command from any Windows or WSL shell.

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

## Commands (put `~/.local/bin` on PATH; the `.ps1`/`.cmd` go in a Windows PATH dir)

| Command | What it does |
|---|---|
| **`cs-start`** | Gentle: starts the daemon **only if down**, never kills a running one, then opens the UI. |
| **`cs-recover`** | Force-restart: `pkill -9`, clears stale `daemon.sock`/`operon.lock`/`sbx-bind-src/sock-*`, restarts, reopens UI. Use when the daemon **wedges**. |

Each exists in three flavors so it works from PowerShell (`.ps1`), cmd (`.cmd`), and WSL bash (the extension-less script). Install with `install.ps1` (copies to `~\.local\bin` + `~/.local/bin`).

## Why `cs-recover` exists (beta gotcha)

The daemon can wedge on **SQLite lock contention** (`operon-cli.db`; server log shows `[perf] db_lock_hold TxMutex 500–1000ms`). That leaves a stale `daemon.sock`/`operon.lock`, which makes a naive `stop`→`serve` **hang**. `cs-recover` clears the locks first. Verify reachability with `Test-NetConnection localhost 8000` (NOT `Get-NetTCPConnection`, which doesn't see mirrored WSL ports); a healthy daemon returns **HTTP 401** on `/` (auth gate).

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
