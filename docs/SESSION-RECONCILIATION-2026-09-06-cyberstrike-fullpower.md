# SESSION RECONCILIATION — CyberStrike Full-Power Purple (2026-09-06)

Status: **SUCCESS** — receipts on disk:
- `D:\opt\cyberstrike-mcp\receipt-fullpower-purple_2026-09-06.md` (round 1)
- `D:\opt\cyberstrike-mcp\receipt-purple-round2_2026-09-06.md` (round 2)

## 1. End state (audited, disk-verified)

### CyberStrike MCP registry — 29 entries
- **20 connected** (verified via `cyberstrike mcp list`): github-security, cve, osint,
  cloud-audit, darknet, dns-security, supply-chain, mcp-scanner, steganography, satellite,
  hexstrike-ai, firecrawl, hacktricks, nuclei, semgrep, sliver, sliver-full, metasploit,
  mitmproxy, frida
- **9 flip-on-demand placeholders (enabled:false)**: burp (needs one-time license
  activation, then BApp on :9876/sse), radare2 (r2mcp.cmd), angr, ghidra-mcp, ida-pro-mcp,
  jadx-mcp, binary-ninja-mcp, windbg (all need their GUI hosts running)
- **hackbrowser: dead built-in — do not enable** (see §4)

### Gateway (D:\opt\cyberstrike-mcp, loopback only)
- Supervisor running `-Profile Heavy`: all 12 fronts (31410-31419, 31380-31381) +
  hexstrike internal :18888. Self-healing with circuit breakers; survived two audit
  sessions with zero restarts (PID stable).
- Boot task `CyberStrikeMcpHttpCore` upgraded **Core → Heavy** (all fronts at logon).
- `SliverLoopbackDaemon` task keeps sliver MP daemon :31337.
- msfrpcd on :55553 (loopback, SSL off); auto-start patched in launcher (see §2.3).

### Purple toolkit (D:\opt\purple-tools)
venv-ad (netexec via GitHub — **not on PyPI** — + bloodhound-python 1.9.0), venv-detect
(sigma-cli + yara-x 1.20.0 + prowler 5.41.0), velociraptor.exe 0.77.2, tshark (scoop),
SecLists, sigma-rules (SigmaHQ), yara-rules, r2mcp 1.8.6 (official Windows build + wrapper),
bettercap 2.41.7 (+ libusb-1.0.dll — release zip ships WITHOUT it), evilginx3 v3.3.0,
gophish 0.12.1 (must run from its own dir), compose/bloodhound-ce.yml + compose/caldera.yml
(on-demand only — RAM discipline).

### WSL Ubuntu
- **Docker Desktop WSL integration ENABLED** for Ubuntu (settings-store.json +
  restart; required for Mythic). Container fleet self-healed.
- Mythic CLI v0.3.26 / server v3.4.36 at `/opt/Mythic/mythic-cli` — installed, NOT started.
- Havoc 0.7 built from source at `/opt/Havoc/havoc` (mingw toolchain installed).
- hcxtools 6.2.7 + hcxdumptool via apt. NOTE: bare `&` background jobs in WSL die with
  the invoking session — use nohup.
- Covenant: source-only clone at `D:\opt\purple-tools\covenant-src` (archived 2020, needs
  .NET build; Mythic/Havoc are the maintained path).

### Burp Suite Pro 2026.3.2
Staged at `D:\opt\burp\` (vodkrak bundle + prebuilt PortSwigger MCP BApp
`burp-mcp-all.jar`). Owner one-time action: `KEYGEN.cmd` → activation steps in
`D:\opt\burp\README-ACTIVATION.md` → load BApp → flip `burp` entry enabled.

## 2. Root causes fixed (all verified after fix)

1. **System-wide npx breakage** — `~/package.json` declared `"node": "^22.23.0"`;
   bun kept regenerating `~/node_modules/.bin/node.exe` as a bun stub that shadows real
   node inside npm's ancestor bin-chain → every `npx -y <pkg>` died with
   "Bun failed to remap this bin". FIX: `npm uninstall node` (in ~) + stub purge.
   RECURRENCE CHECK: if that error reappears, inspect `~/node_modules/.bin/node*` first.
   Held green across two post-fix sessions.
2. **sliver :31380 front** — launcher referenced `sliver-client.exe`; actual binary
   `sliver-client_windows-amd64.exe`. Fixed in `D:\opt\cyberstrike-mcp\sliver-client-mcp-http.cmd`.
3. **nuclei front** — old `tools/mcp/nuclei-mcp/server.py` was deleted from the repo
   (lost in a worktree cleanup), leaving the front pointing at nothing. Rebuilt as a
   FastMCP wrapper (scan/raw/templates-search/update) — **source restored to this repo**
   at `tools/mcp/nuclei-mcp/`; live deployment at `D:\opt\cyberstrike-mcp\nuclei-mcp-server.py`.
4. **metasploit front** — msfrpcd not on daemon PATH. `D:\opt\metasploit\msfmcpd-stdio.py`
   now prepends `D:\metasploit-framework\bin` so the front auto-starts msfrpcd after reboot.
5. **Gateway profile** — boot task launched Core only; upgraded to Heavy (all 12 fronts).

## 3. Config reconciliation (no regressions)

Diff of `~/.config/cyberstrike/cyberstrike.json` vs pre-session backup
(`.bak-enable-all-20260906`) = **exactly the intended changeset, nothing else**:
- enabled:true added — cloud-audit, hexstrike-ai, metasploit, sliver, sliver-full
  (remote) + darknet, dns-security, mcp-scanner, satellite, steganography, supply-chain
  (npx built-ins)
- new local entries — mitmproxy, frida (live) + angr/ghidra/ida/jadx/binja/windbg/radare2
  (placeholders) + burp (remote placeholder)
- zero non-mcp drift; hackbrowser intentionally absent (built-in default = disabled)
Schema notes learned: config file accepts `type: remote` {url, enabled, timeout} and
`type: local` {command: ARRAY, environment, enabled, timeout} — unknown keys rejected;
the TUI-only add flow writes the same shape. (An earlier `command`-as-string attempt was
invalid and was reverted — kept here so nobody retries it blind.)

## 4. hackbrowser built-in — upstream vestige (closed question)

`hackbrowser-mcp` does NOT exist on npm (404, verified) and never did. Upstream source
(github.com/CyberStrikeus/CyberStrike, `packages/cyberstrike/src/tool/hackbrowser.ts` +
`hackbrowser-launcher.ts`) shows hackbrowser is a **native tool**: agent-callable Tool,
`cyberstrike hackbrowser <target>` CLI, and `/hackbrowser` TUI slash command — no MCP
package involved. The `npx -y hackbrowser-mcp` defaults entry is dead code in
cyberstrike's built-in MCP table. Correct posture: keep disabled; use the native surface.
(A third-party `@iflow-mcp/badchars-hackbrowser-mcp` exists but is unrelated —
Firefox multi-container; not wired.)

## 5. Known flakes (not outages)

- `cyberstrike mcp list` intermittently reports `sliver ✗`: the CLI health probe uses a
  short timeout; front :31380 answers MCP initialize correctly (verified: "Sliver MCP
  v1.7.6"). TUI persistent connections (timeout 300000) unaffected.
- bettercap capture paths need npcap (present on this box).
- hcxtools capture needs a monitor-mode-capable USB adapter.

## 6. Operations quick reference

```
# gateway status / restart
powershell D:\opt\cyberstrike-mcp\status-cyberstrike-mcp-http.ps1
powershell D:\opt\cyberstrike-mcp\start-cyberstrike-mcp-http.ps1 -Profile Heavy -Force
# purple heavy services (on-demand only)
docker compose -f D:\opt\purple-tools\compose\bloodhound-ce.yml up -d   # :8080
docker compose -f D:\opt\purple-tools\compose\caldera.yml up -d         # :8888
wsl -d Ubuntu -u root -- /opt/Mythic/mythic-cli start                   # :7443
# enable a placeholder
edit ~/.config/cyberstrike/cyberstrike.json -> "enabled": true -> restart TUI session
```
