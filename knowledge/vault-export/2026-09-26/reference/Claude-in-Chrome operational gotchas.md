---
title: Claude-in-Chrome operational gotchas
type: guide
permalink: main/reference/claude-in-chrome-operational-gotchas
tags:
- claude-in-chrome
- browser-automation
- gotcha
- gmail
- harness
---

Operational gotchas hit while driving Gmail/Outlook via the claude-in-chrome MCP. Verified 2026-07-18.

- [gotcha] The `/login` slash command DISCONNECTS the browser remote control ("Remote Control disconnected"). Reconnect with `/chrome`, then re-run `tabs_context_mcp`. #login-disconnect
- [gotcha] Screenshots intermittently time out ("CDP sendCommand Page.captureScreenshot timed out after 30000ms — renderer may be frozen") on heavy pages (Gmail/Outlook), but DOM tools (`read_page` / `find` / `get_page_text` / `form_input`) KEEP WORKING. Fall back to DOM tools to read state and locate elements when screenshots freeze — the page is usually fine, only the screenshot pipeline stalls. #screenshot-freeze
- [gotcha] After clicking Gmail "Send", WAIT for the "Message sent" toast before navigating away — navigating immediately CANCELS the send (an email silently failed to send this way and had to be re-sent). #wait-for-send
- [gotcha] Some Gmail flows use NATIVE browser prompts automation can't drive (filter-flow "New label" prompt, forwarding-confirmation dialog). Use in-page equivalents instead — e.g. the sidebar "Create new label" opens a FILLABLE in-page dialog. #native-vs-inpage
- [pattern] Verify actions via DOM, not optimistic UI banners — Gmail showed a "You are forwarding…" banner even when the save ERRORED ("Invalid forwarding address"). Read server truth after a hard reload. #verify-dom-not-banner

## Relations
- relates_to [[Gmail forwarding to per-source folders — automation playbook + gotchas]]
