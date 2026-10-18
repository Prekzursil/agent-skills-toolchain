---
name: browser-attach
description: Seamless REAL-browser lane - drive the owner's ALREADY-RUNNING daily-profile Chrome/Edge/Comet from any MCP client with no restart, no automation profile, via Playwright MCP --extension plus the official Playwright Extension. Covers per-browser tokens, the tab-group connect flow, cdp-endpoint fallback, the deferred Firefox lane, and when to use browser-rail instead. Triggers - attach to my running browser, use my real Chrome, drive my logged-in daily profile, extension mode, keep my sessions.
---

# Browser Attach

The seamless REAL-browser lane: drive the owner's **real, already-running,
daily-profile** Chrome, Edge, or Comet from an MCP client - no browser restart,
no dedicated automation profile, logins and cookies intact. A small extension
inside the browser does the bridging; the server never owns, launches, or
closes the owner's browser. This is the estate's counterpart of the
"Claude for Chrome" extension model, and the tier-1 lane for any work that
needs the owner's own sessions.

Sibling skill: **browser-rail** is the tier-2 AUTOMATION-PROFILE lane
(dedicated CDP profile on :9222). The two never touch each other - see
[Two lanes](#two-lanes-browser-attach-vs-browser-rail).

## How attach works

Verified against the Playwright extension package docs
(https://github.com/microsoft/playwright/tree/main/packages/extension) and the
`@playwright/mcp` README (https://github.com/microsoft/playwright-mcp), plus
source reads of `cdpRelay.ts` / `relayConnection.ts` / `connect.tsx` in the
2026-10-18 research lane:

1. The MCP server runs `npx @playwright/mcp@latest --extension` (stdio). On the
   first tool call it hosts a **loopback-only WebSocket relay** on a random
   port and spawns the browser executable with a
   `chrome-extension://.../connect.html` URL.
2. Because the exe is already running, that URL just **opens a tab in the
   ALREADY-RUNNING browser on the DEFAULT daily profile** - no second instance,
   no restart. ("The default profile dir is not passed explicitly, the browser
   resolves it on its own.")
3. The owner drags the tab(s) the agent may drive into the client's **named,
   colored tab group**. Several clients can connect at once, each with its own
   group; a tab belongs to a single client at a time. The extension's status
   page lists every connection and disconnects them individually.
4. Without a token you approve each connection by hand. Copy the
   per-browser-profile token from the extension status page into
   `PLAYWRIGHT_MCP_EXTENSION_TOKEN` for **silent reconnect**. The token is
   unique to the browser profile and is the only auth gate.

## One-time setup per browser

Install the **"Playwright Extension"** (Microsoft, MV3; permissions
`debugger`, `activeTab`, `tabs`, `tabGroups`) from the Chrome Web
Store: https://chromewebstore.google.com/detail/playwright-extension/mmlmfjhmonkocbjadbfplnigmagldckm
(id `mmlmfjhmonkocbjadbfplnigmagldckm`). Then click its icon once and copy the
token shown on the status page.

- **Chrome (daily profile)** - install straight from the listing above.
- **Edge (daily profile)** - install the SAME listing via Edge's other-stores
  compatibility; the Playwright docs say "Chrome or Edge" and no separate Edge
  Add-ons listing exists. Exe (verified on this box):
  `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`.
- **Comet (Perplexity's Chromium browser)** - install the same listing via
  Comet's Chrome Web Store support
  (https://www.perplexity.ai/help-center/comet/en/articles/11734716-extensions;
  "Open the Chrome Web Store in your Comet Browser"). `chrome.debugger` is
  proven to work inside Comet (Perplexity's own bundled agent extensions drive
  pages through it, per Zenity's reverse-engineering, 2026-10-18 research
  lane), but the end-to-end connect flow is UNVERIFIED - the first connect
  session IS the acceptance test. `comet.exe` was NOT found in
  `%LOCALAPPDATA%` (root + Programs, depth 3), Program Files, or Program Files
  (x86) during that lane: resolve the exe path from the Start-menu shortcut
  target at wiring time. Do not guess it.

Prereq: Node >= 20 (this box runs v24.16.0; `npx` at
`C:\Program Files\nodejs\npx.cmd` - re-verified 2026-10-18).

## Server command and per-browser entries

One stdio server per browser, distinguished by env:

- `playwright` (Chrome default): `npx @playwright/mcp@latest --extension` +
  `PLAYWRIGHT_MCP_EXTENSION_TOKEN=<Chrome token>`
- `playwright-edge`: same + `PLAYWRIGHT_MCP_EXECUTABLE_PATH` set to the Edge
  exe above + `<Edge token>` (tokens are per-browser-profile)
- `playwright-comet`: same + `PLAYWRIGHT_MCP_EXECUTABLE_PATH=<resolved
  comet.exe>` + `<Comet token>`

Multiple Chrome profiles: the relay connects to the profile used last; pin one
with `--profile-dir-name "Profile 2"` (last part of "Profile Path" at
chrome://version) or env `PLAYWRIGHT_MCP_PROFILE_DIR_NAME`. The token is
profile-specific, so a pinned profile needs its own token.

Exact registration JSON/TOML for all five clients (ZCode, Claude Code, Codex,
Gemini/AGY, OpenCode) is in
[references/mcp-client-registration.md](references/mcp-client-registration.md),
along with the first-session acceptance checklist.

## Wired on this estate (2026-10-19)

Live in three TUI configs - ZCode `~/.zcode/cli/config.json` (`mcp.servers`),
Claude Code `~/.claude.json` (`mcpServers`), Codex `~/.codex/config.toml`
(`[mcp_servers."..."]`) - as TWO entries each:

- `browser-attach-chrome` - `npx -y @playwright/mcp@latest --extension` with
  env `PLAYWRIGHT_MCP_EXTENSION_TOKEN=<Chrome token>`. Chrome is the default
  exe; no executable-path override needed.
- `browser-attach-edge` - same command with env
  `PLAYWRIGHT_MCP_EXECUTABLE_PATH=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
  plus `PLAYWRIGHT_MCP_EXTENSION_TOKEN=<Edge token>` (tokens are
  per-browser-profile; they differ between Chrome and Edge).

Persistent beyond the configs: `PLAYWRIGHT_MCP_EXTENSION_TOKEN` (the Chrome
default) is set via `setx` at BOTH user and machine scope, so ad-hoc
`npx @playwright/mcp --extension` runs from any shell reconnect silently.
TUIs need one restart to boot the new entries - ZCode connects MCP servers
at startup only. Codex TOML gotcha learned here: Windows paths inside TOML
basic strings must be double-backslash escaped, and a bash-heredoc python
layer can silently halve them - validate with `tomllib` after every edit.

SECURITY RULE: token VALUES never enter this repo, docs, or transcripts.
The literals live only in the local TUI configs and the Windows env; this
module and the registration reference document the env-var NAMES only. If a
token leaks anywhere, reset it from the extension status page - the leaked
one dies with the reset.

## Known limits (teach these verbatim)

- **Downloads throw** "Download is starting" - but the file still lands in
  Downloads natively. Upstream closed as out-of-scope
  (https://github.com/microsoft/playwright-mcp/issues/1396). Route
  download-dependent flows to browser-rail.
- `chrome://`, `edge://`, and `devtools:` tabs are excluded from attach.
- Built-in PDF viewer frames cannot be attached.
- A "started debugging this browser" infobar shows while attached - expected,
  not an error.

## Two lanes: browser-attach vs browser-rail

| | browser-attach (this) | browser-rail |
|---|---|---|
| Whose browser | owner's real daily profile, already running | dedicated CDP profile on :9222 |
| Restart needed | none | launches its own profile once, then reused |
| Logins | already there | owner signs in once, by hand |
| Auth gate | per-profile token | loopback port + separate profile |
| Blast radius | the owner's live session | isolated window |
| Downloads | broken (see above) | work |
| Best for | anything needing the owner's sessions/fingerprint | parallel/heavy scraping, download capture, bot isolation |

Doctrine: REAL-BROWSER lane (this skill) is tier 1 for anything needing the
owner's logins, cookies, or fingerprint; AUTOMATION-PROFILE lane (browser-rail)
stays installed as the tier-2 fallback. The extension entries never touch the
rail, and the rail never touches them - the relay's WebSocket is on a random
loopback port, so there is no conflict with the rail's fixed :9222.

## Fallback: the cdp-endpoint toggle (no extension)

If the extension cannot be installed in a browser, the same server binary
attaches via the one-time `chrome://inspect/#remote-debugging` toggle
("Allow remote debugging for this browser instance"; Chrome/Edge 144+; Comet
inherits it as Chromium 155 - Omaha-verified 2026-10-18 research lane). Change
the entry's flag to `--cdp-endpoint=chrome` (or `msedge`).

Trade-off, taught verbatim: **no token gate** - while the toggle is on, ANY
local process that reaches the debug port can drive the profile. Default the
toggle OFF and enable it per-session only. Comet-via-toggle requires connecting
direct to `ws://127.0.0.1:9222/devtools/browser` (approval mode 404s `/json`
discovery; targets need `Runtime.runIfWaitingForDebugger` - agent-browser
issues #1130/#1133), and Playwright's handling of that quirk over raw `ws://`
is UNVERIFIED. Fallback only.

## Firefox lane (explicitly deferred)

Attaching to an arbitrarily-started Firefox is architecturally impossible
today: Mozilla's remote surfaces (WebDriver BiDi via `--remote-debugging-port`,
Marionette) are strictly startup-time (MDN "Create a WebDriver BiDi
connection",
https://developer.mozilla.org/en-US/docs/Web/WebDriver/How_to/Create_BiDi_connection;
Mozilla's whimboo in Selenium#10096 - no attach to a running instance started
without the flag), and CDP is fully removed since Firefox 141
(https://fxdx.dev/cdp-retirement-in-firefox/). The Playwright extension cannot
run there (Chrome MV3/`chrome.debugger` only; Playwright's Firefox is its own
patched build).

If Firefox automation becomes a real need, wire the OFFICIAL best-effort path:
relaunch the REAL profile ONCE with `--marionette --remote-debugging-port`
(session restore preserves tabs/logins; near-seamless - one relaunch, never
seamless), then `npx @mozilla/firefox-devtools-mcp@latest --connect-existing`
(README verified 2026-10-18: both protocols are required, Marionette default
port 2828 via `--marionette-port`). Caveats: Marionette sets
`navigator.webdriver=true` and changes fingerprint signals - bot-detection risk
on Cloudflare/Akamai (Mozilla-flagged); single BiDi session at a time; robot
icon while attached; Mozilla recommends `--tool-preset slim` to drop
`evaluate_script`. The zero-restart community bridges (firefox-bridge,
Firefox-Browser-MCP, agentfox native-messaging) are tracked but deliberately
NOT wired day-one - small user bases fail the low-maintenance bar that
Microsoft/Google/Mozilla first-party options pass.

## Examples

First connect (Chrome already running and logged in):

1. Client calls any playwright tool (e.g. `browser_navigate`).
2. A connect tab opens in the RUNNING Chrome - no restart, logins intact.
3. Owner drags the target tab into the client's colored group (once; token
   makes later connects silent).
4. Tool results return; the infobar "started debugging this browser" appears
   while attached.

Claude Code registration:

```text
claude mcp add --scope user playwright -- npx @playwright/mcp@latest --extension
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| No connect tab opens | Wrong/missing `PLAYWRIGHT_MCP_EXECUTABLE_PATH` (Edge/Comet entries); for Comet resolve the exe from the Start-menu shortcut target |
| Approval prompt on every connect | Token not set in env, or token from a different browser profile - each profile has its own |
| Connects to the wrong Chrome profile | Relay uses last-used profile; pin with `--profile-dir-name` / `PLAYWRIGHT_MCP_PROFILE_DIR_NAME` |
| Download tool errors | Known upstream behavior (#1396); the file still lands in Downloads - verify there, or use browser-rail |
| Comet connect.html fails | Comet drops to the cdp-endpoint toggle path (see fallback) - extension lane is UNVERIFIED there until first connect succeeds |
| "started debugging this browser" infobar | Expected while attached; disappears on disconnect |
| Rail and attach together | Fine - different ports (rail fixed :9222, relay random loopback); never point one lane at the other |

## Verification status

- Verified 2026-10-18 (this lane and the research lane): extension listing
  name/id/token flow/tab groups (Playwright extension package docs),
  `--extension` + `--cdp-endpoint` flags (playwright-mcp README), Edge exe
  path, Node/npx, ZCode config shape, `~/.claude.json` has no `playwright`
  key among its 34 mcpServers, Comet CWS support article URL,
  firefox-devtools-mcp `--connect-existing` contract.
- UNVERIFIED until the first-session acceptance checklist in the references
  file passes: Comet end-to-end connect, and browser-rail's
  `references/playwright-mcp-extension.md` Option B (lines 84-88 there stay
  UNVERIFIED until then - flip them to VERIFIED as part of that session).
