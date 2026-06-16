# Claude Code Subagent Monitor

A tiny, **read-only**, dependency-free monitor for the background `Task` subagents
a Claude Code session spawns. Gives you **one terminal per agent** (live, clean
feed) plus a refreshing **overview dashboard** — so you stop fighting the glitchy
inline TUI agent list.

## Why this exists
When a session runs several long subagents, the inline TUI list (e.g.
`● general-purpose  Frida capture live AES key/IV  …`) renders poorly and the
agents' output churns the terminal. This tool reads each agent's own transcript
file instead, so monitoring is fully decoupled and can never disturb the running
instance.

## How it works (data source)
Claude Code persists every subagent as an **append-only JSONL** plus a metadata
sidecar:

```
~/.claude/projects/<project>/<session>/subagents/
    agent-<id>.jsonl        # the subagent's full transcript (grows live)
    agent-<id>.meta.json    # { agentType, description, name, toolUseId }
```

- **"Running"** is inferred from the `.jsonl` **mtime recency** (default: touched
  in the last 150 s). The transcript is flushed as the agent works, so a stale
  file = a finished/idle agent.
- The dashboard reads only each file's **tail (~40 KB)**, so refreshing over
  dozens of agents stays cheap.
- The active session is auto-detected as the `subagents/` dir with the most
  recently modified transcript (override with `--dir` / `--session`).

## Usage

**One-click:** double-click `monitor.cmd` — opens a tail terminal per running
agent and turns that window into the dashboard.

**PowerShell:**
```powershell
.\Monitor-Agents.ps1            # spawn per-agent terminals + dashboard
.\Monitor-Agents.ps1 -All       # include finished agents
.\Monitor-Agents.ps1 -Tabs      # tail as tabs in one Windows-Terminal window
.\Monitor-Agents.ps1 -DashboardOnly
.\Monitor-Agents.ps1 -SpawnOnly
```

**Directly (any shell):**
```bash
python agent_monitor.py                 # print the table once
python agent_monitor.py --watch         # live dashboard in this window
python agent_monitor.py --spawn         # one terminal per RUNNING agent
python agent_monitor.py --spawn --all   # ... including finished agents
python agent_tail.py "<...\subagents\agent-<id>.jsonl>"   # tail one agent
```

### agent_monitor.py flags
| Flag | Meaning |
|---|---|
| `--watch` | live-refresh the dashboard (this window) |
| `--spawn` | open one terminal per agent, each tailing via `agent_tail.py` |
| `--all` | include finished agents (default: running only) |
| `--tabs` | spawn as tabs in one Windows-Terminal window (vs separate windows) |
| `--no-wt` | force classic PowerShell windows (skip `wt.exe`) |
| `--dir <path>` | point at a specific `subagents/` dir |
| `--session <id>` | match a session-id substring instead of auto-pick |
| `--active-secs N` | recency window that counts as "running" (default 150) |
| `--interval N` | dashboard refresh seconds (default 2) |

### agent_tail.py flags
| Flag | Meaning |
|---|---|
| `--backfill N` | recent events to show on open (default 8) |
| `--poll S` | poll interval seconds (default 0.6) |
| `--idle S` | seconds of silence before an "idle" notice (default 20) |
| `--width W` | wrap width (defaults to terminal width) |

## The live feed
Each terminal prints one colored line per transcript event:

```
02:36:40  🔧 Bash  command=… D:/ReverseTools/Android/BCSFE-Python …
02:36:48  ↳ === libnative === (132 crypto syms) …
02:36:54  📝 Now I have the full picture. libcrypto.so (BoringSSL) …
```

`🔧` tool call · `↳` tool result (`✗` on error) · `📝` assistant text · `💭` thinking.

## Notes
- Windows-only conveniences (`wt.exe`, PowerShell, `monitor.cmd`); the two Python
  scripts are stdlib-only and run anywhere.
- Prefers Windows Terminal (`wt.exe`) for titled windows/tabs; falls back to
  classic PowerShell windows automatically.
- 100% read-only — it never writes to or signals the monitored Claude Code.
