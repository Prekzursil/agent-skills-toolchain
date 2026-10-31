---
title: playwright-mcp-extension
type: note
permalink: dqverify-repo-20261013/skills/browser-rail/references/playwright-mcp-extension
---

# Playwright MCP: `--extension` bridge and `--cdp-endpoint` attach

Config text for the **claude-closed lane** to apply. Nothing here is applied by the
browser-rail skill, and nothing here should be edited while Claude is running.

> **Do not hand-edit `~/.claude.json` live.** It is rewritten from memory within
> ~30s and your edit is silently lost. Ship changes as an apply-when-closed script
> with `--dry-run` / `--apply` / `--revert` and a timestamped backup, run with
> Claude closed.
>
> **Never rewrite `disabledMcpServers` or the per-project blocks.** That curation is
> load-bearing. Change only the one `mcpServers.playwright` entry.

## Measured current state (2026-07-24)

`@playwright/mcp` version **0.0.78**. Registration in `~/.claude.json` → `mcpServers`:

```json
"playwright": {
  "command": "npx",
  "args": ["-y", "@playwright/mcp"]
}
```

Root `disabledMcpServers` contains `plugin:playwright:playwright` (the plugin copy)
but **not** the bare `playwright` key — so the entry above is the live one.

Relevant flags, quoted from `npx @playwright/mcp@latest --help`:

```
--extension               Connect to a running browser instance
                          (Edge/Chrome only). Requires the
                          "Playwright Extension" to be installed.
--cdp-endpoint <endpoint> CDP endpoint to connect to.
--cdp-timeout <timeout>   timeout in milliseconds for connecting to CDP
                          endpoint, defaults to 30000ms
--user-data-dir <path>    path to the user data directory.
--isolated                keep the browser profile in memory
```

## Option A — attach to the dedicated rail profile (`--cdp-endpoint`)

Points the MCP at the same browser `Start-BrowserRail.ps1` manages. **No extension
to install**, and the CDP endpoint is already proven working on this box.

```json
"playwright": {
  "command": "npx",
  "args": [
    "-y",
    "@playwright/mcp",
    "--cdp-endpoint",
    "http://127.0.0.1:9222"
  ]
}
```

- Requires the rail to be running first, otherwise the MCP fails to start.
- Sessions are whatever the owner signed into **on the rail profile**.
- Loopback only. Do not bind the debug port to a non-loopback address.

## Option B — drive the owner's REAL browser (`--extension`)

Uses the owner's everyday profile, so every site they are already signed into is
available with no second sign-in. The trade is a manual extension install and a
browser-side connection prompt.

```json
"playwright": {
  "command": "npx",
  "args": ["-y", "@playwright/mcp", "--extension"]
}
```

Owner steps, in order:

1. Install the **"Playwright MCP Bridge"** extension in Chrome or Edge.
   *UNVERIFIED — the extension's exact listing name and store URL were not opened
   during this work; only the `--help` text quoting `"Playwright Extension"` was
   read. Settle it by running `npx @playwright/mcp@latest --extension` once and
   following the install link it prints, then record the resolved URL here.*
2. Restart Claude so the new args take effect.
3. Approve the extension's connection prompt on first use.

Caveats:

- Chrome/Edge only (stated by `--help`); no Firefox/WebKit.
- Automation shares the owner's live windows — a stray click lands in their real
  session. Prefer Option A for anything unattended or destructive.
- Extension bridges break on browser or extension updates more often than a plain
  CDP attach does.

## Choosing

| | Option A `--cdp-endpoint` | Option B `--extension` |
|---|---|---|
| Extra install | none | browser extension |
| Whose logins | rail profile (owner signs in once) | owner's real profile, already there |
| Blast radius | isolated window | the owner's live session |
| Proven here | yes, HTTP 200 on `/json/version` | not exercised |
| Best for | unattended, repeated, scripted work | occasional work on the real profile |

Default to **Option A**. It is the configuration this work actually measured, and
it cannot disturb the owner's browsing.

## Rollback

Restore the original three-line entry above. Because the change is confined to
`mcpServers.playwright.args`, reverting is a single-key edit and leaves the rest of
the MCP curation untouched.