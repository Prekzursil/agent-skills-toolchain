---
title: MISSING-FROM-HOME
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/followup/missing-from-home
---

# MISSING-FROM-HOME — fetch-when-awake runbook

Date: 2026-09-30. Author: subagent "Implementer: home-mirror-sweep".
Home (desktop-a60s9gp, 100.97.16.36) was **DOWN** at probe time (17:31–17:33 local):
`tailscale status` showed the peer `active; direct` (stale session state) but
`Test-NetConnection 100.97.16.36 -Port 2022` → `TcpTestSucceeded: False` (twice, plus :2023),
and `rclone lsf homeC:` failed with `couldn't connect SSH: dial tcp 100.97.16.36:2022: i/o timeout`.
Nothing was fetched, mirrored, armed, or re-pointed this session. This file is the queue.

Suggested mirror budget when home wakes (per the ask): license-free items, ~500MB total,
target `D:\opt\mirrored-from-home\<name>\`. Sizes marked **?** = unknown until home is up
(`rclone size homeC:<path>` first). Discovery commands assume home's rclone serve answers on
:2022 (homeC:) / :2023 (homeD:).

## Fetch queue (priority order)

| # | Item | Expected home-side location | agents.json / canonical key | Why | Est. size | License-free? |
|---|------|-----------------------------|------------------------------|-----|-----------|----------------|
| 1 | `mcp_agent_mail` server (agent-mail) | ? — locate: `homeC:/Users/Prekzursil/.local/opt`, pip site-packages, or a service dir; audit says it serves `http://127.0.0.1:18812/mcp/` (agents.json:1210-1237), canonical says `:8812` (canonical-mcp-servers.json:3-6) — note the port drift | `agent-mail` (agents.json:1210-1237) | Coordination bus for codex/claude/zcode/hermes; down | small | yes (OSS) |
| 2 | `gh-cli-mcp` binary | ? — locate: `homeC:/Users/Prekzursil/.local/bin`, `~/.cargo/bin`, or a source build dir; canonical command is bare `gh-cli-mcp` (canonical-mcp-servers.json:203-211) | `github_cli` (agents.json:509-543) | Enabled entry, command not on PATH on VM | small | yes |
| 3 | Burp Suite configs | `homeC:/Users/Prekzursil/AppData/Roaming/BurpSuite` (project files, UserConfig.json, mcp-proxy dir) | `burp` (agents.json:1526-1549) | Configs are the irreplaceable part (project state, scopes, collab config) | ? | configs yes; Burp itself is licensed — do NOT mirror the app |
| 4 | D:/bolt zai-lane surface | `homeD:/bolt` — esp. `enum/pulls/zai-entitlement-fuzz_2026-09-19/zai-anon-mcp.py` and `credentials/breach-vendor-keys.json` | `zai-lane-a` (agents.json:2364-2386), `breach-intel` description (audit #2) | zai-lane-a enabled entry points at `D:/bolt/...` | small (code) | yes |
| 5 | `cursor-bridge` | `homeD:/opt/cursor-bridge` (expects `cursor_bridge_mcp.py`) | `cursor-bridge` (agents.json:1774-1793) | Enabled entry, dir absent on VM | small | yes |
| 6 | `dbx-ai` MCP server | ? — `tools/mcp/dbx-ai` exists NOWHERE on the VM (absent from both `~/source/agent-skills-toolchain` AND the vault repo copy — verified this session) | `dbx-ai` (agents.json:1349-1372) | Enabled entry; only home can have the source | small | yes |
| 7 | `lifesciences-research` source | `homeC:/Users/Prekzursil/source/lifesciences-research` | `lifesciences` (agents.json:2535-2560) | Enabled entry with `--directory` arg | ? | yes |
| 8 | D:/ReverseTools | `homeD:/ReverseTools` — `mcp/paper-search-mcp/venv/Scripts/paper-search-mcp.exe`, `mcp/perplexity-web-mcp/.venv/Scripts/pwm-mcp.exe` (canonical-mcp-servers.json:293-296, 308-311) | `paper-search`, `perplexity` (disabled residue per audit line 35) | Search tooling; prefer re-venv from source over copying venvs | small source, big venvs | yes |
| 9 | `D:/opt/breach-mcp` | `homeD:/opt/breach-mcp` (`breach_intel_mcp.py`) | `breach-intel` (agents.json:2387-2407) | Entry also has literal-backspace corruption in args[0] (audit #2) — fix the JSON escape BEFORE any re-point | small | yes |
| 10 | `.local/opt` RE suite gaps | `homeC:/Users/Prekzursil/.local/opt/{jadx-mcp-server, apktool-mcp-server, cloud-audit-mcp}` | `jadx-mcp` (canonical:242-247), `apktool-mcp` (canonical:7-12), `cloud-audit` (canonical:37-43) | VM already HAS ghidra-mcp, ida-pro-mcp, hexstrike-ai, mitmproxy-mcp, cheatengine, angr, frida-* (verified this session) — only these three are missing | jadx/apktool small; cloud-audit small | yes |
| 11 | sliver / metasploit | ? — none found on VM at `D:\sliver`, `D:\metasploit`, `.local/opt/{sliver,metasploit}`; workspace `out/research/sliver-src` (510MB) and `out/tmp/metasploitframework-latest.msi` (400MB), `out/tmp/sliver-server_windows-amd64.exe` (340MB) already sit on the VM locally | (no agents.json key; offensive-stack surfaces) | Only fetch if home holds configs/state (implant certs, db, msf rc files), NOT the binaries | binaries big; state small | sliver OSS; msf BSD — but binaries already local |
| 12 | `D:/mcp-servers` (ocr-suite) + `D:/micromamba` (openmm-md env) | `homeD:/mcp-servers/abbyy-finereader-ocr-mcp`, `homeD:/micromamba/envs/openmm-md` | `ocr-suite` (canonical:267-272), `openmm-md` (canonical:273-278) | Canonical paths absent on VM; ABBYY is licensed — mirror code only, skip the app | small code | code yes; ABBYY no |
| 13 | `source/repos` MCP sources | `homeC:/Users/Prekzursil/source/repos/{fb-messenger-mcp, rdkit-mcp-server, schrodinger-mcp, openmm-md-mcp}` | canonical:142-146, 352-357, 374-379, 273-278 | VM `source/repos` contains only `mattpocock-skills` (verified) | small-medium | yes (venvs excluded) |
| 14 | MS jdk-21 for burp java path | `homeC:/Program Files/Microsoft/jdk-21.0.10.7-hotspot` — better: fresh-install Microsoft JDK 21 (free) instead of mirroring | `burp` (agents.json:1526-1549) | `C:\Program Files\Microsoft` does not exist on VM | ~180MB | yes (free redistributable — but reinstall, don't mirror) |

## Do NOT mirror (skip list)

- **Burp Suite application binaries** — commercial license; fetch configs only.
- **ABBYY FineReader** (ocr-suite backend) — commercial license.
- **Any venv/site-packages trees** — rebuild with `C:\Python314\python.exe -m venv` + pip install from each project's requirements; venvs are not portable across machines.
- **Ghidra/IDA application installs** — Ghidra is OSS-downloadable; IDA is licensed. VM already has the MCP bridge venvs for both.
- **Large toolchains** (mingw, winlibs, metasploit msi, sliver binaries) — already present in VM workspace `out/research` + `out/tmp`, verified this session.

## Local restorables that need NO home (recorded, NOT applied — "arm nothing")

- `C:\Users\prekzursil\.agents\secrets\env-backups\2026-09-29\machine.env` (214 machine-scope vars) + `user.env` + `HKLM/HKCU-Environment.reg` — duplicated in vault at `D:\opt\vault\agent-skills-toolchain\secrets\env-backups\2026-09-29\`. Importing is an owner decision (audit #3/#4: live env satisfies almost none of the requiredEnv of enabled servers; MCPHUB_TOKEN exists only here).
- agents.json control-char corruption (audit #2: `\x08` in `breach-intel.args[0]`, `burp.description`, `breach-intel.description`) — fix is a local JSON edit, still pending.

## When home wakes (runbook)

1. `tailscale status` + `Test-NetConnection 100.97.16.36 -Port 2022` → confirm `TcpTestSucceeded: True`.
2. `rclone size homeC:/Users/Prekzursil/AppData/Roaming/BurpSuite` etc. for every `?` row above; re-check the ~500MB budget with real numbers.
3. `rclone copy homeC:/Users/Prekzursil/<path> D:\opt\mirrored-from-home\<name>\ --dry-run` first, then real.
4. Only after mirrors land and are verified: fix agents.json corruption, then re-point entries (see audit #1 table for the exact agents.json line ranges).
5. Run `D:\opt\scripts\push-home-mirror.ps1` to drain the VM→home mirror staged in `D:\opt\vault\mirror-pending`.