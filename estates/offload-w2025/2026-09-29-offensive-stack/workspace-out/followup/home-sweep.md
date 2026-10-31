---
title: home-sweep
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/followup/home-sweep
---

# Lane report — home-mirror-sweep

Date: 2026-09-30. Subagent: "Implementer: home-mirror-sweep". Working dir: `C:\Users\prekzursil\.zcode\workspace\default`.
Deliverables: this report + `out/followup/MISSING-FROM-HOME.md` + refreshed staged mirror.

## 1. Home probe — **DOWN**

| Check | Command (exact) | Output | Verdict |
|---|---|---|---|
| Tailnet peer state | `tailscale status` | `100.97.16.36 desktop-a60s9gp prekzursil1993@ windows active; direct 82.78.48.123:41641, tx 1133159048 rx 212204028` | peer listed active (stale session counters) |
| TCP 2022 | `powershell -NoProfile -Command "Test-NetConnection 100.97.16.36 -Port 2022 \| Select-Object ComputerName,RemotePort,TcpTestSucceeded \| Format-List"` | `TcpTestSucceeded : False` (+ ping TimedOut) | port closed |
| TCP 2022+2023 (retry) | `powershell -NoProfile -ExecutionPolicy Bypass -File out\followup\tcp-probe.ps1` | `2022: False  2023: False` | both ports closed |
| SFTP channel | `rclone lsf homeC: --max-depth 1 --timeout 10s --contimeout 10s` | `CRITICAL: Failed to create file system for "homeC:": ... couldn't connect SSH: dial tcp 100.97.16.36:2022: i/o timeout`, exit 1 | mirroring channel dead |

Verdict: **DOWN** (asleep or rclone serve down). Per instructions: no forcing, no waking, no retry grinding — took the DOWN branch. rclone remotes verified: `homeC`/`homeD` = sftp, host 100.97.16.36, ports 2022/2023, user `link`, key `C:\Users\prekzursil\.ssh\vm_to_home`.

## 2. DOWN-branch inventory (vault repo + audit findings)

Sources used: `out/audit/home-configs.md` (the ask's line-32+ table, rows at lines 26-35), `D:\opt\vault\agent-skills-toolchain\tools\mcp\canonical-mcp-servers.json` (437 lines, read in full), `secrets/env-backups/`, `RECONCILE-LOG.md` + `RECONCILE-STATE_2026-09-01.md` (grep for home/bolt/ReverseTools/Burp/cursor-bridge/dbx-ai/lifesciences/sliver/msf/ghidra/IDA/jadx → only a cursor-bridges PR note, line 57; no home-surface listing).

VM-side existence check run this session: `C:/Python314/python.exe out\followup\check_paths.py` (script in this lane's out dir; every row below is its output):

**MISSING on this VM (the fetch-when-awake queue → full detail in MISSING-FROM-HOME.md):**
- Burp Suite: `AppData\Roaming\BurpSuite`, `C:\Program Files\BurpSuite`, mcp-proxy jar, and the MS jdk-21 (`C:\Program Files\Microsoft\jdk-21.0.10.7-hotspot`) that `burp` (agents.json:1526-1549) launches with — all absent.
- `D:\bolt` (zai-lane surface: `zai-anon-mcp.py`, `credentials/breach-vendor-keys.json`) — absent (`zai-lane-a` agents.json:2364-2386).
- `D:\opt\cursor-bridge` — absent (agents.json:1774-1793).
- `dbx-ai` — absent from BOTH `~/source/agent-skills-toolchain/tools/mcp/` and the vault repo copy; only home can hold it (agents.json:1349-1372).
- `lifesciences-research` source — absent under both username casings (agents.json:2535-2560).
- `gh-cli-mcp` — `shutil.which` → None; `pip show gh-cli-mcp` → not found on C:\Python314 (canonical:203-211 uses bare `gh-cli-mcp`).
- `mcp_agent_mail` — not on PATH, not pip-installed; serves :18812 (agents.json:1210-1237) / canonical says :8812 (canonical:3-6) — port drift recorded.
- `D:\ReverseTools` — absent (paper-search canonical:293-296, perplexity canonical:308-311).
- `.local/opt` gaps: `jadx-mcp-server`, `apktool-mcp-server`, `cloud-audit-mcp` absent (canonical:7-12, 37-43, 242-247).
- sliver/msf: no dirs at `D:\sliver`, `D:\metasploit`, `.local/opt/{sliver,metasploit}`; note VM already holds `out/research/sliver-src` (510MB), `out/tmp/metasploitframework-latest.msi` (400MB), `out/tmp/sliver-server_windows-amd64.exe` (340MB) locally.
- Also absent: `D:\mcp-servers` (ocr-suite), `D:\micromamba` (openmm-md env), `source/repos` holds only `mattpocock-skills` (canonical expects fb-messenger/rdkit/schrodinger/openmm-md MCP sources), `D:\opt\breach-mcp` (breach-intel, agents.json:2387-2407 — entry additionally has `\x08` corruption per audit #2).

**PRESENT on this VM (not lost):** `.local/opt/{ghidra-mcp 74.5MB, ida-pro-mcp 28.5MB, hexstrike-ai 763.7MB, mitmproxy-mcp 204.9MB, cheatengine-mcp-bridge 81.4MB, angr 477.8MB}` plus `frida-mcp`, `frida-server`, `ghidra-bridge`, `deepsource-mcp-server`, `poppler`.

**Env restorable locally but NOT applied (arm nothing):** `.agents\secrets\env-backups\2026-09-29\{machine.env (214 vars), user.env, HKCU/HKLM-Environment.reg}` — duplicated at `D:\opt\vault\agent-skills-toolchain\secrets\env-backups\2026-09-29\` (file listing run this session).

## 3. Mirror refresh (done either way)

- Estate mirror tree `D:\opt\vault\agent-skills-toolchain\estates\offload-w2025\2026-09-29-offensive-stack\workspace-out` was a stale subset of the live workspace (223 new/changed items only-in-workspace, 0 only-in-estate; `diff -rq` run this session; workspace `out/` = 6.7GB vs estate copy 145MB).
- Curated sync run: `C:/Python314/python.exe out\followup\sync_delta.py` — copies new/changed files ≤5MB each, excluding `tmp, target, vendor, node_modules, mingw, cloudfox-bin, site-packages, .venv, venv, artblood-src` trees and reserved device names (`nul/con/prn/aux`, which otherwise crash `os.path.relpath`). Result: 0 failures, 26 files >5MB skipped (largest: winlibs.zip 272.9MB, cloudfox-windows-amd64.zip 104MB, sliver git pack 69.8MB, sliver-client.exe 68.3MB — full list in sync output), estate tree 145MB → **392MB**. Idempotence verified: immediate rerun reported `COPIED: 0 files`.
- Delta tarball built against yesterday's snapshot: `offload-w2025-2026-09-29.tar.gz` extracted to temp, content-diffed (md5, size) vs current vault `estates/offload-w2025` + `cyberstrike/gateway/offload-w2025` by `out\followup\build_delta_tar.py`; archive created with GNU tar from bash (note: `C:\Windows\System32\tar.exe` (bsdtar) cannot read MSYS paths, and Python-subprocess invocations of GNU tar fail with Windows-style `-C` args or CRLF/backslash list files — four failed subprocess attempts recorded before the working `/usr/bin/tar` invocation, `TAR-EXIT:0`). Final artifact: `D:\opt\vault\mirror-pending\offload-w2025-2026-09-30-delta.tar.gz` — entry count, byte size and md5 are recorded in the sidecar `mirror-pending\offload-w2025-2026-09-30-delta.md5` (the tarball is rebuilt once after this report is staged, so the archive contains this report's final text; the sidecar is written last and holds the authoritative numbers).
- `D:\opt\scripts\push-home-mirror.ps1`: **not run** — the ask runs it only if home is up. Its own gate (lines 9-12) tests the same `:2022` verified False twice above; it would `exit 1`. Script updated (one line added) to also push the new delta tarball alongside the 09-29 full snapshot, so the staged refresh drains automatically next time it runs.
- `D:\opt\mirrored-from-home\` NOT created (nothing to mirror from a down host); `REPOINT-MAP.md` not produced (UP-branch artifact; superseded by MISSING-FROM-HOME.md).

## 4. Not done / limits

- No home-side sizes (`rclone size`) possible — host down; MISSING-FROM-HOME.md marks them `?`.
- No verification that home actually holds each queued item — the queue is inferred from canonical paths + audit line references; discovery commands per item are embedded in the runbook.
- `github` remote HTTPS endpoints not probed (out of scope, matches audit's "Not verified").
- The vault repo working tree carries untracked research dirs (pre-existing, `git status` shown this session); no commits or pushes made this lane (not requested).