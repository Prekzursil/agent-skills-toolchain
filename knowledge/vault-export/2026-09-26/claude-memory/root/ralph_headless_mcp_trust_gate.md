---
name: ralph-headless-mcp-trust-gate
description: Why ralph-spawned (headless) claude agents don't see user-scope MCP servers,
  and the project .mcp.json fix that gives them the funnel / RE tools
metadata:
  node_type: memory
  type: reference
  originSessionId: c5980bb4-6564-4a44-a055-9721b0720cee
permalink: main/claude-memory/root/ralph-headless-mcp-trust-gate
---

Ralph Orchestrator spawns each hat as a headless claude:
`claude --dangerously-skip-permissions --verbose --output-format stream-json --setting-sources project,local --print --disallowedTools=...`
(find the live args with `Get-CimInstance Win32_Process -Filter "name='claude.exe'" | Select-Object CommandLine`).

**The real blocker is `--setting-sources project,local`** — it EXCLUDES the `user` source, so everything in `~/.claude.json` (user-scope `mcpServers` like mcp-funnel/ida-pro-mcp, AND that file's per-project `hasTrustDialogAccepted` / `disabledMcpServers`) is INVISIBLE to loop agents. `--dangerously-skip-permissions` also makes folder trust irrelevant. So editing `~/.claude.json` does NOTHING for the loop — it only affects interactive sessions (which default to all sources). That red herring cost time: trust + a 94-entry disable list in `~/.claude.json` made a *direct* `claude -p` probe show the funnel, but the loop's `--setting-sources project,local` spawn still saw nothing. Always confirm the spawn's actual flags before picking the config layer.

**FIX (verified end-to-end 2026-05-24):** put the server in PROJECT scope — create `<project>/.mcp.json`:
`{"mcpServers":{"mcp-funnel":{"command":"cmd","args":["/c","npx","-y","mcp-funnel","C:/Users/Prekzursil/.mcp-funnel.json"]}}}`.
With `project` source loaded + `--dangerously-skip-permissions` (auto-approves project MCP, no prompt), the funnel loads. Proven: a spawn with ralph's EXACT flags called `mcp__mcp-funnel__ida-pro-mcp__server_health` → `{"status":"ok","module":"libnative-lib.so",...}` (live IDA on BC 15.3.0). The funnel (`~/.mcp-funnel.json`, exposeCoreTools=discover_*/load_toolset) proxies IDA+HexStrike+Ghidra+Frida+BinaryNinja+CheatEngine through ONE connection and proxies calls directly (no load_toolset needed). It shows `pending` in the `system/init` snapshot (npx cold start) then connects during the turn — a trivial "reply ok" probe exits before it finishes, so verify by making the probe actually CALL a funnel tool. Bonus: `project,local` sources also exclude the ~47 `plugin:*` servers, so only the funnel + (disabled) cloud connectors load — lean by construction. No hat edit, no loop restart; the next spawn reads `.mcp.json`. Diagnose what a spawn truly gets via the stream-json `system/init` `mcp_servers` array in `.ralph/logs/ralph-stdout-*.log`.

**Adding servers / reloading hats (2026-05-24):** to give the loop another server (e.g. `hexstrike-ai` for the RE hat), add it to the project `.mcp.json` (same `mcpServers` format) — reachable on the next spawn. Heavy servers (hexstrike = 150+ tools) connect async and SLOWLY (~30-60s, shows `pending` at init), so a trivial probe sees no tools; instruct the hat to do IDA work first, then `ToolSearch "hexstrike"`, and scope it to LOCAL static binary analysis only (it's an offensive-security framework). To reload the hats YAML mid-run (ralph caches it at `run` start): validate first (`ralph hats validate -c ralph.yml -H <hatsfile>` + `ralph preflight -c ralph.yml`), then tree-kill ralph (`taskkill /F /T /PID <ralph>`). The outer-supervisor watchdog (`.ralph/supervisor/outer-supervisor.ps1`, ralph's PARENT — survives the tree-kill) detects the exit within 60s and relaunches `ralph run --continue --loop-id <id> -H <hatsfile>`, which RE-READS the hats and resumes loop state on the same events file. Kill ONCE — a crash-loop guard exits the supervisor after >3 ralph restarts/10min; confirm the supervisor is alive + `heartbeat.txt` fresh (<180s) before killing. Relates to [[project_mcp_reduction]].