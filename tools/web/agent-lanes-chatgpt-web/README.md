# Agent Lanes ChatGPT Web

`tools/web/agent-lanes-chatgpt-web/` stores the browser-mediated PromptBridge Desktop lane contract plus the local override that stops noisy auto-launch behavior.

## Provenance
- **Curated upstream**: PromptBridge Desktop / talk-lane design and session model
- **Modified local fork**: the copied `local-overrides/mcp-lib.mjs` reflects the current workstation policy

## Local policy override
The workstation now requires explicit desktop readiness for the web lane. The local override disables implicit desktop autostart via:
- `PROMPTBRIDGE_DESKTOP_AUTOSTART=false`
- `AGENTIFY_DESKTOP_AUTOSTART=false`

This prevents constant browser / Electron launch noise from repeated MCP status calls while keeping the lane available when the desktop session is started intentionally.

## Included local overrides
- `local-overrides/mcp-lib.mjs`: current Windows workstation snapshot with `desktop_autostart_disabled` gating in `ensureDesktopRunning(...)`

## Operational note
When the desktop sidecar is not already running and authenticated, the expected result is a clean Lane A fallback rather than repeated browser churn.
