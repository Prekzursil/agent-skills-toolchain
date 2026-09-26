---
title: Claude Science shortcut+conda fixes & QoL tooling (2026-07-07)
type: report
permalink: main/projects/claude-science/claude-science-shortcut-conda-fixes-qo-l-tooling-2026-07-07
tags:
- claude-science
- windows
- qol
- wsl2
- clipaste
- troubleshooting
---

# CS shortcut + conda-env fixes & Windows QoL tooling (2026-07-07)

## Claude Science — two live bugs fixed/diagnosed
1. **Desktop shortcut showed SIGNED OUT** (even with daemon up). Root cause: `cs open` did `Start-Process $script:CSUrl` = the **bare `http://127.0.0.1:8000/`**, which lands on the signed-out auth page. The daemon auths via a **single-use `?nonce=` token** from `claude-science url`. Fixed cs.ps1 to fetch + open the nonce URL (fallback to bare). **PR #48, merged.** (Earlier, #45 fixed the *launcher* — VBScript is removed on Win11 Canary 28120 so the old `wscript cs-open.vbs` was dead; now `conhost --headless`.)
2. **Environments (conda python/r/modal/mcp) fail: "Package downloads blocked by network policy," "connect to conda.anaconda.org:443 via localhost 0ms."** NOT lost internet (host reaches conda 200), NOT the proxy down (socat SOCKS5h pairs running), NOT our cs-recover. Root cause: **CS sandboxes env-creation with ZERO egress; a socat SOCKS5h proxy enforces an allowlist ("network policy"); `userAllowedDomains`+`hostGrants` are EMPTY** so conda.anaconda.org is refused. conda envs dir empty = never succeeded. **Fix (USER action, security setting): CS web UI → Customize → Permissions → grant `conda.anaconda.org` (+ pypi.org, files.pythonhosted.org, repo.anaconda.com). No CLI for grants in this build.** Don't hand-edit preferences.json (grants are UI/DB-managed + it's a security control).

## Windows QoL stack installed (user consolidating on NordPass; picked Ditto + Everything/Espanso/clipaste/Atuin)
- winget: **Ditto** 3.25 (clipboard), **Everything** 1.4.1 (NTFS search), **Espanso** 2.3 (text expander, service registered+running). All hash-verified.
- WSL: **Atuin** 18.16.1 (shell history; init in ~/.bashrc, `atuin import auto` done).
- **clipaste** 2.4.0 (Windows daemon, HKCU Run auto-start). Its `wsl-setup` **FAILS on mirrored-networking WSL** (parses /etc/resolv.conf for the NAT host IP, which mirrored mode lacks). But the daemon IS reachable from mirrored WSL at **localhost:18340** (`GET /health|/clipboard/type|/clipboard/image`). Hand-wired **`~/.local/bin/clipaste-paste`** (curl /clipboard/image -> temp PNG -> print path). The Ctrl+V **xclip shim** needs a real xclip to delegate to (`sudo apt-get install -y xclip` then reinstall shim).

## Browser autofill/Gmail (from the 11-agent audit+research workflow) — user's machine specifics
- **Autofill fails** because of STACKED password managers per browser (Chrome: NordPass+Samsung Pass; Edge: Samsung Pass+2FAS) fighting the login field while locked -> native dropdown suppressed. Fix = ONE manager (user chose NordPass, import+aggregate everything). Compounding: `exit_type=Crashed` from heavy automation force-killing browsers.
- **Gmail signs out** from (1) **Hola VPN** extension (peer-routed IP churn -> Google flags suspicious) in both browsers + NordVPN; (2) target Gmail is a **sync-less secondary** account among 6 stacked, no Chrome-sync token to refresh. Fix = disable Hola; make mariusvisalon70@gmail.com primary + Chrome Sync ON.
- Machine flags: **C: at ~4% free (38.6 GB)**; deliberate **mirrored WSL networking** (keep — CS/DNS depends on it).

Related: [[project_claude_science_hardening_2026-07-07]].


## ⭐ CORRECTION (2026-07-08): conda env-create root cause = ACCOUNT PLAN, not network

The conda-envs fix documented above (grant conda.anaconda.org in Customize>Permissions) was **WRONG — superseded**. Verified via the CS **UI**: the instance is signed into a **FREE-plan account (andreivisalon2002@gmail.com)**, and CS shows *"available for Pro and Max plans — Upgrade to try."* Compute-environment provisioning (which downloads the conda packages) is a **Pro/Max feature** → blocked on Free, surfacing as *"package downloads blocked by network policy."* The **Settings→Network→Package-mirror remedy is ITSELF behind the plan gate**, so NO config fixes it on a Free account.

**RULED OUT (don't re-chase):** the daemon's **socat SOCKS5h egress proxy is UP and reaches conda directly** (`curl --socks5-hostname localhost:<port> https://conda.anaconda.org/... → 200`); host has internet; `host_grants` = filesystem mounts not network; no CLI/env/config lever for the mirror (operon-DB + nonce-session-gated UI).

**FIX = sign CS into a Pro/Max account** (user's `mariusvisalon70` has Max) via *"Sign in with a different account,"* or upgrade `andreivisalon2002`. The WSL daemon holds the prior account session → may need `cs fix` to re-auth after switching. Committed to the toolchain README (PR #58, main). **LESSON: check the CS account/plan entitlement BEFORE the network stack** — I chased the network layer for multiple sessions before checking the UI plan.

*(Flushed from the memory-spool 2026-07-18: this write was spooled 2026-07-08 and never confirmed to basic-memory — recovered 10 days later during a recovery-session spool audit.)*
