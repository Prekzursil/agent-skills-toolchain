---
title: mcp-client-registration
type: note
---

# MCP client registration - browser-attach entries

One entry per browser; register the same server shape in every client. Tokens
come from each browser's Playwright Extension status page and are
per-browser-profile. Replace `<chrome-token>`, `<edge-token>`,
`<comet-token>`, and `<resolved-comet.exe>` before use.

Base server (all clients, all browsers):

```text
command  npx
args     @playwright/mcp@latest --extension
```

## Entry matrix

| Entry | Extra env beyond the token |
|---|---|
| `playwright` | `PLAYWRIGHT_MCP_EXTENSION_TOKEN=<chrome-token>` |
| `playwright-edge` | + `PLAYWRIGHT_MCP_EXECUTABLE_PATH=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` and the Edge token |
| `playwright-comet` | + `PLAYWRIGHT_MCP_EXECUTABLE_PATH=<resolved-comet.exe>` (Start-menu shortcut target) and the Comet token |

## ZCode

File `C:/Users/Prekzursil/.zcode/cli/config.json` under `mcp.servers` (shape
re-verified 2026-10-18; 18 servers today, no playwright entry yet):

```json
"playwright": {
  "command": "npx",
  "args": ["@playwright/mcp@latest", "--extension"],
  "env": { "PLAYWRIGHT_MCP_EXTENSION_TOKEN": "<chrome-token>" }
},
"playwright-edge": {
  "command": "npx",
  "args": ["@playwright/mcp@latest", "--extension"],
  "env": {
    "PLAYWRIGHT_MCP_EXECUTABLE_PATH": "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "PLAYWRIGHT_MCP_EXTENSION_TOKEN": "<edge-token>"
  }
},
"playwright-comet": {
  "command": "npx",
  "args": ["@playwright/mcp@latest", "--extension"],
  "env": {
    "PLAYWRIGHT_MCP_EXECUTABLE_PATH": "<resolved-comet.exe>",
    "PLAYWRIGHT_MCP_EXTENSION_TOKEN": "<comet-token>"
  }
}
```

## Claude Code

`~/.claude.json` currently has NO `playwright` key among its 34 mcpServers
(re-verified 2026-10-18), so this fills a real gap. Do NOT hand-edit that file
live - it is rewritten from memory within ~30s (see browser-rail's
references/playwright-mcp-extension.md). Use the CLI, once per browser:

```text
claude mcp add --scope user playwright --env PLAYWRIGHT_MCP_EXTENSION_TOKEN=<chrome-token> -- npx @playwright/mcp@latest --extension
claude mcp add --scope user playwright-edge --env PLAYWRIGHT_MCP_EXECUTABLE_PATH="C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --env PLAYWRIGHT_MCP_EXTENSION_TOKEN=<edge-token> -- npx @playwright/mcp@latest --extension
claude mcp add --scope user playwright-comet --env PLAYWRIGHT_MCP_EXECUTABLE_PATH=<resolved-comet.exe> --env PLAYWRIGHT_MCP_EXTENSION_TOKEN=<comet-token> -- npx @playwright/mcp@latest --extension
```

## Codex

`~/.codex/config.toml`:

```toml
[mcp_servers.playwright]
command = "npx"
args = ["@playwright/mcp@latest", "--extension"]
env = { PLAYWRIGHT_MCP_EXTENSION_TOKEN = "<chrome-token>" }

[mcp_servers.playwright-edge]
command = "npx"
args = ["@playwright/mcp@latest", "--extension"]
env = { PLAYWRIGHT_MCP_EXECUTABLE_PATH = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", PLAYWRIGHT_MCP_EXTENSION_TOKEN = "<edge-token>" }

[mcp_servers.playwright-comet]
command = "npx"
args = ["@playwright/mcp@latest", "--extension"]
env = { PLAYWRIGHT_MCP_EXECUTABLE_PATH = "<resolved-comet.exe>", PLAYWRIGHT_MCP_EXTENSION_TOKEN = "<comet-token>" }
```

## Gemini / AGY

`~/.gemini/settings.json` under `mcpServers` (same JSON object shape as the
ZCode block above; key names identical).

## OpenCode

`opencode.json` under `mcp`:

```json
"mcp": {
  "playwright": {
    "type": "local",
    "command": ["npx", "@playwright/mcp@latest", "--extension"],
    "environment": { "PLAYWRIGHT_MCP_EXTENSION_TOKEN": "<chrome-token>" }
  },
  "playwright-edge": {
    "type": "local",
    "command": ["npx", "@playwright/mcp@latest", "--extension"],
    "environment": {
      "PLAYWRIGHT_MCP_EXECUTABLE_PATH": "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
      "PLAYWRIGHT_MCP_EXTENSION_TOKEN": "<edge-token>"
    }
  },
  "playwright-comet": {
    "type": "local",
    "command": ["npx", "@playwright/mcp@latest", "--extension"],
    "environment": {
      "PLAYWRIGHT_MCP_EXECUTABLE_PATH": "<resolved-comet.exe>",
      "PLAYWRIGHT_MCP_EXTENSION_TOKEN": "<comet-token>"
    }
  }
}
```

## First-session acceptance checklist (~10 min, in order)

1. Chrome running and logged in on the daily profile: call any playwright
   tool. PASS = connect tab opens in the RUNNING Chrome, no restart, logins
   intact.
2. Repeat via `playwright-edge` in the running Edge.
3. Repeat via `playwright-comet`. If connect.html fails to open in running
   Comet, Comet drops to the cdp-endpoint toggle fallback (SKILL.md).
4. Confirm browser-rail still launches independently on :9222
   (`pwsh -File scripts/Start-BrowserRail.ps1 -Status` from the browser-rail
   skill).

After step 1 passes, flip browser-rail's
`references/playwright-mcp-extension.md` Option B note (lines 84-88, marked
UNVERIFIED) to VERIFIED with the resolved listing URL
(https://chromewebstore.google.com/detail/playwright-extension/mmlmfjhmonkocbjadbfplnigmagldckm)
and the date.
