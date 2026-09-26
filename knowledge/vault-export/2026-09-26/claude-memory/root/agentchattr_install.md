---
name: agentchattr-install
description: AgentChattr multi-agent chat coordinator — install location, ports, and
  global MCP registration across Claude/Codex/Gemini
metadata:
  node_type: memory
  type: reference
  originSessionId: 36cba66d-b7f5-47e0-86a9-0861130bb158
permalink: main/claude-memory/root/agentchattr-install
---

AgentChattr (github.com/bcurts/agentchattr) installed 2026-05-24 at **`D:\agentchattr`**, `.venv` on **Python 3.11.9** (3.14 avoided — FastAPI/mcp dep risk). Local multi-agent chat coordinator: agents `@mention` each other + human in a shared chat.

**Ports:** web UI `:8300`, MCP HTTP `:8200/mcp` (Claude/Codex), MCP SSE `:8201/sse` (Gemini, but HTTP/8200 preferred — SSE has blocking issues).

**Run:** `D:\agentchattr\windows\start.bat` (server only) or `start_claude.bat` / `start_codex.bat` / `start_gemini.bat` (server + wrapped agent with `@mention` auto-injection). Launchers reuse the 3.11 `.venv`.

**DO NOT register agentchattr globally in Claude/Codex/Gemini configs.** Tried 2026-05-24, then REMOVED — it conflicts with the launchers. README is explicit: "start scripts auto-configure MCP on launch; manual registration is an *alternative*." Doing both gives each agent a **duplicate `agentchattr` server** (global no-token + wrapper's per-instance proxy/token), which broke things: Claude hit a 406→"marked unhealthy" health-gate cooldown, Gemini stopped responding (two url-key shapes: `url` vs `httpUrl`). Codex was unaffected (its wrapper `-c mcp_servers.agentchattr.url=<proxy>` flag overrides the global entry).

**Correct setup = launchers only.** The launchers inject the MCP server ephemerally per-launch with proper identity: Claude `--mcp-config <tempfile>` (bearer token), Codex `-c mcp_servers...` (local proxy on auto port that injects sender), Gemini `GEMINI_CLI_SYSTEM_SETTINGS_PATH` temp file. Each instance gets its own identity-injecting proxy.

**Best-model launchers created:** `windows\start_claude_best.bat` (`--model opus --effort max`), `start_codex_best.bat` (`-m gpt-5.5`; xhigh from config), `start_gemini_best.bat` (`-m gemini-3.1-pro-preview`). Originals untouched.

**Gemini → Antigravity CLI (2026-05-24):** Gemini CLI deprecated for this tier on 2026-06-18. Replaced the `gemini` agent in `config.toml` with `antigravity` (command = `C:/Users/Prekzursil/AppData/Local/agy/bin/agy.exe`). Antigravity CLI = `agy` (Go TUI, installed via `irm https://antigravity.google/cli/install.ps1|iex` → `%LOCALAPPDATA%\agy\bin`). NO `--model` flag (model set in-session via `/model`). MCP config is its OWN file `~/.gemini/antigravity-cli/mcp_config.json` using non-standard **`serverUrl`** key (NOT url/httpUrl) — wrote agentchattr there manually; agentchattr's wrapper MCP-injection is NOT used for it. Launcher `start_antigravity_best.bat`. **Blocker:** agy needs one-time interactive Google Sign-In (run `agy` once) before it works. mcp_config.json format is best-guess — verify after first run.

**Windows codex inject fix:** added `enter_backend = "atomic"` mode in `wrapper_windows.py` (writes prompt+Enter as one WriteConsoleInput burst so focus events can't interleave) + `enter_backend="atomic"` on `[agents.codex]`. Pre-inject `FlushConsoleInputBuffer` added too. Backup at `wrapper_windows.py.bak`.

**Instability:** the wrapper processes keep exiting on this Windows box (agents drop offline repeatedly; claude likely the concurrent-instance 401). Root cause not yet pinned.

**Known Windows bug:** Codex injected prompts get `[I[O` focus-event escape-code garbage — wrapper enables `ENABLE_VIRTUAL_TERMINAL_INPUT` on stdin (`wrapper_windows.py:72-74`) → console leaks focus events into input. Upstream bug, not a config fix. Workaround: manually type `mcp read #general` in the agent terminal when mentioned (README tip).

**GOTCHA:** any `mcp list` shows agentchattr "✗ Failed to connect" when the server (`run.py`) is **down** — normal. Pills connect only via the wrapper launchers (register + heartbeat), never via MCP registration alone. Respects [[feedback-mcp-enabled-state]].