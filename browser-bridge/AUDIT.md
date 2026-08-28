# chrome-bridge-mcp audit (estate, 2026-08-28)

**Chosen bridge:** `ShalomObongo/chrome-bridge-mcp` (MIT), cloned `--depth 1` to
`~\.agents\browser-bridge\chrome-bridge-mcp` at commit `4a19963d5914c6e144480605d90efe5623e39c43`
(2026-08-02). Not abandoned (new project, 26 days old). 0 stars — treat as **unaudited-by-community**,
so this file is the local audit.

**Verdict: ACCEPT for dedicated agent profiles only.** Do **not** run upstream `npm run setup`
(it writes `~\.cursor\mcp.json`, `~\.claude.json`, `~\.codex\config.toml` directly and bypasses
`agents.json` + `sync_shared_state.ps1`). Do **not** load this extension into the human/1Password
profile except as an explicit `-Profile live` owner action.

## What was read

- `extension/manifest.json` — MV3; permissions `debugger`, `tabs`, `tabGroups`, `storage`, `alarms`, `downloads`; `host_permissions: <all_urls>`. Expected for this architecture; `debugger` is the whole point.
- `extension/background.js` — connects only to `ws://127.0.0.1:${port}/extension`; command switch is a closed allowlist (`status`, `busy`, `navState`, `focusTab`, `listTabs`, `attach`, `detach`, `newTab`, `closeTab`, `cdp`, `handleDialog`, `consoleLogs`); `focusTab` uses `chrome.tabs.update({active:true})` (activates tab in its window, does **not** call `chrome.windows.update({focused:true})`); refuses `chrome:`, `edge:`, `about:`, `devtools:`, `chrome-extension:`, `view-source:`; does **not** enable the Network domain (no cookie/traffic stream through the extension).
- `extension/popup.js` — local port/token only; no remote URLs.
- `src/hub.ts` — `HOST = "127.0.0.1"`; `verifyClient` origin policy: `/extension` requires `chrome-extension://` Origin; `/client` **rejects** any Origin (so a visited web page cannot drive the browser); optional token; protocol version handshake.
- `src/index.ts` — stdio MCP + `--hub-only`; token/extension-id flags.
- `src/tools.ts` — page control via CDP `Input.*` (trusted events, not OS keystrokes); ref shape-check before interpolation.
- `test/security.mjs` — origin-policy + ref-injection regression tests.
- `src/setup.ts` — **do not run**; writes third-party MCP configs.

## Residual risks (accepted)

- `debugger` + `<all_urls>` is full CDP on whatever profile the extension sits in. Mitigated by dedicated agent profiles (G-90) and the live-profile opt-in contract.
- Token is optional. Origin + loopback is the primary control. Estate pin does not require a token for the agent profile (local processes could still open `/client` with no Origin — same class of risk as any local MCP).
- Upstream default port 8787 is **occupied** on this box by `D:\tools\cc-529-gateway\gateway.mjs` (pid observed). Estate copy `extension-agent` defaults to **8770**.
- Single-author, young repo. Pin the clone; do not `npm run setup`; do not auto-update without re-audit.

## Fallback not used

`TNJ2026/browser-agent-bridge` and `Alij93695/BrowserAgentBridge` were not installed. chrome-bridge-mcp source was available, MIT, and the security model matches the research receipt.
