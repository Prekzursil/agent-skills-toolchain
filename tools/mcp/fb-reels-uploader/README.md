---
title: README
type: note
permalink: dqverify-repo-20261013/tools/mcp/fb-reels-uploader/readme
---

# fb-reels-uploader

> **Status: standalone Playwright script — NOT (yet) an MCP.**
> It lives here under `tools/mcp/` because it belongs to the **social-media family**
> (Instagram / TikTok / Facebook-Messenger / WhatsApp) and serves part of the same goal —
> publishing media to a social platform. It is intentionally a plain CLI today; the
> [roadmap below](#roadmap--promote-to-a-full-mcp) describes promoting it to a real MCP that
> mirrors `insta-mcp`'s connector / worker / oracle layering.

Upload local vertical videos to **Facebook as Reels**, strictly in order, **one Reel per post**.
Companion to the Opus clip downloader (download a project's shorts, then publish them here).

Sibling: see [`skills/social-media-toolchain`](../../../skills/social-media-toolchain/SKILL.md).

## Why not the Facebook Graph API?
Facebook's **official Graph API cannot publish to a personal profile** — only Pages and
Instagram-Business accounts. So personal-profile Reel posting must drive a real browser
(Playwright), the same way `tiktok-mcp` uses Playwright for its work. That browser-automation
core is exactly what this script is — and what a future MCP would wrap.

## Use it now (as a script)
```bash
cd tools/mcp/fb-reels-uploader
npm install                                              # Playwright (+ one-time Chromium)
node fb-reels-upload.mjs "<folder-of-mp4s>"             # all clips, in order
node fb-reels-upload.mjs "<folder>" --start 2 --delay-sec 25
```
First run opens a window — log into Facebook once (session cached in `.profile/`, gitignored).
Then it uploads `*.mp4` sorted numerically (`01_…`, `02_…`) as Reels, Public, no caption,
resuming via a `<folder>/.fb-posted.json` state file and stopping on any failure to keep order.
Options: `--start N`, `--limit M`, `--delay-sec S`, `--audience public|friends|onlyme`,
`--profile DIR`, `--glob EXT`, `--headless`.

⚠️ Bulk automated posting can trip Facebook's spam detection — pace it and watch for security
prompts. Use a throwaway/secondary account for heavy automation.

---

## Roadmap — promote to a full MCP

Mirror `insta-mcp` (`C:\Users\Prekzursil\source\repos\insta-mcp`), which the research mapped to
three roles. The FB equivalent:

| Role | insta-mcp | fb-reels-uploader (MCP form) |
|------|-----------|------------------------------|
| **Connector** | `instagram/{auth,client,session}.ts` — `instagram-private-api` login, device id, `session.json` cache + verify, app-version spoof | A Facebook **session connector**: reuse the `fb-messenger-mcp` cookie pattern (C3C-exported `cookies.json`) *or* a persistent Playwright profile; verify the session (load reels-composer) and refresh on expiry. |
| **Worker** | `instagram/services/` — `MediaService.uploadReel()` → `ig.publish.video()`, gated by `utils/rate-limit.ts` | A **`ReelService.uploadReel(file, opts)`** that performs the `/reels/create/` browser flow (Add Video → Next → Next → audience → Post), behind a rate limiter + the existing `.fb-posted.json` ordering/resume guard. The current `fb-reels-upload.mjs` flow is the seed of this worker. |
| **Oracle** | `server.ts` + `tools/*.ts` — Zod tool schemas (`uploadVideoSchema`, …) that validate input and format MCP responses | An **MCP server** (`@modelcontextprotocol/sdk`, stdio) exposing tools like `fb_upload_reel`, `fb_upload_video`, `fb_list_my_reels`; each validates a file path + audience and returns the posted Reel URL — the "oracle" that confirms success/state back to the agent. |

**Suggested layout when promoting** (kept parallel to insta-mcp):
```
fb-reels-uploader/
  src/
    facebook/{auth,client,session}.ts     # connector
    facebook/services/reel.service.ts      # worker (port fb-reels-upload.mjs flow)
    tools/{upload,index}.ts                # oracle (MCP schemas + handlers)
    server.ts · index.ts                   # MCP entry
    utils/{rate-limit,errors,config}.ts
```
**Registration** (once it's an MCP), matching the family in `.mcp.json`:
```json
"fb-reels": { "type": "stdio", "command": "node",
              "args": ["C:/Users/Prekzursil/source/agent-skills-toolchain/tools/mcp/fb-reels-uploader/dist/index.js"] }
```
Effort estimate (from the feasibility study): ~5–7 weeks to a hardened MCP (session caching +
anti-detection + selector maintenance). Until then, the script here does the job.

A working copy of this script also ships as a **side tool in the opus-bulk-downloader repo**
(`tools/fb-reels-uploader/`).