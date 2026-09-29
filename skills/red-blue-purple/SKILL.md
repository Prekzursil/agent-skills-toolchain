---
name: red-blue-purple
description: Parent descriptor for the estate's tiered offensive/defensive/combined operations tree. Defines the FEW→MEDIUM→HEAVY→FULL→MAX→SOTA tier taxonomy, the enable/disable doctrine, and the domain-wiring matrix (cyberstrike, claude, codex, cursor, grok). Load the child skill for the side you are running.
---

# red-blue-purple — operations tier tree

Three children, each a complete tiered package with enable AND disable commands:
- **`red`** — offensive arsenal wiring per tier (recon→exploitation→C2→agent-integrity)
- **`blue`** — defensive/detection wiring per tier (endpoint→detection-eng→guardrails→measurement)
- **`purple`** — both simultaneously + the scoring system (ISR/GHR/CR/ME, canary battery)

## Tier taxonomy (shared)

| Tier | Meaning | Cost profile |
|---|---|---|
| FEW | bolt-lab natives + local CLI, zero enablement | RAM-free, instant |
| MEDIUM | + Core gateway fronts / basic detection CLIs | ~1 GB, 2 min wire |
| HEAVY | + Full C2/analytics fronts / guardrail watchers | ~2.3 GB, 5 min wire |
| FULL | HEAVY + purple-tools venvs + mitmproxy/frida / audits | ~3 GB, 15 min |
| MAX | FULL + platforms (Mythic/Havoc/Burp/RE suite) / dual-LLM gates | on-demand RAM, 30 min |
| SOTA | MAX + agent-integrity arsenal + multi-agent fan-out + measured ops | full estate, deliberate |

Doctrine: tiers are cumulative; every enable command has a tested disable command; heavy
platforms start on-demand and stop after use (estate RAM discipline); receipts land on disk.

## Domain wiring matrix

| Domain | How tiers wire in | Entry points |
|---|---|---|
| **cyberstrike** (start here) | MCP fronts via `D:\opt\cyberstrike-mcp\start-cyberstrike-mcp-http.ps1 -Profile {Core|Heavy}`; per-server `enabled` flips in `~/.config/cyberstrike/cyberstrike.json`; skills autoload from `.agents\skills` | `cyberstrike mcp list`, status script |
| **claude** | registry `~/.agents/agents.json` → sync → `.mcp.json`; load_tools for on-demand | `sync_shared_state.ps1`, `claude mcp list` |
| **codex** | registry entries with `targets:["codex"]` → config.toml merge (only 4 servers target codex today) | `agents mcp test --runtime codex` |
| **cursor** | registry `targets:["claude"]` auto-mirrors to `.cursor\mcp.json` (safe-default set is owner-gated); CLI bridge `D:\opt\cursor-bridge\cursorctl.cmd` | `cursorctl status/sessions/dispatch` |
| **grok** | read-only supervisor: writes only to SHARED_TASK_NOTES + its own log; reads INBOX.md / runs\ / gh state | monitor prompts in lane dirs |
| **tui (= cyberstrike)** | same as cyberstrike row — the TUI is the primary surface | `/permissions`, `/skills` |

## Where the receipts live
- Gateway ops: `D:\opt\cyberstrike-mcp\receipt-*.md` + `status-cyberstrike-mcp-http.ps1`
- Purple kit: `D:\opt\purple-tools\` (+ its compose files)
- Integrity lane: `D:\bolt\enum\pulls\cs-agent-integrity\` (threat matrix, measurement protocol)
- Bridge: `D:\opt\cursor-bridge\README.md`

Load `red`, `blue`, or `purple` for tier tables and exact commands.
