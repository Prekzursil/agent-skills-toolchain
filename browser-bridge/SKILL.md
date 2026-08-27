---
name: browser-automation
description: "Use as the DEFAULT before any browser-automation run on this box. Mandatory three-way profile choice (live / agent-persistent / agent-ephemeral), dedicated persistent agent profiles, chrome-bridge extension (chrome.debugger CDP) for Chrome/Edge, Playwright BiDi for Firefox, on-demand Tor. No OS keystroke injection, no window-focus requirement, never kill the owner's browsers."
---

# Browser automation (estate)

Read `~\.agents\browser-bridge\PROFILE-CHOICE.md` before driving any browser.

## Mandatory profile choice (every run)

Ask the owner which profile to use. Do not assume silently.

- **(a) `live`** — owner's real Chrome/Edge. Explicit **G-90 override for this run only**. Do not relaunch or kill their windows. Requires the audited extension already loaded in that profile (popup port **8790**). Chrome 136+ ignores `--remote-debugging-port` on the default user-data-dir, so LIVE is extension-only.
- **(b) `agent-persistent`** — **default**. `~\.agents\browser-profiles\{chrome,edge,firefox}-agent`. Logins persist. **Never wipe.**
- **(c) `agent-ephemeral`** — throwaway under `browser-profiles\ephemeral\`; wipe after the run.

Non-interactive: pass `-Profile`. Missing it is a fail.

## How to run (agent-persistent)

```powershell
pwsh -File ~\.agents\browser-bridge\Start-Hub.ps1 -Mode agent
pwsh -File ~\.agents\browser-bridge\Start-AgentBrowser.ps1 -Browser chrome -Profile agent-persistent
pwsh -File ~\.agents\browser-bridge\Start-AgentBrowser.ps1 -Browser edge -Profile agent-persistent
pwsh -File ~\.agents\browser-bridge\Start-FirefoxAgent.ps1 -Profile agent-persistent
```

Hub: `ws://127.0.0.1:8770` (not 8787 — occupied). LIVE hub: `127.0.0.1:8790`.

Drive Chrome/Edge through chrome-bridge MCP / hub (`chrome.debugger` → CDP `Input.*`). Drive Firefox with Playwright `launch_persistent_context` on the firefox-agent dir. Tor is on-demand only (`Start-TorLane.ps1`, no second `tor.exe`).

## Hard rules

- Dedicated profiles only unless the owner picked `live` this run.
- No OS keystroke injection. No focusing the owner's windows to type.
- Do not restart/kill existing owner Chrome/Edge (grok.com logins).
- Bind 127.0.0.1 only. Do not use ports 8765, 8812, 8317, 24680, 8787.
- Agent profiles do **not** inherit grok.com / site logins. The owner signs into the **agent** profile once for login-bound work.
