---
title: PROFILE-CHOICE
type: note
permalink: dqverify-repo-20261013/browser-bridge/profile-choice
---

# Browser-automation profile-choice contract

**Status:** mandatory invocation contract for every browser-automation run on this box.
**Default when the owner is prompted and presses Enter:** `(b) agent-persistent`.
**Non-interactive runs:** `-Profile` is required. Missing it is a hard fail — never silently pick LIVE, never silently pick ephemeral.

House rule G-90 still stands as the *default*: agents do not attach to or drive the human 1Password/default browser profile. The owner may **override G-90 for a single run** by explicitly choosing `(a) live`. That override does not persist to the next run.

## The three choices

| Id | `-Profile` value | What it is | Logins | Wipe | G-90 |
|---|---|---|---|---|---|
| **(a)** | `live` | Owner's real Chrome / Edge (already running). Do **not** relaunch, do **not** kill, do **not** pass `--user-data-dir` at the default User Data path. Drive only via the audited extension already loaded in that profile (or fail with install-once instructions). | Owner's real sessions (grok.com, etc.) | Never | **Explicit per-run override** |
| **(b)** | `agent-persistent` | Dedicated agent profile under `~\.agents\browser-profiles\`. Stable `--user-data-dir`. **Default.** | Whatever the owner signed into *this* profile; survives restarts | **Never wipe** | Honored |
| **(c)** | `agent-ephemeral` | Throwaway `--user-data-dir` under `~\.agents\browser-profiles\ephemeral\`. | None (fresh) | Wipe after the run | Honored |

## Persistent profile paths (stable, never wiped)

- Chrome: `C:\Users\Prekzursil\.agents\browser-profiles\chrome-agent`
- Edge: `C:\Users\Prekzursil\.agents\browser-profiles\edge-agent`
- Firefox: `C:\Users\Prekzursil\.agents\browser-profiles\firefox-agent`
- Tor (on-demand, dedicated): `C:\Users\Prekzursil\.agents\browser-profiles\tor-agent`

These directories are created if missing and are **never** deleted by automation. Signing an account into an agent profile once is how login-bound tasks (grok.com, etc.) work on the agent lane.

## How to surface the choice

Every launcher (`Start-AgentBrowser.ps1`, `Start-FirefoxAgent.ps1`, proof scripts) must:

1. Print the three options (a/b/c) on stderr/stdout before acting.
2. Accept `-Profile live|agent-persistent|agent-ephemeral`.
3. If `-Profile` is omitted and stdin is an interactive console: prompt; empty answer = `agent-persistent`.
4. If `-Profile` is omitted and stdin is not a TTY: exit `2` with the three options listed. Do not proceed.
5. Refuse `live` if it would require restarting or killing the owner's existing browser windows.

## Chrome 152 extension load (branded builds)

`--load-extension` is ignored on branded Chrome/Edge 137+. The HTTP `--remote-debugging-port` `Extensions` domain returns an id but `getExtensions` stays empty. Estate launch uses Playwright's **pipe** CDP session (`lib/launch-agent.py`) plus `--enable-unsafe-extension-debugging` and `Extensions.loadUnpacked`. Anti-throttle flags still apply. No HTTP debug port is opened on the agent profile for the GOAT path.

## LIVE caveats (Chrome 136+ / G-90)

- Chrome 136+ **silently ignores** `--remote-debugging-port` on the default user-data-dir. LIVE cannot be "just attach CDP to the window that's already open" via that flag.
- LIVE is therefore extension-bridge only: the owner loads **`extension-live`** (port **8790 baked in**, no popup footgun) into the real profile. Automation must **not** auto-install it and must **not** load `extension-agent` (port 8770) into the human profile.
- First-time LIVE setup is an **owner action**: Load unpacked `~\.agents\browser-bridge\extension-live` once (token from `~\.agents\local.json` `chromeBridge.liveToken`, pasted in the popup — agents never print it). Then rerun with `-Profile live`.
- LIVE hub binds `127.0.0.1:8790` with a **distinct token** and **pinned extension id**. Agent hub is `127.0.0.1:8770` + `extension-agent` id `bdccimcedobipcmhcikcnakjdemiechj`.

## Ports (loopback only; do not collide with 8765 / 8812 / 8317 / 24680 / 8787)

| Role | Bind |
|---|---|
| Agent hub (persistent + ephemeral, sequential) | `127.0.0.1:8770` |
| LIVE hub | `127.0.0.1:8790` |
| Chrome agent companion CDP (extension-load fallback only) | `127.0.0.1:9224` |
| Edge agent companion CDP (extension-load fallback only) | `127.0.0.1:9334` |
| Occupied elsewhere on this box — do not use | `8787` (cc-529-gateway), `8765` basic-memory, `8812` agent-mail, `8317` auth2api, `24680` |

Companion CDP ports exist only on **dedicated** agent profiles (Chrome 136+ allows `--remote-debugging-port` there). They are never pointed at the default/live User Data directory.

## Input rules

- No OS keystroke injection (`SendKeys`, `keybd_event`, UI Automation typing into the focused window).
- Chrome/Edge: CDP `Input.dispatchMouseEvent` / `Input.dispatchKeyEvent` via `chrome.debugger` (trusted in-page events). Window OS-focus is not required; anti-throttle flags keep occluded windows alive.
- Firefox: Playwright WebDriver BiDi against the dedicated profile. Same no-keystroke rule.
- Tor: on-demand Marionette/tbselenium; never a second `tor.exe`; never the human's TB UI session.