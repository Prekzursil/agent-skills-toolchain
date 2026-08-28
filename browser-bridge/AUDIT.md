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
- `src/hub.ts` — `HOST = "127.0.0.1"`; `verifyClient` origin policy: `/extension` requires `chrome-extension://` Origin; `/client` **rejects** any Origin (so a visited web page cannot drive the browser); **token is mandatory**; `--extension-id` pin; protocol version handshake; CDP allowlist on `type: "cdp"` before the command is sent to the extension.
- `src/index.ts` — stdio MCP + `--hub-only`; refuses to start without `CHROME_BRIDGE_TOKEN`; `--hub-only` also requires `--extension-id`.
- `src/tools.ts` — page control via CDP `Input.*` (trusted events, not OS keystrokes); ref shape-check before interpolation; `browser_cdp` wrapped in the allowlist; `browser_evaluate` refuses cookie/storage expressions.
- `test/security.mjs` — origin-policy + ref-injection regression tests.
- `src/setup.ts` — **do not run**; writes third-party MCP configs.

## Residual risks (accepted)

- `debugger` + `<all_urls>` is full CDP on whatever profile the extension sits in. Mitigated by dedicated agent profiles (G-90), a **mandatory hub token**, **pinned extension id**, **LIVE on 8790 with a separate extension**, and a **CDP allowlist** that denies cookie APIs.
- `Runtime.evaluate` remains required for snapshots. Static filters block `document.cookie` / `localStorage` / `sessionStorage` / `indexedDB` / `cookieStore`. Obfuscated JS can still read cookies in page context — residual, documented in the 2026-08-27 hardening receipt.
- Token lives in `~\.agents\local.json` (gitignored). Same-user local processes that can read that file can still authenticate. Loopback + token is defence against *other* local processes that cannot read the file.
- Upstream default port 8787 is **occupied** on this box by `D:\tools\cc-529-gateway\gateway.mjs`. Estate `extension-agent` defaults to **8770**; `extension-live` is **8790** baked in.
- Single-author, young repo. Pin the clone; do not `npm run setup`; do not auto-update without re-audit.

## Fallback not used

`TNJ2026/browser-agent-bridge` and `Alij93695/BrowserAgentBridge` were not installed. chrome-bridge-mcp source was available, MIT, and the security model matches the research receipt.
