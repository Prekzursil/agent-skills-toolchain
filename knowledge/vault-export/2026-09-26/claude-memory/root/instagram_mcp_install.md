---
name: instagram-mcp-install
description: Instagram private-API MCP working via app-version-override; the unsupported_version
  checkpoint fix
metadata:
  node_type: memory
  type: reference
  originSessionId: 0d02c989-c946-4f88-98b0-1c889787bc73
permalink: main/claude-memory/root/instagram-mcp-install
---

insta-mcp (arjun1194/insta-mcp, JS `instagram-private-api`) installed + WORKING at `C:\Users\Prekzursil\source\repos\insta-mcp`, registered Claude Code **user scope** (`claude mcp add insta-mcp -- node ...\dist\index.js`). Covers personal saved/posts/DMs/search (get_saved_posts, get_inbox, get_direct_messages, get_recent_posts, search_instagram, get_liked_posts...). Account @realprekzursil. **Restart Claude Code to load its tools.**

**⭐ THE KEY FIX (non-obvious, reusable for Meta private-API libs):** `instagram-private-api` 1.46.1 (the latest on npm) spoofs ancient `APP_VERSION=222.0.0.13.114` → Instagram returns `checkpoint_required` with `checkpoint_url=/web/unsupported_version/` — a web-only checkpoint the private API CANNOT resolve (no email/SMS step; lib crashes on `challenge.api_path` undefined). FIX = impersonate the CURRENT IG app version. Read it off the device: `adb -s 127.0.0.1:5555 shell "dumpsys package com.instagram.android | grep versionName"` → **431.1.0.49.82** (versionCode 383810323). Override the getter: `Object.defineProperty(ig.state,'appVersion',{get:()=>'431.1.0.49.82',configurable:true})` + same for `appVersionCode`. Patched into `src/index.ts` (env-overridable `IG_APP_VERSION`/`IG_APP_VERSION_CODE`). Verified end-to-end: login + currentUser + getSavedPosts + getInbox all succeed, no checkpoint.

**Auth model (2FA stays ON):** session-based. `login.mjs` (2FA-aware, has the version override) does a one-time login → `data/session.json`; the MCP rides the session and never calls password-login (so 2FA never triggers). Real password is NEVER stored — `data/credentials.json` holds username + a placeholder pw. Re-auth when the session expires: `node login.mjs`. Gotchas: `IgCheckpointError extends IgResponseError` (currentUser checkpoints arrive as the generic parent), and `ig.state.checkpoint`/`challenge` are `Enumerable(false)` (won't survive serialize → can't split challenge flows across processes).

**Caveats:** private API = IG ToS/ban risk; the account got **flagged** during the unsupported_version attempts (recommend rotating the password — it was also pasted into a CC transcript). 2 critical npm vulns in deps (project's own code scanned clean). Full runbook: `source/repos/insta-mcp/SETUP-2FA.md`. Related: [[claude-swap-install]]. FB/Messenger equivalent attempt pending (fbchat dead; fbchat-muqit is the modern fork).