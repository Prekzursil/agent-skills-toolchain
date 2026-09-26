---
title: browser-automation-council-review 2026-08-27
type: report
permalink: main/agents/browser-automation-council-review-2026-08-27
tags:
- browser-automation
- council
- security
- harness
---

# browser-automation-council-review 2026-08-27

Council review of native browser-bridge stand-up (read-only). Full receipt: `C:\\Users\\Prekzursil\\Cowork\\output\\browser-automation-council-review_2026-08-27.md`.

## Grade
**B-** — Chromium agent-persistent + focus-independent CDP click is real. Not trusted yet: unauthenticated loopback hub, raw `browser_cdp` can dump cookies, G-90/LIVE contract is launcher-only.

## Top 3 must-fix (security first)
1. Mandatory hub token + `--extension-id` pin; fork `extension-live` with port 8790 baked in (default 8770 on LIVE steals the agent hub).
2. CDP allowlist on the wire; remove/wrap MCP `browser_cdp` (`Network.getAllCookies` is in the tool description).
3. Do not load debugger into the human/1Password profile; do not register `agents.json` / Cursor G-6 until 1–2 land.

## Top 3 improvements
1. Owner-attended login-bind wizard into `browser-profiles/*-agent` (never agent-typed passwords).
2. Warm one headed Chrome + on-demand hub; never Chrome+Edge+Firefox in parallel on this RAM box.
3. Estate skill under `.agents/skills/browser-automation`; do not sync upstream "drive the user's real Chrome" skill.

## Harness fold-in
Belongs in `agent-skills-toolchain` as **runtime + skill**, not always-on Cursor MCP. Commit launchers, estate extensions, pinned `chrome-bridge-mcp` @ `4a19963`, PROFILE-CHOICE, AUDIT. **Never commit** `browser-profiles/` (cookies). Token in `local.json`. Register Claude-only later; do not add to `CURSOR_ENABLED_SERVERS` until owner expands G-6.

## Do not
- Run upstream `npm run setup` (bypasses agents.json).
- Open HTTP `--remote-debugging-port` while `--enable-unsafe-extension-debugging` is on.
- Treat Firefox click or Tor -Launch as proven (click skipped; Tor dry-run/stub).
